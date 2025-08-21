"""
plugah_seren: Drop-in Seren planner for Plugah

Usage (in any Plugah-based app):

    import plugah_seren  # auto-installs Seren planner
    from plugah.boardroom import BoardRoom
    # BoardRoom().plan_organization(...) now uses SerenPlanner

To control installation explicitly:

    import plugah_seren
    plugah_seren.enable()   # install Seren planner
    plugah_seren.disable()  # restore stock planner

This package wraps Seren’s planner from `app.seren_planner` and replaces
`plugah.boardroom.Planner` at runtime so consumers of Plugah need no code
changes. In mock/offline mode (PLUGAH_MODE=mock), Seren emits a deterministic
OAG; otherwise it uses the OpenAI JSON response format for planning.
"""

from __future__ import annotations

from types import SimpleNamespace


_state = SimpleNamespace(
    installed=False,
    original_planner=None,
)


def enable():
    """Install SerenPlanner into plugah.boardroom as the Planner."""
    if _state.installed:
        return
    # Import here to avoid importing OpenAI in environments that only need mock mode
    from app.seren_planner import SerenPlanner  # type: ignore
    import plugah.boardroom as br  # type: ignore

    if _state.original_planner is None:
        _state.original_planner = getattr(br, "Planner", None)
    br.Planner = SerenPlanner  # type: ignore[assignment]
    _state.installed = True


def disable():
    """Restore Plugah’s stock Planner if previously overridden."""
    if not _state.installed:
        return
    import plugah.boardroom as br  # type: ignore

    if _state.original_planner is not None:
        br.Planner = _state.original_planner  # type: ignore[assignment]
    _state.installed = False


# Auto-install on import unless explicitly disabled via env
def _auto():
    import os
    if os.getenv("SEREN_PLANNER", "on").lower() in {"0", "false", "off"}:
        return
    enable()


_auto()

