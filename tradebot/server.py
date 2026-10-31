"""FastAPI webhook sunucusu + sinyal işleyici.

Akış: TradingView → POST /webhook → doğrulama → queue →
consumer → RiskEngine → Executor (paper/ccxt) → Journal.

Çalıştırma:
    uvicorn tradebot.server:app --host 0.0.0.0 --port 8000

Redis'e geçiş: queue soyutlaması tek noktada (asyncio.Queue) —
prod'da aynı arayüzle Redis list'e taşınır.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from .config import RiskParams, ServerConfig
from .execution import CcxtExecutor, ExchangeConfig, PaperExecutor
from .journal import Journal
from .notify import TelegramNotifier, fmt_kill_switch, fmt_signal, fmt_trade_opened
from .risk import RiskEngine
from .sessions import in_killzone, now_utc


class SignalPayload(BaseModel):
    symbol: str
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    setup: str = "ssl_sweep_fvg"
    timeframe: str = "15"
    htf_bias: str = ""
    session: str = ""
    volume_ratio: float = 1.0
    fvg_top: float | None = None
    fvg_bottom: float | None = None
    timestamp: str = ""

    @field_validator("direction")
    @classmethod
    def _direction(cls, v: str) -> str:
        if v not in ("long", "short"):
            raise ValueError("direction 'long' veya 'short' olmalı")
        return v

    @model_validator(mode="after")
    def _stop_side(self) -> "SignalPayload":
        if self.direction == "long" and self.stop_loss >= self.entry:
            raise ValueError("Long için stop < entry olmalı")
        if self.direction == "short" and self.stop_loss <= self.entry:
            raise ValueError("Short için stop > entry olmalı")
        return self


class AppState:
    def __init__(self):
        cfg = ServerConfig()
        self.cfg = cfg
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.journal = Journal(cfg.journal_db)
        self.risk = RiskEngine(
            RiskParams(), float(os.getenv("ACCOUNT_BALANCE", "1000"))
        )
        self.executor = (
            PaperExecutor() if cfg.paper_mode else CcxtExecutor(ExchangeConfig())
        )
        self.notifier = TelegramNotifier()
        self.consumer_task: asyncio.Task | None = None


state = AppState()


async def process_signal(payload: dict) -> None:
    """Tek sinyalin tam yaşam döngüsü."""
    # 1) Risk kontrolü
    ok, msg = state.risk.can_trade()
    if not ok:
        state.journal.log_signal(payload, accepted=False, reject_reason=msg)
        if state.risk.kill_switch_active:
            await state.notifier.send(
                fmt_kill_switch(msg, state.risk.daily_pnl_r, state.risk.weekly_pnl_r)
            )
        else:
            await state.notifier.send(fmt_signal(payload, False, msg))
        return

    # 2) Session filtresi (sunucu tarafında ikinci savunma hattı)
    if not in_killzone(now_utc()):
        state.journal.log_signal(
            payload, accepted=False, reject_reason="killzone dışı"
        )
        return

    # 3) RR kontrolü
    if not state.risk.validate_rr(
        payload["entry"], payload["stop_loss"], payload["take_profit"]
    ):
        state.journal.log_signal(
            payload, accepted=False, reject_reason="RR < minimum"
        )
        return

    # 4) Position sizing (1R burada sabitlenir)
    sizing = state.risk.position_size(payload["entry"], payload["stop_loss"])
    signal_id = state.journal.log_signal(payload, accepted=True)

    # 5) Emir gönder
    result = await state.executor.place_order(
        symbol=payload["symbol"],
        direction=payload["direction"],
        position_size=sizing.position_size,
        entry=payload["entry"],
        stop_loss=payload["stop_loss"],
        take_profit=payload["take_profit"],
    )
    if result.status == "ok":
        state.journal.open_trade(
            signal_id,
            payload,
            sizing.position_size,
            sizing.risk_amount,
            paper=state.cfg.paper_mode,
        )
        await state.notifier.send(
            fmt_trade_opened(payload, sizing.position_size, sizing.risk_amount)
        )
    else:
        await state.notifier.send(
            fmt_signal(payload, False, f"emir hatası: {result.reason}")
        )


async def consumer() -> None:
    while True:
        payload = await state.queue.get()
        try:
            await process_signal(payload)
        except Exception as e:  # sinyal başına izolasyon: tek hata sistemi durdurmaz
            state.journal.log_signal(
                payload, accepted=False, reject_reason=f"internal_error: {e}"
            )
        finally:
            state.queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.consumer_task = asyncio.create_task(consumer())
    yield
    state.consumer_task.cancel()
    await state.executor.close()
    state.journal.close()


app = FastAPI(title="TradeBot Webhook", lifespan=lifespan)


@app.post("/webhook")
async def webhook(payload: SignalPayload, authorization: str = Header(default="")):
    secret = state.cfg.webhook_secret
    if not secret:
        raise HTTPException(500, "WEBHOOK_SECRET tanımlı değil")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, secret):
        raise HTTPException(401, "Geçersiz token")

    try:
        state.queue.put_nowait(payload.model_dump())
    except asyncio.QueueFull:
        raise HTTPException(503, "Queue dolu")
    return {"status": "queued", "symbol": payload.symbol}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "paper_mode": state.cfg.paper_mode,
        "kill_switch": state.risk.kill_switch_active,
        "queue_size": state.queue.qsize(),
    }


@app.get("/stats")
async def stats():
    return state.journal.stats()
