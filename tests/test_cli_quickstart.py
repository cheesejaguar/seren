import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_cli_quickstart_mock(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)

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
    assert "Project complete!" in result.output

    # Auto-answers are generated one per discovery question
    questions = json.loads((tmp_path / "questions.json").read_text())
    answers = json.loads((tmp_path / "answers.json").read_text())
    assert len(answers) == len(questions) > 0
    assert answers[0].startswith("Auto-answer 1: ")

    # The budget flag flows through to the PRD and the OAG caps
    assert json.loads((tmp_path / "prd.json").read_text())["budget"] == 10.0
    oag = json.loads((tmp_path / "oag.json").read_text())
    assert oag["budget"]["caps"]["hard_cap_usd"] == 10.0
    assert "total_cost" in json.loads((tmp_path / "results.json").read_text())


def test_cli_init_plan_run_stages(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--problem", "Build a CLI todo app", "--budget", "40", "--mock"])
    assert result.exit_code == 0, result.output
    questions = json.loads((tmp_path / "questions.json").read_text())
    assert f"questions.json with {len(questions)} questions" in result.output

    (tmp_path / "answers.json").write_text(json.dumps([f"A{i}" for i in range(len(questions))]))
    result = runner.invoke(app, ["plan", "--problem", "Build a CLI todo app", "--budget", "40", "--mock"])
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "prd.json").read_text())["title"] == "Build a CLI todo app"
    assert json.loads((tmp_path / "oag.json").read_text())["budget"]["caps"]["hard_cap_usd"] == 40.0

    result = runner.invoke(app, ["run", "--mock"])
    assert result.exit_code == 0, result.output
    assert "Execution Summary" in result.output
    assert "total_cost" in json.loads((tmp_path / "results.json").read_text())


def test_cli_plan_rejects_non_array_answers(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "answers.json").write_text(json.dumps({"not": "a list"}))

    result = runner.invoke(app, ["plan", "--mock"])
    assert result.exit_code != 0
    assert not (tmp_path / "prd.json").exists()


def test_cli_plan_warns_when_answers_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan", "--budget", "30", "--mock"])
    assert result.exit_code == 0, result.output
    assert "No answers found" in result.output
    assert (tmp_path / "prd.json").exists()
