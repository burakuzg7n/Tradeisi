"""Kural dili: stratejiyi kod yazmadan, metinle tanimlama.

Superalgos'un dugum/kosul tabanli strateji tanimindan ve Vibe-Trading'in
'yaziyla strateji' fikrinden esinli. Ifadeler guvenli bir ayristiricidan gecer
(eval YOK): yalniz asagidaki adlar, sayilar, karsilastirmalar ve and/or/not.

Seriler   : open high low close volume
Islevler  : ema(n) sma(n) rsi(n) atr(n) highest(n) lowest(n) roc(n) zscore(n) std(n)
            (ilk arguman seri olabilir: ema(volume, 20); verilmezse close;
             highest varsayilan high, lowest varsayilan low kullanir)
            cross_up(a, b) cross_down(a, b) abs(x) max(a, b) min(a, b)
Gecmis    : x[1] = bir onceki bar, x[n] = n bar once
Ornek     : cross_up(ema(20), ema(50)) and close > ema(200) and rsi(14) < 70
"""
from __future__ import annotations

import ast
import json
import os
import re

import numpy as np

from . import gostergeler as g
from .strateji import DiziStrateji

KURAL_KLASORU = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kurallar")
_SERI_ISLEV = {"ema": g.ema, "sma": g.sma, "rsi": g.rsi, "highest": g.highest, "lowest": g.lowest,
               "roc": g.roc, "zscore": g.zscore, "std": g.std}
_VARSAYILAN_SERI = {"highest": "high", "lowest": "low"}
_KARSILASTIR = {ast.Gt: np.greater, ast.Lt: np.less, ast.GtE: np.greater_equal,
                ast.LtE: np.less_equal, ast.Eq: np.equal, ast.NotEq: np.not_equal}
_ISLEM = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide}


class KuralHatasi(ValueError):
    pass


class Degerlendirici:
    def __init__(self, bars):
        self.seri = {"open": bars.o, "high": bars.h, "low": bars.l, "close": bars.c,
                     "volume": bars.v}
        self.bars = bars
        self.n = len(bars)
        self._onbellek: dict = {}

    def hesapla(self, ifade: str) -> np.ndarray:
        """Ifadeyi bool diziye cevirir (nan = False)."""
        if not ifade or not str(ifade).strip():
            return np.zeros(self.n, dtype=bool)
        try:
            agac = ast.parse(str(ifade).strip(), mode="eval")
        except SyntaxError as e:
            raise KuralHatasi(f"Yazim hatasi: {ifade!r} ({e.msg})") from e
        with np.errstate(divide="ignore", invalid="ignore"):
            deger = self._d(agac.body)
        dizi = np.broadcast_to(np.asarray(deger), (self.n,))
        if dizi.dtype != bool:
            dizi = np.nan_to_num(dizi.astype(float), nan=0.0) != 0
        return np.array(dizi, dtype=bool)

    def _sayi(self, dugum) -> float:
        v = self._d(dugum)
        if isinstance(v, np.ndarray):
            raise KuralHatasi("Burada sabit bir sayi bekleniyor (ornek: ema(20)).")
        return float(v)

    def _d(self, d):
        if isinstance(d, ast.Constant):
            if isinstance(d.value, bool) or not isinstance(d.value, (int, float)):
                raise KuralHatasi(f"Izin verilmeyen sabit: {d.value!r}")
            return float(d.value)
        if isinstance(d, ast.Name):
            if d.id not in self.seri:
                raise KuralHatasi(f"Bilinmeyen ad: {d.id!r}. Seriler: {', '.join(self.seri)}")
            return self.seri[d.id]
        if isinstance(d, ast.BoolOp):
            parcalar = [self._bool(self._d(v)) for v in d.values]
            fn = np.logical_and if isinstance(d.op, ast.And) else np.logical_or
            out = parcalar[0]
            for p in parcalar[1:]:
                out = fn(out, p)
            return out
        if isinstance(d, ast.UnaryOp):
            if isinstance(d.op, ast.Not):
                return np.logical_not(self._bool(self._d(d.operand)))
            if isinstance(d.op, ast.USub):
                return -self._d(d.operand)
            if isinstance(d.op, ast.UAdd):
                return self._d(d.operand)
        if isinstance(d, ast.BinOp) and type(d.op) in _ISLEM:
            return _ISLEM[type(d.op)](self._d(d.left), self._d(d.right))
        if isinstance(d, ast.Compare):
            sol = self._d(d.left)
            out = None
            for op, sag_d in zip(d.ops, d.comparators):
                if type(op) not in _KARSILASTIR:
                    raise KuralHatasi("Desteklenmeyen karsilastirma.")
                sag = self._d(sag_d)
                parca = _KARSILASTIR[type(op)](sol, sag)
                out = parca if out is None else np.logical_and(out, parca)
                sol = sag
            return out
        if isinstance(d, ast.Subscript):
            return g.shift(np.broadcast_to(np.asarray(self._d(d.value), dtype=float), (self.n,)),
                           int(self._sayi(d.slice)))
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and not d.keywords:
            return self._cagri(d.func.id, d.args, ast.dump(d))
        raise KuralHatasi(f"Izin verilmeyen ifade: {ast.dump(d)[:60]}")

    @staticmethod
    def _bool(v):
        a = np.asarray(v)
        return a if a.dtype == bool else np.nan_to_num(a.astype(float), nan=0.0) != 0

    def _cagri(self, ad: str, args: list, anahtar: str):
        if anahtar in self._onbellek:
            return self._onbellek[anahtar]
        if ad in _SERI_ISLEV:
            if len(args) == 1:
                seri, n = self.seri[_VARSAYILAN_SERI.get(ad, "close")], self._sayi(args[0])
            elif len(args) == 2:
                seri, n = self._d(args[0]), self._sayi(args[1])
            else:
                raise KuralHatasi(f"{ad}(n) ya da {ad}(seri, n) seklinde yazin.")
            if not 1 <= n <= 5000:
                raise KuralHatasi(f"{ad}: periyot 1-5000 arasinda olmali.")
            out = _SERI_ISLEV[ad](np.broadcast_to(np.asarray(seri, dtype=float), (self.n,)), int(n))
        elif ad == "atr":
            n = self._sayi(args[0]) if args else 14
            out = g.atr(self.bars.h, self.bars.l, self.bars.c, int(n))
        elif ad in ("cross_up", "cross_down") and len(args) == 2:
            fn = g.cross_up if ad == "cross_up" else g.cross_down
            out = fn(np.broadcast_to(np.asarray(self._d(args[0]), float), (self.n,)),
                     np.broadcast_to(np.asarray(self._d(args[1]), float), (self.n,)))
        elif ad == "abs" and len(args) == 1:
            out = np.abs(self._d(args[0]))
        elif ad in ("max", "min") and len(args) == 2:
            out = (np.fmax if ad == "max" else np.fmin)(self._d(args[0]), self._d(args[1]))
        else:
            raise KuralHatasi(f"Bilinmeyen islev ya da yanlis arguman: {ad}")
        self._onbellek[anahtar] = out
        return out


class KuralStratejisi(DiziStrateji):
    kaynak = "Superalgos + Vibe-Trading"

    def __init__(self, tanim: dict):
        self.tanim = tanim
        self.ad = "kural_" + re.sub(r"[^a-z0-9_]", "_", str(tanim.get("ad", "adsiz")).lower())
        self.baslik = tanim.get("aciklama") or tanim.get("ad", "Kural stratejisi")
        self.stop_atr = float(tanim.get("stop_atr", 2.0))
        self.kar_atr = float(tanim.get("kar_atr", 0.0))

    def diziler(self, sembol, bars, piyasa):
        d = Degerlendirici(bars)
        return {"le": d.hesapla(self.tanim.get("long_giris", "")),
                "lx": d.hesapla(self.tanim.get("long_cikis", "")),
                "se": d.hesapla(self.tanim.get("short_giris", "")),
                "sx": d.hesapla(self.tanim.get("short_cikis", ""))}

    def neden(self, sembol, i, yon):
        return f"kural: {self.tanim.get('long_giris' if yon > 0 else 'short_giris', '')}"


def dogrula(tanim: dict) -> None:
    """Tum ifadeleri kucuk bir sentetik veri uzerinde dener; hata varsa KuralHatasi."""
    from .veri import sentetik
    d = Degerlendirici(sentetik("DOGRULAMA", 400))
    if not str(tanim.get("long_giris", "")).strip() and not str(tanim.get("short_giris", "")).strip():
        raise KuralHatasi("En az bir giris kurali gerekli (long_giris ya da short_giris).")
    for alan in ("long_giris", "long_cikis", "short_giris", "short_cikis"):
        d.hesapla(tanim.get(alan, ""))


def kurallari_yukle(klasor: str | None = None) -> list:
    klasor = klasor or KURAL_KLASORU
    out = []
    if not os.path.isdir(klasor):
        return out
    for dosya in sorted(os.listdir(klasor)):
        if not dosya.endswith(".json"):
            continue
        try:
            with open(os.path.join(klasor, dosya), encoding="utf-8-sig") as f:
                tanim = json.load(f)
            if tanim.get("kapali"):
                continue
            dogrula(tanim)
            out.append(KuralStratejisi(tanim))
        except (OSError, ValueError) as e:
            print(f"UYARI: kural dosyasi atlandi ({dosya}): {e}")
    return out


def kural_kaydet(ad: str, long_giris: str, long_cikis: str = "", short_giris: str = "",
                 short_cikis: str = "", stop_atr: float = 2.0, kar_atr: float = 0.0,
                 aciklama: str = "", klasor: str | None = None) -> str:
    tanim = {"ad": ad, "aciklama": aciklama or ad, "long_giris": long_giris,
             "long_cikis": long_cikis, "short_giris": short_giris, "short_cikis": short_cikis,
             "stop_atr": stop_atr, "kar_atr": kar_atr}
    dogrula(tanim)
    klasor = klasor or KURAL_KLASORU
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, re.sub(r"[^a-z0-9_]", "_", ad.lower()) + ".json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(tanim, f, indent=2, ensure_ascii=False)
    return yol
