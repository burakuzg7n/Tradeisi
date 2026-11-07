"""Telegram bildirimleri.

Token yoksa sessizce devre disi kalir. Bildirim hatasi ASLA trade akisini
durdurmaz (tum cagrilar exception-swallow eder).
"""
from __future__ import annotations

import html
import os

import httpx


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                )
                return resp.status_code == 200
        except Exception:
            return False


def esc(value) -> str:
    """Telegram HTML guvenli metin."""
    return html.escape(str(value), quote=False)


def fmt_signal(signal: dict, accepted: bool, reason: str | None = None) -> str:
    head = "✅ SİNYAL KABUL" if accepted else "🚫 SİNYAL RED"
    lines = [
        f"<b>{head}</b>",
        f"{esc(signal.get('symbol', ''))} {esc(str(signal.get('side', '')).upper())}",
    ]
    if signal.get("entry") is not None:
        lines.append(f"Entry: {signal.get('entry')}")
    if signal.get("stop") is not None:
        lines.append(f"Stop: {signal.get('stop')}  TP: {signal.get('target')}")
    if signal.get("weight") is not None:
        lines.append(f"Ağırlık: %{float(signal['weight']) * 100:.2f}")
    lines.append(f"Strateji: {esc(signal.get('strategy', '-'))}")
    if not accepted and reason:
        lines.append(f"Sebep: {esc(reason)}")
    return "\n".join(lines)


def fmt_trade_opened(symbol: str, side: str, qty: float, entry: float,
                     stop: float | None, target: float | None,
                     risk_amount: float) -> str:
    lines = [
        "<b>📈 POZİSYON AÇILDI</b>",
        f"{esc(symbol)} {esc(side.upper())}",
        f"Entry: {entry}",
    ]
    if stop is not None:
        lines.append(f"Stop: {stop}")
    if target is not None:
        lines.append(f"TP: {target}")
    lines.append(f"Miktar: {qty:.6f}   Risk (1R): ${risk_amount:.2f}")
    return "\n".join(lines)


def fmt_trade_closed(symbol: str, side: str, pnl_r: float, pnl_usd: float,
                     reason: str) -> str:
    emoji = "🟢" if pnl_usd > 0 else "🔴"
    return "\n".join([
        f"<b>{emoji} POZİSYON KAPANDI</b>",
        f"{esc(symbol)} {esc(side.upper())} — {esc(reason)}",
        f"P&L: {pnl_r:+.2f}R (${pnl_usd:+.2f})",
    ])


def fmt_kill_switch(reason: str, daily_r: float, weekly_r: float, dd: float) -> str:
    return "\n".join([
        "<b>⛔ KILL SWITCH AKTİF</b>",
        f"Sebep: {esc(reason)}",
        f"Gün: {daily_r:+.1f}R   Hafta: {weekly_r:+.1f}R   DD: {dd:.2%}",
        "Sistem durdu — manuel inceleme gerekli.",
    ])


def fmt_start(mode: str, strategy: str, symbols: list[str]) -> str:
    return "\n".join([
        "<b>🤖 TradeBot başladı</b>",
        f"Mod: <b>{esc(mode)}</b>",
        f"Strateji: {esc(strategy)}",
        f"Semboller: {esc(', '.join(symbols))}",
    ])


def fmt_daily_summary(date_str: str, trades: int, pnl_usd: float, pnl_r: float,
                      equity: float) -> str:
    emoji = "🟢" if pnl_usd >= 0 else "🔴"
    return "\n".join([
        f"<b>{emoji} GÜNLÜK ÖZET — {esc(date_str)}</b>",
        f"İşlem: {trades}   P&L: {pnl_r:+.2f}R (${pnl_usd:+.2f})",
        f"Equity: ${equity:.2f}",
    ])
