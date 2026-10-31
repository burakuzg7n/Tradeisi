"""Risk Engine — canlı/paper pipeline'ın kalbi.

Kurallar (roadmap):
- İşlem başına risk %0.5, minimum RR 1:2
- Daily limit -3R, weekly limit -8R
- Max drawdown %10 → kill switch (manuel inceleme olmadan açılmaz)
- 1R işlem AÇILIŞINDA sabitlenir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from .config import RiskParams


class KillSwitchReason(Enum):
    DAILY_LIMIT = "daily_loss_limit"
    WEEKLY_LIMIT = "weekly_loss_limit"
    MAX_DRAWDOWN = "max_drawdown"
    MANUAL = "manual"


@dataclass
class PositionSize:
    position_size: float
    risk_amount: float   # 1R dolar değeri — işlem boyunca SABİT
    stop_distance: float


class RiskEngine:
    def __init__(self, params: RiskParams, account_balance: float):
        self.p = params
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.peak_balance = account_balance
        self.daily_pnl_r = 0.0
        self.weekly_pnl_r = 0.0
        self.kill_switch_active = False
        self.kill_switch_reason: str | None = None
        self._day: date | None = None
        self._week: tuple[int, int] | None = None

    # --- zaman bazlı sıfırlama ---
    def _roll_clock(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        d = now.date()
        w = now.isocalendar()[:2]
        if self._day != d:
            self._day = d
            self.daily_pnl_r = 0.0
        if self._week != w:
            self._week = w
            self.weekly_pnl_r = 0.0

    # --- kontroller ---
    def can_trade(self, now: datetime | None = None) -> tuple[bool, str]:
        self._roll_clock(now)
        if self.kill_switch_active:
            return False, f"Kill switch aktif: {self.kill_switch_reason}"
        if self.daily_pnl_r <= -self.p.daily_loss_limit_r:
            self._kill(KillSwitchReason.DAILY_LIMIT)
            return False, f"Günlük kayıp limiti (-{self.p.daily_loss_limit_r}R)"
        if self.weekly_pnl_r <= -self.p.weekly_loss_limit_r:
            self._kill(KillSwitchReason.WEEKLY_LIMIT)
            return False, f"Haftalık kayıp limiti (-{self.p.weekly_loss_limit_r}R)"
        return True, "OK"

    def validate_rr(self, entry: float, stop: float, target: float) -> bool:
        risk = abs(entry - stop)
        if risk == 0:
            return False
        return abs(target - entry) / risk >= self.p.min_rr

    def position_size(self, entry: float, stop: float) -> PositionSize:
        stop_distance = abs(entry - stop)
        if stop_distance == 0:
            raise ValueError("Stop, entry ile aynı olamaz")
        risk_amount = self.current_balance * self.p.risk_per_trade
        return PositionSize(
            position_size=risk_amount / stop_distance,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
        )

    # --- sonuç kaydı ---
    def record_result(
        self, pnl_r: float, risk_amount: float, now: datetime | None = None
    ) -> None:
        """risk_amount: işlem açılışında sabitlenen 1R dolar değeri."""
        self._roll_clock(now)
        self.daily_pnl_r += pnl_r
        self.weekly_pnl_r += pnl_r
        self.current_balance += pnl_r * risk_amount
        self.peak_balance = max(self.peak_balance, self.current_balance)
        if self.current_drawdown >= self.p.max_drawdown_pct:
            self._kill(KillSwitchReason.MAX_DRAWDOWN)

    @property
    def current_drawdown(self) -> float:
        return (self.peak_balance - self.current_balance) / self.peak_balance

    def _kill(self, reason: KillSwitchReason) -> None:
        self.kill_switch_active = True
        self.kill_switch_reason = reason.value

    def manual_reset(self) -> None:
        """Kill switch SADECE bilinçli manuel kararla sıfırlanır."""
        self.kill_switch_active = False
        self.kill_switch_reason = None
