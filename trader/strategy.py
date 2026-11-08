"""Strateji arayuzu.

Bir strateji:
  * `name`            — benzersiz ad (rapor/gunluk anahtari)
  * `research_candidate` — True ise arastirma adayidir ve protokol kapilarina
    tabidir. False ise yalnizca sistem testi/cizgi amaclidir ve canli
    (testnet dahil) calistirilamaz.
  * `timeframe`       — sinyalin olusacagi bar periyodu
  * `generate(panel, ts)` — `ts` barindaki KAPANIS sonrasi uretilen sinyaller

Lookahead kurali: `generate` yalnizca `ts` ve ONCESI barlari gorebilir.
Emirler `ts` barinin kapanisinda olusur; market emirler BIR SONRAKI barin
open'inda dolar (motorun isi).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass
class Signal:
    """Bir strateji ciktisi.

    action:
        "target_weight" — hedef agirlik (portfoy stratejileri)
        "open"          — giris (stop/target ile)
        "close"         — cikis
    """

    symbol: str
    side: str                    # "long" | "short" | "flat"
    action: str = "target_weight"
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    weight: float | None = None  # equity orani; long +, short -
    order_type: str = "market"   # "market" | "limit"
    ts: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "strategy": getattr(self, "strategy", ""),
            "symbol": self.symbol,
            "side": self.side,
            "action": self.action,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "weight": self.weight,
            "order_type": self.order_type,
            "meta": self.meta,
        }


class Panel:
    """ coklu sembollu veri paneli — stratejilerin gordugu tek arayuz.

    `panel[symbol]` bir OHLCV DataFrame'idir (UTC index).
    `panel.until(ts, symbol)` yalnizca ts ve oncesi barlari dondurur.
    """

    def __init__(self, data: dict[str, pd.DataFrame]):
        self._data = data

    def __contains__(self, symbol: str) -> bool:
        return symbol in self._data

    def __getitem__(self, symbol: str) -> pd.DataFrame:
        return self._data[symbol]

    def symbols(self) -> list[str]:
        return sorted(self._data.keys())

    def frame(self, symbol: str) -> pd.DataFrame:
        return self._data.get(symbol, pd.DataFrame())

    def until(self, symbol: str, ts: pd.Timestamp) -> pd.DataFrame:
        """ts ve oncesi barlar (lookahead korumasi burada da gecerli)."""
        df = self.frame(symbol)
        if df.empty:
            return df
        return df.loc[df.index <= ts]

    def last_ts(self) -> pd.Timestamp | None:
        ends = [df.index[-1] for df in self._data.values() if len(df)]
        return max(ends) if ends else None


class Strategy(Protocol):
    name: str
    research_candidate: bool
    timeframe: str

    def generate(self, panel: Panel, ts: pd.Timestamp) -> list[Signal]:
        ...
