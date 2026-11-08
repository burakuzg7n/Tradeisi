"""Store (SQLite) ve protokol kapilari testleri."""
from __future__ import annotations

import json

import pytest

from trader.gates import check as gate_check
from trader.gates import load_gates, record_gate, save_gates
from trader.store import Store


def test_upsert_order_partial_update_preserves_fields(tmp_store):
    """KISMI guncelleme mevcut alanlari SILMEZ."""
    tmp_store.upsert_order({
        "client_order_id": "tb-1", "symbol": "BTCUSDT", "side": "buy",
        "kind": "market", "qty": 1.0, "status": "sending", "strategy": "x",
    })
    tmp_store.upsert_order({"client_order_id": "tb-1", "status": "open",
                            "filled_qty": 0.5})
    row = tmp_store.get_order("tb-1")
    assert row["symbol"] == "BTCUSDT"
    assert row["qty"] == 1.0
    assert row["status"] == "open"
    assert row["filled_qty"] == 0.5


def test_signals_roundtrip(tmp_store):
    payload = {"ts": "2024-01-01T00:00:00+00:00", "strategy": "s",
               "symbol": "BTCUSDT", "side": "long", "action": "open",
               "entry": 100.0, "stop": 95.0, "target": 110.0, "meta": {"a": 1}}
    sid = tmp_store.log_signal(payload, True)
    rows = tmp_store.recent_signals()
    assert len(rows) == 1
    assert rows[0]["id"] == sid
    assert rows[0]["accepted"] == 1
    assert json.loads(rows[0]["meta"])["a"] == 1


def test_trades_after_filters_by_timestamp(tmp_store):
    for i, ts in enumerate(["2024-01-01T00:00:00+00:00",
                            "2024-02-01T00:00:00+00:00",
                            "2024-03-01T00:00:00+00:00"]):
        tmp_store.log_trade({
            "strategy": "s", "symbol": "BTCUSDT", "side": "long",
            "entry": 100, "exit": 110, "qty": 1, "pnl_usd": 10, "pnl_r": 1,
            "entry_ts": ts, "exit_ts": ts, "exit_reason": "target", "mode": "paper",
        })
    newer = tmp_store.trades_after("2024-01-15T00:00:00+00:00")
    assert len(newer) == 2


def test_stats_uses_closed_trades(tmp_store):
    for pnl in (10.0, -5.0, 20.0):
        tmp_store.log_trade({
            "strategy": "s", "symbol": "BTCUSDT", "side": "long",
            "entry": 100, "exit": 110, "qty": 1, "pnl_usd": pnl, "pnl_r": 1,
            "entry_ts": "2024-01-01T00:00:00+00:00",
            "exit_ts": "2024-01-02T00:00:00+00:00", "exit_reason": "x",
            "mode": "paper",
        })
    stats = tmp_store.stats("s")
    assert stats["closed_trades"] == 3
    assert stats["win_rate"] == pytest.approx(2 / 3)
    assert stats["profit_factor"] == pytest.approx(30 / 5)
    assert stats["total_pnl_usd"] == pytest.approx(25.0)


def test_equity_curve_and_drawdown(tmp_store):
    for ts, eq in [("2024-01-01", 1000), ("2024-01-02", 1200),
                   ("2024-01-03", 900), ("2024-01-04", 1100)]:
        tmp_store.record_equity(ts, eq, eq, 0, 0, mode="paper", strategy="s")
    curve = tmp_store.equity_curve("s")
    assert len(curve) == 4
    stats = tmp_store.stats("s")
    # tepe 1200 -> dip 900 = %25
    assert stats["max_drawdown"] == pytest.approx(0.25)


def test_kv_roundtrip(tmp_store):
    tmp_store.set_kv("risk_state:x", {"kill": False})
    assert tmp_store.get_kv("risk_state:x") == {"kill": False}
    assert tmp_store.get_kv("yok", "varsayilan") == "varsayilan"


# --------------------------------------------------------------------------
# kapilar
# --------------------------------------------------------------------------

class _FakeStrategy:
    def __init__(self, name, research):
        self.name = name
        self.research_candidate = research


@pytest.fixture(autouse=True)
def clean_gates(tmp_path, monkeypatch):
    """Kaplari gecici dosyada tut (gercek out/gates.json'a dokunma)."""
    import trader.gates as gates_module

    path = tmp_path / "gates.json"
    monkeypatch.setattr(gates_module, "GATE_FILE", path)
    yield


def test_non_research_strategy_blocked_from_live():
    strat = _FakeStrategy("sistem_testi", False)
    assert gate_check(strat, "live").allowed is False
    assert gate_check(strat, "testnet").allowed is True
    assert gate_check(strat, "paper").allowed is True


def test_research_strategy_testnet_requires_gates():
    strat = _FakeStrategy("sepet_momentum", True)
    decision = gate_check(strat, "testnet")
    assert decision.allowed is False
    assert "hold-out" in decision.reason


def test_research_strategy_testnet_allowed_after_gates():
    strat = _FakeStrategy("sepet_momentum", True)
    record_gate("sepet_momentum", "backtest", True, {"pf": 1.5})
    record_gate("sepet_momentum", "holdout", True, {"pf": 1.2})
    assert gate_check(strat, "testnet").allowed is True
    # canli icin testnet kapisi da gerekir
    assert gate_check(strat, "live").allowed is False
    record_gate("sepet_momentum", "testnet", True, {"trades": 120})
    assert gate_check(strat, "live").allowed is True


def test_failed_gate_does_not_unlock():
    strat = _FakeStrategy("sepet_momentum", True)
    record_gate("sepet_momentum", "backtest", False, {"pf": 0.9})
    record_gate("sepet_momentum", "holdout", False, {"pf": 0.8})
    assert gate_check(strat, "testnet").allowed is False
    assert gate_check(strat, "live").allowed is False


def test_paper_always_allowed():
    strat = _FakeStrategy("sepet_momentum", True)
    assert gate_check(strat, "paper").allowed is True
