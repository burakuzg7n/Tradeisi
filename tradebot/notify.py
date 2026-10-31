"""Telegram bildirimleri (Aşama 5 — paper trading gözlemi).

Token yoksa sessizce devre dışı; bildirim hatası trade akışını ASLA durdurmaz.
Kurulum: @BotFather'dan bot oluştur → TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
env değişkenlerini .env'e ekle.
"""
from __future__ import annotations

import os

import httpx


class TelegramNotifier:
    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    async def send(self, text: str) -> bool:
        """Mesaj gönderir. Hata olursa False döner, exception yükseltmez."""
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False  # bildirim hatası sistemi durdurmaz


# --- Mesaj formatlayıcılar (test edilebilir, IO'suz) ---

def fmt_signal(payload: dict, accepted: bool, reason: str | None = None) -> str:
    head = "✅ SİNYAL KABUL" if accepted else "🚫 SİNYAL RED"
    lines = [
        f"<b>{head}</b>",
        f"{payload.get('symbol')} {str(payload.get('direction', '')).upper()}",
        f"Entry: {payload.get('entry')}",
        f"Stop: {payload.get('stop_loss')}  TP: {payload.get('take_profit')}",
        f"Setup: {payload.get('setup', '-')}  Seans: {payload.get('session', '-')}",
    ]
    if not accepted and reason:
        lines.append(f"Sebep: {reason}")
    return "\n".join(lines)


def fmt_trade_opened(payload: dict, position_size: float, risk_amount: float) -> str:
    return "\n".join(
        [
            "<b>📈 POZİSYON AÇILDI</b>",
            f"{payload.get('symbol')} {str(payload.get('direction', '')).upper()}",
            f"Entry: {payload.get('entry')}  Boyut: {position_size:.6f}",
            f"Risk (1R): ${risk_amount:.2f}",
        ]
    )


def fmt_trade_closed(symbol: str, pnl_r: float, pnl_usd: float, reason: str) -> str:
    emoji = "🟢" if pnl_usd > 0 else "🔴"
    return "\n".join(
        [
            f"<b>{emoji} POZİSYON KAPANDI</b>",
            f"{symbol}  {reason}",
            f"P&L: {pnl_r:+.2f}R (${pnl_usd:+.2f})",
        ]
    )


def fmt_kill_switch(reason: str, daily_r: float, weekly_r: float) -> str:
    return "\n".join(
        [
            "<b>⛔ KILL SWITCH AKTİF</b>",
            f"Sebep: {reason}",
            f"Gün: {daily_r:+.1f}R  Hafta: {weekly_r:+.1f}R",
            "Sistem durdu — manuel inceleme gerekli.",
        ]
    )
