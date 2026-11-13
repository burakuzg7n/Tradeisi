"""Twin Range Filter — TradingView'daki ayni adli gostergenin (colinmck, MPL-2.0) kurallarinin
numpy ile yeniden yazimi (kod kopyasi degil; Burak'in 13 Kasim 2026 istegi).

Gostergenin yaptigi:
  1) Yumusatilmis aralik: |kapanis - onceki kapanis| -> EMA(per) -> EMA(2*per-1) x carpan.
     Hizli (27, 1.6) ve yavas (55, 2.0) icin ayri hesaplanir, ortalamasi alinir (smrng).
  2) Aralik filtresi: fiyat filtreden smrng'den fazla uzaklasmadikca filtre yerinde durur;
     uzaklasinca fiyati smrng geriden izler (kucuk oynamalari yutar).
  3) Filtrenin smrng ustu / alti iki bant; bantlar SuperTrend gibi yalniz fiyata dogru
     sikisir (ust bant yalniz iner, alt bant yalniz cikar; kapanis disina tasinca sifirlanir).
  4) TRF cizgisi: yukari trendde alt bant, asagi trendde ust bant. Kapanis cizgiyi yukari
     keserse AL, asagi keserse SAT. Yani surekli pozisyonda kalan bir "dur ve don" trend sistemi.

Parametreler gostergenin varsayilanlaridir; hicbir veriye bakilarak ayarlanmamistir.
Gostergede stop yoktur (cikis = ters sinyal). Burada motor ek olarak giristen stop_atr x ATR
uzakta koruyucu stop tutar: boyut hesabi (islem basi %risk) icin gerekli. 3 ATR, cizginin
tipik uzakligindan (~2 x smrng ~ 2,4 ATR) genis secildi ki normalde once ters sinyal cikarsin;
sonuca bakilarak secilmedi.

Fuzyon oylamasina KATILMAZ (oy_verir = False): mevcut 'fuzyon' hesabinin gecmis ve canli
kaydi bu stratejinin eklenmesiyle degismesin diye.
"""
import numpy as np

from .. import gostergeler as g
from ..strateji import DiziStrateji


def yumusak_aralik(c, per: int, carpan: float) -> np.ndarray:
    fark = np.abs(np.diff(np.asarray(c, dtype=float), prepend=np.nan))
    return g.ema(g.ema(fark, per), 2 * per - 1) * carpan


def twin_range(c, per1: int = 27, mult1: float = 1.6, per2: int = 55, mult2: float = 2.0):
    """(trf, filt, smrng) dizilerini dondurur. Nedensel: i. deger yalniz 0..i barlarini kullanir."""
    c = np.asarray(c, dtype=float)
    smrng = (yumusak_aralik(c, per1, mult1) + yumusak_aralik(c, per2, mult2)) / 2.0
    n = len(c)
    trf = np.full(n, np.nan)
    filt = np.full(n, np.nan)
    cs, rs = c.tolist(), smrng.tolist()
    nan = float("nan")
    f_on = 0.0                       # Pine: nz(rngfilt[1])
    fub_on, flb_on, trf_on = nan, 0.0, 0.0   # Pine'da isinma barlarindaki degerler
    for i in range(1, n):
        r, x = rs[i], cs[i]
        if r != r or x != x:
            continue
        if x > f_on:
            f = f_on if x - r < f_on else x - r
        else:
            f = f_on if x + r > f_on else x + r
        ust, alt = f + r, f - r
        c1 = cs[i - 1]
        fub_nz = 0.0 if fub_on != fub_on else fub_on
        fub = ust if (ust < fub_nz or c1 > fub_nz) else fub_nz
        flb = alt if (alt > flb_on or c1 < flb_on) else flb_on
        if trf_on == fub_on:
            t = fub if x <= fub else flb
        elif trf_on == flb_on:
            t = flb if x >= flb else fub
        else:
            t = fub
        trf[i], filt[i] = t, f
        f_on, fub_on, flb_on, trf_on = f, fub, flb, t
    return trf, filt, smrng


class TwinRange(DiziStrateji):
    ad = "twin_range"
    baslik = "Twin Range Filter: kapanış filtre çizgisini kesince dön (27/1.6 + 55/2.0)"
    kaynak = "TradingView / colinmck"
    oy_verir = False
    stop_atr = 3.0
    per1, mult1, per2, mult2 = 27, 1.6, 55, 2.0

    def diziler(self, sembol, bars, piyasa):
        trf, _, _ = twin_range(bars.c, self.per1, self.mult1, self.per2, self.mult2)
        al, sat = g.cross_up(bars.c, trf), g.cross_down(bars.c, trf)
        return {"le": al, "se": sat, "lx": sat, "sx": al}

    def neden(self, sembol, i, yon):
        return f"Twin Range: kapanış filtre çizgisinin {'üstüne çıktı' if yon > 0 else 'altına indi'}"
