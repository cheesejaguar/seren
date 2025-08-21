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
        """Sketch out a Crew to propose an OAG. Currently returns a
        heuristic OAG while leaving hooks for real agent calls."""

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
                "Given the PRD and budget, propose agents, tasks, and dependencies."
                " Return a compact summary; Seren will construct the final OAG."
            ),
            expected_output=(
                "A bullet list of roles and tasks with brief rationales."
            ),
            agent=org_architect,
        )

        crew = Crew(agents=[org_architect], tasks=[design_task])
        try:
            _ = crew.kickoff()  # May call providers; let it fail gracefully
        except Exception:
            pass

        # Construct OAG from PRD using heuristic mapping (deterministic)
        return self._heuristic_plan(prd, budget_usd)

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
    import plugah.boardroom as br

    br.Planner = SerenPlanner  # type: ignore[assignment]
    return SerenPlanner
