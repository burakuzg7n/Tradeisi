"""Veri katmani: Binance acik (anahtarsiz) mum verisi, CSV onbellek, sentetik veri, Piyasa hizalamasi.

CSV bicimi projedeki mevcut dosyalarla aynidir: timestamp(ms, bar ACILISI),open,high,low,close,volume
"""
from __future__ import annotations

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

ARALIK_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
             "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
SUNUCULAR = ("https://api.binance.com", "https://data-api.binance.vision",
             "https://api1.binance.com", "https://api.binance.me")
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


def veri_klasoru(klasor: str | None = None) -> str:
    yol = klasor or os.path.join(KOK, "data")
    os.makedirs(yol, exist_ok=True)
    return yol


def csv_yolu(sembol: str, aralik: str, klasor: str | None = None) -> str:
    return os.path.join(veri_klasoru(klasor), f"{sembol}_{aralik}.csv")


def csv_oku(yol: str) -> Bars:
    if not os.path.exists(yol):
        return Bars.bos()
    try:
        a = np.loadtxt(yol, delimiter=",", skiprows=1, ndmin=2)
    except ValueError:
        return Bars.bos()
    return Bars.satirlardan(a[:, :6]) if a.size else Bars.bos()


def csv_yaz(yol: str, bars: Bars) -> None:
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8", newline="\n") as f:
        f.write("timestamp,open,high,low,close,volume\n")
        for t, o, h, l, c, v in zip(bars.ts.tolist(), bars.o.tolist(), bars.h.tolist(),
                                    bars.l.tolist(), bars.c.tolist(), bars.v.tolist()):
            f.write(f"{int(t)},{o!r},{h!r},{l!r},{c!r},{v!r}\n")
    os.replace(gecici, yol)


def _http_json(url: str, zaman_asimi: float = 20.0):
    istek = urllib.request.Request(url, headers={"User-Agent": "fuzyon/1.0"})
    with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
        return json.loads(r.read().decode("utf-8"))


def binance_mumlar(sembol: str, aralik: str, bas_ms: int, son_ms: int | None = None,
                   ilerleme=None) -> Bars:
    """bas_ms'ten itibaren KAPANMIS mumlari indirir. Sunucu sirasiyla denenir."""
    adim = ARALIK_MS[aralik]
    simdi = int(time.time() * 1000)
    son_ms = min(son_ms or simdi, simdi)
    satirlar: list[list[float]] = []
    imlec = int(bas_ms)
    sunucu_i = 0
    hata_sayisi = 0
    while imlec < son_ms:
        q = urllib.parse.urlencode({"symbol": sembol, "interval": aralik, "startTime": imlec,
                                    "limit": 1000})
        url = f"{SUNUCULAR[sunucu_i]}/api/v3/klines?{q}"
        try:
            parca = _http_json(url)
        except (urllib.error.URLError, OSError, ValueError) as e:
            hata_sayisi += 1
            sunucu_i = (sunucu_i + 1) % len(SUNUCULAR)
            if hata_sayisi > 2 * len(SUNUCULAR):
                raise ConnectionError(f"Binance verisine ulasilamadi ({sembol}): {e}") from e
            time.sleep(1.0)
            continue
        hata_sayisi = 0
        if not parca:
            break
        for k in parca:
            acilis = int(k[0])
            if acilis + adim <= simdi:  # yalniz kapanmis mum
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
    yol = csv_yolu(sembol, aralik, klasor)
    eski = csv_oku(yol)
    adim = ARALIK_MS[aralik]
    simdi = int(time.time() * 1000)
    if len(eski):
        bas = int(eski.ts[-1]) + adim
    else:
        bas = (simdi - gecmis_gun * 86_400_000) // adim * adim
    if bas + adim > simdi:
        return eski
    yeni = binance_mumlar(sembol, aralik, bas, ilerleme=ilerleme)
    if len(yeni) == 0:
        return eski
    hepsi = Bars.satirlardan(np.vstack([eski.satirlar(), yeni.satirlar()])) if len(eski) else yeni
    csv_yaz(yol, hepsi)
    return hepsi


def sentetik(sembol: str, n: int = 6000, aralik: str = "15m", tohum: int = 7,
             bas_ts: int = 1_700_000_000_000) -> Bars:
    """Internetsiz deneme/test icin rejim degistiren rastgele yuruyus."""
    r = np.random.default_rng(zlib.crc32(sembol.encode()) % 9973 + tohum * 100_003)
    adim = ARALIK_MS[aralik]
    rejim = np.repeat(r.choice([-1.0, 0.0, 1.0], size=n // 200 + 1), 200)[:n]
    oyn = 0.004 * (1.0 + 0.6 * np.sin(np.arange(n) / 150.0 + r.uniform(0, 6)))
    getiri = rejim * 0.0004 + r.normal(0, 1, n) * oyn
    c = 100.0 * (1 + r.uniform(0, 5)) * np.exp(np.cumsum(getiri))
    o = np.concatenate([[c[0]], c[:-1]])
    fitil = np.abs(r.normal(0, 1, n)) * oyn * c * 0.5
    h = np.maximum(o, c) + fitil
    l = np.minimum(o, c) - np.abs(r.normal(0, 1, n)) * oyn * c * 0.5
    v = (1000 + 800 * np.abs(r.normal(0, 1, n))) * (1 + 3 * np.abs(getiri) / oyn.mean())
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
        for s, b in self.barlar.items():
            ix = np.full(len(self.T), -1, dtype=np.int64)
            ix[np.searchsorted(self.T, b.ts)] = np.arange(len(b))
            self.idx[s] = ix
            self.atr[s] = g.atr(b.h, b.l, b.c, 14)

    def k_bul(self, ts_ms: int) -> int:
        """ts_ms ve sonrasindaki ilk adimin indeksi."""
        return int(np.searchsorted(self.T, ts_ms, side="left"))

    def hizala(self, kaynak: str, hedef: str, dizi: np.ndarray) -> np.ndarray:
        """kaynak sembolun dizisini hedef sembolun bar indekslerine tasir (eslesmeyen = nan)."""
        kb, hb = self.barlar[kaynak], self.barlar[hedef]
        out = np.full(len(hb), np.nan)
        p = np.searchsorted(kb.ts, hb.ts)
        p_ok = np.clip(p, 0, len(kb) - 1)
        esit = kb.ts[p_ok] == hb.ts
        out[esit] = np.asarray(dizi, dtype=float)[p_ok[esit]]
        return out


def piyasa_yukle(semboller, aralik: str, klasor: str | None = None, sentetik_mi: bool = False,
                 sentetik_n: int = 6000) -> Piyasa:
    barlar = {}
    for s in semboller:
        barlar[s] = sentetik(s, sentetik_n, aralik) if sentetik_mi else csv_oku(csv_yolu(s, aralik, klasor))
    return Piyasa(barlar, aralik)
