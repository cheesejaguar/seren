"""
Seren Planner: CrewAI-powered planner that Plugah can use for OAG creation.

By default we install this planner into `plugah.boardroom.Planner` so that
BoardRoom.plan_organization() uses Seren rather than the stock planner.

Notes:
- In mock/offline mode (PLUGAH_MODE=mock), we generate a deterministic OAG
  via simple heuristics, no network calls.
- If CrewAI is available and the environment is configured, this file can be
  extended to actually orchestrate an agentic planning step. For now, we
  structure the call but fall back to heuristics if anything is unavailable.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

try:
    # CrewAI is available via Plugah dependency, but keep it optional here
    from crewai import Agent, Task, Crew  # type: ignore
except Exception:  # pragma: no cover - optional import path
    Agent = Task = Crew = object  # type: ignore

from plugah.oag_schema import (
    OAG,
    AgentSpec,
    BudgetCaps,
    BudgetModel,
    BudgetPolicy,
    Contract,
    ContractIO,
    CostTrack,
    Edge,
    OrgMeta,
    RoleLevel,
    TaskSpec,
    TaskStatus,
    OKR,
    Objective,
    KeyResult,
    KPI,
)
from plugah.selector import Selector


class SerenPlanner:
    """CrewAI-oriented Planner.

    Uses CrewAI agent(s) to propose an OAG from PRD + budget. Falls back to
    deterministic heuristics under mock or missing provider configuration.
    """

    def __init__(self, selector: Selector | None = None):
        self.selector = selector or Selector()

    def plan(
        self,
        prd: dict[str, Any],
        budget_usd: float,
        context: dict[str, Any] | None = None,
    ) -> OAG:
        context = context or {}
        if os.getenv("PLUGAH_MODE") == "mock":
            return self._heuristic_plan(prd, budget_usd)

        # Try a CrewAI-based flow; if anything fails, fall back to heuristics
        try:
            return self._crewai_plan(prd, budget_usd)
        except Exception:
            return self._heuristic_plan(prd, budget_usd)

    # ----------------------------
    # CrewAI-backed orchestration
    # ----------------------------
    def _crewai_plan(self, prd: dict[str, Any], budget_usd: float) -> OAG:
        """Use a small CrewAI flow to propose an OAG and parse it.

        The agent is instructed to return strict JSON with:
        {
          "agents": [
            {"role": "CEO", "reports_to": null},
            {"role": "VP Engineering", "reports_to": "CEO"},
          ],
          "tasks": [
            {"title": "Design MVP", "description": "...", "assignee": "VP Engineering", "depends_on": [], "dod": "..."}
          ]
        }
        If anything fails or JSON is malformed, we fall back to heuristics.
        """

        # Example (no-op) crew to indicate where agent logic would run.
        if Crew is object:
            # crewai not importable in environment; fall back
            return self._heuristic_plan(prd, budget_usd)

        org_architect = Agent(
            role="Org Architect",
            goal="Design an effective organizational graph for the PRD",
            backstory="Seasoned org designer focusing on lean, budget-sensitive teams.",
            allow_delegation=False,
        )

        design_task = Task(
            description=(
                "You are designing an Organizational Agent Graph (OAG) for the PRD below.\n"
                "Return ONLY JSON (no prose) matching this schema: \n"
                "{\n  \"agents\": [ { \"role\": string, \"reports_to\": string|null } ],\n"
                "  \"tasks\": [ { \"title\": string, \"description\": string, \"assignee\": string, \"depends_on\": string[], \"dod\": string } ]\n}"
                "\nWhere 'assignee' and 'reports_to' refer to agent roles.\n"
                f"PRD: {prd}\nBudget USD: {budget_usd}\n"
            ),
            expected_output=(
                "Strict JSON matching the schema above."
            ),
            agent=org_architect,
        )

        crew = Crew(agents=[org_architect], tasks=[design_task])
        output = None
        try:
            res = crew.kickoff()  # May call providers
            output = str(res)
        except Exception:
            return self._heuristic_plan(prd, budget_usd)

        parsed = self._parse_design_output(output)
        if not parsed:
            return self._heuristic_plan(prd, budget_usd)
        return self._oag_from_design(prd, budget_usd, parsed)

    def _parse_design_output(self, text: str) -> dict[str, Any] | None:
        import json
        import re
        if not text:
            return None
        # Try strict JSON parse first
        try:
            return json.loads(text)
        except Exception:
            pass
        # Extract JSON block heuristically
        m = re.search(r"\{[\s\S]*\}$", text.strip())
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    def _role_to_level(self, role: str) -> RoleLevel:
        r = role.lower()
        if any(k in r for k in ["ceo", "cto", "cfo", "chief"]):
            return RoleLevel.C_SUITE
        if r.startswith("vp"):
            return RoleLevel.VP
        if "director" in r:
            return RoleLevel.DIRECTOR
        if "manager" in r:
            return RoleLevel.MANAGER
        return RoleLevel.IC

    def _oag_from_design(self, prd: dict[str, Any], budget_usd: float, design: dict[str, Any]) -> OAG:
        project_id = str(uuid.uuid4())
        title = prd.get("title", "Project")
        domain = prd.get("domain", "general")
        objectives = prd.get("objectives", [])

        meta = OrgMeta(project_id=project_id, title=title, domain=domain)
        budget = BudgetModel(
            caps=BudgetCaps(soft_cap_usd=budget_usd * 0.8, hard_cap_usd=budget_usd),
            policy=self._determine_budget_policy(budget_usd, len(objectives)),
            forecast_cost_usd=0.0,
        )
        oag = OAG(meta=meta, budget=budget, nodes={}, edges=[])

        # Build agents with ids and record by role
        role_to_id: dict[str, str] = {}
        agents = design.get("agents", []) or []
        for a in agents:
            role = str(a.get("role", "IC")).strip()
            agent = AgentSpec(id=str(uuid.uuid4()), role=role, level=self._role_to_level(role))
            oag.add_node(agent)
            role_to_id[role] = agent.id

        # Wire reporting edges
        for a in agents:
            role = str(a.get("role", "")).strip()
            mgr = a.get("reports_to")
            if mgr and role in role_to_id and mgr in role_to_id:
                oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=role_to_id[mgr], to_id=role_to_id[role]))

        # Build tasks
        tasks = []
        for t in design.get("tasks", []) or []:
            assignee_role = str(t.get("assignee", "")).strip()
            agent_id = role_to_id.get(assignee_role)
            if not agent_id and role_to_id:
                agent_id = next(iter(role_to_id.values()))
            contract = Contract(
                inputs=[ContractIO(name="spec", dtype="text", description=t.get("title", ""))],
                outputs=[ContractIO(name="deliverable", dtype="text", description=t.get("dod", "deliverable"))],
                definition_of_done=t.get("dod", "Meets acceptance criteria"),
            )
            task = TaskSpec(
                id=str(uuid.uuid4()),
                description=t.get("description", t.get("title", "Task")),
                agent_id=agent_id or str(uuid.uuid4()),
                contract=contract,
                expected_output=t.get("dod", "deliverable"),
                status=TaskStatus.PLANNED,
                cost=CostTrack(est_cost_usd=0.0),
            )
            oag.add_node(task)
            tasks.append(task)

        # Task dependencies
        title_to_id = {t.description: t.id for t in tasks}
        for t in design.get("tasks", []) or []:
            depends = t.get("depends_on", []) or []
            to_id = title_to_id.get(t.get("description", t.get("title", "")))
            for d in depends:
                from_id = title_to_id.get(d)
                if from_id and to_id:
                    oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=from_id, to_id=to_id))

        # Compute forecast and attach OKRs/KPIs
        oag.budget.forecast_cost_usd = self._forecast_cost(oag)
        self._attach_okrs_kpis(oag)
        return oag

    def _attach_okrs_kpis(self, oag: OAG) -> None:
        agents = oag.get_agents()
        tasks = oag.get_tasks()
        for agent in agents.values():
            # Simple: one OKR per agent based on assigned tasks
            owned_tasks = [t for t in tasks.values() if t.agent_id == agent.id]
            if not owned_tasks:
                continue
            obj = Objective(
                id=str(uuid.uuid4()),
                title=f"Deliver assigned tasks ({len(owned_tasks)})",
                description="Complete planned work on time and within budget",
                owner_agent_id=agent.id,
            )
            kr = KeyResult(
                id=str(uuid.uuid4()),
                objective_id=obj.id,
                metric="tasks_done",
                target=len(owned_tasks),
                current=0,
            )
            agent.okrs.append(OKR(objective=obj, key_results=[kr]))
            agent.kpis.append(
                KPI(
                    id=str(uuid.uuid4()),
                    metric="throughput",
                    target=len(owned_tasks),
                    current=0,
                    owner_agent_id=agent.id,
                )
            )

    # ----------------------------
    # Deterministic OAG generator
    # ----------------------------
    def _heuristic_plan(self, prd: dict[str, Any], budget_usd: float) -> OAG:
        project_id = str(uuid.uuid4())
        title = prd.get("title", "Project")
        domain = prd.get("domain", "general")
        objectives = prd.get("objectives", [])
        success_criteria = prd.get("success_criteria", [])

        policy = self._determine_budget_policy(budget_usd, len(objectives))

        meta = OrgMeta(project_id=project_id, title=title, domain=domain)
        budget = BudgetModel(
            caps=BudgetCaps(soft_cap_usd=budget_usd * 0.8, hard_cap_usd=budget_usd),
            policy=policy,
            forecast_cost_usd=0.0,
        )
        oag = OAG(meta=meta, budget=budget, nodes={}, edges=[])

        # Use Selector to estimate staffing
        staffing = self.selector.determine_staffing_level(
            scope_size=self._estimate_scope_size(objectives),
            budget=budget_usd,
            domain=domain,
        )

        # Board Room (CEO/CTO/CFO)
        self._create_board_room(oag, title, domain)

        # VP(s), Directors, Managers, ICs
        vps = self._create_vps(oag, title, domain, staffing.get("vps", 1))
        directors = self._create_directors(oag, title, domain, vps, staffing.get("directors", 1))
        managers = self._create_managers(oag, title, domain, directors, staffing.get("managers", 2))
        ics = self._create_ics(oag, title, domain, managers, staffing.get("ics", 3))

        # Tasks from objectives
        tasks = self._create_tasks(oag, objectives, success_criteria, ics)
        self._create_task_dependencies(oag, tasks)

        oag.budget.forecast_cost_usd = self._forecast_cost(oag)
        return oag

    # ---- Heuristic helpers (adapted from stock planner patterns) ----
    def _determine_budget_policy(self, budget: float, num_objectives: int) -> BudgetPolicy:
        if budget < 20 or num_objectives > 5:
            return BudgetPolicy.CONSERVATIVE
        elif budget > 100 and num_objectives <= 3:
            return BudgetPolicy.AGGRESSIVE
        else:
            return BudgetPolicy.BALANCED

    def _estimate_scope_size(self, objectives: list[dict]) -> str:
        n = len(objectives) or 1
        return "small" if n <= 2 else "medium" if n <= 5 else "large"

    def _create_board_room(self, oag: OAG, title: str, domain: str) -> None:
        ceo = AgentSpec(id=str(uuid.uuid4()), role="CEO", level=RoleLevel.C_SUITE)
        cto = AgentSpec(id=str(uuid.uuid4()), role="CTO", level=RoleLevel.C_SUITE, manager_id=ceo.id)
        cfo = AgentSpec(id=str(uuid.uuid4()), role="CFO", level=RoleLevel.C_SUITE, manager_id=ceo.id)
        oag.add_node(ceo)
        oag.add_node(cto)
        oag.add_node(cfo)
        oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=ceo.id, to_id=cto.id))
        oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=ceo.id, to_id=cfo.id))

    def _create_vps(self, oag: OAG, title: str, domain: str, count: int) -> list[AgentSpec]:
        roles = ["VP Engineering", "VP Product", "VP Marketing"]
        vps: list[AgentSpec] = []
        for i in range(min(count, len(roles))):
            spec = AgentSpec(id=str(uuid.uuid4()), role=roles[i], level=RoleLevel.VP)
            oag.add_node(spec)
            vps.append(spec)
        return vps

    def _create_directors(self, oag: OAG, title: str, domain: str, vps: list[AgentSpec], count: int) -> list[AgentSpec]:
        directors: list[AgentSpec] = []
        for i in range(count):
            spec = AgentSpec(id=str(uuid.uuid4()), role=f"Director {i+1}", level=RoleLevel.DIRECTOR, manager_id=(vps[0].id if vps else None))
            oag.add_node(spec)
            if vps:
                oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=vps[i % len(vps)].id, to_id=spec.id))
            directors.append(spec)
        return directors

    def _create_managers(self, oag: OAG, title: str, domain: str, directors: list[AgentSpec], count: int) -> list[AgentSpec]:
        managers: list[AgentSpec] = []
        for i in range(count):
            spec = AgentSpec(id=str(uuid.uuid4()), role=f"Engineering Manager {i+1}", level=RoleLevel.MANAGER, manager_id=(directors[0].id if directors else None))
            oag.add_node(spec)
            if directors:
                oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=directors[i % len(directors)].id, to_id=spec.id))
            managers.append(spec)
        return managers

    def _create_ics(self, oag: OAG, title: str, domain: str, managers: list[AgentSpec], count: int) -> list[AgentSpec]:
        ics: list[AgentSpec] = []
        for i in range(count):
            spec = AgentSpec(id=str(uuid.uuid4()), role=f"IC {i+1}", level=RoleLevel.IC, manager_id=(managers[0].id if managers else None))
            oag.add_node(spec)
            if managers:
                oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=managers[i % len(managers)].id, to_id=spec.id))
            ics.append(spec)
        return ics

    def _create_tasks(
        self,
        oag: OAG,
        objectives: list[dict],
        success: list[str],
        assignees: list[AgentSpec],
    ) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        if not objectives:
            objectives = [{"title": "Deliver MVP", "description": "Ship core features"}]
        for i, obj in enumerate(objectives, start=1):
            agent_id = assignees[i % len(assignees)].id if assignees else (oag.get_agents() or {"ceo": AgentSpec(id="ceo", role="CEO", level=RoleLevel.C_SUITE)}).popitem()[1].id
            contract = Contract(
                inputs=[ContractIO(name="spec", dtype="text", description=obj.get("title", ""))],
                outputs=[ContractIO(name="deliverable", dtype="text", description="Resulting artifact")],
                definition_of_done="Meets acceptance criteria",
            )
            t = TaskSpec(
                id=str(uuid.uuid4()),
                description=obj.get("description", obj.get("title", f"Objective {i}")),
                agent_id=agent_id,
                contract=contract,
                expected_output="deliverable",
                status=TaskStatus.PLANNED,
                cost=CostTrack(est_cost_usd=0.0),
            )
            oag.add_node(t)
            tasks.append(t)
        return tasks

    def _create_task_dependencies(self, oag: OAG, tasks: list[TaskSpec]) -> None:
        for i in range(1, len(tasks)):
            oag.add_edge(Edge(id=str(uuid.uuid4()), from_id=tasks[i-1].id, to_id=tasks[i].id))

    def _forecast_cost(self, oag: OAG) -> float:
        # Simple forecast: number of agents * base rate
        num_agents = len(oag.get_agents())
        return round(num_agents * 10.0, 2)


def install_seren_planner() -> type[SerenPlanner]:
    """Install SerenPlanner into plugah.boardroom so BoardRoom uses it."""
    import os
    if os.getenv("SEREN_PLANNER", "on").lower() in {"0", "false", "off"}:
        return SerenPlanner
    import plugah.boardroom as br
    br.Planner = SerenPlanner  # type: ignore[assignment]
    return SerenPlanner

# Make Seren the default planner on import (can be disabled via SEREN_PLANNER=off)
try:
    install_seren_planner()
except Exception:
    pass
