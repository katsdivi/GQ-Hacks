"""Tests for the SYNTHETIC simulator (scripts/mm_v4_sim.py); not market evidence."""
import numpy as np

import mm_v4_sim as S
import posthoc_mm_v4 as M


def test_seed_reproduces():
    p = S.load_params()
    g1, g2 = S.game(p, np.random.default_rng(7)), S.game(p, np.random.default_rng(7))
    assert np.array_equal(g1["tts"], g2["tts"]) and np.array_equal(g1["book"].bid, g2["book"].bid)
    assert g1["payout"] == g2["payout"]


def test_adapter_no_lookahead():
    """Changing the synthetic path after time T never changes fills before T."""
    p = S.load_params()
    g = S.game(p, np.random.default_rng(11))
    T = g["ko"] + 2 * 3600 * M.NS
    f_full = S.run_maker(g, 0.0)
    b = g["book"]
    keep = b.ts < T
    tk = g["tts"] < T
    g2 = dict(g)
    rng = np.random.default_rng(99)
    g2["book"] = M.Book(np.concatenate([b.ts[keep], b.ts[~keep]]),
                        np.concatenate([b.bid[keep], rng.uniform(0.1, 0.5, (~keep).sum()).round(2)]),
                        np.concatenate([b.ask[keep], rng.uniform(0.5, 0.9, (~keep).sum()).round(2)]),
                        np.concatenate([b.bsz[keep], b.bsz[~keep]]), np.concatenate([b.asz[keep], b.asz[~keep]]))
    g2["tpx"] = np.where(tk, g["tpx"], rng.uniform(0.05, 0.95, len(g["tpx"])).round(2))
    f_alt = S.run_maker(g2, 0.0)
    a = f_full[f_full["t"] < T][["t", "side", "price", "qty"]].reset_index(drop=True)
    c = f_alt[f_alt["t"] < T][["t", "side", "price", "qty"]].reset_index(drop=True)
    assert a.equals(c)


def test_calibration_readouts():
    p = S.load_params()
    rng = np.random.default_rng(20261011)
    sp1, w, ntr, mins, thr, mv = 0.0, 0.0, 0, 0.0, [], []
    for _ in range(60):
        g = S.game(p, rng)
        b = g["book"]
        dur = np.diff(np.append(b.ts, g["hi"])) / M.NS
        sp = np.round((b.ask - b.bid) * 100)
        sp1 += dur[sp == 1].sum()
        w += dur.sum()
        ntr += len(g["tts"])
        mins += (g["hi"] - g["lo"]) / M.NS / 60
        thr += list(g["thr"])
        m = g["mid"]
        s = g["tsec"]
        e = np.minimum(s + 60, len(m) - 1)
        mv += list(g["tdir"] * (m[e] - m[s]) * 100)
    assert abs(sp1 / w - p.spread_probs[0]) < 0.12          # floor/clip shifts some mass; within tolerance
    assert abs(ntr / mins - p.trades_per_min) < 0.1
    assert abs(np.mean(thr) - p.through) < 0.02
    assert abs(np.mean(mv) - p.informed * p.d_inf * 100) < 0.25
