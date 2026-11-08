"""Canli/paper risk motoru — kalici durum, kill switch, pozisyon boyutlama.

1R islem ACILISINDA sabitlenir. Gunluk/haftalik kayip limitleri ve maksimum
drawdown limiti asilirsa kill switch aktif olur ve OTOMATIK sifirlanmaz
(manuel inceleme gerekir). Durum SQLite'a yazilir; yeniden baslatildiginda
korunur.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

from .config import RiskSettings


class KillSwitchReason(Enum):
    DAILY_LIMIT = "daily_loss_limit"
    WEEKLY_LIMIT = "weekly_loss_limit"
    MAX_DRAWDOWN = "max_drawdown"
    MANUAL = "manual"


@dataclass
class PositionSize:
    position_size: float
    risk_amount: float
    stop_distance: float


class RiskEngine:
    def __init__(self, settings: RiskSettings, account_balance: float,
                 state: dict | None = None):
        self.p = settings
        self.initial_balance = account_balance
        self.current_balance = account_balance
        self.peak_balance = account_balance
        self.daily_pnl_r = 0.0
        self.weekly_pnl_r = 0.0
        self.kill_switch_active = False
        self.kill_switch_reason: str | None = None
        self._day: date | None = None
        self._week: tuple[int, int] | None = None
        if state:
            self.load_state(state)

    # ---------- kalici durum ----------

    def state(self) -> dict:
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "daily_pnl_r": self.daily_pnl_r,
            "weekly_pnl_r": self.weekly_pnl_r,
            "kill_switch_active": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "day": self._day.isoformat() if self._day else None,
            "week": list(self._week) if self._week else None,
        }

    def load_state(self, state: dict) -> None:
        self.initial_balance = float(state.get("initial_balance", self.initial_balance))
        self.current_balance = float(state.get("current_balance", self.current_balance))
        self.peak_balance = float(state.get("peak_balance", self.peak_balance))
        self.daily_pnl_r = float(state.get("daily_pnl_r", 0.0))
        self.weekly_pnl_r = float(state.get("weekly_pnl_r", 0.0))
        self.kill_switch_active = bool(state.get("kill_switch_active", False))
        self.kill_switch_reason = state.get("kill_switch_reason")
        day = state.get("day")
        self._day = date.fromisoformat(day) if day else None
        week = state.get("week")
        self._week = tuple(week) if week else None

    # ---------- zaman ----------

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

    # ---------- kontroller ----------

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
        return abs(target - entry) / risk >= 2.0

    def position_size(self, entry: float, stop: float) -> PositionSize:
        stop_distance = abs(entry - stop)
        if stop_distance == 0:
            raise ValueError("Stop ile entry aynı olamaz")
        risk_amount = self.current_balance * self.p.risk_per_trade
        return PositionSize(
            position_size=risk_amount / stop_distance,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
        )

    # ---------- sonuc kaydi ----------

    def record_result(self, pnl_r: float, risk_amount: float,
                      now: datetime | None = None) -> None:
        self._roll_clock(now)
        self.daily_pnl_r += pnl_r
        self.weekly_pnl_r += pnl_r
        self.current_balance += pnl_r * risk_amount
        self.peak_balance = max(self.peak_balance, self.current_balance)
        if self.current_drawdown >= self.p.max_drawdown_pct:
            self._kill(KillSwitchReason.MAX_DRAWDOWN)

    @property
    def current_drawdown(self) -> float:
        if self.peak_balance <= 0:
            return 0.0
        return (self.peak_balance - self.current_balance) / self.peak_balance

    def _kill(self, reason: KillSwitchReason) -> None:
        self.kill_switch_active = True
        self.kill_switch_reason = reason.value

    def manual_reset(self) -> None:
        """Kill switch SADECE bilinçli manuel kararla sıfırlanır."""
        self.kill_switch_active = False
        self.kill_switch_reason = None

    def snapshot(self) -> dict:
        return {
            "balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "drawdown": self.current_drawdown,
            "daily_pnl_r": self.daily_pnl_r,
            "weekly_pnl_r": self.weekly_pnl_r,
            "kill_switch": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason or "",
            "daily_limit_r": self.p.daily_loss_limit_r,
            "weekly_limit_r": self.p.weekly_loss_limit_r,
            "max_drawdown_pct": self.p.max_drawdown_pct,
        }
