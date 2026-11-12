"""Motor sonucunu panelin okudugu JSON'a cevirir ve diske yazar."""
from __future__ import annotations

import csv
import json
import math
import os
import time

import numpy as np

from . import olcum
from .ayar import cikti_klasoru
from .veri import degistir


def _temiz(x):
    if isinstance(x, float):
        return None if (math.isnan(x) or math.isinf(x)) else x
    if isinstance(x, dict):
        return {k: _temiz(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_temiz(v) for v in x]
    return x


def maliyet_orani(sonuc) -> float | None:
    """Gidis-donus maliyetinin (komisyon + kayma, iki yon) 2 ATR'lik stop mesafesine orani:
    'islem basina kac R maliyet'. Degerlendirilen donemde, semboller arasi medyan."""
    p, a = sonuc.piyasa, sonuc.ayar
    maliyet = 2.0 * (float(a["komisyon_bps"]) + float(a["kayma_bps"])) / 10_000.0
    oranlar = []
    for s in p.semboller:
        i = p.idx[s][sonuc.k_bas:sonuc.k_son + 1]
        i = i[i >= 0]
        if len(i) == 0:
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            atr_orani = p.atr[s][i] / p.barlar[s].c[i]
        if np.isfinite(atr_orani).any():
            oranlar.append(maliyet / (2.0 * float(np.nanmedian(atr_orani))))
    return float(np.median(oranlar)) if oranlar else None


def olustur(sonuc, mod: str, not_: str = "") -> dict:
    p, a = sonuc.piyasa, sonuc.ayar
    sermaye = float(a["baslangic_sermaye"])
    k_son = sonuc.k_son
    tablo = []
    for s in sonuc.stratejiler:
        h = sonuc.hesaplar[s.ad]
        o = olcum.ozet(h.egri, h.islemler, p.adim_ms, sermaye)
        pozlar = [{"sembol": q.sembol, "yon": 1 if q.adet > 0 else -1, "adet": abs(q.adet),
                   "giris": q.giris, "stop": q.stop, "kar": q.kar, "fiyat": q.son_fiyat,
                   "pnl": q.adet * (q.son_fiyat - q.giris), "ts": q.ts_giris, "neden": q.neden}
                  for q in h.poz.values()]
        maliyet = sum(t["maliyet"] for t in h.islemler)
        net = sum(t["pnl"] for t in h.islemler)
        tablo.append({"ad": s.ad, "baslik": s.baslik, "kaynak": s.kaynak, "pozisyonlar": pozlar,
                      "kilitli": k_son < h.kilit_k, "komisyon": h.komisyon, "maliyet": maliyet,
                      "net_pnl": net, "brut_pnl": net + maliyet, **o})
    tablo.sort(key=lambda r: -r["ozsermaye"])
    n = len(sonuc.egri_ts)
    adim = max(1, -(-n // 300))
    secim = list(range(0, n, adim))
    if n and secim[-1] != n - 1:
        secim.append(n - 1)
    egriler = {ad: [round(h.egri[i], 2) for i in secim] for ad, h in sonuc.hesaplar.items()}
    islemler = []
    for ad, h in sonuc.hesaplar.items():
        for t in h.islemler[-60:]:
            islemler.append({"strateji": ad, **t})
    islemler.sort(key=lambda t: -t["ts_cikis"])
    fiyatlar = {s: float(p.barlar[s].c[-1]) for s in p.semboller}
    kurul = {}
    for s in sonuc.stratejiler:
        if hasattr(s, "puanlar"):
            for sem in p.semboller:
                kurul[sem] = s.puanlar(sem, len(p.barlar[sem]) - 1)
    return _temiz({
        "mod": mod, "not": not_, "guncelleme": int(time.time() * 1000), "aralik": p.aralik,
        "adim_ms": p.adim_ms, "semboller": p.semboller, "sermaye": sermaye,
        "bas_ts": sonuc.egri_ts[0] if n else None,
        "son_ts": (sonuc.egri_ts[-1] + p.adim_ms) if n else None, "bar_sayisi": n,
        "tablo": tablo, "egri_ts": [sonuc.egri_ts[i] for i in secim], "egriler": egriler,
        "olaylar": sonuc.olaylar[-200:][::-1], "islemler": islemler[:80], "fiyatlar": fiyatlar,
        "kurul": kurul, "maliyet_r": maliyet_orani(sonuc),
        "ayar": {k: a[k] for k in ("risk_yuzde", "komisyon_bps", "kayma_bps", "short_acik",
                                   "dd_siniri", "max_pozisyon", "max_kaldirac", "fuzyon_oy",
                                   "takip")},
    })


def yaz(durum: dict, a: dict, ad: str) -> str:
    yol = os.path.join(cikti_klasoru(a), f"durum_{ad}.json")
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False)
    degistir(gecici, yol)
    return yol


def islemleri_yaz(sonuc, a: dict, ad: str) -> str:
    """Tum kapanmis islemler: kar/zarar analizini kendiniz yapabilmeniz icin CSV."""
    yol = os.path.join(cikti_klasoru(a), f"islemler_{ad}.csv")
    alanlar = ["strateji", "sembol", "yon", "adet", "giris", "cikis", "giris_zamani", "cikis_zamani",
               "bar", "pnl", "maliyet", "r", "giris_neden", "cikis_neden"]
    with open(yol, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(alanlar)
        for st, h in sonuc.hesaplar.items():
            for t in h.islemler:
                w.writerow([st, t["sembol"], "long" if t["yon"] > 0 else "short", f"{t['adet']:.8f}",
                            f"{t['giris']:.8f}", f"{t['cikis']:.8f}", _zaman(t["ts_giris"]),
                            _zaman(t["ts_cikis"]), t["bar"], f"{t['pnl']:.4f}", f"{t['maliyet']:.4f}",
                            "" if t["r"] is None else f"{t['r']:.3f}", t["giris_neden"], t["cikis_neden"]])
    return yol


def egrileri_yaz(sonuc, a: dict, ad: str) -> str:
    yol = os.path.join(cikti_klasoru(a), f"ozsermaye_{ad}.csv")
    adlar = list(sonuc.hesaplar)
    with open(yol, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["zaman"] + adlar)
        for i, ts in enumerate(sonuc.egri_ts):
            w.writerow([_zaman(ts + sonuc.piyasa.adim_ms)] + [f"{sonuc.hesaplar[x].egri[i]:.2f}" for x in adlar])
    return yol


def _zaman(ms: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(ms / 1000)) + " UTC"


def tablo_yazdir(durum: dict) -> None:
    print(f"\n{'#':>2} {'strateji':24} {'özsermaye':>10} {'getiri':>8} {'maks düşüş':>10} "
          f"{'PF':>6} {'işlem':>6} {'kazanma':>8} {'maliyet öncesi':>14} {'maliyet':>9} {'açık':>4}")
    for i, r in enumerate(durum["tablo"], 1):
        pf = "-" if r["pf"] is None else f"{r['pf']:.2f}"
        print(f"{i:>2} {r['ad']:24} {r['ozsermaye']:>10.2f} {r['getiri'] * 100:>7.1f}% "
              f"{r['max_dusus'] * 100:>9.1f}% {pf:>6} {r['islem']:>6} "
              f"{r['kazanma'] * 100:>7.1f}% {r['brut_pnl']:>14.2f} {r['maliyet']:>9.2f} "
              f"{len(r['pozisyonlar']):>4}"
              + ("  [KİLİTLİ]" if r["kilitli"] else ""))
    m = durum.get("maliyet_r")
    if m is not None:
        print(f"\nBu aralıkta ({durum['aralik']}) gidiş-dönüş maliyeti, 2 ATR'lik stopun %{m * 100:.0f}'i: "
              f"işlem başına ≈ {m:.2f} R." + ("  ← maliyet çok yüksek" if m > 0.15 else ""))
    print()
