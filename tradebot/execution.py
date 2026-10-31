"""Execution katmanı: Paper (varsayılan) + CCXT (borsa-bağımsız).

Canlıya geçiş SADECE roadmap kriterleri sağlanınca:
PF > 1.3, 300+ paper trade, 100+ testnet trade, DD < %15.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .config import ExchangeConfig


@dataclass
class OrderResult:
    status: str              # "ok" | "error" | "retry"
    order_id: str | None = None
    reason: str | None = None
    detail: str | None = None


class PaperExecutor:
    """Emirleri gerçek borsaya göndermez; anında 'dolu' kabul eder.

    Paper trading aşamasında fiyat takibi TradingView alert'leri /
    ayrı bir fiyat izleyici ile yapılır; burada sadece kayıt semantiği var.
    """

    async def place_order(self, **kwargs) -> OrderResult:
        return OrderResult(status="ok", order_id=f"paper-{id(kwargs)}")

    async def close(self) -> None:
        return None


class CcxtExecutor:
    """CCXT async — exchange_id config'den gelir (bybit/binance/...).

    Borsaya özel parametreler _exchange_params içinde izole edildi.
    """

    def __init__(self, cfg: ExchangeConfig):
        import ccxt.async_support as ccxt  # lazy import

        klass = getattr(ccxt, cfg.exchange_id)
        self.exchange = klass(
            {
                "apiKey": cfg.api_key,
                "secret": cfg.api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        if cfg.testnet:
            self.exchange.set_sandbox_mode(True)
        # load_markets, API anahtarı varken private fetchCurrencies çağırır
        # (bybit: /v5/asset/coin/query-info) — testnette gereksiz ve sorunlu.
        # Piyasa verisi + emir için gerekmez → kapat.
        self.exchange.has["fetchCurrencies"] = False
        # Windows saat kayması imza hatası yaratmasın
        self.exchange.options["recvWindow"] = 20000
        self.exchange_id = cfg.exchange_id

    def _exchange_params(self, stop_loss: float, take_profit: float) -> dict:
        if self.exchange_id == "bybit":
            return {
                "stopLoss": {"triggerPrice": stop_loss, "orderType": "Market"},
                "takeProfit": {"triggerPrice": take_profit, "orderType": "Limit"},
                "positionIdx": 0,  # one-way mode
            }
        # ccxt unified fallback (binance vb.)
        return {"stopLossPrice": stop_loss, "takeProfitPrice": take_profit}

    async def place_order(
        self,
        symbol: str,
        direction: str,
        position_size: float,
        entry: float,
        stop_loss: float,
        take_profit: float,
        order_type: str = "limit",
        max_retries: int = 3,
    ) -> OrderResult:
        import ccxt.async_support as ccxt

        side = "buy" if direction == "long" else "sell"
        params = self._exchange_params(stop_loss, take_profit)

        for attempt in range(max_retries):
            try:
                order = await self.exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=position_size,
                    price=entry if order_type == "limit" else None,
                    params=params,
                )
                return OrderResult(status="ok", order_id=order["id"])
            except ccxt.InsufficientFunds as e:
                return OrderResult(
                    status="error", reason="insufficient_funds", detail=str(e)
                )
            except (ccxt.RateLimitExceeded, ccxt.NetworkError) as e:
                if attempt == max_retries - 1:
                    return OrderResult(status="error", reason="network", detail=str(e))
                await asyncio.sleep(2**attempt)  # 1s, 2s, 4s
            except Exception as e:  # bilinmeyen hata: retry etme, logla
                return OrderResult(status="error", reason="unknown", detail=str(e))
        return OrderResult(status="error", reason="max_retries")

    async def fetch_order_status(self, order_id: str, symbol: str) -> dict:
        order = await self.exchange.fetch_order(order_id, symbol)
        return {
            "status": order.get("status"),
            "filled": order.get("filled"),
            "remaining": order.get("remaining"),
        }

    async def close(self) -> None:
        await self.exchange.close()
