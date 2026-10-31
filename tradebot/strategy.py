"""HTF Bias + Liquidity Sweep + FVG Retest stratejisi.

Akış (her 15M bar kapanışında değerlendirilir — barstate.isconfirmed eşdeğeri):
  1. Kapanmış son 4H mumdan bias al (1 bull / -1 bear / 0 nötr → trade yok).
  2. Kesinleşmiş 15M swing low/high seviyelerini takip et (likidite).
  3. Sweep: bias yönünün tersindeki likidite süpürülür ve mum geri kapanır.
     - Bull bias: low < swingLow ve close > swingLow  (SSL sweep)
     - Bear bias: high > swingHigh ve close < swingHigh (BSL sweep)
  4. Sweep sonrası `setup_window` bar içinde bias yönünde FVG oluşursa
     → FVG %50 doluluk seviyesine LIMIT emir kur.
  5. Stop: sweep dibi ile FVG kenarının kötüsü - tampon. Target: RR hedefi.
  6. Emir `entry_window` bar içinde dolmazsa veya fiyat FVG'yi tamamen
     doldurup geçerse iptal.

Lookahead yok: her karar yalnızca o bar ve öncesi kapanmış verilerle alınır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import StrategyParams
from .fvg import fvg_at
from .sessions import in_killzone, session_name
from .structure import find_swings, htf_bias_for_ltf


@dataclass
class PendingOrder:
    side: str                # "long" | "short"
    entry: float             # limit fiyatı
    stop: float
    target: float
    created_idx: int         # emrin kurulduğu bar (bu barın KAPANIŞI)
    expiry_idx: int          # bu bardan sonra iptal
    cancel_beyond: float     # fiyat bunu aşarsa (close bazlı) iptal — FVG geçersiz
    market: bool = False     # True: bir sonraki barın open'ında market fill (V2)
    meta: dict = field(default_factory=dict)

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)


def generate_orders(
    ltf_df: pd.DataFrame,
    htf_df: pd.DataFrame,
    params: StrategyParams = StrategyParams(),
) -> list[PendingOrder]:
    """Tüm veri üzerinde yürüyerek pending limit emirleri üretir.

    Emirler oluşturuldukları barın kapanışında "verilmiş" sayılır;
    fill simülasyonu backtest motorunun işidir.
    """
    df = ltf_df
    n = len(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    index = df.index

    bias = htf_bias_for_ltf(index, htf_df, params.htf_timeframe, params.htf_pivot)
    sh, sl = find_swings(df, params.ltf_pivot, params.ltf_pivot)

    # Volume konfirmasyonu: sweep barının hacmi ortalamanın üstünde olmalı.
    # Rolling ortalama i barında i dahil GEÇMİŞ pencereyi kullanır (lookahead yok).
    if params.use_volume_filter:
        vol = df["volume"].to_numpy(dtype=float)
        vol_ma = (
            df["volume"].rolling(params.vol_ma_window, min_periods=params.vol_ma_window)
            .mean()
            .shift(1)  # kendi barını ortalamaya katma
            .to_numpy(dtype=float)
        )

    orders: list[PendingOrder] = []

    last_swing_low = np.nan
    last_swing_high = np.nan

    # sweep durumu
    sweep_dir = 0          # 1: SSL sweep oldu (long arıyoruz), -1: BSL sweep
    sweep_idx = -1
    sweep_extreme = np.nan  # sweep mumunun ucu (long için low)
    sweep_level = np.nan

    r = params.ltf_pivot
    for i in range(n):
        # 1) Bu barda kesinleşen pivotları kaydet (i-r konumundaki pivot)
        j = i - r
        if j >= 0:
            if not np.isnan(sl[j]):
                last_swing_low = sl[j]
            if not np.isnan(sh[j]):
                last_swing_high = sh[j]

        b = bias[i]

        # 2) Sweep süresi doldu mu / bias değişti mi → sıfırla
        if sweep_dir != 0:
            if i - sweep_idx > params.setup_window or b != sweep_dir:
                sweep_dir = 0

        # 3) Yeni sweep tespiti (bias yönünde)
        vol_ok = True
        if params.use_volume_filter:
            vol_ok = (not np.isnan(vol_ma[i])) and vol[i] >= params.vol_spike_mult * vol_ma[i]

        if b == 1 and not np.isnan(last_swing_low) and vol_ok:
            if low[i] < last_swing_low and close[i] > last_swing_low:
                sweep_dir = 1
                sweep_idx = i
                sweep_extreme = low[i]
                sweep_level = last_swing_low
                last_swing_low = np.nan  # aynı seviye tekrar süpürülmesin
        elif b == -1 and not np.isnan(last_swing_high) and vol_ok:
            if high[i] > last_swing_high and close[i] < last_swing_high:
                sweep_dir = -1
                sweep_idx = i
                sweep_extreme = high[i]
                sweep_level = last_swing_high
                last_swing_high = np.nan

        # 4) Sweep aktifken bias yönünde FVG arıyoruz (bu bar 3. mum olacak
        #    şekilde; FVG bu barın kapanışında kesinleşir)
        if sweep_dir != 0 and i > sweep_idx:
            fvg = fvg_at(df, i, params.fvg_min_size_pct)
            if fvg is not None and fvg.direction == sweep_dir:
                ts = index[i]
                if params.use_session_filter and not in_killzone(
                    ts, params.killzones_utc
                ):
                    # KZ dışı: setup yandı, sweep beklemeye devam etmez
                    sweep_dir = 0
                    continue

                entry = fvg.fill_level(params.fvg_fill_entry)
                if sweep_dir == 1:
                    raw_stop = min(sweep_extreme, fvg.bottom)
                    stop = raw_stop * (1 - params.stop_buffer_pct)
                    risk = entry - stop
                    if risk <= 0 or risk / entry < params.min_risk_pct:
                        sweep_dir = 0  # fee-dominated dar stop → ekonomik değil
                        continue
                    target = entry + params.rr_target * risk
                    cancel_beyond = fvg.bottom
                else:
                    raw_stop = max(sweep_extreme, fvg.top)
                    stop = raw_stop * (1 + params.stop_buffer_pct)
                    risk = stop - entry
                    if risk <= 0 or risk / entry < params.min_risk_pct:
                        sweep_dir = 0
                        continue
                    target = entry - params.rr_target * risk
                    cancel_beyond = fvg.top

                orders.append(
                    PendingOrder(
                        side="long" if sweep_dir == 1 else "short",
                        entry=float(entry),
                        stop=float(stop),
                        target=float(target),
                        created_idx=i,
                        expiry_idx=i + params.entry_window,
                        cancel_beyond=float(cancel_beyond),
                        meta={
                            "sweep_level": float(sweep_level),
                            "sweep_extreme": float(sweep_extreme),
                            "sweep_idx": int(sweep_idx),
                            "fvg_top": float(fvg.top),
                            "fvg_bottom": float(fvg.bottom),
                            "session": session_name(index[i]),
                            "htf_bias": int(b),
                            "timestamp": str(index[i]),
                        },
                    )
                )
                sweep_dir = 0  # sweep başına tek setup

    return orders
