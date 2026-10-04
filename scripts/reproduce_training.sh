#!/bin/bash
# One command: reproduce every committed TRAINING number (results/numbers.json) from the raw training data.
#   scripts/reproduce_training.sh            (uses .venv-run, built from the pinned requirements.txt if missing)
# Needs the raw training data under data/ (gitignored, vendor data; see README "Reproduce"). Runs Strategy A,
# Strategy B (with its placebo and costs x2) and the book report, then diffs results/numbers.json against the
# committed file and prints every differing key. Re-runs are not new variants: --no-variants-log keeps
# experiments/variants.csv unchanged.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv-run/bin/python
if [ ! -x "$PY" ]; then python3 -m venv .venv-run && .venv-run/bin/pip install -q -r requirements.txt; fi
$PY -c "import pandas, numpy; assert (pandas.__version__, numpy.__version__) == ('2.3.2', '1.26.4'), (pandas.__version__, numpy.__version__)"
[ -f out/strategy_b/b_games_espn.csv ] || $PY scripts/build_b_games_espn.py
$PY run_strategy_a.py --no-variants-log > out/reproduce_strategy_a.log
$PY run_strategy_b.py --no-variants-log > out/reproduce_strategy_b.log
$PY report_book.py > out/reproduce_report_book.log
$PY - <<'PYEOF'
import json, math, subprocess
new = json.load(open("results/numbers.json"))
old = json.loads(subprocess.run(["git", "show", "HEAD:results/numbers.json"], capture_output=True, text=True).stdout)
def same(a, b):
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1.0, abs(a))
    return a == b
keys = sorted(set(old) | set(new))
diff = [k for k in keys if not same(old.get(k, {}).get("value"), new.get(k, {}).get("value"))]
print(f"numbers.json: committed {len(old)} keys, reproduced {len(new)}; matching {len(keys) - len(diff)}/{len(keys)}")
for k in diff:
    print("  DIFF", k, old.get(k, {}).get("value"), "->", new.get(k, {}).get("value"))
raise SystemExit(1 if diff else 0)
PYEOF
