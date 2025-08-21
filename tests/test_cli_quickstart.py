from typer.testing import CliRunner
from pathlib import Path

from app.cli import app


def test_cli_quickstart_mock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "quickstart",
            "--problem",
            "Build a Slack summarizer bot",
            "--budget",
            "10",
            "--policy",
            "BALANCED",
            "--mock",
        ],
    )
    assert result.exit_code == 0, result.output

    # Verify artifacts
    assert (tmp_path / "questions.json").exists()
    assert (tmp_path / "prd.json").exists()
    assert (tmp_path / "oag.json").exists()
    assert (tmp_path / "results.json").exists()
