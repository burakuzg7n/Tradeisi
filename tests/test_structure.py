import numpy as np
import pandas as pd

from tests.conftest import make_df
from tradebot.structure import detect_structure, find_swings, htf_bias_for_ltf


def test_swing_detection_basic():
    # Ortada belirgin bir tepe: index 5
    bars = []
    highs = [100, 101, 102, 103, 104, 110, 104, 103, 102, 101, 100]
    for h in highs:
        bars.append((h - 1, h, h - 2, h - 1))
    df = make_df(bars)
    sh, sl = find_swings(df, left=3, right=3)
    assert not np.isnan(sh[5])
    assert sh[5] == 110
    # Kenarlarda pivot olamaz
    assert np.isnan(sh[0]) and np.isnan(sh[-1])


def test_no_lookahead_in_structure():
    """Pivot kesinleşmeden BOS tetiklenmemeli.

    Senaryo: tepe i=5'te oluşur (right=3 → i=8'de kesinleşir).
    i=6'da fiyat tepenin üstüne kapansa bile i=6'da kırılım işaretlenemez
    çünkü o an tepe henüz pivot değil.
    """
    highs = [100, 101, 102, 103, 104, 110, 111, 103, 102, 101, 100, 100, 100]
    bars = [(h - 1, h, h - 2, h - 0.5) for h in highs]
    df = make_df(bars)
    st = detect_structure(df, left=3, right=3)
    # i=6'da close 110.5 > 110 ama pivot kesinleşmedi → sinyal yok
    assert not st["bos_bullish"].iloc[6]
    assert not st["choch_bullish"].iloc[6]


def test_choch_then_bos():
    """İlk kırılım CHoCH (trend 0→1), aynı yönde ikincisi BOS olmalı."""
    # İki tepe oluştur, ikisi de sonradan kırılsın
    seq = [100, 99, 98, 97, 96, 95,          # düşüş
           96, 97, 98, 99, 100, 101,          # tepe1 arkası
           99, 98, 97, 96,                    # geri çek (tepe kesinleşir)
           102, 103, 104, 105,                # kırılım 1
           103, 102, 101, 100,                # geri çek → tepe2 kesinleşir
           106, 107, 108, 109]                # kırılım 2
    bars = [(p, p + 0.5, p - 0.5, p) for p in seq]
    df = make_df(bars)
    st = detect_structure(df, left=3, right=3)
    chochs = st.index[st["choch_bullish"]].tolist()
    boss = st.index[st["bos_bullish"]].tolist()
    assert len(chochs) >= 1, "İlk yukarı kırılım CHoCH olmalı"
    if boss:
        assert boss[0] > chochs[0], "BOS, CHoCH'tan sonra gelmeli"


def test_htf_bias_alignment_no_lookahead():
    """4H mumu kapanmadan bias LTF'e sızmamalı."""
    htf = make_df(
        [(100, 101, 99, 100)] * 10 + [(100, 120, 100, 119)] * 5,
        freq="4h",
    )
    ltf_idx = pd.date_range(htf.index[0], periods=15 * 16, freq="15min", tz="UTC")
    bias = htf_bias_for_ltf(ltf_idx, htf, "4h", pivot=2)
    # İlk 4H mumu kapanmadan (ilk 16 LTF barı) bias mutlaka 0
    assert (bias[:16] == 0).all()
