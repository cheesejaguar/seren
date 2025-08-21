import asyncio
from typing import Any, Sequence

from plugah import BoardRoom, BudgetPolicy  # From Plugah README
from .io import read_json, write_json

# Keep a single BoardRoom per-process to preserve internal state across stages.
_boardroom: BoardRoom | None = None

def _br() -> BoardRoom:
    global _boardroom
    if _boardroom is None:
        _boardroom = BoardRoom()
    return _boardroom

def map_policy(name: str) -> BudgetPolicy:
    name = (name or "BALANCED").upper()
    return {
        "CONSERVATIVE": BudgetPolicy.CONSERVATIVE,
        "BALANCED": BudgetPolicy.BALANCED,
        "AGGRESSIVE": BudgetPolicy.AGGRESSIVE,
    }[name]

async def run_discovery(problem: str, budget_usd: float) -> list[str]:
    """
    Returns discovery questions from Plugah's startup_phase.
    Also writes questions.json for convenience.
    """
    questions = await _br().startup_phase(problem=problem, budget_usd=budget_usd)
    write_json("questions.json", questions)
    return questions

async def build_prd(answers: Sequence[str], problem: str, budget_usd: float) -> dict[str, Any]:
    """
    Feeds discovery answers to produce a PRD.
    Writes prd.json.
    """
    prd = await _br().process_discovery(list(answers), problem, budget_usd)
    write_json("prd.json", prd)
    return prd

async def plan_oag(prd: dict[str, Any], budget_usd: float) -> dict[str, Any]:
    """
    Plans the Organizational Agent Graph (OAG) from the PRD.
    Writes oag.json.
    """
    oag = await _br().plan_organization(prd, budget_usd)
    write_json("oag.json", oag)
    return oag

async def execute_plan() -> dict[str, Any]:
    """
    Executes the planned work.
    Writes results.json and returns execution results (must include total_cost).
    """
    results = await _br().execute()
    write_json("results.json", results)
    return results
