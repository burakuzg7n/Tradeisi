# Market Structure — Implementation

> NOT: Üretim kodu `tradebot/structure.py` içindedir. Buradaki kod referanstır.

## Pine Script: BOS ve CHoCH Tespiti

```pine
//@version=5
indicator("Market Structure", overlay=true)

// Pivot tespiti (sol 3, sağ 3 mum) — pivot ancak 3 mum SONRA kesinleşir
ph = ta.pivothigh(high, 3, 3)
pl = ta.pivotlow(low, 3, 3)

// Son kesinleşmiş swing high/low seviyeleri
var float lastSwingHigh = na
var float lastSwingLow = na

if not na(ph)
    lastSwingHigh := ph
if not na(pl)
    lastSwingLow := pl

// Kırılım tespiti (close bazlı, kesinleşmiş seviyeye karşı)
upBreak   = not na(lastSwingHigh) and ta.crossover(close, lastSwingHigh)
downBreak = not na(lastSwingLow)  and ta.crossunder(close, lastSwingLow)

// DİKKAT: CHoCH kararını kırılımdan ÖNCEKİ trend verir.
// Trend önce güncellenirse CHoCH hiçbir zaman tetiklenmez (klasik sıralama hatası).
var bool isBullishTrend = false
wasBullish = isBullishTrend

bullishBOS   = upBreak   and wasBullish        // trend devamı
bearishBOS   = downBreak and not wasBullish
bullishCHoCH = upBreak   and not wasBullish    // bearish trendde yukarı kırılım
bearishCHoCH = downBreak and wasBullish        // bullish trendde aşağı kırılım

// Trend, kırılım SONRASI güncellenir
if upBreak
    isBullishTrend := true
if downBreak
    isBullishTrend := false

// Görselleştirme
plotshape(bullishBOS, "BOS ↑", shape.triangleup,
    location.belowbar, color.green, size=size.small)
plotshape(bearishBOS, "BOS ↓", shape.triangledown,
    location.abovebar, color.red, size=size.small)
plotshape(bullishCHoCH, "CHoCH ↑", shape.triangleup,
    location.belowbar, color.lime, size=size.normal)
plotshape(bearishCHoCH, "CHoCH ↓", shape.triangledown,
    location.abovebar, color.orange, size=size.normal)
```

---

## Python: Swing Nokta Tespiti

```python
import pandas as pd
import numpy as np

def find_swing_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """Swing high noktalarını tespit eder."""
    highs = df['high']
    swing_highs = pd.Series(np.nan, index=df.index)

    for i in range(left, len(df) - right):
        if highs.iloc[i] == max(highs.iloc[i-left:i+right+1]):
            swing_highs.iloc[i] = highs.iloc[i]

    return swing_highs

def find_swing_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.Series:
    """Swing low noktalarını tespit eder."""
    lows = df['low']
    swing_lows = pd.Series(np.nan, index=df.index)

    for i in range(left, len(df) - right):
        if lows.iloc[i] == min(lows.iloc[i-left:i+right+1]):
            swing_lows.iloc[i] = lows.iloc[i]

    return swing_lows

def detect_market_structure(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """BOS ve CHoCH noktalarını LOOKAHEAD BIAS OLMADAN işaretler.

    Kritik kural: i konumundaki bir pivot ancak `right` mum sonra kesinleşir.
    Bu yüzden i barında yalnızca i-right ve öncesinde oluşmuş pivotlar kullanılır.
    (Önceki sürüm tüm geçmişi son swing seviyesiyle karşılaştırıyordu →
    future data leak, backtest sonuçları geçersiz olurdu.)
    """
    df = df.copy()
    df['swing_high'] = find_swing_highs(df, left, right)
    df['swing_low'] = find_swing_lows(df, left, right)

    n = len(df)
    sh = df['swing_high'].to_numpy()
    sl = df['swing_low'].to_numpy()
    close = df['close'].to_numpy()

    bos_bull = np.zeros(n, bool); bos_bear = np.zeros(n, bool)
    choch_bull = np.zeros(n, bool); choch_bear = np.zeros(n, bool)
    trend = np.zeros(n, int)  # 1=bull, -1=bear, 0=belirsiz

    t = 0
    last_sh = np.nan
    last_sl = np.nan

    for i in range(n):
        # i-right konumundaki pivot bu barda kesinleşti → artık kullanılabilir
        j = i - right
        if j >= 0:
            if not np.isnan(sh[j]):
                last_sh = sh[j]
            if not np.isnan(sl[j]):
                last_sl = sl[j]

        if not np.isnan(last_sh) and close[i] > last_sh:
            if t == 1:
                bos_bull[i] = True      # trend devamı
            else:
                choch_bull[i] = True    # trend dönüşü
            t = 1
            last_sh = np.nan            # aynı seviye tekrar tetiklenmesin
        elif not np.isnan(last_sl) and close[i] < last_sl:
            if t == -1:
                bos_bear[i] = True
            else:
                choch_bear[i] = True
            t = -1
            last_sl = np.nan

        trend[i] = t

    df['bos_bullish'] = bos_bull
    df['bos_bearish'] = bos_bear
    df['choch_bullish'] = choch_bull
    df['choch_bearish'] = choch_bear
    df['trend'] = trend
    return df
```

---

## HTF Bias Servisi

```python
class BiasService:
    """HTF bias'ı belirler ve LTF entry için filtre uygular."""

    BEARISH = "bearish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"

    def __init__(self, htf_df: pd.DataFrame):
        self.df = detect_market_structure(htf_df)

    def get_bias(self) -> str:
        # trend kolonu: o ana kadar kesinleşmiş yapıya göre kümülatif durum
        t = self.df['trend'].iloc[-1]
        if t == 1:
            return self.BULLISH
        if t == -1:
            return self.BEARISH
        return self.NEUTRAL

    def allows_long(self) -> bool:
        return self.get_bias() == self.BULLISH

    def allows_short(self) -> bool:
        return self.get_bias() == self.BEARISH
```
