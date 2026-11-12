"""Veri katmani: Binance acik (anahtarsiz) mum verisi, CSV onbellek, sentetik veri, Piyasa hizalamasi.

CSV bicimi projedeki mevcut dosyalarla aynidir: timestamp(ms, bar ACILISI),open,high,low,close,volume
"""
from __future__ import annotations

import atexit
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass

import numpy as np

from . import gostergeler as g

ARALIK_MS = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "10m": 600_000, "15m": 900_000,
             "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
             "1d": 86_400_000}
# Binance'te hazir olmayan araliklar daha kucuk bir araliktan toplanarak uretilir
TUREV = {"10m": "5m"}
# Yalniz Binance'in resmi acik veri uclari
SUNUCULAR = ("https://api.binance.com", "https://data-api.binance.vision",
             "https://api1.binance.com", "https://api-gcp.binance.com")
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Bars:
    ts: np.ndarray  # int64 ms, bar acilis zamani
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray

    def __len__(self) -> int:
        return len(self.ts)

    @staticmethod
    def bos() -> "Bars":
        z = np.array([], dtype=float)
        return Bars(np.array([], dtype=np.int64), z, z.copy(), z.copy(), z.copy(), z.copy())

    @staticmethod
    def satirlardan(satirlar) -> "Bars":
        if len(satirlar) == 0:
            return Bars.bos()
        a = np.asarray(satirlar, dtype=float)
        a = a[np.argsort(a[:, 0], kind="stable")]
        _, ilk = np.unique(a[:, 0], return_index=True)
        a = a[ilk]
        return Bars(a[:, 0].astype(np.int64), a[:, 1].copy(), a[:, 2].copy(), a[:, 3].copy(),
                    a[:, 4].copy(), a[:, 5].copy())

    def satirlar(self) -> np.ndarray:
        return np.column_stack([self.ts.astype(float), self.o, self.h, self.l, self.c, self.v])

    def kes(self, bas_ts: int | None = None, son_ts: int | None = None) -> "Bars":
        m = np.ones(len(self), dtype=bool)
        if bas_ts is not None:
            m &= self.ts >= bas_ts
        if son_ts is not None:
            m &= self.ts <= son_ts
        return Bars(self.ts[m], self.o[m], self.h[m], self.l[m], self.c[m], self.v[m])


def degistir(gecici: str, yol: str) -> None:
    """os.replace, Windows'ta hedef dosya baska bir programca (OneDrive, tarayici) acikken
    PermissionError verir; kisa araliklarla yeniden dener."""
    for deneme in range(8):
        try:
            os.replace(gecici, yol)
            return
        except PermissionError:
            if deneme == 7:
                raise
            time.sleep(0.25)


def veri_klasoru(klasor: str | None = None) -> str:
    yol = klasor or os.path.join(KOK, "data")
    os.makedirs(yol, exist_ok=True)
    return yol


def csv_yolu(sembol: str, aralik: str, klasor: str | None = None) -> str:
    return os.path.join(veri_klasoru(klasor), f"{sembol}_{aralik}.csv")


# yol -> {"imza": (mtime_ns, boyut), "bars": Bars, "bekleyen": diske henuz yazilmamis mum sayisi,
#         "son_yazim": zaman}. Kisa araliklarda dosyayi her mumda yeniden okumamak VE yazmamak icin.
_ONBELLEK: dict = {}
YAZ_BEKLET_SN = 1800      # kisa aralikta yeni mumlar en gec bu kadar sonra diske yazilir
YAZ_BEKLET_MUM = 60       # ya da bu kadar mum birikince (hangisi once olursa)


def _onbellege_koy(yol: str, bars: Bars) -> None:
    try:
        st = os.stat(yol)
        _ONBELLEK[yol] = {"imza": (st.st_mtime_ns, st.st_size), "bars": bars, "bekleyen": 0,
                          "son_yazim": time.time()}
    except OSError:
        _ONBELLEK.pop(yol, None)


def bekleyenleri_yaz() -> int:
    """Bellekte bekleyen mumlari diske yazar (servis dururken ve surec kapanirken cagrilir).
    Yazilamazsa veri kaybolmaz: bir sonraki acilista eksik mumlar yeniden indirilir."""
    n = 0
    for yol, k in list(_ONBELLEK.items()):
        if k["bekleyen"] > 0:
            try:
                bars = k["bars"]
                i = len(bars) - k["bekleyen"]
                csv_ekle(yol, Bars(bars.ts[i:], bars.o[i:], bars.h[i:], bars.l[i:], bars.c[i:], bars.v[i:]))
                n += k["bekleyen"]
                _onbellege_koy(yol, bars)
            except OSError:
                pass
    return n


atexit.register(bekleyenleri_yaz)


def csv_oku(yol: str) -> Bars:
    """Dondurulen Bars onbellekte paylasilir: cagiran dizileri DEGISTIRMEMELIDIR."""
    try:
        st = os.stat(yol)
    except OSError:
        return Bars.bos()
    kayit = _ONBELLEK.get(yol)
    if kayit is not None and kayit["imza"] == (st.st_mtime_ns, st.st_size):
        return kayit["bars"]                    # diske henuz yazilmamis mumlar dahil
    try:
        a = np.loadtxt(yol, delimiter=",", skiprows=1, ndmin=2)
    except ValueError:
        return Bars.bos()
    bars = Bars.satirlardan(a[:, :6]) if a.size else Bars.bos()
    _ONBELLEK[yol] = {"imza": (st.st_mtime_ns, st.st_size), "bars": bars, "bekleyen": 0,
                      "son_yazim": time.time()}
    return bars


def topla(bars: Bars, kaynak_adim: int, hedef_adim: int) -> Bars:
    """Kucuk mumlari buyuk muma toplar (ornek 5m -> 10m). Yalniz KAPANMIS hedef mumlar doner:
    son grubun kapanisi, eldeki son kucuk mumun kapanisindan sonraysa o grup atilir."""
    if len(bars) == 0:
        return Bars.bos()
    grup = bars.ts // hedef_adim
    bas = np.flatnonzero(np.diff(grup, prepend=grup[0] - 1))
    son = np.append(bas[1:], len(bars)) - 1
    out = Bars(grup[bas] * hedef_adim, bars.o[bas].copy(), np.maximum.reduceat(bars.h, bas),
               np.minimum.reduceat(bars.l, bas), bars.c[son].copy(), np.add.reduceat(bars.v, bas))
    if int(out.ts[-1]) + hedef_adim > int(bars.ts[-1]) + kaynak_adim:
        out = Bars(out.ts[:-1], out.o[:-1], out.h[:-1], out.l[:-1], out.c[:-1], out.v[:-1])
    return out


def oku(sembol: str, aralik: str, klasor: str | None = None) -> Bars:
    """Onbellekteki mumlar; turetilmis araliklar (10m) taban araliktan toplanir."""
    taban = TUREV.get(aralik)
    if taban is None:
        return csv_oku(csv_yolu(sembol, aralik, klasor))
    return topla(csv_oku(csv_yolu(sembol, taban, klasor)), ARALIK_MS[taban], ARALIK_MS[aralik])


def _satir_yaz(f, bars: Bars) -> None:
    for t, o, h, l, c, v in zip(bars.ts.tolist(), bars.o.tolist(), bars.h.tolist(),
                                bars.l.tolist(), bars.c.tolist(), bars.v.tolist()):
        f.write(f"{int(t)},{o!r},{h!r},{l!r},{c!r},{v!r}\n")


def csv_yaz(yol: str, bars: Bars) -> None:
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8", newline="\n") as f:
        f.write("timestamp,open,high,low,close,volume\n")
        _satir_yaz(f, bars)
    degistir(gecici, yol)
    _onbellege_koy(yol, bars)


def csv_ekle(yol: str, yeni: Bars) -> None:
    """Dosyanin sonuna ekler (15 dakikada bir tum dosyayi yeniden yazmamak icin)."""
    with open(yol, "rb") as f:
        f.seek(0, os.SEEK_END)
        boyut = f.tell()
        son = b"\n"
        if boyut:
            f.seek(boyut - 1)
            son = f.read(1)
    with open(yol, "a", encoding="utf-8", newline="\n") as f:
        if son != b"\n":
            f.write("\n")
        _satir_yaz(f, yeni)


def _http_json(url: str, zaman_asimi: float = 20.0):
    istek = urllib.request.Request(url, headers={"User-Agent": "fuzyon/1.0"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
        return json.loads(r.read().decode("utf-8"))


_SAAT = {"fark": 0, "okundu": 0.0}
_IYI_SUNUCU = {"i": 0}


def sunucu_farki(yenile: bool = False) -> int:
    """Binance saati - bilgisayar saati (ms). Bilgisayar saati kayiksa kapanmamis mumu
    'kapandi' sanmamak icin kullanilir. Okunamazsa son bilinen deger (ilk seferde 0)."""
    if not yenile and time.time() - _SAAT["okundu"] < 1800:
        return _SAAT["fark"]
    for sunucu in SUNUCULAR:
        try:
            t0 = time.time()
            st = int(_http_json(f"{sunucu}/api/v3/time", 8.0)["serverTime"])
            t1 = time.time()
            _SAAT["fark"] = int(st - (t0 + t1) / 2 * 1000)
            _SAAT["okundu"] = t1
            break
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            continue
    else:
        # Internet yok: her cagrida yeniden denemek paneli ve donguyu kilitler; 1 dk sonra dene
        _SAAT["okundu"] = time.time() - 1800 + 60
    return _SAAT["fark"]


def simdi_ms() -> int:
    """Binance saatine gore simdi."""
    return int(time.time() * 1000) + sunucu_farki()


def binance_mumlar(sembol: str, aralik: str, bas_ms: int, son_ms: int | None = None,
                   ilerleme=None) -> Bars:
    """bas_ms'ten itibaren KAPANMIS mumlari indirir. Sunucular sirayla denenir."""
    adim = ARALIK_MS[aralik]
    simdi = simdi_ms()
    son_ms = min(son_ms or simdi, simdi)
    satirlar: list[list[float]] = []
    imlec = int(bas_ms)
    sunucu_i = _IYI_SUNUCU["i"]          # son calisan sunucudan basla (bazi bolgelerde ilki kapali)
    hata_sayisi = 0
    while imlec < son_ms:
        q = urllib.parse.urlencode({"symbol": sembol, "interval": aralik, "startTime": imlec,
                                    "limit": 1000})
        url = f"{SUNUCULAR[sunucu_i]}/api/v3/klines?{q}"
        try:
            parca = _http_json(url)
            if not isinstance(parca, list):
                raise ValueError(f"beklenmeyen yanit: {str(parca)[:80]}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            hata_sayisi += 1
            sunucu_i = (sunucu_i + 1) % len(SUNUCULAR)
            if hata_sayisi > 2 * len(SUNUCULAR):
                raise ConnectionError(f"Binance verisine ulasilamadi ({sembol}): {e}") from e
            time.sleep(1.0)
            continue
        hata_sayisi = 0
        _IYI_SUNUCU["i"] = sunucu_i
        if not parca:
            break
        for k in parca:
            acilis = int(k[0])
            if acilis + adim <= simdi:  # yalniz kapanmis mum (Binance saatine gore)
                satirlar.append([acilis, float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                                 float(k[5])])
        sonraki = int(parca[-1][0]) + adim
        if sonraki <= imlec:
            break
        imlec = sonraki
        if ilerleme:
            ilerleme(sembol, imlec, son_ms)
        if len(parca) < 1000:
            break
        time.sleep(0.12)
    return Bars.satirlardan(satirlar)


def guncelle(sembol: str, aralik: str, gecmis_gun: int, klasor: str | None = None,
             ilerleme=None) -> Bars:
    """CSV onbellegini Binance'ten tamamlar (yalniz sona ekler; baslangic sabit kalir)."""
    taban = TUREV.get(aralik)
    if taban is not None:
        return topla(guncelle(sembol, taban, gecmis_gun, klasor, ilerleme),
                     ARALIK_MS[taban], ARALIK_MS[aralik])
    yol = csv_yolu(sembol, aralik, klasor)
    eski = csv_oku(yol)
    adim = ARALIK_MS[aralik]
    simdi = simdi_ms()
    if len(eski):
        bas = int(eski.ts[-1]) + adim
    else:
        bas = (simdi - gecmis_gun * 86_400_000) // adim * adim
        bas = max(bas, (simdi // adim - MAX_ILK_INDIRME) * adim)     # yanlis ayara karsi sinir
    if bas + adim > simdi:
        return eski
    yeni = binance_mumlar(sembol, aralik, bas, ilerleme=ilerleme)
    if len(yeni) == 0:
        return eski
    if len(eski) == 0:
        csv_yaz(yol, yeni)
        return yeni
    yeni = yeni.kes(bas_ts=int(eski.ts[-1]) + 1)
    if len(yeni) == 0:
        return eski
    hepsi = Bars.satirlardan(np.vstack([eski.satirlar(), yeni.satirlar()]))
    k = _ONBELLEK.get(yol)
    bekleyen = (k["bekleyen"] if k else 0) + len(yeni)
    if (k is None or adim >= 1_800_000 or bekleyen >= YAZ_BEKLET_MUM
            or time.time() - k["son_yazim"] >= YAZ_BEKLET_SN):
        i = len(hepsi) - bekleyen
        csv_ekle(yol, Bars(hepsi.ts[i:], hepsi.o[i:], hepsi.h[i:], hepsi.l[i:], hepsi.c[i:], hepsi.v[i:]))
        _onbellege_koy(yol, hepsi)
    else:                       # kisa aralik: her mumda dosyaya yazma, bellekte tut
        k["bars"], k["bekleyen"] = hepsi, bekleyen
    return hepsi


def hepsini_guncelle(semboller, aralik: str, gecmis_gun: int, klasor: str | None = None,
                     ilerleme=None, tekrar: int = 3) -> str:
    """Tum sembolleri gunceller. Bir sembolun son mumu digerlerinden gerideyse (borsa o mumu
    henuz yayinlamadiysa) kisa bekleyip yeniden dener. Uyari metni dondurur ('' = sorun yok)."""
    adim = ARALIK_MS[aralik]
    uyari = ""
    for deneme in range(max(1, tekrar)):
        sonlar = {}
        try:
            for s in semboller:
                b = guncelle(s, aralik, gecmis_gun, klasor, ilerleme)
                if len(b):
                    sonlar[s] = int(b.ts[-1])
        except ConnectionError as e:
            return f"Veri güncellenemedi, eldeki veriyle devam: {e}"
        beklenen = (simdi_ms() // adim - 1) * adim
        geride = [s for s, t in sonlar.items() if t < beklenen]
        if not geride:
            return ""
        uyari = f"Son mumu gelmeyen semboller: {', '.join(geride)}"
        if deneme < tekrar - 1:
            time.sleep(3.0)
    return uyari


def sentetik(sembol: str, n: int = 6000, aralik: str = "15m", tohum: int = 7,
             bas_ts: int = 1_699_999_200_000, ara_adim: int = 32) -> Bars:
    """Internetsiz deneme/test icin YONSUZ rastgele yuruyus (oynakligi dalgalanir).
    Bilerek hicbir egilim/kalip icermez: demo, stratejileri oldugundan iyi gostermesin.
    Her mum ara_adim ara adimdan uretilir; high/low bu yolun gercek uclaridir (fitiller de
    rastgele yuruyusun parcasidir, sonradan eklenmez)."""
    r = np.random.default_rng(zlib.crc32(sembol.encode()) % 9973 + tohum * 100_003)
    adim = ARALIK_MS[aralik]
    m = int(ara_adim)
    oyn = 0.004 * (1.0 + 0.6 * np.sin(np.arange(n) / 150.0 + r.uniform(0, 6)))
    ara = r.normal(0, 1, (n, m)) * (oyn / np.sqrt(m))[:, None]
    yol = np.cumsum(ara, axis=1)                      # mum ici log yol (acilisa gore)
    son = np.cumsum(yol[:, -1])                       # mum kapanislarinin log duzeyi
    taban = 100.0 * (1 + r.uniform(0, 5))
    onceki = np.concatenate([[0.0], son[:-1]])
    o = taban * np.exp(onceki)
    c = taban * np.exp(son)
    h = taban * np.exp(onceki + np.maximum(yol.max(axis=1), 0.0))
    l = taban * np.exp(onceki + np.minimum(yol.min(axis=1), 0.0))
    v = (1000 + 800 * np.abs(r.normal(0, 1, n))) * (1 + 3 * np.abs(yol[:, -1]) / oyn.mean())
    ts = bas_ts + np.arange(n, dtype=np.int64) * adim
    return Bars(ts, o, h, l, c, v)


class Piyasa:
    """Sembollerin ortak zaman cizgisine hizalanmis hali.

    T[k]            : k. adimin bar ACILIS zamani (ms)
    idx[sembol][k]  : o adimda sembolun bar indeksi, yoksa -1
    atr[sembol]     : ATR(14) (boyutlama ve stop mesafesi icin)
    """

    def __init__(self, barlar: dict[str, Bars], aralik: str):
        self.aralik = aralik
        self.adim_ms = ARALIK_MS[aralik]
        self.barlar = {s: b for s, b in barlar.items() if len(b) > 0}
        self.semboller = list(self.barlar)
        if not self.semboller:
            raise ValueError("Hic veri yok. Once veri indirin (Fuzyon.bat -> 2) ya da 'demo' kullanin.")
        self.T = np.unique(np.concatenate([b.ts for b in self.barlar.values()]))
        self.idx: dict[str, np.ndarray] = {}
        self.atr: dict[str, np.ndarray] = {}
        self._onbellek: dict = {}
        for s, b in self.barlar.items():
            ix = np.full(len(self.T), -1, dtype=np.int64)
            ix[np.searchsorted(self.T, b.ts)] = np.arange(len(b))
            self.idx[s] = ix
            self.atr[s] = g.atr(b.h, b.l, b.c, 14)

    def k_bul(self, ts_ms: int) -> int:
        """ts_ms ve sonrasindaki ilk adimin indeksi."""
        return int(np.searchsorted(self.T, ts_ms, side="left"))

    def oyn_orani(self, sembol: str) -> np.ndarray:
        """ATR/fiyat'in kendi 672 barlik medyanina orani (birden cok strateji kullanir)."""
        if sembol not in self._onbellek:
            with np.errstate(divide="ignore", invalid="ignore"):
                oyn = self.atr[sembol] / self.barlar[sembol].c
                self._onbellek[sembol] = oyn / g.median(oyn, 672)
        return self._onbellek[sembol]

    def hizala(self, kaynak: str, hedef: str, dizi: np.ndarray) -> np.ndarray:
        """kaynak sembolun dizisini hedef sembolun bar indekslerine tasir (eslesmeyen = nan)."""
        kb, hb = self.barlar[kaynak], self.barlar[hedef]
        out = np.full(len(hb), np.nan)
        p = np.searchsorted(kb.ts, hb.ts)
        p_ok = np.clip(p, 0, len(kb) - 1)
        esit = kb.ts[p_ok] == hb.ts
        out[esit] = np.asarray(dizi, dtype=float)[p_ok[esit]]
        return out


MAX_ILK_INDIRME = 120_000   # bir sembol icin ilk indirmede en fazla mum
ISINMA_BAR = 22_000   # degerlendirme baslangicindan once tutulan bar (Q-ajan egitimi + gostergeler)


def piyasa_yukle(semboller, aralik: str, klasor: str | None = None, sentetik_mi: bool = False,
                 sentetik_n: int = 6000) -> Piyasa:
    barlar = {}
    for s in semboller:
        barlar[s] = sentetik(s, sentetik_n, aralik) if sentetik_mi else oku(s, aralik, klasor)
    return Piyasa(barlar, aralik)


def kirp(piyasa: Piyasa, bas_ts: int) -> Piyasa:
    """Degerlendirme baslangicindan ISINMA_BAR oncesine kadar olan gecmisi atar. Baslangic
    sabit oldugu surece kesim noktasi da sabittir (yeniden oynatma deterministik kalir);
    yillarca veri varken her turda hepsini hesaplamayi onler."""
    kesim = int(bas_ts) - ISINMA_BAR * piyasa.adim_ms
    if kesim <= int(piyasa.T[0]):
        return piyasa
    return Piyasa({s: b.kes(bas_ts=kesim) for s, b in piyasa.barlar.items()}, piyasa.aralik)
