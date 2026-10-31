# Order Blocks — Implementation

## Python: OB Tespiti

```python
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

class OBType(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"

@dataclass
class OrderBlock:
    type: OBType
    high: float
    low: float
    bar_index: int
    mitigated: bool = False

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low


def detect_order_blocks(df: pd.DataFrame, lookback: int = 5) -> list[OrderBlock]:
    """
    BOS öncesi son karşı yönlü mumu Order Block olarak tespit eder.
    """
    obs = []

    for i in range(lookback + 1, len(df)):
        # Bullish BOS tespiti: close, son swing high'ı kırdı
        recent_highs = df['high'].iloc[i - lookback:i]
        swing_high = recent_highs.max()

        if df['close'].iloc[i] > swing_high:
            # BOS oluştu → geriye git, son bearish mumu bul
            for j in range(i - 1, max(i - lookback, 0), -1):
                if df['close'].iloc[j] < df['open'].iloc[j]:  # bearish mum
                    obs.append(OrderBlock(
                        type=OBType.BULLISH,
                        high=df['high'].iloc[j],
                        low=df['low'].iloc[j],
                        bar_index=j
                    ))
                    break

        # Bearish BOS tespiti
        recent_lows = df['low'].iloc[i - lookback:i]
        swing_low = recent_lows.min()

        if df['close'].iloc[i] < swing_low:
            for j in range(i - 1, max(i - lookback, 0), -1):
                if df['close'].iloc[j] > df['open'].iloc[j]:  # bullish mum
                    obs.append(OrderBlock(
                        type=OBType.BEARISH,
                        high=df['high'].iloc[j],
                        low=df['low'].iloc[j],
                        bar_index=j
                    ))
                    break

    return obs


def update_ob_mitigation(obs: list[OrderBlock], df: pd.DataFrame) -> list[OrderBlock]:
    """OB'lerin mitigasyon durumunu günceller."""
    for ob in obs:
        future = df.iloc[ob.bar_index + 1:]
        for _, candle in future.iterrows():
            if ob.type == OBType.BULLISH:
                if candle['low'] <= ob.midpoint:
                    ob.mitigated = True
                    break
            else:
                if candle['high'] >= ob.midpoint:
                    ob.mitigated = True
                    break
    return obs
```

---

## Pine Script: OB Görselleştirme

```pine
//@version=5
indicator("Order Blocks", overlay=true)

lookback = input.int(5, "Lookback")

// Son bearish mum (Bullish OB adayı)
lastBearishHigh = ta.highest(high, lookback)[1]
lastBearishLow  = ta.lowest(low, lookback)[1]

// Bullish BOS tespiti
bullBOS = barstate.isconfirmed and close > ta.highest(high, lookback)[1]

// Bearish BOS tespiti
bearBOS = barstate.isconfirmed and close < ta.lowest(low, lookback)[1]

var box[] bullOBBoxes = array.new_box()
var box[] bearOBBoxes = array.new_box()

if bullBOS
    // Son bearish mumu bul ve kutu çiz
    for i = 1 to lookback
        if close[i] < open[i]  // bearish mum
            b = box.new(bar_index - i, high[i], bar_index + 30, low[i],
                border_color=color.green, bgcolor=color.new(color.green, 85))
            array.push(bullOBBoxes, b)
            break

if bearBOS
    for i = 1 to lookback
        if close[i] > open[i]  // bullish mum
            b = box.new(bar_index - i, high[i], bar_index + 30, low[i],
                border_color=color.red, bgcolor=color.new(color.red, 85))
            array.push(bearOBBoxes, b)
            break
```

---

## OB + FVG Confluence Tespiti

```python
from knowledge.fvg.implementation import FVG, FVGType

def find_ob_fvg_confluence(
    obs: list[OrderBlock],
    fvgs: list[FVG],
    overlap_threshold: float = 0.5
) -> list[dict]:
    """OB ve FVG çakışmalarını bulur."""
    confluences = []

    for ob in obs:
        if ob.mitigated:
            continue
        for fvg in fvgs:
            if fvg.mitigated:
                continue
            # Tip uyumu kontrol
            if ob.type.value != fvg.type.value:
                continue

            # Örtüşme hesapla
            overlap_low = max(ob.low, fvg.bottom)
            overlap_high = min(ob.high, fvg.top)
            if overlap_high > overlap_low:
                overlap_size = overlap_high - overlap_low
                ob_size = ob.size
                overlap_ratio = overlap_size / ob_size

                if overlap_ratio >= overlap_threshold:
                    confluences.append({
                        "type": ob.type.value,
                        "zone_high": min(ob.high, fvg.top),
                        "zone_low": max(ob.low, fvg.bottom),
                        "strength": "high" if overlap_ratio > 0.75 else "medium",
                        "ob": ob,
                        "fvg": fvg,
                    })

    return confluences
```
