# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2025-08-21
- feat: Add `plugah_seren` drop-in module to install Seren as Plugah’s planner via `import plugah_seren` (with `enable()`/`disable()`).
- docs: Add README section showing drop-in usage, env toggles (`SEREN_PLANNER`, `PLUGAH_MODE`, `SEREN_MODEL`).
- tests: Add `tests/test_plugah_seren.py` and keep coverage above configured 75% gate.
- chore: Sync with latest `vendor/plugah` `main` and confirm compatibility (no API breaks).
- docs: Add `AGENTS.md` repository guidelines.

## [0.1.0] - 2025-08-20
- Initial release of Seren Orchestrator (CLI + FastAPI, mock mode, integration with Plugah).

