# Volume — Implementation

## Python: Temel Hacim Analizi

```python
import pandas as pd
import numpy as np

def volume_analysis(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Temel hacim metriklerini hesaplar."""
    df = df.copy()

    # Ortalama hacim
    df['avg_volume'] = df['volume'].rolling(window).mean()
    df['vol_ratio'] = df['volume'] / df['avg_volume']

    # Yüksek hacim filtresi
    df['high_volume'] = df['vol_ratio'] > 1.5  # ortalamadan %50 fazla

    # Bullish/Bearish mum hacmi
    df['is_bullish'] = df['close'] > df['open']
    df['bull_volume'] = df['volume'].where(df['is_bullish'], 0)
    df['bear_volume'] = df['volume'].where(~df['is_bullish'], 0)

    # CVD (basit tahmin: taker buy/sell ayrımı yoksa close pozisyonuna göre)
    df['delta'] = df['bull_volume'] - df['bear_volume']
    df['cvd'] = df['delta'].cumsum()

    return df

def volume_divergence(df: pd.DataFrame) -> pd.Series:
    """
    Fiyat ve CVD arasındaki divergence'ı tespit eder.
    Returns: 'bullish_div', 'bearish_div', veya None
    """
    signals = pd.Series(None, index=df.index, dtype=object)

    for i in range(5, len(df)):
        window = df.iloc[i-5:i]

        # Bearish divergence: fiyat HH ama CVD LH
        price_hh = df['high'].iloc[i] > window['high'].max()
        cvd_lh = df['cvd'].iloc[i] < window['cvd'].max()
        if price_hh and cvd_lh:
            signals.iloc[i] = 'bearish_div'

        # Bullish divergence: fiyat LL ama CVD HL
        price_ll = df['low'].iloc[i] < window['low'].min()
        cvd_hl = df['cvd'].iloc[i] > window['cvd'].min()
        if price_ll and cvd_hl:
            signals.iloc[i] = 'bullish_div'

    return signals
```

---

## Pine Script: Volume Filter

```pine
//@version=5
indicator("Volume Filter", overlay=false)

volMA = ta.sma(volume, 20)
volRatio = volume / volMA

// Renk: yüksek hacim = parlak, düşük = soluk
barColor = close > open ?
    (volRatio > 1.5 ? color.lime : color.green) :
    (volRatio > 1.5 ? color.red : color.maroon)

plot(volume, style=plot.style_histogram, color=barColor)
plot(volMA, color=color.yellow, linewidth=2)

// Yüksek hacim uyarısı
highVol = barstate.isconfirmed and volRatio > 2.0
plotshape(highVol, "High Vol", shape.triangleup,
    location.bottom, color.white, size=size.tiny)
```

---

## Webhook'a Volume Ekleme

```json
{
  "symbol": "BTCUSDT",
  "direction": "long",
  "entry": 50000,
  "stop": 49500,
  "target": 51000,
  "setup": "ssl_sweep_fvg",
  "volume_ratio": 2.3,
  "volume_confirmed": true
}
```

Volume ratio webhook'a eklenerek journal'da kayıt altına alınır ve sonradan analiz edilir.
