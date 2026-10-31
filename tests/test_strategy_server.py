import numpy as np
import pandas as pd
import pytest

from tests.conftest import make_df
from tradebot.config import StrategyParams
from tradebot.sessions import in_killzone, session_name
from tradebot.strategy import generate_orders


# ---------- Sessions ----------

def test_session_priority_london_kz_not_asian():
    """07:00-09:00 UTC hem Asian(0-9) hem London icinde -> London kazanmali."""
    ts = pd.Timestamp("2026-07-06 08:00", tz="UTC")
    assert session_name(ts) == "london"
    assert in_killzone(ts)


def test_overlap_priority():
    ts = pd.Timestamp("2026-07-06 14:00", tz="UTC")
    assert session_name(ts) == "london_ny_overlap"
    assert in_killzone(ts)


def test_off_hours():
    ts = pd.Timestamp("2026-07-06 23:00", tz="UTC")
    assert session_name(ts) == "off_hours"
    assert not in_killzone(ts)


# ---------- Strateji ----------

def _bull_scenario_df():
    """Sentetik senaryo: swing low kur -> sweep -> bullish FVG.

    i=5'te dip (pivot, lb=3 -> i=8'de kesin), i=10 sweep, i=12 FVG 3. mumu.
    start 06:00 -> i=12 bari 09:00'da = London KZ [7,10) icinde.
    """
    bars = []
    prices = [100, 99.5, 99, 98, 97, 95, 97, 98, 98.5, 99]  # i=5 dip (low 94.7)
    for p in prices:
        bars.append((p + 0.2, p + 0.5, p - 0.3, p))
    bars.append((99, 96.2, 94, 96))        # i=10: sweep (low 94 < 94.7, close 96 >)
    bars.append((96, 98.5, 95.8, 98.3))    # i=11: momentum
    bars.append((98.3, 100.5, 97.0, 100))  # i=12: low 97 > 96.2 -> FVG [96.2, 97]
    bars += [(100, 100.5, 99.5, 100)] * 5
    return make_df(bars, start="2026-07-06 06:00")


def _bull_htf():
    """Bullish bias veren 4H serisi.

    Swing high olusmali (i=7 tepe, high=100) ve sonra KIRILMALI ki
    detect_structure trend=1 uretsin - monoton seri pivot uretmez.
    """
    seq = [100, 99, 98, 97, 96, 95, 97, 99, 98, 96.5, 96, 100, 102, 104, 106, 108]
    bars = [(p, p + 1, p - 1, p) for p in seq]
    return make_df(bars, start="2026-07-01", freq="4h")


def test_strategy_generates_long_after_sweep_and_fvg():
    ltf = _bull_scenario_df()
    htf = _bull_htf()
    params = StrategyParams(
        ltf_pivot=3, fvg_min_size_pct=0.0001, use_session_filter=True
    )
    orders = generate_orders(ltf, htf, params)
    assert len(orders) == 1
    o = orders[0]
    assert o.side == "long"
    assert o.entry == pytest.approx((96.2 + 97.0) / 2, abs=0.01)
    assert o.stop < 94  # sweep dibinin alti
    assert (o.target - o.entry) == pytest.approx(2 * (o.entry - o.stop), rel=0.01)
    assert o.meta["session"] in ("london", "london_ny_overlap")


def test_strategy_rejects_outside_killzone():
    ltf = _bull_scenario_df()
    ltf.index = pd.date_range(
        "2026-07-06 22:00", periods=len(ltf), freq="15min", tz="UTC"
    )
    htf = _bull_htf()
    params = StrategyParams(
        ltf_pivot=3, fvg_min_size_pct=0.0001, use_session_filter=True
    )
    assert len(generate_orders(ltf, htf, params)) == 0


def test_strategy_no_orders_when_bias_neutral():
    ltf = _bull_scenario_df()
    htf = make_df([(100, 100.5, 99.5, 100)] * 16, freq="4h")  # yapi yok -> bias 0
    params = StrategyParams(
        ltf_pivot=3, fvg_min_size_pct=0.0001, use_session_filter=False
    )
    assert len(generate_orders(ltf, htf, params)) == 0


# ---------- Webhook sunucusu ----------

def test_webhook_auth_and_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("JOURNAL_DB", str(tmp_path / "j.db"))
    monkeypatch.setenv("PAPER_MODE", "1")

    import importlib
    import tradebot.server as server
    importlib.reload(server)

    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        payload = {
            "symbol": "BTCUSDT",
            "direction": "long",
            "entry": 50000,
            "stop_loss": 49500,
            "take_profit": 51000,
        }
        # Token yok -> 401
        assert client.post("/webhook", json=payload).status_code == 401
        # Dogru token -> 200
        r = client.post(
            "/webhook",
            json=payload,
            headers={"Authorization": "Bearer test-secret"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "queued"
        # Gecersiz stop (long'da stop > entry) -> 422
        bad = dict(payload, stop_loss=50500)
        r = client.post(
            "/webhook",
            json=bad,
            headers={"Authorization": "Bearer test-secret"},
        )
        assert r.status_code == 422
        # Health
        assert client.get("/health").json()["status"] == "ok"


def test_volume_filter_rejects_low_volume_sweep():
    """Hacim filtresi acikken dusuk hacimli sweep setup uretmemeli."""
    ltf = _bull_scenario_df()
    ltf["volume"] = 100.0  # sweep bari dahil her yer ayni hacim -> spike yok
    htf = _bull_htf()
    params = StrategyParams(
        ltf_pivot=3, fvg_min_size_pct=0.0001, use_session_filter=False,
        use_volume_filter=True, vol_spike_mult=1.5, vol_ma_window=5,
    )
    assert len(generate_orders(ltf, htf, params)) == 0

    # Ayni senaryo, sweep barinda 3x hacim -> setup uretilmeli
    ltf2 = _bull_scenario_df()
    ltf2["volume"] = 100.0
    ltf2.iloc[10, ltf2.columns.get_loc("volume")] = 300.0  # sweep bari i=10
    assert len(generate_orders(ltf2, htf, params)) == 1


# ---------- Telegram bildirimi ----------

def test_notifier_disabled_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    import asyncio
    from tradebot.notify import TelegramNotifier
    n = TelegramNotifier()
    assert not n.enabled
    # Token yokken send False doner, exception yukseltmez
    assert asyncio.get_event_loop().run_until_complete(n.send("test")) is False


def test_notify_message_formats():
    from tradebot.notify import fmt_signal, fmt_trade_closed, fmt_kill_switch
    payload = {"symbol": "BTCUSDT", "direction": "long", "entry": 50000,
               "stop_loss": 49500, "take_profit": 51000, "setup": "ssl_sweep_fvg"}
    ok_msg = fmt_signal(payload, True)
    assert "KABUL" in ok_msg and "BTCUSDT" in ok_msg
    red_msg = fmt_signal(payload, False, "killzone disi")
    assert "RED" in red_msg and "killzone disi" in red_msg
    closed = fmt_trade_closed("BTCUSDT", 2.0, 10.0, "target")
    assert "+2.00R" in closed
    ks = fmt_kill_switch("daily_loss_limit", -3.0, -5.0)
    assert "KILL SWITCH" in ks


# ---------- Live runner (ag gerektirmeyen birim testler) ----------

def test_live_helpers():
    from tradebot.live import ohlcv_to_df, drop_forming_bar, pick_new_orders, next_bar_close
    from tradebot.strategy import PendingOrder
    from datetime import datetime, timezone

    rows = [
        [1736208000000, 100, 101, 99, 100.5, 10],
        [1736208900000, 100.5, 102, 100, 101, 12],
        [1736209800000, 101, 101.5, 100.5, 101.2, 8],  # forming
    ]
    df = ohlcv_to_df(rows)
    assert len(df) == 3 and df.index.tz is not None
    closed = drop_forming_bar(df)
    assert len(closed) == 2  # son bar atildi

    def mk(idx):
        return PendingOrder(side="long", entry=100, stop=99, target=102,
                            created_idx=idx, expiry_idx=idx+32, cancel_beyond=98)
    orders = [mk(5), mk(9), mk(10)]
    new = pick_new_orders(orders, last_idx=10)
    assert len(new) == 1 and new[0].created_idx == 10  # sadece son bar

    # 12:07 -> bir sonraki 15m kapanisi 12:15 (+20s tampon)
    now = datetime(2026, 7, 6, 12, 7, tzinfo=timezone.utc)
    nb = next_bar_close(now)
    assert nb.hour == 12 and nb.minute == 15 and nb.second == 20


def test_load_env(tmp_path, monkeypatch):
    from tradebot.config import load_env
    monkeypatch.delenv("TEST_ENV_KEY_X", raising=False)
    envfile = tmp_path / ".env"
    envfile.write_text('TEST_ENV_KEY_X=abc\n# yorum\nBOS_SATIR=\n', encoding='utf-8')
    import os
    load_env(str(envfile))
    assert os.environ.get("TEST_ENV_KEY_X") == "abc"
