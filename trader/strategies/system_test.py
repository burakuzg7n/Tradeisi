"""SISTEM TESTI stratejisi — ALTYAPI DOGRULAMA ICIN.

UYARI: Bu bir arastirma adayi DEGILDIR ve bir kazanc iddiasi TASIMAZ.
Tek amaci: sinyal -> emir -> dolum -> P&L -> journal -> dashboard -> Telegram
 zincirinin ucuca kadar dogru calistigini gostermek.

`research_candidate = False` oldugu icin canli/testnet yurutucusu bu
stratejiyi CALISTIRMAZ; paper modunda da "ALTYAPI TESTI" etiketiyle calisir.

Kural (sadelestirilmis, parametre oynanmaz):
  - 15m bar, RSI(14)
  - RSI < 30  -> long : stop = entry %1, target = entry %2
  - RSI > 70  -> short: stop = entry %1, target = entry %2
  - Ayni anda tek pozisyon.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import rsi
from ..strategy import Panel, Signal

STRATEGY_NAME = "sistem_testi"


class SystemTest:
    """Altyapi dogrulama stratejisi — arastirma adayi degildir."""

    name = STRATEGY_NAME
    research_candidate = False     # <-- canli/testnet kapisi KAPALI
    timeframe = "15m"

    def __init__(self, symbol: str = "BTCUSDT", rsi_period: int = 14,
                 oversold: float = 30.0, overbought: float = 70.0,
                 stop_pct: float = 0.01, target_pct: float = 0.02):
        self.symbol = symbol
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.in_position = False

    def generate(self, panel: Panel, ts: pd.Timestamp) -> list[Signal]:
        df = panel.until(self.symbol, ts)
        if len(df) < self.rsi_period + 5:
            return []
        series = rsi(df["close"], self.rsi_period)
        if series.empty or pd.isna(series.iloc[-1]):
            return []
        value = float(series.iloc[-1])
        close = float(df["close"].iloc[-1])
        meta = {"strategy": self.name, "rsi": round(value, 2), "kind": "ALTYAPI_TESTI"}

        if self.in_position:
            return []

        if value < self.oversold:
            self.in_position = True
            return [Signal(
                symbol=self.symbol, side="long", action="open",
                entry=close, stop=close * (1 - self.stop_pct),
                target=close * (1 + self.target_pct), ts=ts.isoformat(), meta=meta,
            )]
        if value > self.overbought:
            self.in_position = True
            return [Signal(
                symbol=self.symbol, side="short", action="open",
                entry=close, stop=close * (1 + self.stop_pct),
                target=close * (1 - self.target_pct), ts=ts.isoformat(), meta=meta,
            )]
        return []
