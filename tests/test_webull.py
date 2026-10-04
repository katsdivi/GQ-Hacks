"""execution/webull.py with a mocked SDK client: no network, no keys, no SDK install needed."""
import json

import pytest

from execution import webull as W

T = "KXNCAAFGAME-25AUG30ALBYIOWA-IOWA"


class FakeRes:
    def __init__(self, code=200, body=None):
        self.status_code, self._b = code, body or {"ok": True}

    def json(self):
        return self._b


class FakeOrders:
    def __init__(self):
        self.calls = []

    def place_order(self, account, orders):
        self.calls.append(("place", account, orders))
        return FakeRes(200, {"client_order_id": orders[0]["client_order_id"]})

    def get_order_detail(self, account, coid):
        self.calls.append(("detail", account, coid))
        return FakeRes(200, {"status": "FILLED"})


class FakeClient:
    def __init__(self):
        self.order_v3 = FakeOrders()


def test_payload_fields_match_sdk_event_sample():
    p = W.build_payload(T, "IOWA", 10, 0.83, "abc")
    assert p == {"combo_type": "NORMAL", "client_order_id": "abc", "instrument_type": "EVENT", "market": "US",
                 "symbol": T, "order_type": "LIMIT", "entrust_type": "QTY", "time_in_force": "IOC",
                 "side": "BUY", "quantity": "10", "limit_price": "0.83", "event_outcome": "yes"}


def test_outcome_mapping():
    assert W.event_outcome("IOWA", "IOWA") == "yes"
    assert W.event_outcome("ALBY", "IOWA") == "no"
    assert W.build_payload("KXNCAAFGAME-25AUG30ALBYIOWA-ALBY", "IOWA", 1, 0.2, "x")["event_outcome"] == "no"


@pytest.mark.parametrize("qty,px", [(0, 0.5), (2.5, 0.5), (10, 1.0), (10, 0.0)])
def test_bad_orders_refused(qty, px):
    with pytest.raises(ValueError):
        W.build_payload(T, "IOWA", qty, px, "x")


def test_dry_run_logs_payload_and_never_fills(tmp_path):
    c = FakeClient()
    w = W.WebullPaper(dry_run=True, trade_client=c, log_path=tmp_path / "o.jsonl")
    r = w.place_paper_order(T, "IOWA", 10, 0.83)
    assert r["status"] == "dry_run_not_sent" and r["response"] is None and r["internal_id"].startswith("sl-")
    assert c.order_v3.calls == []                                   # nothing sent
    logged = json.loads((tmp_path / "o.jsonl").read_text())
    assert logged["payload"] == r["payload"]
    assert w.order_status(r["client_order_id"])["status"] == "dry_run_not_sent"
    assert "fill" not in json.dumps(logged).lower()


def test_client_order_ids_unique(tmp_path):
    w = W.WebullPaper(log_path=tmp_path / "o.jsonl")
    ids = {w.place_paper_order(T, "IOWA", 1, 0.5)["client_order_id"] for _ in range(200)}
    assert len(ids) == 200


def test_live_sandbox_send_uses_mock_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBULL_ACCOUNT_ID", "acct-test")
    c = FakeClient()
    w = W.WebullPaper(dry_run=False, trade_client=c, log_path=tmp_path / "o.jsonl")
    r = w.place_paper_order(T, "IOWA", 10, 0.83)
    kind, acct, orders = c.order_v3.calls[0]
    assert (kind, acct, orders) == ("place", "acct-test", [r["payload"]])
    assert r["status"] == "sent"
    assert "acct-test" not in (tmp_path / "o.jsonl").read_text()     # account id is not logged


def test_non_sandbox_host_refused():
    with pytest.raises(ValueError):
        W.WebullPaper(host="api.webull.com")


def test_missing_keys_raise_without_printing(monkeypatch, capsys):
    for k in W.ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="missing env vars"):
        W._sdk_trade_client(W.SANDBOX_HOST)
    assert capsys.readouterr().out == ""


def test_rate_limiter_30_per_60s():
    t = [0.0]
    slept = []
    lim = W.RateLimiter(clock=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    for _ in range(30):
        lim.acquire()
    assert slept == []
    lim.acquire()                               # 31st call inside the window must wait the full 60 s
    assert slept == [60.0] and t[0] == 60.0
    stamps = list(lim.calls)
    assert all(b - a >= 0 for a, b in zip(stamps, stamps[1:]))
    assert sum(1 for s in stamps if t[0] - s < 60) <= 30
