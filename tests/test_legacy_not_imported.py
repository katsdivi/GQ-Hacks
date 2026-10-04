"""The legacy/backtest.py header says it is not used for any reported number: importing the one-run script must
not import it (directly or through any module the script reaches)."""
import importlib
import sys


def test_final_run_does_not_import_legacy_backtest():
    for m in [m for m in sys.modules if m == "legacy.backtest" or m.startswith("legacy")]:
        del sys.modules[m]                      # other tests in the session may have imported it
    importlib.import_module("scripts.final_test_run")
    assert "legacy.backtest" not in sys.modules
    importlib.import_module("scripts.final_test_fixtures")      # the dry-run path too
    assert "legacy.backtest" not in sys.modules
