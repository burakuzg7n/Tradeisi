"""Demo/testnet canlı çalıştırıcı — TradingView'sız yol.

Her 15M bar kapanışında:
  1. ccxt ile son mumları çek (kapanmamış bar ATILIR — repaint imkânsız)
  2. Backtest'tekiyle BİREBİR AYNI strateji kodunu çalıştır
  3. Yeni setup varsa: risk kontrolü → limit emir + SL/TP → journal + Telegram
  4. Bekleyen emirlerin/pozisyonların yaşam döngüsünü yönet

Aynı kod backtest'te ve canlıda çalıştığı için "backtest'te vardı canlıda yok"
sorunu yapısal olarak imkânsız.

Çalıştırma (kendi makinende):
    python scripts/live_runner.py            # .env'den okur (testnet önerilir)
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import ExchangeConfig, RiskParams, StrategyParams, load_env
from .execution import CcxtExecutor
from .journal import Journal
from .notify import (
    TelegramNotifier,
    fmt_kill_switch,
    fmt_signal,
    fmt_trade_closed,
    fmt_trade_opened,
)
from .risk import RiskEngine
from .strategy import PendingOrder, generate_orders

LTF_TF = "15m"
HTF_TF = "4h"
LTF_MINUTES = 15
LTF_LIMIT = 1500   # ~15.6 gün — swing/FVG penceresi için bol
HTF_LIMIT = 400    # ~66 gün — HTF bias için yeterli


def ohlcv_to_df(rows: list) -> pd.DataFrame:
    """ccxt fetch_ohlcv çıktısı → UTC indexli OHLCV DataFrame."""
    df = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop(columns=["timestamp"]).astype(float)
    return df[~df.index.duplicated(keep="first")].sort_index()


def drop_forming_bar(df: pd.DataFrame) -> pd.DataFrame:
    """Son bar henüz kapanmamış olabilir → her zaman atılır.

    barstate.isconfirmed eşdeğeri: yalnızca kesinleşmiş mumlarla karar.
    """
    return df.iloc[:-1] if len(df) else df


def pick_new_orders(orders: list[PendingOrder], last_idx: int) -> list[PendingOrder]:
    """Yalnızca SON KAPANAN barda oluşturulan emirler yenidir.

    Geçmiş barlardaki emirler önceki turlarda değerlendirildi — tekrar
    işlenirse çifte pozisyon açılır.
    """
    return [o for o in orders if o.created_idx == last_idx]


def next_bar_close(now: datetime, tf_minutes: int = LTF_MINUTES, delay_s: int = 20) -> datetime:
    """Bir sonraki bar kapanışı + borsanın mumu kesinleştirmesi için tampon."""
    epoch_min = int(now.timestamp() // 60)
    next_min = ((epoch_min // tf_minutes) + 1) * tf_minutes
    return datetime.fromtimestamp(next_min * 60, tz=timezone.utc) + timedelta(seconds=delay_s)


class LiveRunner:
    def __init__(
        self,
        symbols: tuple[str, ...],
        params: StrategyParams,
        risk: RiskEngine,
        journal: Journal,
        executor: CcxtExecutor,
        notifier: TelegramNotifier,
        max_positions: int = 1,
    ):
        self.symbols = symbols
        self.params = params
        self.risk = risk
        self.journal = journal
        self.ex = executor
        self.notifier = notifier
        self.max_positions = max_positions
        # tracked: her kayıt bir emrin yaşam döngüsü
        # {order_id, symbol, side, entry, stop, target, risk_amount,
        #  position_size, signal_id, trade_id, status, created_at, expires_at}
        self.tracked: list[dict] = []

    # ---------- veri ----------

    async def fetch_frames(self, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        ltf_rows = await self.ex.exchange.fetch_ohlcv(symbol, LTF_TF, limit=LTF_LIMIT)
        htf_rows = await self.ex.exchange.fetch_ohlcv(symbol, HTF_TF, limit=HTF_LIMIT)
        return (
            drop_forming_bar(ohlcv_to_df(ltf_rows)),
            drop_forming_bar(ohlcv_to_df(htf_rows)),
        )

    # ---------- sinyal ----------

    async def scan_symbol(self, symbol: str) -> None:
        ltf, htf = await self.fetch_frames(symbol)
        if len(ltf) < 100 or len(htf) < 50:
            return
        orders = generate_orders(ltf, htf, self.params)
        for o in pick_new_orders(orders, len(ltf) - 1):
            await self.handle_new_order(symbol, o)

    async def handle_new_order(self, symbol: str, o: PendingOrder) -> None:
        payload = {
            "symbol": symbol,
            "direction": o.side,
            "entry": o.entry,
            "stop_loss": o.stop,
            "take_profit": o.target,
            "setup": "ssl_sweep_fvg",
            "session": o.meta.get("session", ""),
            "htf_bias": str(o.meta.get("htf_bias", "")),
        }

        open_count = sum(1 for t in self.tracked if t["status"] in ("pending", "open"))
        if open_count >= self.max_positions:
            self.journal.log_signal(payload, False, "tek pozisyon kuralı")
            return

        ok, msg = self.risk.can_trade()
        if not ok:
            self.journal.log_signal(payload, False, msg)
            if self.risk.kill_switch_active:
                await self.notifier.send(
                    fmt_kill_switch(msg, self.risk.daily_pnl_r, self.risk.weekly_pnl_r)
                )
            return

        if not self.risk.validate_rr(o.entry, o.stop, o.target):
            self.journal.log_signal(payload, False, "RR < minimum")
            return

        sizing = self.risk.position_size(o.entry, o.stop)
        signal_id = self.journal.log_signal(payload, True)

        result = await self.ex.place_order(
            symbol=symbol,
            direction=o.side,
            position_size=sizing.position_size,
            entry=o.entry,
            stop_loss=o.stop,
            take_profit=o.target,
            order_type="limit",
        )
        if result.status != "ok":
            self.journal.log_signal(payload, False, f"emir hatası: {result.reason}")
            await self.notifier.send(fmt_signal(payload, False, str(result.reason)))
            return

        now = datetime.now(timezone.utc)
        self.tracked.append(
            {
                "order_id": result.order_id,
                "symbol": symbol,
                "side": o.side,
                "entry": o.entry,
                "stop": o.stop,
                "target": o.target,
                "risk_amount": sizing.risk_amount,
                "position_size": sizing.position_size,
                "signal_id": signal_id,
                "trade_id": None,
                "status": "pending",
                "created_at": now,
                "expires_at": now + timedelta(minutes=LTF_MINUTES * self.params.entry_window),
                "payload": payload,
            }
        )
        await self.notifier.send(fmt_signal(payload, True))
        print(f"[{now:%H:%M}] EMİR: {symbol} {o.side} limit={o.entry:.2f} "
              f"SL={o.stop:.2f} TP={o.target:.2f}")

    # ---------- yaşam döngüsü ----------

    async def manage_tracked(self) -> None:
        now = datetime.now(timezone.utc)
        for t in self.tracked:
            try:
                if t["status"] == "pending":
                    info = await self.ex.fetch_order_status(t["order_id"], t["symbol"])
                    if info["status"] == "closed":  # limit doldu → pozisyon açık
                        t["status"] = "open"
                        t["trade_id"] = self.journal.open_trade(
                            t["signal_id"], t["payload"],
                            t["position_size"], t["risk_amount"],
                            paper=False,
                        )
                        await self.notifier.send(
                            fmt_trade_opened(t["payload"], t["position_size"], t["risk_amount"])
                        )
                    elif info["status"] == "canceled" or now > t["expires_at"]:
                        if info["status"] != "canceled":
                            await self.ex.exchange.cancel_order(t["order_id"], t["symbol"])
                        t["status"] = "cancelled"

                elif t["status"] == "open":
                    positions = await self.ex.exchange.fetch_positions([t["symbol"]])
                    still_open = any(
                        (p.get("contracts") or 0) > 0 for p in positions
                    )
                    if not still_open:
                        pnl_r, pnl_usd, reason = await self._closed_pnl(t)
                        self.risk.record_result(pnl_r, t["risk_amount"])
                        if t["trade_id"]:
                            self.journal.close_trade(
                                t["trade_id"],
                                exit_price=t["target"] if pnl_r > 0 else t["stop"],
                                exit_reason=reason,
                                pnl_usd=pnl_usd, pnl_r=pnl_r,
                            )
                        await self.notifier.send(
                            fmt_trade_closed(t["symbol"], pnl_r, pnl_usd, reason)
                        )
                        t["status"] = "closed"
            except Exception as e:  # tek emir hatası döngüyü durdurmaz
                print(f"yaşam döngüsü hatası ({t['symbol']}): {e}")

        self.tracked = [t for t in self.tracked if t["status"] in ("pending", "open")]

    async def _closed_pnl(self, t: dict) -> tuple[float, float, str]:
        """Kapanan pozisyonun gerçek P&L'i — borsadan; olmazsa tahmin."""
        try:  # Bybit v5 closed-pnl endpoint'i (ccxt implicit)
            raw = t["symbol"].replace("/", "").replace(":USDT", "")
            resp = await self.ex.exchange.private_get_v5_position_closed_pnl(
                {"category": "linear", "symbol": raw, "limit": 1}
            )
            item = resp["result"]["list"][0]
            pnl_usd = float(item["closedPnl"])
            pnl_r = pnl_usd / t["risk_amount"]
            reason = "target" if pnl_usd > 0 else "stop"
            return pnl_r, pnl_usd, reason
        except Exception:
            # Tahmin: son fiyat hedefe mi stopa mı yakın kapandı
            ticker = await self.ex.exchange.fetch_ticker(t["symbol"])
            last = float(ticker["last"])
            hit_target = abs(last - t["target"]) < abs(last - t["stop"])
            pnl_r = 2.0 if hit_target else -1.0
            return pnl_r, pnl_r * t["risk_amount"], "target(est)" if hit_target else "stop(est)"

    # ---------- ana döngü ----------

    async def run(self) -> None:
        mode = "TESTNET (demo bakiye)" if ExchangeConfig().testnet else "CANLI"
        print(f"LiveRunner başladı — {mode} — semboller: {', '.join(self.symbols)}")
        await self.notifier.send(f"🤖 TradeBot başladı — {mode}")
        while True:
            target = next_bar_close(datetime.now(timezone.utc))
            wait = (target - datetime.now(timezone.utc)).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)
            await self.manage_tracked()
            for sym in self.symbols:
                try:
                    await self.scan_symbol(sym)
                except Exception as e:
                    print(f"tarama hatası ({sym}): {type(e).__name__}: {str(e)[:300]}")


async def main() -> None:
    load_env()
    from .config import LIVE_SYMBOLS, ServerConfig
    import os

    cfg = ExchangeConfig()
    if not cfg.testnet:
        print("!" * 60)
        print("UYARI: TRADING_MODE=live — GERÇEK PARA. Strategy Bible §8")
        print("kriterleri (PF>1.3, 300+ paper, 100+ testnet) sağlanmadan")
        print("canlı çalıştırma roadmap'e aykırıdır.")
        print("!" * 60)
        if input("Yine de devam? (evet yazın): ").strip().lower() != "evet":
            return

    # .env ile sembol listesi özelleştirilebilir:
    # LIVE_SYMBOLS=BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT
    env_syms = os.getenv("LIVE_SYMBOLS", "")
    symbols = tuple(
        s.strip() for s in env_syms.split(",") if s.strip()
    ) or LIVE_SYMBOLS

    runner = LiveRunner(
        symbols=symbols,
        params=replace(StrategyParams(), use_volume_filter=True),
        risk=RiskEngine(RiskParams(), float(os.getenv("ACCOUNT_BALANCE", "10000"))),
        journal=Journal(ServerConfig().journal_db),
        executor=CcxtExecutor(cfg),
        notifier=TelegramNotifier(),
    )
    try:
        await runner.run()
    finally:
        await runner.ex.close()


if __name__ == "__main__":
    asyncio.run(main())
