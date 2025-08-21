# Seren — Plugah Orchestrator ✨

Seren is a minimal, runnable orchestrator around **[Plugah](https://github.com/cheesejaguar/plugah)** that drives dynamic agentic graph generation end‑to‑end:

1) 🔎 Discovery → 2) 📝 PRD → 3) 🧩 Organization Planning (OAG) → 4) 🚀 Execution

It ships with a CLI and a small FastAPI service. Offline “mock” mode is supported for CI and demos. 🧪

## Requirements

- Python 3.11+

## Install 📦

```bash
# Editable install (recommended for development)
pip install -e ".[dev]"

# If Plugah isn’t available from PyPI in your environment, you can install from GitHub:
# pip install "git+https://github.com/cheesejaguar/plugah.git"
```

## Quickstart (CLI) ⚡️

Run the full pipeline non‑interactively in offline mock mode:

```bash
plugah-orchestrate quickstart \
  --problem "Build a Slack summarizer bot" \
  --budget 100 \
  --policy BALANCED \
  --model gpt-4o \
  --mock
```

Stage‑by‑stage:

```bash
# 1) Discovery → questions.json
plugah-orchestrate init --problem "Build X" --budget 100 --policy BALANCED --model gpt-4o --mock

# Provide answers (edit answers.json or generate your own)
echo '["Answer 1","Answer 2"]' > answers.json

# 2) PRD → prd.json, 3) OAG → oag.json
plugah-orchestrate plan --answers-file answers.json --policy AGGRESSIVE --mock

# 4) Execution → results.json (includes total_cost)
plugah-orchestrate run --mock
```

Generated artifacts in the repo root 📁:

- questions.json
- answers.json (if you used quickstart auto generation)
- prd.json
- oag.json
- results.json

## Web API 🌐

Start the API server:

```bash
plugah-web
# or: uvicorn app.web:app --host 127.0.0.1 --port 8000 --reload
```

Endpoints:

- POST /orchestrate

```json
{
  "problem": "Build a Slack summarizer bot",
  "budget": 100,
  "policy": "BALANCED",
  "model_hint": "gpt-4o",
  "mock": true
}
```

- POST /plan

```json
{
  "problem": "Build a Slack summarizer bot",
  "budget": 100,
  "answers": ["Answer 1", "Answer 2"],
  "policy": "BALANCED",
  "model_hint": "gpt-4o",
  "mock": true
}
```

- POST /execute → returns execution result with `total_cost`.

## How it integrates with Plugah 🔌

Seren now provides a planner used by [Plugah](https://github.com/cheesejaguar/plugah) during the Organization Planning phase. We inject `SerenPlanner` as Plugah’s `Planner`, so when `BoardRoom.plan_organization()` runs, it calls into Seren.

Pipeline entrypoints remain:

- `startup_phase(problem, budget_usd, model_hint?, policy?)` → questions
- `process_discovery(answers, problem, budget_usd, model_hint?, policy?)` → PRD
- `plan_organization(prd, budget_usd, model_hint?, policy?)` → OAG
- `execute(on_event?)` → ExecutionResult (includes `total_cost`)

Mock mode: set `PLUGAH_MODE=mock` or pass `--mock`/`mock: true` to run deterministically without network/API keys.

### SerenPlanner architecture

- Default: Seren installs itself as the planner at import-time. You can disable it via `SEREN_PLANNER=off`.
- Mock: In `PLUGAH_MODE=mock`, Seren generates a deterministic OAG with budget-aware heuristics (no network calls).
- CrewAI path: In non-mock mode, Seren spins up a small Crew (e.g., an “Org Architect” agent) and instructs it to emit strict JSON describing:
  - `agents`: role hierarchy via `reports_to`
  - `tasks`: title/description/assignee/dependencies/DoD
  Seren parses the JSON and constructs a valid OAG (Agents, Tasks, Edges). If parsing fails or providers are unavailable, Seren falls back to heuristics.

### Provider configuration

Seren relies on the underlying CrewAI/LiteLLM provider configuration. Common environment variables:
- `OPENAI_API_KEY` (or other LiteLLM-compatible providers)
- Optional: model hints via CLI `--model` are forwarded to Plugah where possible

You can also disable Seren’s injection with `SEREN_PLANNER=off` to use Plugah’s stock planner.

## Testing 🧪

```bash
pytest -q
```

Tests run in mock mode and validate Discovery → PRD → OAG → Execution, asserting a `total_cost` is returned.

Additional CLI smoke test validates artifact generation via `quickstart --mock`.

## Notes 🧭

- The CLI accepts `--policy` (CONSERVATIVE|BALANCED|AGGRESSIVE) and `--model` as a hint to [Plugah](https://github.com/cheesejaguar/plugah).
- OAG and results are safely JSON‑serialized even when returned as Pydantic models.
