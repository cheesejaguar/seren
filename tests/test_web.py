from pathlib import Path

from fastapi.testclient import TestClient

from app.web import app


def test_orchestrate_plan_execute_endpoints(tmp_path: Path, monkeypatch):
    # setenv first so the endpoint's os.environ write is undone after the test
    monkeypatch.setenv("PLUGAH_MODE", "mock")
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    r = client.post("/orchestrate", json={"problem": "Build a Slack bot", "budget": 30, "mock": True})
    assert r.status_code == 200
    questions = r.json()["questions"]
    assert len(questions) > 0 and all(isinstance(q, str) for q in questions)

    r = client.post(
        "/plan",
        json={
            "problem": "Build a Slack bot",
            "budget": 30,
            "answers": ["a"] * len(questions),
            "policy": "CONSERVATIVE",
            "mock": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["prd"]["title"] == "Build a Slack bot"
    assert body["oag"]["budget"]["caps"]["hard_cap_usd"] == 30.0
    assert (tmp_path / "oag.json").exists()

    r = client.post("/execute")
    assert r.status_code == 200
    assert "total_cost" in r.json()


def test_plan_validates_request_body():
    client = TestClient(app)
    r = client.post("/plan", json={"problem": "x", "budget": 1})  # missing answers
    assert r.status_code == 422
