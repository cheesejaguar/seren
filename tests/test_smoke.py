from pathlib import Path
import pytest

from app.core import run_discovery, build_prd, plan_oag, execute_plan

@pytest.mark.asyncio
async def test_pipeline_smoke(tmp_path: Path, monkeypatch):
    # Ensure offline deterministic behavior
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    # Run minimal discovery
    qs = await run_discovery("Build a Slack summarizer bot", 25.0)
    assert isinstance(qs, list)

    # Provide minimal answers (use first few questions)
    answers = [f"Answer {i+1}" for i, _ in enumerate(qs[:5])]
    prd = await build_prd(answers, "Build a Slack summarizer bot", 25.0)
    assert isinstance(prd, dict)

    # Plan
    oag = await plan_oag(prd, 25.0)
    assert isinstance(oag, dict)

    # Execute
    results = await execute_plan()
    assert isinstance(results, dict)
    assert "total_cost" in results
