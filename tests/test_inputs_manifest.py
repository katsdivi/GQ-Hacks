"""scripts/final_test_run.manifest_checks: the frozen GAPS tables and heartbeat logs the runner reads must match
results/holdout_inputs_manifest.txt (sha256), and no machine may read the tracked GAPS.md."""
import hashlib

import holdout_mid as H
from scripts.final_test_run import manifest_checks


def setup(tmp_path):
    for name in ("vultr", "mac"):
        hb = tmp_path / "data" / name / "heartbeats"
        hb.mkdir(parents=True)
        (hb / "20261003.jsonl").write_text(f'{{"venue": "kalshi_ws", "{name}": 1}}\n')
        (tmp_path / "data" / name / f"GAPS_{name}.md").write_text(f"| gaps {name} |\n")
    files = sorted(p for p in (tmp_path / "data").rglob("*") if p.is_file())
    man = tmp_path / "manifest.txt"
    man.write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(tmp_path)}\n" for p in files))
    ms = [H.Machine(n, tmp_path, tmp_path / "data" / n / f"GAPS_{n}.md", tmp_path / "data" / n / "heartbeats")
          for n in ("vultr", "mac")]
    return ms, man


def test_manifest_ok_then_detects_change_and_tracked_gaps(tmp_path):
    ms, man = setup(tmp_path)
    assert all(v["ok"] for v in manifest_checks(ms, man, tmp_path).values())
    (tmp_path / "data" / "mac" / "heartbeats" / "20261003.jsonl").write_text("changed\n")       # edited after freeze
    r = manifest_checks(ms, man, tmp_path)
    assert not r["mac frozen inputs match manifest"]["ok"] and r["vultr frozen inputs match manifest"]["ok"]
    (tmp_path / "GAPS.md").write_text("tracked\n")
    ms[1] = H.Machine("mac", tmp_path, tmp_path / "GAPS.md", tmp_path / "data" / "mac" / "heartbeats")
    assert not manifest_checks(ms, man, tmp_path)["mac does not read tracked GAPS.md"]["ok"]
    assert not manifest_checks(ms, tmp_path / "nope.txt", tmp_path)["inputs manifest present"]["ok"]
