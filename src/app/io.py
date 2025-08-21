import json
from pathlib import Path
from typing import Any

# Resolve to the repo root by default
ROOT = Path.cwd()

def read_json(path: str) -> Any | None:
    p = ROOT / path
    if not p.exists():
        return None
    return json.loads(p.read_text())

def _json_default(o: Any):
    # Try common object-to-dict conversions
    if hasattr(o, "model_dump"):
        try:
            return o.model_dump(mode="json")
        except TypeError:
            return o.model_dump()
    if hasattr(o, "dict"):
        try:
            return o.dict()
        except Exception:
            pass
    if hasattr(o, "__dict__"):
        return dict(o.__dict__)
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)

def write_json(path: str, obj: Any) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default))
