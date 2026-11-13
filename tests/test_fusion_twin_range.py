"""Twin Range Filter stratejisinin testleri (pandas gerektirmez)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from fusion import ayar, stratejiler, veri
from fusion import gostergeler as g
from fusion.motor import Motor
from fusion.stratejiler.twin_range import twin_range


def _seri(n=3000, tohum=3):
    return veri.sentetik("TESTUSDT", n, "4h", tohum).c


def _pine_gibi(c, per1=27, mult1=1.6, per2=55, mult2=2.0):
    """Pine betiginin satir satir, seri/nz/na mantigiyla yavas taklidi (bagimsiz dogrulama)."""
    na = float("nan")
    nz = lambda v: 0.0 if v != v else v
    n = len(c)
    fark = [na] + [abs(c[i] - c[i - 1]) for i in range(1, n)]
    sm = lambda t, m: g.ema(g.ema(fark, t), 2 * t - 1) * m
    smrng = ((sm(per1, mult1) + sm(per2, mult2)) / 2).tolist()
    filt, FUB, FLB, TRF = [na] * n, [na] * n, [na] * n, [na] * n
    for i in range(n):
        x, r = c[i], smrng[i]
        f1 = nz(filt[i - 1]) if i else 0.0
        if x > f1:
            filt[i] = f1 if x - r < f1 else x - r
        else:
            filt[i] = f1 if x + r > f1 else x + r
        STR, STS = filt[i] + r, filt[i] - r
        c1 = c[i - 1] if i else na
        fub1, flb1, trf1 = (FUB[i - 1], FLB[i - 1], TRF[i - 1]) if i else (na, na, na)
        FUB[i] = STR if (STR < nz(fub1) or c1 > nz(fub1)) else nz(fub1)
        FLB[i] = STS if (STS > nz(flb1) or c1 < nz(flb1)) else nz(flb1)
        if nz(trf1) == fub1 and x <= FUB[i]:
            TRF[i] = FUB[i]
        elif nz(trf1) == fub1 and x >= FUB[i]:
            TRF[i] = FLB[i]
        elif nz(trf1) == flb1 and x >= FLB[i]:
            TRF[i] = FLB[i]
        elif nz(trf1) == flb1 and x <= FLB[i]:
            TRF[i] = FUB[i]
        else:
            TRF[i] = FUB[i]
    return np.array(TRF)


def test_pine_taklidiyle_ayni():
    c = _seri()
    trf, _, smrng = twin_range(c)
    ref = _pine_gibi(c.tolist())
    hazir = ~np.isnan(smrng)
    assert hazir.sum() > 2500
    assert np.allclose(trf[hazir], ref[hazir], rtol=0, atol=1e-9)
    # sinyaller de ayni
    assert (g.cross_up(c, trf)[hazir] == g.cross_up(c, ref)[hazir]).all()
    assert (g.cross_down(c, trf)[hazir] == g.cross_down(c, ref)[hazir]).all()


def test_nedensel():
    c = _seri()
    tam = twin_range(c)[0]
    for m in (500, 1234, 2999):
        kismi = twin_range(c[:m])[0]
        assert np.array_equal(kismi, tam[:m], equal_nan=True)


def test_sinyaller_sirayla_ve_cizgi_dogru_tarafta():
    c = _seri()
    trf = twin_range(c)[0]
    al, sat = g.cross_up(c, trf), g.cross_down(c, trf)
    assert al.sum() > 10 and sat.sum() > 10
    sira = [1 if al[i] else -1 for i in range(len(c)) if al[i] or sat[i]]
    assert all(a != b for a, b in zip(sira, sira[1:]))        # AL-SAT-AL-SAT...
    yon = 0
    for i in range(len(c)):
        yon = 1 if al[i] else -1 if sat[i] else yon
        if yon > 0:
            assert trf[i] <= c[i]
        elif yon < 0:
            assert trf[i] >= c[i]


def _kos(adlar):
    a = dict(ayar.VARSAYILAN)
    a["stratejiler"] = adlar
    p = veri.piyasa_yukle(["AAAUSDT", "BBBUSDT"], "4h", sentetik_mi=True, sentetik_n=3000)
    return Motor(p, stratejiler.hepsi(a), a).kos(600)


def test_arenada_calisir_ve_fuzyonu_degistirmez():
    once = _kos(["kirilim", "ortalamaya_donus", "ajan_kurulu"])
    sonra = _kos(["kirilim", "ortalamaya_donus", "ajan_kurulu", "twin_range"])
    assert len(sonra.hesaplar["twin_range"].islemler) > 20
    for ad in ("kirilim", "ortalamaya_donus", "ajan_kurulu", "fuzyon"):
        assert once.hesaplar[ad].egri == sonra.hesaplar[ad].egri
    assert "twin_range" in [s.ad for s in stratejiler.hepsi(dict(ayar.VARSAYILAN))]


def test_adim_adim_ile_tek_seferde_ayni():
    a = dict(ayar.VARSAYILAN)
    a["stratejiler"] = ["twin_range"]
    p = veri.piyasa_yukle(["AAAUSDT", "BBBUSDT"], "4h", sentetik_mi=True, sentetik_n=1500)
    tek = Motor(p, stratejiler.hepsi(a), a).kos(600)
    m = Motor(p, stratejiler.hepsi(a), a)
    m.baslat(600)
    for k in range(600, len(p.T), 97):
        m.ilerle(k)
    adim = m.ilerle()
    assert tek.hesaplar["twin_range"].egri == adim.hesaplar["twin_range"].egri


if __name__ == "__main__":
    for ad, fn in list(globals().items()):
        if ad.startswith("test_"):
            fn()
            print("gecti:", ad)
