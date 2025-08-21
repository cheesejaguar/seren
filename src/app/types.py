from typing import Any, TypedDict

class ExecutionResult(TypedDict, total=False):
    total_cost: float
    artifacts: dict[str, Any]
    metrics: dict[str, Any]
    details: dict[str, Any]
