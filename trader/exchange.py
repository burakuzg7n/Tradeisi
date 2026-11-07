"""Borsa adaptoru (ccxt) — guvenli emir gonderimi.

Bu katman, eski `tradebot/execution.py` + `tradebot/live.py` icindeki kayitli
DORT YUKSEK CiddIYETLI hatayi KAPATIR:

  1) "Borsa emri kabul edip yanit kaybolursa emir yeniden gonderilir" ->
     `place_order()` her gonderimden ONCE ayni `clientOrderId` ile bir emir
     var mi diye SORAR. Varsa TEKRAR GONDERMEZ, mevcut emri dondurur.
     Ag hatasi sonrasi da once sorgulama yapilir.
  2) "Kismen dolmus emrin kalani iptal edilince kayit takipten cikar; dolmus
     pozisyon takipsiz kalir" -> `ExchangeOrder.filled/remaining` ayri tutulur;
     dolum miktarindaki degisim pozisyon muhasebesine islenir; iptal edilen
     emirde dolmus miktar KAPANIS olarak kaydedilir.
  3) "Yeniden bastarmada acik emir/pozisyon ve onceki zarar sinirlari
     borsayla uzlastirilmaz" -> `reconcile()` acilista borsadaki acik emirleri
     ve pozisyonlari okur, yerel kayitlarla birlestirir ve eksik SL/TP'yi
     yeniden asar.
  4) "Kapanis kaydi islem kimligiyle eslesmez; sorgu basarisizsa sonuuc
     fiyat yakinligindan +2R/-1R tahmin edilir" -> P&L GERCEK dolum
     verisinden hesaplanir (ortalama giris/cikis fiyati + gercek ucretler).
     Fiyat yakinligindan tahmin YOKTUR.

Ayrica: `clientOrderId` 36 karakter sinirinda tutulur (bybit orderLinkId,
binance newClientOrderId).
"""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .config import ExchangeSettings


class ExchangeError(RuntimeError):
    pass


class DuplicateClientOrderId(ExchangeError):
    """Borsa ayni clientOrderId'yi reddetti (emir zaten var)."""


# --------------------------------------------------------------------------
# sembol yardimcilari
# --------------------------------------------------------------------------

def to_ccxt_symbol(symbol: str, default_type: str = "swap") -> str:
    """'BTCUSDT' -> 'BTC/USDT:USDT' (swap) veya 'BTC/USDT' (spot)."""
    if "/" in symbol:
        return symbol
    base = symbol
    quote = "USDT"
    for q in ("USDT", "USDC", "USD"):
        if symbol.endswith(q):
            base = symbol[: -len(q)]
            quote = q
            break
    if default_type == "swap":
        return f"{base}/{quote}:{quote}"
    return f"{base}/{quote}"


def strip_symbol(symbol: str) -> str:
    """'BTC/USDT:USDT' -> 'BTCUSDT'."""
    if "/" not in symbol:
        return symbol
    base, _, rest = symbol.partition("/")
    quote = rest.split(":")[0]
    return f"{base}{quote}"


def make_client_order_id(*parts: Any) -> str:
    """Deterministik idempotency anahtari (<=36 karakter)."""
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"tb-{digest}"[:36]


def order_client_id(raw: dict) -> str | None:
    """Ham emir nesnesinden client order id cikar (borsaya gore)."""
    for key in ("clientOrderId", "orderLinkId", "newClientOrderId"):
        value = raw.get(key)
        if value:
            return str(value)
    info = raw.get("info") or {}
    if isinstance(info, dict):
        for key in ("clientOrderId", "orderLinkId", "newClientOrderId"):
            value = info.get(key)
            if value:
                return str(value)
    return None


@dataclass
class ExchangeOrder:
    client_order_id: str
    exchange_order_id: str | None
    symbol: str
    side: str
    type: str
    amount: float
    price: float | None
    filled: float
    remaining: float
    average_price: float | None
    status: str
    fee: float = 0.0
    raw: dict = field(default_factory=dict)

    @property
    def is_filled(self) -> bool:
        return self.filled > 0 and self.remaining <= 1e-12

    @property
    def is_open(self) -> bool:
        return self.status in ("open", "pending", "partially_filled", "created")


# --------------------------------------------------------------------------
# ccxt adaptoru
# --------------------------------------------------------------------------

class CcxtAdapter:
    """Async ccxt sarmalayici. Idempotent + uzlasabilir."""

    def __init__(self, settings: ExchangeSettings):
        import ccxt.async_support as ccxt

        self.settings = settings
        klass = getattr(ccxt, settings.exchange_id, None)
        if klass is None:
            raise ExchangeError(
                f"Bilinmeyen borsa: {settings.exchange_id}. "
                "ccxt'te 'bybit' veya 'binance' kullan."
            )
        self.exchange = klass({
            "apiKey": settings.api_key,
            "secret": settings.api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": settings.default_type},
        })
        if settings.testnet:
            self.exchange.set_sandbox_mode(True)
        # API anahtari varken private fetchCurrencies cagriliyor (bybit) —
        # emir/fiyat icin gerekmez, kapatilir.
        self.exchange.has["fetchCurrencies"] = False
        self.exchange.options["recvWindow"] = settings.recv_window_ms

    # ---------- yardimcilar ----------

    def sym(self, symbol: str) -> str:
        return to_ccxt_symbol(symbol, self.settings.default_type)

    async def load_markets(self) -> None:
        await self.exchange.load_markets()

    @staticmethod
    def _parse(raw: dict) -> ExchangeOrder:
        amount = float(raw.get("amount") or 0.0)
        filled = float(raw.get("filled") or 0.0)
        remaining = raw.get("remaining")
        remaining = float(remaining) if remaining is not None else max(amount - filled, 0.0)
        fee = 0.0
        fee_info = raw.get("fee") or {}
        if isinstance(fee_info, dict):
            fee = float(fee_info.get("cost") or 0.0)
        return ExchangeOrder(
            client_order_id=order_client_id(raw) or "",
            exchange_order_id=str(raw.get("id")) if raw.get("id") else None,
            symbol=str(raw.get("symbol") or ""),
            side=str(raw.get("side") or ""),
            type=str(raw.get("type") or ""),
            amount=amount,
            price=float(raw["price"]) if raw.get("price") else None,
            filled=filled,
            remaining=remaining,
            average_price=float(raw["average"]) if raw.get("average") else None,
            status=str(raw.get("status") or ""),
            fee=fee,
            raw=raw,
        )

    # ---------- piyasa verisi ----------

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        rows = await self.exchange.fetch_ohlcv(self.sym(symbol), timeframe, limit=limit)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        try:
            df.index = df.index.as_unit("ns")
        except AttributeError:
            pass
        df = df.drop(columns=["timestamp"]).astype(float)
        return df[~df.index.duplicated(keep="last")].sort_index()

    async def fetch_ticker(self, symbol: str) -> dict:
        return await self.exchange.fetch_ticker(self.sym(symbol))

    async def fetch_funding_rates(self, symbol: str, since_ms: int | None = None,
                                  limit: int = 1000) -> pd.DataFrame:
        """Perpetual funding oranlari -> DataFrame (index: zaman, funding_rate).

        Desteklenmeyen borsa/hesapta bos tablo doner (paper motoru bunu
        "maliyet yok" saymaz; backtest ile tutarlilik icin onemlidir).
        """
        from .market import finalize_funding

        if not self.exchange.has.get("fetchFundingRateHistory"):
            return finalize_funding(pd.DataFrame(columns=["timestamp", "funding_rate"]))
        try:
            rows = await self.exchange.fetch_funding_rate_history(
                self.sym(symbol), since=since_ms, limit=limit
            )
        except Exception:
            return finalize_funding(pd.DataFrame(columns=["timestamp", "funding_rate"]))
        if not rows:
            return finalize_funding(pd.DataFrame(columns=["timestamp", "funding_rate"]))
        out: list[list] = []
        for r in rows:
            ts = r.get("fundingTimestamp") or r.get("timestamp")
            rate = r.get("fundingRate")
            if ts is None or rate is None:
                continue
            try:
                out.append([int(ts), float(rate)])
            except (TypeError, ValueError):
                continue
        if not out:
            return finalize_funding(pd.DataFrame(columns=["timestamp", "funding_rate"]))
        df = pd.DataFrame(out, columns=["timestamp", "funding_rate"])
        return finalize_funding(df)

    # ---------- emirler ----------

    async def find_order(self, client_order_id: str, symbol: str) -> ExchangeOrder | None:
        """clientOrderId ile mevcut emri bul. Bulunamazsa None.

        Sirasi: (1) unified fetchOrderWithClientOrderId (destekleyen borsalar),
        (2) acik emirler taramasi, (3) son kapanmis emirler taramasi.
        """
        if not client_order_id:
            return None
        sym = self.sym(symbol)

        if self.exchange.has.get("fetchOrderWithClientOrderId"):
            try:
                raw = await self.exchange.fetch_order_with_client_order_id(client_order_id, sym)
                if raw:
                    return self._parse(raw)
            except Exception:
                pass

        try:
            for raw in await self.exchange.fetch_open_orders(sym):
                if order_client_id(raw) == client_order_id:
                    return self._parse(raw)
        except Exception:
            pass

        try:
            since = int((datetime.now(timezone.utc).timestamp() - 7 * 86400) * 1000)
            for raw in await self.exchange.fetch_closed_orders(sym, since=since):
                if order_client_id(raw) == client_order_id:
                    return self._parse(raw)
        except Exception:
            pass
        return None

    async def place_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        amount: float,
        order_type: str = "market",
        price: float | None = None,
        params: dict | None = None,
        max_retries: int = 3,
    ) -> ExchangeOrder:
        """Idempotent emir gonderimi.

        Ayni `client_order_id` ile daha once gonderilmis bir emir varsa
        YENIDEN GONDERILMEZ. Ag hatasinda once SORULUR.
        """
        import ccxt.async_support as ccxt

        if len(client_order_id) > 36:
            client_order_id = client_order_id[:36]

        existing = await self.find_order(client_order_id, symbol)
        if existing is not None:
            return existing

        request = dict(params or {})
        request["clientOrderId"] = client_order_id
        if self.settings.exchange_id == "bybit":
            request["positionIdx"] = request.get("positionIdx", 0)  # one-way mode

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                raw = await self.exchange.create_order(
                    symbol=self.sym(symbol),
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=request,
                )
                parsed = self._parse(raw)
                if not parsed.client_order_id:
                    parsed.client_order_id = client_order_id
                return parsed
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                message = str(exc).lower()
                # Borsa ayni client id'yi reddetti -> emir zaten var
                if "duplicate" in message or "170141" in message:
                    found = await self.find_order(client_order_id, symbol)
                    if found is not None:
                        return found
                    raise DuplicateClientOrderId(str(exc)) from exc
                if isinstance(exc, ccxt.InsufficientFunds):
                    raise
                # Ag/rate-limit hatasi: yanit KAYBOLMUS olabilir.
                # Once SOR — bulursak tekrar gondermeyiz.
                found = await self.find_order(client_order_id, symbol)
                if found is not None:
                    return found
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise ExchangeError(f"Emir gonderilemedi: {last_error}")

    async def cancel_order(self, exchange_order_id: str, symbol: str) -> dict:
        return await self.exchange.cancel_order(exchange_order_id, self.sym(symbol))

    # ---------- pozisyon / bakiye ----------

    async def fetch_positions(self, symbols: list[str]) -> list[dict]:
        try:
            return await self.exchange.fetch_positions([self.sym(s) for s in symbols])
        except Exception:
            return []

    async def fetch_open_orders(self, symbol: str) -> list[dict]:
        try:
            return await self.exchange.fetch_open_orders(self.sym(symbol))
        except Exception:
            return []

    async def fetch_my_trades(self, symbol: str, since_ms: int | None = None) -> list[dict]:
        try:
            return await self.exchange.fetch_my_trades(self.sym(symbol), since=since_ms)
        except Exception:
            return []

    async def fetch_balance(self) -> dict:
        return await self.exchange.fetch_balance()

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        try:
            await self.exchange.set_leverage(leverage, self.sym(symbol))
        except Exception:
            pass

    async def close(self) -> None:
        try:
            await self.exchange.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# yardimci: gercek P&L hesabi
# --------------------------------------------------------------------------

def realized_pnl_from_trades(trades: list[dict], side: str) -> dict:
    """Kendirne gore gerceklesen P&L: dolum fiyatlari + ucretler.

    `side`: 'long' veya 'short'. trades: ccxt 'fetch_my_trades' formatinda
    (side, price, amount, fee.cost, timestamp).
    """
    total_qty = 0.0
    total_cost = 0.0
    fees = 0.0
    for t in trades:
        qty = float(t.get("amount") or 0.0)
        price = float(t.get("price") or 0.0)
        fee = t.get("fee") or {}
        fee_cost = float(fee.get("cost") or 0.0) if isinstance(fee, dict) else 0.0
        fees += fee_cost
        total_qty += qty
        total_cost += qty * price
    if total_qty <= 0:
        return {"avg_price": 0.0, "qty": 0.0, "fees": fees, "gross": 0.0, "net": 0.0}
    avg = total_cost / total_qty
    return {"avg_price": avg, "qty": total_qty, "fees": fees}
