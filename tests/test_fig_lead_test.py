"""scripts/fig_lead_test.py on FAKE lead-test outputs only (never results/holdout)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fig_lead_test as F  # noqa: E402


def fake_results(d: Path) -> Path:
    rng = np.random.default_rng(1)
    dec = {}
    for t in F.TESTS:
        n = 40
        pd.DataFrame({"game_id": [f"fake_{i}" for i in range(n + 3)],
                      "qualifying": [True] * n + [False] * 3,
                      "lag_s": list(rng.integers(0, 6, n).astype(float)) + [np.nan] * 3,
                      "reason": [""] * n + ["excluded: fake outage"] * 3}).to_csv(d / f"lead_{t}_per_game.csv", index=False)
        pd.DataFrame({"game_a": range(30), "game_b": range(1, 31), "machine": "vultr",
                      "lag_s": rng.integers(-15, 16, 30).astype(float)}).to_csv(d / f"lead_{t}_placebo.csv", index=False)
        dec[t] = {"n_qualifying": n, "n_placebo": 30, "median_corrected_lag_s": 2.0, "mann_whitney_p": 0.01,
                  "placebo_median_s": 0.0, "holm_level": 0.025, "result": "fake result"}
    (d / "lead_decisions.json").write_text(json.dumps(dec))
    return d


def test_figure_from_fake_results(tmp_path):
    res = fake_results(tmp_path)
    out = tmp_path / "fig.png"
    assert F.main(["--results", str(res), "--out", str(out)]) == 0
    assert out.exists() and out.stat().st_size > 10_000


def test_only_qualifying_games_are_plotted(tmp_path):
    real, pl = F.load(fake_results(tmp_path), "polymarket.com")
    assert len(real) == 40 and len(pl) == 30


def test_refuses_without_results(tmp_path):
    assert F.main(["--results", str(tmp_path / "missing"), "--out", str(tmp_path / "x.png")]) == 1
    assert not (tmp_path / "x.png").exists()
