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

def write_json(path: str, obj: Any) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
