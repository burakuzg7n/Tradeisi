# Liquidity — Implementation

> NOT: Üretim kodu `tradebot/strategy.py` içindedir (sweep tespiti state
> machine olarak). Buradaki kod referanstır.

## Pine Script: Liquidity Level Tespiti

```pine
//@version=5
indicator("Liquidity Levels", overlay=true)

lookback = input.int(10, "Swing Lookback")

ph = ta.pivothigh(high, lookback, lookback)
pl = ta.pivotlow(low, lookback, lookback)

// Equal Highs/Lows toleransı (%0.1)
eqTolerance = input.float(0.001, "EQ Tolerance")

// Son kesinleşmiş pivot seviyelerini sakla
// NOT: ph/pl serileri sadece tespit barında değer taşır, diğer barlarda na'dır.
// pl[lookback] gibi sabit offset kullanmak sweep'i neredeyse hiç yakalamaz (eski hata).
var float lastPH = na
var float lastPL = na
if not na(ph)
    lastPH := ph
if not na(pl)
    lastPL := pl

// Sweep tespiti: wick seviyeyi geçer, close geri döner (mum kapanışında)
bullishSweep = barstate.isconfirmed and not na(lastPL) and
    low < lastPL and close > lastPL

bearishSweep = barstate.isconfirmed and not na(lastPH) and
    high > lastPH and close < lastPH

// Sweep edilen seviye tekrar kullanılmasın
if bullishSweep
    lastPL := na
if bearishSweep
    lastPH := na

plotshape(bullishSweep, "SSL Sweep ↑", shape.circle,
    location.belowbar, color.green, size=size.normal)
plotshape(bearishSweep, "BSL Sweep ↓", shape.circle,
    location.abovebar, color.red, size=size.normal)
```

---

## Python: Sweep Tespiti

```python
import pandas as pd
import numpy as np

def detect_liquidity_sweeps(
    df: pd.DataFrame,
    lookback: int = 10
) -> pd.DataFrame:
    """
    Sell-side ve buy-side liquidity sweep'lerini tespit eder.
    Sweep = wick seviyeyi geçer ama close geri döner.
    """
    df = df.copy()

    # Swing noktaları (rolling center=True gelecek mumlara bakar —
    # bu yüzden bir swing ancak `lookback` mum SONRA kesinleşmiş sayılır)
    df['swing_high'] = df['high'].rolling(lookback * 2 + 1,
        center=True).max() == df['high']
    df['swing_low'] = df['low'].rolling(lookback * 2 + 1,
        center=True).min() == df['low']

    df['ssl_sweep'] = False  # sell-side liquidity sweep (bullish)
    df['bsl_sweep'] = False  # buy-side liquidity sweep (bearish)

    positions = {ts: i for i, ts in enumerate(df.index)}
    swing_high_pos = [positions[ts] for ts in df[df['swing_high']].index]
    swing_low_pos = [positions[ts] for ts in df[df['swing_low']].index]
    highs = df['high'].to_numpy()
    lows = df['low'].to_numpy()
    closes = df['close'].to_numpy()

    for i in range(len(df)):
        # LOOKAHEAD KORUMASI: i barında yalnızca i - lookback ve öncesinde
        # OLUŞMUŞ swingler kesinleşmiştir. (Eski sürüm index < i şartıyla
        # henüz kesinleşmemiş swingleri kullanıyordu → future data leak.)
        confirmed_lows = [p for p in swing_low_pos if p <= i - lookback]
        if confirmed_lows:
            last_low = lows[confirmed_lows[-1]]
            if lows[i] < last_low and closes[i] > last_low:
                df.iloc[i, df.columns.get_loc('ssl_sweep')] = True

        confirmed_highs = [p for p in swing_high_pos if p <= i - lookback]
        if confirmed_highs:
            last_high = highs[confirmed_highs[-1]]
            if highs[i] > last_high and closes[i] < last_high:
                df.iloc[i, df.columns.get_loc('bsl_sweep')] = True

    return df

def find_equal_levels(
    levels: list[float],
    tolerance_pct: float = 0.001
) -> list[tuple[float, float]]:
    """Birbirine yakın seviyeleri (EQH/EQL) bulur."""
    equal_pairs = []
    for i, lvl1 in enumerate(levels):
        for lvl2 in levels[i+1:]:
            diff = abs(lvl1 - lvl2) / lvl1
            if diff <= tolerance_pct:
                equal_pairs.append((lvl1, lvl2))
    return equal_pairs
```

---

## Sinyal Üretimi

```python
class LiquiditySignal:
    def __init__(self, df: pd.DataFrame, bias: str):
        self.df = detect_liquidity_sweeps(df)
        self.bias = bias  # "bullish" veya "bearish"

    def get_entry_signal(self) -> dict | None:
        last = self.df.iloc[-1]

        # Bullish: SSL sweep + bullish bias
        if self.bias == "bullish" and last['ssl_sweep']:
            return {
                "direction": "long",
                "type": "ssl_sweep",
                "price": last['close'],
                "note": "Sell-side liquidity temizlendi, long arıyoruz"
            }

        # Bearish: BSL sweep + bearish bias
        if self.bias == "bearish" and last['bsl_sweep']:
            return {
                "direction": "short",
                "type": "bsl_sweep",
                "price": last['close'],
                "note": "Buy-side liquidity temizlendi, short arıyoruz"
            }

        return None
```
