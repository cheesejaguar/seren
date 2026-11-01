import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from plugah.budget import BudgetPolicy
from pydantic import BaseModel

from app.config import default_settings
from app.core import _call_maybe_async, _filter_kwargs, map_policy
from app.export_crewai import export_to_crewai
from app.io import read_json, write_json


class _Model(BaseModel):
    x: int


@dataclass
class _Plain:
    y: str


def test_write_and_read_json_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_json("missing.json") is None

    write_json("nested/out.json", {"m": _Model(x=1), "p": _Plain(y="z"), "s": {3}, "t": (1, 2)})
    assert (tmp_path / "nested" / "out.json").exists()
    assert read_json("nested/out.json") == {"m": {"x": 1}, "p": {"y": "z"}, "s": [3], "t": [1, 2]}


def test_write_json_falls_back_to_str(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class Slotted:
        __slots__ = ()

        def __str__(self):
            return "slotted!"

    write_json("o.json", [Slotted()])
    assert json.loads((tmp_path / "o.json").read_text()) == ["slotted!"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("conservative", BudgetPolicy.CONSERVATIVE),
        ("BALANCED", BudgetPolicy.BALANCED),
        ("Aggressive", BudgetPolicy.AGGRESSIVE),
        ("nonsense", BudgetPolicy.BALANCED),
    ],
)
def test_map_policy(name, expected):
    assert map_policy(name) == expected


def test_map_policy_none_defaults_to_balanced_string():
    assert map_policy(None) == "BALANCED"


def test_filter_kwargs_keeps_only_accepted_non_none():
    def fn(problem, budget_usd, policy=None):
        return None

    out = _filter_kwargs(fn, {"problem": "p", "budget_usd": 1.0, "policy": None, "extra": 1})
    assert out == {"problem": "p", "budget_usd": 1.0}


@pytest.mark.asyncio
async def test_call_maybe_async_handles_sync_and_async():
    async def a(x):
        return x * 2

    assert await _call_maybe_async(lambda x: x + 1, 1) == 2
    assert await _call_maybe_async(a, 2) == 4


def test_export_to_crewai_writes_placeholder(tmp_path: Path):
    out = tmp_path / "crew"
    export_to_crewai({"nodes": {}}, str(out))
    assert "CrewAI" in (out / "README.txt").read_text()


def test_default_settings():
    s = default_settings()
    assert s.budget_hard_cap_usd == 100.0
    assert s.budget_soft_cap_usd == 80.0
    assert s.budget_policy == "BALANCED"
