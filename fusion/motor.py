"""Olay motoru + kagit hesap.

Backtest ve canli AYNI kodu kullanir: canli mod, baslangic anindan bugune kadar olan
barlari her yeni mumda deterministik olarak yeniden oynatir (durum dosyasi gerekmez,
cokme sonrasi ayni yerden devam eder).

Bar k icin sira (her hesapta):
  1) k-1 kapanisinda verilen emirler k barinin ACILISINDA dolar (kayma + komisyon)
  2) bar ici stop / kar-al kontrolu (ayni barda ikisi de degdiyse STOP sayilir)
  3) kapanista degerleme, DD kilidi
  4) strateji k kapanisini gorur, k+1 acilisi icin emir verir (lookahead yok)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .veri import Piyasa


@dataclass
class Emir:
    sembol: str
    yon: int                      # +1 long, -1 short, 0 pozisyonu kapat
    stop_mesafe: float | None = None   # fiyat cinsinden mesafe (giris fiyatina gore)
    kar_mesafe: float | None = None
    agirlik: float | None = None  # stopsuz emirde ozsermaye orani
    carpan: float = 1.0           # risk yoneticisi olcegi
    neden: str = ""
    yas: int = 0


@dataclass
class Pozisyon:
    sembol: str
    adet: float                   # isaretli: + long, - short
    giris: float
    stop: float | None
    kar: float | None
    k_giris: int
    ts_giris: int
    neden: str
    giris_komisyon: float
    risk: float                   # stop'a kadar planlanan kayip (USDT), yoksa 0
    son_fiyat: float = 0.0


@dataclass
class Hesap:
    ad: str
    nakit: float
    poz: dict = field(default_factory=dict)
    bekleyen: dict = field(default_factory=dict)   # sembol -> Emir
    islemler: list = field(default_factory=list)
    egri: list = field(default_factory=list)
    son_oz: float = 0.0
    tepe: float = 0.0
    kilit_k: int = -1
    bekleme: dict = field(default_factory=dict)
    komisyon: float = 0.0

    def isaret(self, sembol: str) -> int:
        p = self.poz.get(sembol)
        return 0 if p is None else (1 if p.adet > 0 else -1)

    def niyet(self, sembol: str) -> int:
        """Bekleyen emir uygulanmis gibi yon: stratejiler bununla karar verir."""
        e = self.bekleyen.get(sembol)
        return e.yon if e is not None else self.isaret(sembol)


@dataclass
class Baglam:
    piyasa: Piyasa
    ayar: dict
    hesaplar: dict
    idx: dict
    h: dict
    l: dict
    c: dict
    atr: dict
    oy_verenler: frozenset = frozenset()
    k: int = 0


@dataclass
class Sonuc:
    piyasa: Piyasa
    ayar: dict
    stratejiler: list
    hesaplar: dict
    olaylar: list
    k_bas: int
    k_son: int
    egri_ts: list


class Motor:
    def __init__(self, piyasa: Piyasa, stratejiler: list, ayar: dict):
        self.p = piyasa
        self.stratejiler = stratejiler
        self.a = ayar
        self.kom = float(ayar["komisyon_bps"]) / 10_000.0
        self.kayma = float(ayar["kayma_bps"]) / 10_000.0
        self.T = piyasa.T.tolist()
        self.idx = {s: piyasa.idx[s].tolist() for s in piyasa.semboller}
        self.o = {s: piyasa.barlar[s].o.tolist() for s in piyasa.semboller}
        self.h = {s: piyasa.barlar[s].h.tolist() for s in piyasa.semboller}
        self.l = {s: piyasa.barlar[s].l.tolist() for s in piyasa.semboller}
        self.c = {s: piyasa.barlar[s].c.tolist() for s in piyasa.semboller}
        self.atr = {s: piyasa.atr[s].tolist() for s in piyasa.semboller}
        self.olaylar: list = []

    # ------------------------------------------------------------------ olay
    def _olay(self, ts: int, k: int, hesap: Hesap, tur: str, sembol: str, yon: int,
              fiyat: float | None, neden: str, **ek) -> None:
        o = {"ts": int(ts), "k": k, "strateji": hesap.ad, "tur": tur, "sembol": sembol,
             "yon": yon, "fiyat": fiyat, "neden": neden}
        o.update(ek)
        self.olaylar.append(o)

    # ---------------------------------------------------------------- boyut
    def _boyut(self, h: Hesap, e: Emir, fiyat: float):
        """(adet, risk) ya da None. Hem sinyal aninda (on kontrol) hem dolumda kullanilir.
        Sinirlar: tek pozisyon nominali <= poz_tavan x ozsermaye; tum pozisyonlarin toplam
        nominali <= max_kaldirac x ozsermaye (kapanmak uzere olanlar ve ayni sembol haric)."""
        a = self.a
        oz = h.son_oz
        if oz <= 0 or fiyat <= 0:
            return None
        risk = 0.0
        if e.stop_mesafe and e.stop_mesafe > 0:
            risk = oz * float(a["risk_yuzde"]) / 100.0 * e.carpan
            adet = risk / e.stop_mesafe
        else:
            agirlik = e.agirlik if e.agirlik is not None else 1.0 / int(a["max_pozisyon"])
            adet = oz * agirlik * e.carpan / fiyat
        istenen = adet
        adet = min(adet, oz * float(a["poz_tavan"]) / fiyat)
        brut = 0.0
        for s, q in h.poz.items():
            b = h.bekleyen.get(s)
            if s == e.sembol or (b is not None and b.yon == 0):
                continue
            brut += abs(q.adet) * q.son_fiyat
        kalan = (oz * float(a["max_kaldirac"]) - brut) / fiyat
        if adet > kalan:
            if kalan < 0.5 * adet:      # yer yok: yarim boydan kucuk pozisyon acma
                return None
            adet = kalan
        if adet * fiyat < 1.0:
            return None
        return adet, risk * adet / istenen

    def _girilebilir(self, h: Hesap, e: Emir, k: int, fiyat: float) -> bool:
        """Sinyal aninda on kontrol: dolmayacagi belli olan giris emri SINYAL olarak yayinlanmaz
        (bekleme/kilit/kapasite suresince her barda ayni sinyalin tekrar etmesini onler)."""
        a = self.a
        if k + 1 < h.kilit_k or h.bekleme.get(e.sembol, -1) > k + 1:
            return False
        if e.yon < 0 and not a["short_acik"]:
            return False
        if e.sembol not in h.poz:
            kapanacak = sum(1 for s, b in h.bekleyen.items() if b.yon == 0 and s in h.poz)
            acilacak = sum(1 for s, b in h.bekleyen.items() if b.yon != 0 and s not in h.poz)
            if len(h.poz) - kapanacak + acilacak >= int(a["max_pozisyon"]):
                return False
        return self._boyut(h, e, fiyat) is not None

    # ----------------------------------------------------------------- dolum
    def _kapat(self, h: Hesap, sembol: str, ham_fiyat: float, k: int, neden: str) -> None:
        p = h.poz.pop(sembol)
        yon = 1 if p.adet > 0 else -1
        fiyat = ham_fiyat * (1.0 - yon * self.kayma)
        brut = p.adet * (fiyat - p.giris)
        kom = abs(p.adet) * fiyat * self.kom
        h.nakit += brut - kom
        h.komisyon += kom
        pnl = brut - kom - p.giris_komisyon
        maliyet = kom + p.giris_komisyon + abs(p.adet) * (p.giris + fiyat) * self.kayma
        h.islemler.append({
            "sembol": sembol, "yon": yon, "adet": abs(p.adet), "giris": p.giris, "cikis": fiyat,
            "ts_giris": p.ts_giris, "ts_cikis": self.T[k], "bar": k - p.k_giris, "pnl": pnl,
            "maliyet": maliyet, "r": (pnl / p.risk) if p.risk > 0 else None,
            "giris_neden": p.neden, "cikis_neden": neden,
        })
        if neden.startswith("stop"):
            h.bekleme[sembol] = k + int(self.a["bekleme_bar"])
        self._olay(self.T[k], k, h, "CIKIS", sembol, yon, fiyat, neden, pnl=pnl, adet=abs(p.adet))

    def _ac(self, h: Hesap, e: Emir, acilis: float, k: int) -> None:
        a = self.a
        if k < h.kilit_k or h.bekleme.get(e.sembol, -1) > k:
            return
        if len(h.poz) >= int(a["max_pozisyon"]) or (e.yon < 0 and not a["short_acik"]):
            return
        fiyat = acilis * (1.0 + e.yon * self.kayma)
        boyut = self._boyut(h, e, fiyat)
        if boyut is None:
            return
        adet, risk = boyut
        kom = adet * fiyat * self.kom
        h.nakit -= kom
        h.komisyon += kom
        stop = fiyat - e.yon * e.stop_mesafe if e.stop_mesafe else None
        kar = fiyat + e.yon * e.kar_mesafe if e.kar_mesafe else None
        h.poz[e.sembol] = Pozisyon(e.sembol, e.yon * adet, fiyat, stop, kar, k, self.T[k], e.neden,
                                   kom, risk, fiyat)
        self._olay(self.T[k], k, h, "GIRIS", e.sembol, e.yon, fiyat, e.neden, adet=adet, stop=stop,
                   kar=kar)

    def _dolum(self, h: Hesap, k: int) -> None:
        if not h.bekleyen:
            return
        kalan = {}
        # once kapanislar, sonra girisler (rotasyonda nakit/pozisyon sirasi)
        sirali = sorted(h.bekleyen.values(), key=lambda x: (x.yon != 0, x.sembol))
        h.bekleyen = {}
        for e in sirali:
            i = self.idx[e.sembol][k]
            if i < 0:
                e.yas += 1
                if e.yas < 4:
                    kalan[e.sembol] = e
                continue
            acilis = self.o[e.sembol][i]
            mevcut = h.isaret(e.sembol)
            if e.yon == 0:
                if mevcut:
                    self._kapat(h, e.sembol, acilis, k, e.neden or "sinyal")
            elif mevcut != e.yon:
                if mevcut:
                    self._kapat(h, e.sembol, acilis, k, "ters sinyal")
                self._ac(h, e, acilis, k)
        h.bekleyen = kalan

    def _bar_ici(self, h: Hesap, k: int) -> None:
        for s in list(h.poz):
            i = self.idx[s][k]
            if i < 0:
                continue
            p = h.poz[s]
            o, hi, lo = self.o[s][i], self.h[s][i], self.l[s][i]
            if p.adet > 0:
                if p.stop is not None and lo <= p.stop:
                    self._kapat(h, s, min(o, p.stop), k, "stop")
                elif p.kar is not None and hi >= p.kar:
                    self._kapat(h, s, max(o, p.kar), k, "kar al")
            else:
                if p.stop is not None and hi >= p.stop:
                    self._kapat(h, s, max(o, p.stop), k, "stop")
                elif p.kar is not None and lo <= p.kar:
                    self._kapat(h, s, min(o, p.kar), k, "kar al")

    def _degerle(self, h: Hesap, k: int) -> None:
        oz = h.nakit
        for s, p in h.poz.items():
            i = self.idx[s][k]
            if i >= 0:
                p.son_fiyat = self.c[s][i]
            oz += p.adet * (p.son_fiyat - p.giris)
        h.son_oz = oz
        h.egri.append(oz)
        if oz > h.tepe:
            h.tepe = oz
        if k >= h.kilit_k and h.tepe > 0 and oz <= h.tepe * (1.0 - float(self.a["dd_siniri"])):
            h.kilit_k = k + 1 + int(self.a["dd_kilit_bar"])
            dusus = 1.0 - oz / h.tepe
            h.tepe = oz
            self._olay(self.T[k] + self.p.adim_ms, k, h, "KILIT", "-", 0, None,
                       f"dusus %{dusus * 100:.1f} >= sinir; {int(self.a['dd_kilit_bar'])} bar yeni giris yok")

    # ------------------------------------------------------------------- kos
    def kos(self, k_bas: int, k_son: int | None = None) -> Sonuc:
        p, a = self.p, self.a
        k_son = len(self.T) - 1 if k_son is None else min(k_son, len(self.T) - 1)
        k_bas = max(0, min(k_bas, k_son))
        sermaye = float(a["baslangic_sermaye"])
        hesaplar = {s.ad: Hesap(s.ad, sermaye, son_oz=sermaye, tepe=sermaye) for s in self.stratejiler}
        b = Baglam(p, a, hesaplar, self.idx, self.h, self.l, self.c, self.atr,
                   frozenset(s.ad for s in self.stratejiler if getattr(s, "oy_verir", True)))
        for s in self.stratejiler:
            s.hazirla(p, k_bas, a)
        self.olaylar = []
        kapanis_farki = p.adim_ms
        for k in range(k_bas, k_son + 1):
            b.k = k
            for s in self.stratejiler:
                h = hesaplar[s.ad]
                self._dolum(h, k)
                self._bar_ici(h, k)
                self._degerle(h, k)
                if k < h.kilit_k:
                    for sem in h.poz:
                        h.bekleyen[sem] = Emir(sem, 0, neden="DD kilidi")
                for e in s.bar(k, h, b) or ():
                    i = self.idx[e.sembol][k]
                    fiyat = self.c[e.sembol][i] if i >= 0 else None
                    if h.niyet(e.sembol) == e.yon:
                        continue                      # zaten o yonde / zaten bos: yinelenen emir
                    if e.yon != 0 and (fiyat is None or not self._girilebilir(h, e, k, fiyat)):
                        continue
                    h.bekleyen[e.sembol] = e
                    self._olay(self.T[k] + kapanis_farki, k, h, "SINYAL", e.sembol, e.yon, fiyat,
                               e.neden, stop_mesafe=e.stop_mesafe, kar_mesafe=e.kar_mesafe)
        return Sonuc(p, a, self.stratejiler, hesaplar, self.olaylar, k_bas, k_son,
                     self.T[k_bas:k_son + 1])
