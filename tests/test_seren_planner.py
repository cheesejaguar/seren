import json
from types import SimpleNamespace

import plugah.boardroom as br
import pytest
from plugah.oag_schema import BudgetPolicy, RoleLevel

import app.seren_planner as sp
from app.seren_planner import SerenPlanner, install_seren_planner

PRD = {
    "title": "Slack Summarizer",
    "domain": "productivity",
    "objectives": [
        {"title": "Ingest", "description": "Ingest Slack messages"},
        {"title": "Summarize", "description": "Summarize threads"},
        {"title": "Deliver", "description": "Post daily digest"},
    ],
    "success_criteria": ["Digest posted daily"],
}


def _roles(oag):
    return sorted(a.role for a in oag.get_agents().values())


# ---------------------------------------------------------------------------
# Deterministic (mock) planner
# ---------------------------------------------------------------------------


def test_mock_mode_plan_is_deterministic_heuristic(monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    oag = SerenPlanner().plan(PRD, 25.0)

    assert oag.meta.title == "Slack Summarizer"
    assert oag.meta.domain == "productivity"
    assert oag.budget.policy == BudgetPolicy.BALANCED
    assert oag.budget.caps.hard_cap_usd == 25.0
    assert oag.budget.caps.soft_cap_usd == 20.0

    # Balanced selector with budget < 50: 1 VP, 2 directors, 2 managers, 4 ICs + board
    roles = _roles(oag)
    assert {"CEO", "CTO", "CFO", "VP Engineering"} <= set(roles)
    assert sum(r.startswith("Director") for r in roles) == 2
    assert sum(r.startswith("Engineering Manager") for r in roles) == 2
    assert sum(r.startswith("IC ") for r in roles) == 4
    assert oag.budget.forecast_cost_usd == len(roles) * 10.0

    # One task per objective, chained in order and assigned to ICs
    tasks = list(oag.get_tasks().values())
    assert [t.description for t in tasks] == [o["description"] for o in PRD["objectives"]]
    agents = oag.get_agents()
    assert all(agents[t.agent_id].level == RoleLevel.IC for t in tasks)
    assert oag.get_dependencies(tasks[1].id) == [tasks[0].id]
    assert oag.get_dependencies(tasks[2].id) == [tasks[1].id]


def test_heuristic_plan_without_objectives_creates_default_task(monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    oag = SerenPlanner().plan({"title": "Tiny"}, 10.0)
    tasks = list(oag.get_tasks().values())
    assert [t.description for t in tasks] == ["Ship core features"]
    # budget < 20 forces a conservative policy
    assert oag.budget.policy == BudgetPolicy.CONSERVATIVE


@pytest.mark.parametrize(
    ("budget", "n_objectives", "expected"),
    [
        (10.0, 1, BudgetPolicy.CONSERVATIVE),
        (50.0, 6, BudgetPolicy.CONSERVATIVE),
        (150.0, 3, BudgetPolicy.AGGRESSIVE),
        (150.0, 4, BudgetPolicy.BALANCED),
        (50.0, 2, BudgetPolicy.BALANCED),
    ],
)
def test_determine_budget_policy(budget, n_objectives, expected):
    assert SerenPlanner()._determine_budget_policy(budget, n_objectives) == expected


@pytest.mark.parametrize(
    ("n", "expected"), [(0, "small"), (2, "small"), (3, "medium"), (5, "medium"), (6, "large")]
)
def test_estimate_scope_size(n, expected):
    assert SerenPlanner()._estimate_scope_size([{}] * n) == expected


@pytest.mark.parametrize(
    ("role", "level"),
    [
        ("Chief Data Officer", RoleLevel.C_SUITE),
        ("CTO", RoleLevel.C_SUITE),
        ("VP Product", RoleLevel.VP),
        ("Director of Eng", RoleLevel.DIRECTOR),
        ("Product Manager", RoleLevel.MANAGER),
        ("Backend Engineer", RoleLevel.IC),
    ],
)
def test_role_to_level(role, level):
    assert SerenPlanner()._role_to_level(role) == level


def test_parse_design_output():
    p = SerenPlanner()
    assert p._parse_design_output("") is None
    assert p._parse_design_output('{"a": 1}') == {"a": 1}
    assert p._parse_design_output('Here you go:\n{"a": {"b": 2}}') == {"a": {"b": 2}}
    assert p._parse_design_output("no json here") is None
    assert p._parse_design_output("prefix {not json}") is None


# ---------------------------------------------------------------------------
# Design -> OAG translation (the local logic around the OpenAI response)
# ---------------------------------------------------------------------------

DESIGN = {
    "agents": [
        {"role": "CTO", "level": "C_SUITE", "reports_to": None},
        {"role": "Backend Engineer", "level": "IC", "reports_to": "CTO"},
        {"role": "Product Manager", "level": "bogus", "reports_to": "CTO"},
    ],
    "tasks": [
        {
            "title": "Build ingest",
            "description": "Pull messages from Slack",
            "assignee": "Backend Engineer",
            "dod": "Messages stored",
        },
        {
            "title": "Write summarizer",
            "description": "LLM summary of threads",
            "assignee": "Unknown Role",
            "depends_on": ["Build ingest"],
        },
    ],
    "budget_policy": "aggressive",
    "forecast_cost_usd": 42.5,
    "okrs": [
        {
            "owner_role": "CTO",
            "objective": "Ship v1",
            "key_results": [{"metric": "uptime", "target": 99}],
            "kpis": [{"metric": "latency_ms", "target": 500}],
        },
        {"owner_role": "Nobody", "objective": "ignored"},
    ],
}


def test_oag_from_design_builds_agents_edges_tasks_and_okrs():
    oag = SerenPlanner()._oag_from_design(PRD, 60.0, DESIGN)

    assert oag.budget.policy == BudgetPolicy.AGGRESSIVE
    assert oag.budget.forecast_cost_usd == 42.5
    assert oag.budget.caps.hard_cap_usd == 60.0

    by_role = {a.role: a for a in oag.get_agents().values()}
    assert set(by_role) == {"CTO", "Backend Engineer", "Product Manager"}
    assert by_role["Backend Engineer"].level == RoleLevel.IC
    # Invalid level falls back to role-name inference
    assert by_role["Product Manager"].level == RoleLevel.MANAGER

    # reports_to produces manager -> report edges
    pairs = {(e.from_id, e.to_id) for e in oag.edges}
    assert (by_role["CTO"].id, by_role["Backend Engineer"].id) in pairs
    assert (by_role["CTO"].id, by_role["Product Manager"].id) in pairs

    tasks = {t.description: t for t in oag.get_tasks().values()}
    ingest = tasks["Pull messages from Slack"]
    summarize = tasks["LLM summary of threads"]
    assert ingest.agent_id == by_role["Backend Engineer"].id
    assert ingest.contract.definition_of_done == "Messages stored"
    # Unknown assignee falls back to the first agent
    assert summarize.agent_id == by_role["CTO"].id
    # depends_on references the task title
    assert oag.get_dependencies(summarize.id) == [ingest.id]

    cto = by_role["CTO"]
    assert len(cto.okrs) == 1
    assert cto.okrs[0].objective.title == "Ship v1"
    assert [(kr.metric, kr.target) for kr in cto.okrs[0].key_results] == [("uptime", 99.0)]
    assert [(k.metric, k.target) for k in cto.kpis] == [("latency_ms", 500.0)]


def test_oag_from_design_unknown_policy_defaults_to_balanced():
    oag = SerenPlanner()._oag_from_design(PRD, 10.0, {"agents": [], "tasks": [], "budget_policy": "??"})
    assert oag.budget.policy == BudgetPolicy.BALANCED
    assert oag.budget.forecast_cost_usd == 0.0


# ---------------------------------------------------------------------------
# OpenAI boundary (third-party paid API: the only thing faked here)
# ---------------------------------------------------------------------------


class _FakeOpenAI:
    calls: list[dict] = []
    content: str = ""
    error: Exception | None = None

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        type(self).calls.append(kwargs)
        if type(self).error:
            raise type(self).error
        msg = SimpleNamespace(content=type(self).content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.fixture
def fake_openai(monkeypatch):
    monkeypatch.delenv("PLUGAH_MODE", raising=False)
    _FakeOpenAI.calls = []
    _FakeOpenAI.content = json.dumps(DESIGN)
    _FakeOpenAI.error = None
    monkeypatch.setattr(sp, "OpenAI", _FakeOpenAI)
    return _FakeOpenAI


def test_openai_plan_sends_schema_request_and_parses_response(fake_openai, monkeypatch):
    monkeypatch.setenv("SEREN_MODEL", "gpt-test")
    oag = SerenPlanner().plan(PRD, 60.0)

    assert len(fake_openai.calls) == 1
    req = fake_openai.calls[0]
    assert req["model"] == "gpt-test"
    assert req["response_format"]["type"] == "json_schema"
    schema = req["response_format"]["json_schema"]["schema"]
    assert schema["required"] == ["agents", "tasks", "budget_policy"]
    system, user = req["messages"]
    assert system["role"] == "system" and user["role"] == "user"
    assert "Slack Summarizer" in user["content"]
    assert "Budget USD: 60.0" in user["content"]

    # The response, not the heuristic, drives the OAG
    assert _roles(oag) == ["Backend Engineer", "CTO", "Product Manager"]
    assert oag.budget.policy == BudgetPolicy.AGGRESSIVE


def test_openai_default_model(fake_openai, monkeypatch):
    monkeypatch.delenv("SEREN_MODEL", raising=False)
    SerenPlanner().plan(PRD, 60.0)
    assert fake_openai.calls[0]["model"] == "gpt-4o-mini"


def test_openai_failure_falls_back_to_heuristic(fake_openai):
    fake_openai.error = RuntimeError("rate limited")
    oag = SerenPlanner().plan(PRD, 25.0)
    assert len(fake_openai.calls) == 1
    assert {"CEO", "CTO", "CFO"} <= set(_roles(oag))


def test_missing_openai_package_falls_back_to_heuristic(monkeypatch):
    monkeypatch.delenv("PLUGAH_MODE", raising=False)
    monkeypatch.setattr(sp, "OpenAI", None)
    with pytest.raises(RuntimeError, match="openai package not installed"):
        SerenPlanner()._openai_plan(PRD, 25.0)
    oag = SerenPlanner().plan(PRD, 25.0)
    assert {"CEO", "CTO", "CFO"} <= set(_roles(oag))


# ---------------------------------------------------------------------------
# Installation into plugah.boardroom
# ---------------------------------------------------------------------------


def test_install_seren_planner_respects_env(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(br, "Planner", sentinel)

    monkeypatch.setenv("SEREN_PLANNER", "off")
    assert install_seren_planner() is SerenPlanner
    assert br.Planner is sentinel

    monkeypatch.setenv("SEREN_PLANNER", "on")
    install_seren_planner()
    assert br.Planner is SerenPlanner
