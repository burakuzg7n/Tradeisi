# FVG — Implementation

> NOT: Üretim kodu `tradebot/fvg.py` içindedir. Buradaki kod referanstır.

## Python: FVG Tespiti

```python
from dataclasses import dataclass
from enum import Enum
import pandas as pd

class FVGType(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"

@dataclass
class FVG:
    type: FVGType
    top: float       # FVG üst sınırı
    bottom: float    # FVG alt sınırı
    midpoint: float  # %50 seviyesi
    bar_index: int   # Oluştuğu mum (2. mum)
    mitigated: bool = False

    @property
    def size(self) -> float:
        return self.top - self.bottom

    def entry_zone(self) -> tuple[float, float]:
        """OTE: FVG'nin %50-%79 DOLULUK bölgesi.

        Bullish FVG üstten doldurulur: %50 doluluk = midpoint,
        %79 doluluk = bottom + size*(1-0.79). Yani bölge midpoint'in
        ALTINDADIR (daha derin retrace = daha iyi fiyat).
        (Eski sürüm bölgeyi midpoint'in üstüne koyuyordu — %21-%50
        doluluğa denk gelir, OTE tanımıyla çelişirdi.)
        """
        if self.type == FVGType.BULLISH:
            return (self.bottom + self.size * (1 - 0.79),
                    self.midpoint)
        else:
            return (self.midpoint,
                    self.top - self.size * (1 - 0.79))


def detect_fvgs(df: pd.DataFrame, min_size_pct: float = 0.0005) -> list[FVG]:
    """
    DataFrame'de tüm FVG'leri tespit eder.
    min_size_pct: FVG'nin fiyata oranı minimum büyüklük filtresi
    """
    fvgs = []

    for i in range(1, len(df) - 1):
        candle1 = df.iloc[i - 1]
        candle3 = df.iloc[i + 1]
        mid_price = df.iloc[i]['close']

        # Bullish FVG: candle3 low > candle1 high
        if candle3['low'] > candle1['high']:
            size = candle3['low'] - candle1['high']
            if size / mid_price >= min_size_pct:
                fvgs.append(FVG(
                    type=FVGType.BULLISH,
                    top=candle3['low'],
                    bottom=candle1['high'],
                    midpoint=(candle3['low'] + candle1['high']) / 2,
                    bar_index=i
                ))

        # Bearish FVG: candle3 high < candle1 low
        elif candle3['high'] < candle1['low']:
            size = candle1['low'] - candle3['high']
            if size / mid_price >= min_size_pct:
                fvgs.append(FVG(
                    type=FVGType.BEARISH,
                    top=candle1['low'],
                    bottom=candle3['high'],
                    midpoint=(candle1['low'] + candle3['high']) / 2,
                    bar_index=i
                ))

    return fvgs


def check_fvg_mitigation(fvgs: list[FVG], df: pd.DataFrame) -> list[FVG]:
    """Oluşan FVG'lerin mitigasyon durumunu günceller.

    ÖNEMLİ TUTARLILIK NOTU: Entry zone %50-%79 doluluk bölgesinde olduğu
    için mitigasyon eşiği midpoint OLAMAZ — aksi halde fiyat entry bölgesine
    her girişinde FVG 'mitigated' sayılır ve hiçbir entry üretilemez
    (eski sürümdeki çelişki). Mitigasyon = FVG'nin TAMAMEN doldurulması
    (fiyat karşı sınırı geçer) → FVG geçersiz, IFVG'ye dönüşebilir.
    """
    for fvg in fvgs:
        future_candles = df.iloc[fvg.bar_index + 2:]
        for _, candle in future_candles.iterrows():
            if fvg.type == FVGType.BULLISH:
                # Fiyat FVG'nin altını tamamen doldurdu mu?
                if candle['low'] <= fvg.bottom:
                    fvg.mitigated = True
                    break
            else:
                # Fiyat FVG'nin üstünü tamamen doldurdu mu?
                if candle['high'] >= fvg.top:
                    fvg.mitigated = True
                    break
    return fvgs
```

---

## Pine Script: FVG Görselleştirme

```pine
//@version=5
indicator("FVG Detector", overlay=true)

// Bullish FVG
bullFVG = low[0] > high[2]  // candle3.low > candle1.high
bearFVG = high[0] < low[2]  // candle3.high < candle1.low

// Sadece barstate.isconfirmed ile çalış
if barstate.isconfirmed
    if bullFVG
        box.new(bar_index - 2, low[0], bar_index + 20, high[2],
            border_color=color.green, bgcolor=color.new(color.green, 85))
    if bearFVG
        box.new(bar_index - 2, high[0], bar_index + 20, low[2],
            border_color=color.red, bgcolor=color.new(color.red, 85))
```

---

## FVG Entry Servisi

```python
class FVGEntryService:
    def __init__(self, fvgs: list[FVG], bias: str):
        self.fvgs = [f for f in fvgs if not f.mitigated]
        self.bias = bias

    def get_active_fvgs(self) -> list[FVG]:
        """Bias ile hizalı, mitigate edilmemiş FVG'leri döner."""
        if self.bias == "bullish":
            return [f for f in self.fvgs if f.type == FVGType.BULLISH]
        return [f for f in self.fvgs if f.type == FVGType.BEARISH]

    def price_in_fvg(self, price: float) -> FVG | None:
        """Fiyat herhangi bir aktif FVG içinde mi?"""
        for fvg in self.get_active_fvgs():
            if fvg.bottom <= price <= fvg.top:
                return fvg
        return None

    def get_entry_signal(self, current_price: float) -> dict | None:
        fvg = self.price_in_fvg(current_price)
        if fvg is None:
            return None

        low_zone, high_zone = fvg.entry_zone()
        if low_zone <= current_price <= high_zone:
            return {
                "direction": "long" if self.bias == "bullish" else "short",
                "fvg_top": fvg.top,
                "fvg_bottom": fvg.bottom,
                "entry_zone": (low_zone, high_zone),
                "stop_loss": fvg.bottom * 0.999 if self.bias == "bullish" else fvg.top * 1.001,
            }
        return None
```
