"""Fair Value Gap tespiti.

Bullish FVG: candle3.low > candle1.high (3 ardışık mum, ortada momentum).
FVG, 3. mumun KAPANIŞINDA bilinir hâle gelir → formed_at = 3. mumun indexi.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class FVG:
    direction: int      # 1 = bullish, -1 = bearish
    top: float
    bottom: float
    formed_at: int      # 3. mumun bar indexi (bu barın kapanışında biliniyor)

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2

    def fill_level(self, fill_ratio: float) -> float:
        """FVG'nin fill_ratio kadar dolduğu fiyat.

        Bullish FVG üstten (top'tan) dolar: 0.5 → midpoint, 1.0 → bottom.
        Bearish FVG alttan dolar: 0.5 → midpoint, 1.0 → top.
        """
        if self.direction == 1:
            return self.top - self.size * fill_ratio
        return self.bottom + self.size * fill_ratio


def fvg_at(df: pd.DataFrame, i: int, min_size_pct: float = 0.0005) -> FVG | None:
    """i indexli mum 3. mum olacak şekilde FVG kontrolü (i kapanışında)."""
    if i < 2:
        return None
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    ref_price = c[i - 1]

    # Bullish: 3. mum low > 1. mum high
    if l[i] > h[i - 2]:
        size = l[i] - h[i - 2]
        if size / ref_price >= min_size_pct:
            return FVG(direction=1, top=l[i], bottom=h[i - 2], formed_at=i)

    # Bearish: 3. mum high < 1. mum low
    if h[i] < l[i - 2]:
        size = l[i - 2] - h[i]
        if size / ref_price >= min_size_pct:
            return FVG(direction=-1, top=l[i - 2], bottom=h[i], formed_at=i)

    return None
