import importlib

import plugah.boardroom as br
from plugah.planner import Planner as StockPlanner

from app.seren_planner import SerenPlanner


def test_plugah_seren_enable_disable(monkeypatch):
    monkeypatch.delenv("SEREN_PLANNER", raising=False)
    # Start from a clean slate: stock planner installed, fresh plugah_seren state.
    monkeypatch.setattr(br, "Planner", StockPlanner)
    import plugah_seren as ps

    ps = importlib.reload(ps)  # auto-installs on import
    assert br.Planner is SerenPlanner
    assert ps._state.installed is True

    ps.disable()
    assert br.Planner is StockPlanner

    ps.enable()
    assert br.Planner is SerenPlanner

    ps.disable()
    assert br.Planner is StockPlanner


def test_plugah_seren_disable_restores_stock_after_app_import(monkeypatch):
    # app.seren_planner swaps the planner on import; disable() must still restore
    # Plugah's stock planner rather than "restoring" SerenPlanner.
    monkeypatch.delenv("SEREN_PLANNER", raising=False)
    monkeypatch.setattr(br, "Planner", SerenPlanner)
    import plugah_seren as ps

    ps = importlib.reload(ps)
    assert br.Planner is SerenPlanner
    ps.disable()
    assert br.Planner is StockPlanner


def test_plugah_seren_env_flag_disables_auto_install(monkeypatch):
    monkeypatch.setattr(br, "Planner", StockPlanner)
    monkeypatch.setenv("SEREN_PLANNER", "off")
    import plugah_seren as ps

    ps = importlib.reload(ps)
    assert br.Planner is StockPlanner
    assert ps._state.installed is False
    # disable() before any enable() is a no-op
    ps.disable()
    assert br.Planner is StockPlanner
