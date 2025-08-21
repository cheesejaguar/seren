# Contributing to Seren (Plugah Orchestrator)

Thanks for your interest in contributing! This guide covers setup, development workflow, and how to propose changes.

## Quick Start

1) Clone and create a virtual environment
```bash
git clone https://github.com/cheesejaguar/seren.git
cd seren
python -m venv .venv && source .venv/bin/activate
```

2) Install (editable) with dev extras
```bash
pip install -e ".[dev]"
```

3) Run tests in mock mode (offline)
```bash
export PLUGAH_MODE=mock
pytest -q
```

4) Lint and type-check
```bash
ruff check .
mypy src
```

## Development Workflow

- Keep changes focused and minimal; match existing style and `src/` layout.
- Prefer small, reviewable PRs with a clear description and checklist.
- Update tests under `tests/` to cover new behavior; do not change unrelated areas.
- Update `README.md` and CLI help if behavior/flags change.

### Branching & Commits

- Branch off `main` using a descriptive name:
  - `feature/<short-slug>` or `bugfix/<short-slug>`
- Write clear, imperative commit messages:
  - `feat: …`, `fix: …`, `chore: …`, `docs: …`, `tests: …`

### Running the CLI locally
```bash
plugah-orchestrate quickstart --mock --problem "Build a Slack summarizer bot" --budget 100
```

## Pull Requests

Please ensure:
- [ ] Tests pass (`pytest`) in mock mode
- [ ] Lint and types pass (`ruff`, `mypy`)
- [ ] Docs updated (README/API/CLI help) if needed
- [ ] No regressions across Discovery → PRD → OAG → Execution

## Reporting Security Issues

Please see `SECURITY.md` for instructions on privately reporting vulnerabilities.

## Code of Conduct

By participating, you agree to abide by our `CODE_OF_CONDUCT.md`.

