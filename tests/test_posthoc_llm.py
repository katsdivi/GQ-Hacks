"""Synthetic tests for scripts/posthoc_llm.py (no real data)."""
import numpy as np
import pandas as pd
import pytest

import posthoc_llm as L
import regress_common as C


def _row(**kw):
    r = {c: 0.0 for c in L.PROMPT_COLS}
    r.update(nfl=1, p=0.62, q=0.39, s=1.01, mins_from_ko=70, espn_ok=1, wp=0.7, score_diff=7, period=3, sec_left=1200)
    r.update(kw)
    return r


def test_no_future_field_in_prompt():
    base = _row()
    planted = dict(base, pay=1.0, r=0.38, y=1, c=0.028, week=12, game_id="nfl_x", team="KC", t_ns=123, future_px=0.99)
    assert L.make_prompt(base) == L.make_prompt(planted)
    txt = L.make_prompt(planted)
    for bad in ("pay", "nfl_x", "KC", "0.99", "future"):
        assert bad not in txt


def test_fold_boundaries():
    df = pd.DataFrame({"week": np.repeat(np.arange(25), 3)})
    for k in L.FOLDS:
        tr, te = L.fold_frames(df, k)
        assert tr["week"].max() < te["week"].min()
    tested = sorted(set().union(*[set(L.FOLDS[k][1]) for k in L.FOLDS]))
    assert tested == list(range(6, 25))


def test_labels_anchor_on_cost():
    assert L.label(0.05, 0.028) == "under"
    assert L.label(-0.05, 0.028) == "over"
    assert L.label(0.01, 0.028) == "fair"


def test_taker_fee_and_fill():
    assert C.fee_taker(0.5) == 0.18          # 0.07*10*0.25 = 0.175 -> 0.18
    assert C.fee_taker(0.95) == 0.04         # 0.0333 -> 0.04
    ts = np.array([10, 20, 30]) * C.NS
    px = np.array([0.40, 0.41, 0.42])
    assert C.taker_entry(ts, px, 10 * C.NS, win_s=300) == (20 * C.NS, 0.42)   # never the print at t
    assert C.taker_entry(ts, px, 30 * C.NS, win_s=300) is None                 # nothing at or after t + 1 s


class _Tok:
    pad_token_id = 0

    def encode(self, s, add_special_tokens=False):
        return {"under": [5], "fair": [6], "over": [7]}[s]

    def apply_chat_template(self, msgs, add_generation_prompt=True, tokenize=True):
        return [1] + [2 + (len(msgs[0]["content"]) % 3)] * (1 + len(msgs[0]["content"]) % 4)


def test_class_readout_deterministic():
    mx = pytest.importorskip("mlx.core")

    class _M:
        def __call__(self, x):
            b, n = x.shape
            base = mx.arange(10).astype(mx.float32)
            return mx.broadcast_to(base, (b, n, 10)) + x[..., None].astype(mx.float32) * 0.1

    tok = _Tok()
    ids = L.class_token_ids(tok)
    texts = ["aa", "bbbbb", "c"]
    a = L.class_probs(_M(), tok, texts, ids, batch=2)
    b = L.class_probs(_M(), tok, texts, ids, batch=3)
    assert np.allclose(a, b) and np.allclose(a.sum(1), 1.0)
