import json
from pathlib import Path

import pytest

from app.core import build_prd, execute_plan, plan_oag, run_discovery


@pytest.mark.asyncio
async def test_pipeline_smoke(tmp_path: Path, monkeypatch):
    # Ensure offline deterministic behavior
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)

    # Discovery returns questions and persists them
    qs = await run_discovery("Build a Slack summarizer bot", 25.0)
    assert len(qs) > 0
    assert all(isinstance(q, str) and q for q in qs)
    assert json.loads((tmp_path / "questions.json").read_text()) == qs

    # PRD reflects the problem and budget that were passed in
    answers = [f"Answer {i+1}" for i, _ in enumerate(qs[:5])]
    prd = await build_prd(answers, "Build a Slack summarizer bot", 25.0)
    assert prd["title"] == "Build a Slack summarizer bot"
    assert prd["budget"] == 25.0
    assert prd["objectives"]
    assert json.loads((tmp_path / "prd.json").read_text())["title"] == prd["title"]

    # Plan: the OAG is dumped to a JSON-serialisable dict honouring the budget caps
    oag = await plan_oag(prd, 25.0)
    assert oag["budget"]["caps"] == {"hard_cap_usd": 25.0, "soft_cap_usd": 20.0}
    roles = {n["role"] for n in oag["nodes"].values() if "role" in n}
    assert {"CEO", "CTO", "CFO"} <= roles
    assert json.loads((tmp_path / "oag.json").read_text()) == oag

    # Execute
    results = await execute_plan()
    assert isinstance(results["total_cost"], (int, float))
    assert results["total_cost"] <= 25.0
    assert json.loads((tmp_path / "results.json").read_text())["total_cost"] == results["total_cost"]
