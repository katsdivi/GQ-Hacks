"""Synthetic tests for the Kalshi-leads-CME Stage 1 (no real data)."""
import numpy as np
import pandas as pd

import kalshi_cme_stage1 as S

NS = S.NS


def test_signal_uses_trailing_window_only():
    ts = np.array([0, 5, 9, 30], np.int64) * NS
    px = np.array([0.50, 0.51, 0.54, 0.90])
    assert S.signals(ts, px, 0, 100 * NS, 0.03) == [(9 * NS, 1)]   # the 30 s print is not used for the 9 s signal


def _book(rows):
    return S.Book(pd.DataFrame(rows, columns=["ts_event", "sequence", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]))


def test_book_state_is_backward_asof():
    b = _book([(0, 1, 0.40, 0.42, 5, 5), (3 * NS, 2, 0.45, 0.47, 5, 5)])
    assert b.at(3 * NS - 1)[1] == 0.42 and b.at(3 * NS)[1] == 0.47


def test_leg_enters_at_t_plus_L_and_charges_fees():
    b = _book([(0, 1, 0.40, 0.42, 5, 7), (2 * NS, 2, 0.40, 0.43, 5, 3), (60 * NS, 3, 0.50, 0.52, 5, 5)])
    r = {x["exit_mode"]: x for x in S.legs(b, 0, 1, 2, 1.0)}
    assert r["t60"]["entry"] == 0.43 and r["t60"]["qty"] == 3
    assert abs(r["t60"]["profit_pc"] - (0.50 - 0.43 - 0.02)) < 1e-12
    assert abs(r["settle"]["profit_pc"] - (1.0 - 0.43 - 0.01)) < 1e-12


def test_moved_mid_is_not_executable():
    b = _book([(0, 1, 0.40, 0.42, 5, 5), (1 * NS, 2, 0.42, 0.44, 5, 5)])
    assert not S.legs(b, 0, 1, 1, 1.0)[0]["executable"]


import kalshi_cme_maker as M


def test_maker_fill_strictly_through_only():
    tts = np.array([1, 2, 3], np.int64) * NS
    assert M.first_through(tts, np.array([0.40, 0.40, 0.40]), 0, 5, 0.40, 1) is None   # touching is not a fill
    assert M.first_through(tts, np.array([0.40, 0.39, 0.38]), 0, 5, 0.40, 1) == 2 * NS
    assert M.first_through(tts, np.array([0.41, 0.42, 0.40]), 0, 5, 0.41, -1) == 2 * NS
    assert M.first_through(tts, np.array([0.30]), 0, 0, 0.40, 1) is None                # outside W


def test_maker_no_print_at_or_before_t():
    tts = np.array([0, 10 * NS], np.int64)
    assert M.first_through(tts, np.array([0.30, 0.40]), 0, 30, 0.40, 1) is None         # the print at t is excluded
