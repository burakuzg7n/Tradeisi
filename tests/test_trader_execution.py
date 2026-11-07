"""Yurutme katmani regresyon testleri.

Bunlar `docs/KARAR_NOTU_C_2026-11-02.md` §4'te kayitli DORT yuksek
ciddiyetli hatayi kapatir:

  1) Cift emir (yanit kayboldu)          -> test_duplicate_order_prevented
  2) Takipsiz kismi dolum                -> test_partial_fill_not_lost
  3) Yeniden baslatmada uzlastirma yok  -> test_reconcile_adopts_open_state
  4) P&L fiyat yakinligindan tahmin      -> test_pnl_from_real_fills_not_guess
"""
from __future__ import annotations

import asyncio

import pytest

from trader.config import ExchangeSettings, RiskSettings
from trader.exchange import CcxtAdapter, make_client_order_id
from trader.live import LiveRunner
from trader.strategy import Panel, Signal


# --------------------------------------------------------------------------
# sahte borsa
# --------------------------------------------------------------------------

class FakeCcxt:
    """Async sahte ccxt exchange."""

    def __init__(self):
        self.has = {"fetchOrderWithClientOrderId": False,
                    "fetchCurrencies": False}
        self.orders: dict[str, dict] = {}
        self.positions: list[dict] = []
        self.trades: list[dict] = []
        self.created: list[str] = []
        self.lose_response_once = False
        self.fail_create = False

    async def create_order(self, symbol, type, side, amount, price, params):
        cid = params.get("clientOrderId")
        if self.fail_create:
            raise RuntimeError("exchange down")
        if cid and any(o.get("clientOrderId") == cid for o in self.orders.values()):
            raise RuntimeError("Duplicate clientOrderId.")
        oid = f"ord-{len(self.orders) + 1}"
        raw = {
            "id": oid, "clientOrderId": cid, "symbol": symbol, "side": side,
            "type": type, "amount": amount, "price": price, "filled": 0.0,
            "remaining": amount, "status": "open", "average": None, "fee": None,
        }
        self.orders[oid] = raw
        self.created.append(cid or "")
        if self.lose_response_once:
            self.lose_response_once = False
            raise ConnectionError("response lost after accept")
        return raw

    async def fetch_open_orders(self, symbol=None):
        return [o for o in self.orders.values() if o["status"] == "open"]

    async def fetch_closed_orders(self, symbol=None, since=None):
        return [o for o in self.orders.values() if o["status"] != "open"]

    async def fetch_order(self, order_id, symbol=None):
        return self.orders.get(order_id)

    async def fetch_positions(self, symbols=None):
        return list(self.positions)

    async def fetch_my_trades(self, symbol=None, since=None):
        return list(self.trades)

    async def load_markets(self):
        return {}

    async def close(self):
        return None


def make_adapter(fake: FakeCcxt) -> CcxtAdapter:
    adapter = CcxtAdapter.__new__(CcxtAdapter)
    adapter.settings = ExchangeSettings(exchange_id="bybit", api_key="",
                                        api_secret="", testnet=True)
    adapter.exchange = fake
    return adapter


class DummyStrategy:
    name = "test_dummy"
    research_candidate = False
    timeframe = "15m"

    def generate(self, panel: Panel, ts):
        return []


def make_runner(adapter, store, symbols=("BTCUSDT",)):
    return LiveRunner(
        strategy=DummyStrategy(),
        symbols=list(symbols),
        adapter=adapter,
        store=store,
        settings=adapter.settings,
        risk_settings=RiskSettings(max_drawdown_pct=0.99),
        initial_equity=10_000.0,
        mode="testnet",
    )


# --------------------------------------------------------------------------
# 1) cift emir
# --------------------------------------------------------------------------

def test_duplicate_order_prevented(tmp_store):
    """Yanit kayboldu -> ayni clientOrderId ile IKINCI emir gonderilmez.

    1. gonderim: borsa emri kabul eder, CEVAP KAYBOLUR.
       Adaptor hata yakalayip once SORAR; emri bulur ve aynen onu dondurur.
    2. tekrar deneme: emir zaten var -> yeniden GONDERILMEZ.
    """
    fake = FakeCcxt()
    adapter = make_adapter(fake)

    async def scenario():
        fake.lose_response_once = True
        order = await adapter.place_order(
            client_order_id="tb-abc123", symbol="BTCUSDT", side="buy",
            amount=0.1, order_type="market", price=None, params={},
        )
        # borsada emir KABUL edilmis, cevap kaybolmus -> adaptor emri buldu
        assert len(fake.orders) == 1
        assert order.exchange_order_id is not None

        # ayni client id ile tekrar dene -> cift emir OLUSMAZ
        await adapter.place_order(
            client_order_id="tb-abc123", symbol="BTCUSDT", side="buy",
            amount=0.1, order_type="market", price=None, params={},
        )
        assert len(fake.orders) == 1

    asyncio.run(scenario())
    # create_order sadece BIR kez cagrildi
    assert len(fake.created) == 1


def test_client_order_id_is_deterministic_and_short():
    a = make_client_order_id("x", "BTCUSDT", "buy", 0.5)
    b = make_client_order_id("x", "BTCUSDT", "buy", 0.5)
    c = make_client_order_id("x", "BTCUSDT", "buy", 0.6)
    assert a == b
    assert a != c
    assert len(a) <= 36      # bybit orderLinkId / binance newClientOrderId siniri


# --------------------------------------------------------------------------
# 3) uzlastirma
# --------------------------------------------------------------------------

def test_reconcile_adopts_open_state(tmp_store):
    """Yeniden baslatmada borsadaki acik emir ve pozisyon bulunur."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    fake.orders["ord-1"] = {
        "id": "ord-1", "clientOrderId": "tb-restart-1", "symbol": "BTC/USDT:USDT",
        "side": "buy", "type": "market", "amount": 1.0, "price": None,
        "filled": 0.4, "remaining": 0.6, "status": "open", "average": 60000.0,
        "fee": None,
    }
    fake.positions = [{
        "symbol": "BTC/USDT:USDT", "side": "long", "contracts": 0.4,
        "amount": 0.4, "entryPrice": 60000.0, "markPrice": 60500.0,
    }]

    result = asyncio.run(runner.reconcile())
    assert result["orders"] == 1
    assert result["positions"] == 1
    assert "tb-restart-1" in runner.orders
    assert runner.orders["tb-restart-1"].filled_qty == 0.4
    assert "BTCUSDT" in runner.positions
    assert runner.positions["BTCUSDT"].qty == 0.4
    assert runner.positions["BTCUSDT"].reconciled is True


def test_reconcile_ignores_foreign_orders(tmp_store):
    """Bizim olmayan emirler (kullanicinin elle girdigi) dokunulmaz."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)
    fake.orders["ord-x"] = {
        "id": "ord-x", "clientOrderId": "manual-1", "symbol": "BTC/USDT:USDT",
        "side": "buy", "type": "market", "amount": 1.0, "price": None,
        "filled": 0.0, "remaining": 1.0, "status": "open", "average": None,
        "fee": None,
    }
    result = asyncio.run(runner.reconcile())
    assert result["orders"] == 0
    assert runner.orders == {}


# --------------------------------------------------------------------------
# 4) gercek P&L
# --------------------------------------------------------------------------

def test_pnl_from_real_fills_not_guess(tmp_store):
    """P&L gercek dolum fiyatindan hesaplanir; fiyat yakinligindan TAHMIN yok."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    from trader.live import TrackedPosition
    from datetime import datetime, timezone

    pos = TrackedPosition(symbol="BTCUSDT", side="long", qty=2.0,
                          entry_price=100.0, stop=95.0, target=110.0,
                          risk_amount=10.0,
                          opened_at=datetime.now(timezone.utc))
    # gercek kapanis dolumu: 105'te 2 adet, ucret 1.0
    fake.trades = [{
        "side": "sell", "amount": 2.0, "price": 105.0,
        "fee": {"cost": 1.0}, "timestamp": 1700000000000,
    }]
    pnl_usd, pnl_r, exit_price, fees = asyncio.run(runner._pnl_from_trades(pos, "closed"))
    assert exit_price == pytest.approx(105.0)
    assert fees == pytest.approx(1.0)
    # (105-100)*2 - 1.0 ucret = 9.0
    assert pnl_usd == pytest.approx(9.0)
    assert pnl_r == pytest.approx(0.9)


def test_pnl_does_not_guess_when_fills_missing(tmp_store):
    """Dolum yoksa P&L 0'dir — -1R/+2R tahmini YAPILMAZ."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    from trader.live import TrackedPosition
    from datetime import datetime, timezone

    pos = TrackedPosition(symbol="BTCUSDT", side="long", qty=2.0,
                          entry_price=100.0, stop=95.0, target=110.0,
                          risk_amount=10.0,
                          opened_at=datetime.now(timezone.utc))
    fake.trades = []
    pnl_usd, pnl_r, exit_price, fees = asyncio.run(runner._pnl_from_trades(pos, "closed"))
    assert pnl_usd == 0.0
    assert pnl_r == 0.0
    assert exit_price == pytest.approx(100.0)


# --------------------------------------------------------------------------
# 2) kismi dolum
# --------------------------------------------------------------------------

def test_partial_fill_not_lost(tmp_store):
    """Kismen dolmus emir iptal edilince dolmus miktar KAYBOLMAZ.

    Iptal edilen emir icin kayit kapanir, ama dolmus kisim POZISYON olarak
    takipte kalir ve sonra normal akista gercek P&L ile kapanir.
    """
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    from trader.live import TrackedOrder
    from datetime import datetime, timezone

    tracked = TrackedOrder(
        client_order_id="tb-partial-1", exchange_order_id="ord-1",
        symbol="BTCUSDT", side="buy", qty=1.0, filled_qty=0.0,
        avg_price=100.0, price=None, status="pending",
        created_at=datetime.now(timezone.utc), strategy="test_dummy",
    )
    runner.orders[tracked.client_order_id] = tracked
    # borsada emir yaridan dolmus ve iptal edilmis
    fake.orders["ord-1"] = {
        "id": "ord-1", "clientOrderId": "tb-partial-1", "symbol": "BTC/USDT:USDT",
        "side": "buy", "type": "market", "amount": 1.0, "price": None,
        "filled": 0.5, "remaining": 0.5, "status": "canceled", "average": 100.0,
        "fee": None,
    }
    # dolmus kisim hâlâ borsada pozisyon olarak duruyor
    fake.positions = [{
        "symbol": "BTC/USDT:USDT", "side": "long", "contracts": 0.5,
        "amount": 0.5, "entryPrice": 100.0, "markPrice": 100.0,
    }]
    fake.trades = [{
        "side": "buy", "amount": 0.5, "price": 100.0,
        "fee": {"cost": 0.1}, "timestamp": 1700000000000,
    }]

    asyncio.run(runner.manage())

    # emir iptal edildi
    assert runner.orders["tb-partial-1"].status == "cancelled"
    # dolmus pozisyon KAYBOLMADI
    assert "BTCUSDT" in runner.positions
    assert runner.positions["BTCUSDT"].qty == pytest.approx(0.5)
    # pozisyon hâlâ acik -> islem kaydi yok
    assert len(tmp_store.recent_trades()) == 0


def test_partial_fill_position_closes_with_real_pnl(tmp_store):
    """Kismen dolmus pozisyon sonradan kapanirsa gercek P&L ile kaydedilir."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    from trader.live import TrackedOrder, TrackedPosition
    from datetime import datetime, timezone

    tracked = TrackedOrder(
        client_order_id="tb-partial-3", exchange_order_id="ord-3",
        symbol="BTCUSDT", side="buy", qty=1.0, filled_qty=0.5,
        avg_price=100.0, status="cancelled",
        created_at=datetime.now(timezone.utc), strategy="test_dummy",
    )
    runner.orders[tracked.client_order_id] = tracked
    runner.positions["BTCUSDT"] = TrackedPosition(
        symbol="BTCUSDT", side="long", qty=0.5, entry_price=100.0,
        stop=95.0, target=110.0, risk_amount=2.5,
        opened_at=datetime.now(timezone.utc), strategy="test_dummy",
    )
    fake.orders["ord-3"] = {
        "id": "ord-3", "clientOrderId": "tb-partial-3", "symbol": "BTC/USDT:USDT",
        "side": "buy", "type": "market", "amount": 1.0, "price": None,
        "filled": 0.5, "remaining": 0.5, "status": "canceled", "average": 100.0,
        "fee": None,
    }
    fake.positions = []   # borsada pozisyon kapandi
    fake.trades = [
        {"side": "buy", "amount": 0.5, "price": 100.0,
         "fee": {"cost": 0.1}, "timestamp": 1700000000000},
        {"side": "sell", "amount": 0.5, "price": 105.0,
         "fee": {"cost": 0.1}, "timestamp": 1700000100000},
    ]

    asyncio.run(runner.manage())

    trades = tmp_store.recent_trades()
    assert len(trades) == 1
    assert trades[0]["qty"] == pytest.approx(0.5)
    assert trades[0]["exit"] == pytest.approx(105.0)
    # (105-100)*0.5 = 2.5 brut; giris uceti 0.1 + cikis uceti 0.1 -> net 2.3
    # (giris uceti burada sayilir: risk motoru bakiyesi giriste guncellenmez,
    #  P&L tam kapandiginda tek seferde eklenir -> cift sayim olmaz)
    assert trades[0]["pnl_usd"] == pytest.approx(2.3)
    assert "BTCUSDT" not in runner.positions


def test_partial_fill_updates_position(tmp_store):
    """Kismi dolum pozisyon miktarini dogru gunceller."""
    fake = FakeCcxt()
    adapter = make_adapter(fake)
    runner = make_runner(adapter, tmp_store)

    from trader.live import TrackedOrder
    from datetime import datetime, timezone

    tracked = TrackedOrder(
        client_order_id="tb-partial-2", exchange_order_id="ord-2",
        symbol="BTCUSDT", side="buy", qty=1.0, filled_qty=0.0,
        avg_price=0.0, status="pending",
        created_at=datetime.now(timezone.utc), strategy="test_dummy",
    )
    runner.orders[tracked.client_order_id] = tracked
    fake.orders["ord-2"] = {
        "id": "ord-2", "clientOrderId": "tb-partial-2", "symbol": "BTC/USDT:USDT",
        "side": "buy", "type": "market", "amount": 1.0, "price": None,
        "filled": 0.3, "remaining": 0.7, "status": "open", "average": 100.0,
        "fee": None,
    }
    fake.positions = [{
        "symbol": "BTC/USDT:USDT", "side": "long", "contracts": 0.3,
        "amount": 0.3, "entryPrice": 100.0, "markPrice": 100.0,
    }]
    asyncio.run(runner.manage())
    assert "BTCUSDT" in runner.positions
    assert runner.positions["BTCUSDT"].qty == pytest.approx(0.3)
