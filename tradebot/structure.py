"""Market structure: swing tespiti, BOS/CHoCH, HTF bias.

Lookahead kuralı: i konumundaki pivot ancak `right` bar sonra kesinleşir.
i barında karar verirken yalnızca i-right ve öncesi pivotlar kullanılır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def find_swings(df: pd.DataFrame, left: int, right: int) -> tuple[np.ndarray, np.ndarray]:
    """Swing high/low seviyeleri. Pivot konumunda değer, diğer yerlerde NaN.

    Not: Bu diziler pivotun OLUŞTUĞU konumu işaretler; kesinleşme
    `right` bar sonradır. Tüketen kod bu gecikmeyi uygulamak zorundadır.
    """
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(df)
    sh = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    for i in range(left, n - right):
        window_h = high[i - left : i + right + 1]
        window_l = low[i - left : i + right + 1]
        if high[i] == window_h.max() and (window_h == high[i]).sum() == 1:
            sh[i] = high[i]
        if low[i] == window_l.min() and (window_l == low[i]).sum() == 1:
            sl[i] = low[i]
    return sh, sl


def detect_structure(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """BOS/CHoCH ve kümülatif trend (bias) — lookahead yok.

    trend: 1 = bullish, -1 = bearish, 0 = belirsiz.
    """
    out = df.copy()
    sh, sl = find_swings(df, left, right)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)

    bos_bull = np.zeros(n, bool)
    bos_bear = np.zeros(n, bool)
    choch_bull = np.zeros(n, bool)
    choch_bear = np.zeros(n, bool)
    trend = np.zeros(n, np.int8)

    t = 0
    last_sh = np.nan
    last_sl = np.nan

    for i in range(n):
        j = i - right  # bu barda kesinleşen pivot konumu
        if j >= 0:
            if not np.isnan(sh[j]):
                last_sh = sh[j]
            if not np.isnan(sl[j]):
                last_sl = sl[j]

        if not np.isnan(last_sh) and close[i] > last_sh:
            if t == 1:
                bos_bull[i] = True
            else:
                choch_bull[i] = True
            t = 1
            last_sh = np.nan
        elif not np.isnan(last_sl) and close[i] < last_sl:
            if t == -1:
                bos_bear[i] = True
            else:
                choch_bear[i] = True
            t = -1
            last_sl = np.nan

        trend[i] = t

    out["bos_bullish"] = bos_bull
    out["bos_bearish"] = bos_bear
    out["choch_bullish"] = choch_bull
    out["choch_bearish"] = choch_bear
    out["trend"] = trend
    return out


_TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}


def htf_bias_for_ltf(
    ltf_index: pd.DatetimeIndex,
    htf_df: pd.DataFrame,
    htf_timeframe: str = "4h",
    pivot: int = 3,
) -> np.ndarray:
    """Her LTF barı için, o an KAPANMIŞ son HTF mumunun trend değeri.

    HTF mumu open_time + tf süresi dolunca kapanır; bias ancak o andan
    itibaren LTF tarafında kullanılabilir (aksi hâlde lookahead).
    """
    tf_min = _TF_MINUTES[htf_timeframe]
    st = detect_structure(htf_df, left=pivot, right=pivot)
    avail = st.index + pd.Timedelta(minutes=tf_min)  # bias'ın geçerli olduğu an
    # merge_asof: her ltf ts için avail <= ts olan son bias.
    # NOT: Kolonlar açıkça kurulur — reset_index() index ADINA göre
    # ("timestamp" vb.) kolon üretir, "index" varsayımı sessizce kırılırdı.
    # Farklı pandas sürümleri farklı çözünürlük üretir (ns/us/ms) —
    # merge_asof iki tarafın AYNI tipte olmasını ister. ns'e sabitle.
    left_ts = pd.DatetimeIndex(ltf_index)
    right_ts = pd.DatetimeIndex(avail)
    try:
        left_ts = left_ts.as_unit("ns")
        right_ts = right_ts.as_unit("ns")
    except AttributeError:  # pandas < 2.0
        pass
    left = pd.DataFrame({"ts": left_ts})
    right = pd.DataFrame(
        {"ts": right_ts, "bias": st["trend"].to_numpy()}
    ).sort_values("ts")
    merged = pd.merge_asof(left, right, on="ts", direction="backward")
    return merged["bias"].fillna(0).to_numpy(dtype=np.int8)
