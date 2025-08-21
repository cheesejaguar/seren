import importlib
import os


def test_plugah_seren_enable_disable(monkeypatch):
    # Ensure auto-install is on for import
    monkeypatch.delenv("SEREN_PLANNER", raising=False)

    # Fresh import to trigger auto-install path
    if "plugah_seren" in list(importlib.sys.modules.keys()):
        importlib.reload(importlib.import_module("plugah_seren"))
    else:
        import plugah_seren  # noqa: F401

    import plugah.boardroom as br

    original = getattr(br, "Planner", None)

    # Explicitly enable, then disable, then restore
    import plugah_seren as ps

    ps.enable()
    assert getattr(br, "Planner", None) is not None
    # Expect Seren planner class installed
    assert getattr(br, "Planner").__name__.lower().endswith("planner")

    ps.disable()
    assert getattr(br, "Planner", None) is original

    # Ensure env flag disables auto-install
    monkeypatch.setenv("SEREN_PLANNER", "off")
    importlib.reload(ps)
    assert getattr(br, "Planner", None) is original

