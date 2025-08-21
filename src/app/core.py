import inspect
from typing import Any, Sequence

# Prefer stable module paths with fallbacks
try:
    from plugah.boardroom import BoardRoom
except Exception:  # pragma: no cover
    from plugah import BoardRoom  # type: ignore

try:
    from plugah.budget import BudgetPolicy  # new export location
except Exception:  # pragma: no cover
    try:
        from plugah import BudgetPolicy  # legacy export
    except Exception:
        BudgetPolicy = None  # type: ignore

from .io import write_json

# Keep a single BoardRoom per-process to preserve internal state across stages.
_boardroom: BoardRoom | None = None

def _br() -> BoardRoom:
    global _boardroom
    if _boardroom is None:
        _boardroom = BoardRoom()
    return _boardroom

def map_policy(name: str | None):
    if not name or BudgetPolicy is None:
        return name or "BALANCED"
    name = name.upper()
    return {
        "CONSERVATIVE": BudgetPolicy.CONSERVATIVE,
        "BALANCED": BudgetPolicy.BALANCED,
        "AGGRESSIVE": BudgetPolicy.AGGRESSIVE,
    }.get(name, BudgetPolicy.BALANCED)

def _filter_kwargs(fn, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        sig = inspect.signature(fn)
        keys = sig.parameters.keys()
        return {k: v for k, v in kwargs.items() if k in keys and v is not None}
    except Exception:
        return {}

async def _call_maybe_async(fn, /, *args, **kwargs):
    res = fn(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res

async def run_discovery(problem: str, budget_usd: float, *, model_hint: str | None = None, policy: str | None = None) -> list[str]:
    """
    Returns discovery questions from Plugah's startup_phase.
    Also writes questions.json for convenience.
    """
    fn = _br().startup_phase
    kwargs = _filter_kwargs(fn, {
        "problem": problem,
        "budget_usd": budget_usd,
        "model_hint": model_hint,
        "policy": map_policy(policy),
        "context": None,
    })
    result = await _call_maybe_async(fn, **kwargs)
    # Accept dict with "questions" or direct list
    if isinstance(result, dict):
        qs = result.get("questions", [])
    else:
        qs = result
    write_json("questions.json", qs)
    return list(qs)

async def build_prd(answers: Sequence[str], problem: str, budget_usd: float, *, model_hint: str | None = None, policy: str | None = None) -> dict[str, Any]:
    """
    Feeds discovery answers to produce a PRD.
    Writes prd.json.
    """
    fn = _br().process_discovery
    kwargs = _filter_kwargs(fn, {
        "answers": list(answers),
        "problem": problem,
        "budget_usd": budget_usd,
        "model_hint": model_hint,
        "policy": map_policy(policy),
    })
    prd = await _call_maybe_async(fn, **kwargs)
    write_json("prd.json", prd)
    return prd

async def plan_oag(prd: dict[str, Any], budget_usd: float, *, model_hint: str | None = None, policy: str | None = None) -> dict[str, Any]:
    """
    Plans the Organizational Agent Graph (OAG) from the PRD.
    Writes oag.json.
    """
    fn = _br().plan_organization
    kwargs = _filter_kwargs(fn, {
        "prd": prd,
        "budget_usd": budget_usd,
        "model_hint": model_hint,
        "policy": map_policy(policy),
    })
    oag = await _call_maybe_async(fn, **kwargs)
    oag_dict = oag
    # If OAG is a Pydantic model, dump it to dict for JSON
    if hasattr(oag, "model_dump"):
        try:
            oag_dict = oag.model_dump(mode="json")
        except TypeError:
            oag_dict = oag.model_dump()
    elif hasattr(oag, "dict"):
        oag_dict = oag.dict()
    write_json("oag.json", oag_dict)
    return oag_dict  # keep returning dict for callers

async def execute_plan(on_event: Any | None = None) -> dict[str, Any]:
    """
    Executes the planned work.
    Writes results.json and returns execution results (must include total_cost).
    """
    fn = _br().execute
    kwargs = _filter_kwargs(fn, {"on_event": on_event})
    results = await _call_maybe_async(fn, **kwargs)
    results_dict = results
    if hasattr(results, "model_dump"):
        try:
            results_dict = results.model_dump(mode="json")
        except TypeError:
            results_dict = results.model_dump()
    elif not isinstance(results, dict) and hasattr(results, "__dict__"):
        # Best-effort conversion
        results_dict = dict(results.__dict__)
    write_json("results.json", results_dict)
    return results_dict
