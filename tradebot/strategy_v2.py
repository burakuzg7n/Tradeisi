"""V2: Sweep + CHoCH konfirmasyonu — DEVIR_NOTU.md §8'in birebir kodu.

Kurallar 8 Tem 2026'da veriye bakılmadan sabitlendi. DEĞİŞTİRİLEMEZ.
V1'den fark: FVG'ye limit emir yerine, sweep sonrası yapı dönüşü onayı
(sweep öncesi lokal ekstremin close ile kırılması) beklenir; giriş MARKET.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import StrategyParams
from .sessions import in_killzone, session_name
from .strategy import PendingOrder
from .structure import find_swings, htf_bias_for_ltf

TRIGGER_LOOKBACK = 10   # sabit (spec): max(high[s-10..s]) / min(low[s-10..s])


def generate_orders_v2(
    ltf_df: pd.DataFrame,
    htf_df: pd.DataFrame,
    params: StrategyParams = StrategyParams(),
    trade_from_idx: int = 0,
) -> list[PendingOrder]:
    """trade_from_idx: bu bardan ÖNCEKİ barlar yalnız GÖSTERGE ısınması içindir
    (pivotlar/swing seviyeleri güncellenir); sweep/setup durumu oluşmaz ve hiçbir
    swing seviyesi "tüketilmez". Böylece dönem, bekleyen setup olmadan başlar
    (SPEC_EKLERI E3c). trade_from_idx=0 → eski davranış."""
    df = ltf_df
    n = len(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    index = df.index

    bias = htf_bias_for_ltf(index, htf_df, params.htf_timeframe, params.htf_pivot)
    sh, sl = find_swings(df, params.ltf_pivot, params.ltf_pivot)

    orders: list[PendingOrder] = []
    last_swing_low = np.nan
    last_swing_high = np.nan
    sweep_dir = 0
    sweep_idx = -1
    sweep_extreme = np.nan
    trigger_level = np.nan

    r = params.ltf_pivot
    for i in range(n):
        j = i - r
        if j >= 0:
            if not np.isnan(sl[j]):
                last_swing_low = sl[j]
            if not np.isnan(sh[j]):
                last_swing_high = sh[j]

        if i < trade_from_idx:
            continue

        b = bias[i]

        # pencere/bias kontrolü (setup_window=24, V1 ile aynı)
        if sweep_dir != 0 and (i - sweep_idx > params.setup_window or b != sweep_dir):
            sweep_dir = 0

        # CHoCH tetiği: sweep öncesi lokal ekstrem close ile kırıldı mı?
        if sweep_dir == 1 and i > sweep_idx and close[i] > trigger_level:
            ts = index[i]
            if params.use_session_filter and not in_killzone(ts, params.killzones_utc):
                sweep_dir = 0
            else:
                entry_ref = close[i]
                stop = sweep_extreme * (1 - params.stop_buffer_pct)
                risk = entry_ref - stop
                if risk > 0 and risk / entry_ref >= params.min_risk_pct:
                    orders.append(PendingOrder(
                        side="long", entry=float(entry_ref), stop=float(stop),
                        target=float(entry_ref + params.rr_target * risk),
                        created_idx=i, expiry_idx=i + 2,
                        cancel_beyond=-1e18, market=True,
                        meta={"session": session_name(ts), "htf_bias": int(b),
                              "timestamp": str(ts), "sweep_idx": int(sweep_idx),
                              "trigger": float(trigger_level)},
                    ))
                sweep_dir = 0
        elif sweep_dir == -1 and i > sweep_idx and close[i] < trigger_level:
            ts = index[i]
            if params.use_session_filter and not in_killzone(ts, params.killzones_utc):
                sweep_dir = 0
            else:
                entry_ref = close[i]
                stop = sweep_extreme * (1 + params.stop_buffer_pct)
                risk = stop - entry_ref
                if risk > 0 and risk / entry_ref >= params.min_risk_pct:
                    orders.append(PendingOrder(
                        side="short", entry=float(entry_ref), stop=float(stop),
                        target=float(entry_ref - params.rr_target * risk),
                        created_idx=i, expiry_idx=i + 2,
                        cancel_beyond=1e18, market=True,
                        meta={"session": session_name(ts), "htf_bias": int(b),
                              "timestamp": str(ts), "sweep_idx": int(sweep_idx),
                              "trigger": float(trigger_level)},
                    ))
                sweep_dir = 0

        # yeni sweep tespiti (V1 ile aynı tanım; volume filtresi V2'de YOK)
        if sweep_dir == 0:
            if b == 1 and not np.isnan(last_swing_low):
                if low[i] < last_swing_low and close[i] > last_swing_low:
                    sweep_dir = 1
                    sweep_idx = i
                    sweep_extreme = low[i]
                    lb = max(0, i - TRIGGER_LOOKBACK)
                    trigger_level = high[lb : i + 1].max()
                    last_swing_low = np.nan
            elif b == -1 and not np.isnan(last_swing_high):
                if high[i] > last_swing_high and close[i] < last_swing_high:
                    sweep_dir = -1
                    sweep_idx = i
                    sweep_extreme = high[i]
                    lb = max(0, i - TRIGGER_LOOKBACK)
                    trigger_level = low[lb : i + 1].min()
                    last_swing_high = np.nan

    return orders
