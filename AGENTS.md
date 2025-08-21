# Repository Guidelines

## Project Structure & Module Organization
- `src/app/`: Core package (CLI, web API, planner, I/O, config). Example: `src/app/cli.py`, `src/app/web.py`.
- `tests/`: Pytest suite (`test_*.py`).
- `dist/`: Build artifacts.
- `vendor/`: Embedded Plugah sources (excluded from this repo’s tests).
- Root JSON artifacts produced by runs: `questions.json`, `prd.json`, `oag.json`, `results.json`.

## Build, Test, and Development Commands
- Install (dev): `pip install -e ".[dev]"`
- CLI quickstart: `plugah-orchestrate quickstart --mock` (runs discovery → PRD → OAG → execution).
- Stage-by-stage: `plugah-orchestrate init|plan|run --mock`
- Web API (dev): `plugah-web` (FastAPI via Uvicorn at `127.0.0.1:8000`).
- Tests: `pytest -q` (coverage gate 75%).
- Lint: `ruff check .`  Format: `ruff format .`
- Types: `mypy src`

## Coding Style & Naming Conventions
- Python 3.11+, 4‑space indentation; LF newlines (`.editorconfig`).
- Line length 100 (`tool.ruff.line-length`).
- Names: modules/functions `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE_CASE`.
- Prefer type hints; mypy is lenient (`ignore_missing_imports = true`).
- Keep changes minimal and localized; match existing patterns under `src/app/`.

## Testing Guidelines
- Framework: Pytest (+ `pytest-asyncio`); mark async tests with `@pytest.mark.asyncio`.
- Layout: place tests in `tests/` with filenames `test_*.py`.
- Coverage: configured via `pyproject.toml` to fail under 75% (`--cov=src`).
- Run focused tests: `pytest tests/test_cli_quickstart.py -q`.
- Mock/offline: prefer `--mock` or `PLUGAH_MODE=mock` for deterministic tests.

## Commit & Pull Request Guidelines
- Commits: use concise, imperative messages. Conventional prefixes encouraged (e.g., `feat:`, `fix:`, `ci:`, `chore:`, `docs:`).
- PRs: include summary, rationale, linked issues, test coverage notes, and CLI/HTTP sample output or screenshots.
- Checks: ensure `pytest`, `ruff check`, and `mypy src` pass locally.

## Security & Configuration Tips
- API providers: set `OPENAI_API_KEY` when not using mock mode.
- Planner toggles: `SEREN_PLANNER=off` to use stock Plugah planner; `SEREN_MODEL=gpt-4o-mini` to override default model.
- Always prefer mock for local/CI runs without credentials: `--mock` or `PLUGAH_MODE=mock`.
