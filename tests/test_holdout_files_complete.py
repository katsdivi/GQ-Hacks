"""scripts/final_test_run.holdout_files_complete: every A/B holdout file of a kept game (ESPN kickoff <= 20:00 ET
2026-10-03) must have been written at or after kickoff + 5 h (v3 Amendment 4). Synthetic files; times set by os.utime."""
import os

import pandas as pd

from scripts.final_test_run import holdout_files_complete


def test_complete_early_missing_and_cutoff(tmp_path):
    for d in ("kalshi", "polymarket"):
        (tmp_path / d).mkdir()
    ko = {"g1": "2026-09-20T17:00:00Z", "g2": "2026-10-03T23:00:00Z", "late": "2026-10-04T02:30:00Z"}
    pd.DataFrame({"game_id": list(ko), "espn_kickoff": list(ko.values())}).to_csv(tmp_path / "events.csv", index=False)
    pd.DataFrame({"game_id": ["g1"]}).to_csv(tmp_path / "pm_map.csv", index=False)
    def write(venue, g, when):
        f = tmp_path / venue / f"{g}.parquet"
        f.write_text("x")
        t = pd.Timestamp(when).timestamp()
        os.utime(f, (t, t))
    write("kalshi", "g1", "2026-09-20T22:00:00Z")          # exactly kickoff + 5 h: complete
    write("polymarket", "g1", "2026-09-20T23:00:00Z")
    write("kalshi", "g2", "2026-10-04T02:48:00Z")          # 22:48 ET, window ends 04:00 UTC: early
    r = holdout_files_complete(tmp_path)
    assert r["holdout polymarket files written after window end"]["ok"]
    k = r["holdout kalshi files written after window end"]
    assert not k["ok"] and "written before window end 1" in k["value"] and "2 kept games" in k["value"]   # late dropped
    write("kalshi", "g2", "2026-10-04T04:01:00Z")
    assert holdout_files_complete(tmp_path)["holdout kalshi files written after window end"]["ok"]
    (tmp_path / "kalshi" / "g1.parquet").unlink()
    assert "missing 1" in holdout_files_complete(tmp_path)["holdout kalshi files written after window end"]["value"]
