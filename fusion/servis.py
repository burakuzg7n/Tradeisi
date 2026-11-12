"""Arka plan servisi: tum zaman dilimlerini TEK surecte calistirir, paneli sunar, Telegram'i dinler.

Pencere gerektirmez (Fuzyon.vbs gizli baslatir). Her sey panelden yonetilir:
aralik ac/kapa, bildirim ac/kapa, backtest, Telegram baglantisi, durdurma.
Is parcaciklari:
  * calisan  : vadesi gelen araliklarin canli turunu atar, eksik veriyi indirir, kuyruktaki isleri yapar
  * telegram : bot mesajlarini dinler (/durum vb.), baglanti kurulurken sohbeti yakalar
  * http     : panel (panel.py)
"""
from __future__ import annotations

import collections
import json
import os
import queue
import sys
import threading
import time

from . import ayar as ayar_m
from . import canli, iletim, islem, stratejiler, veri

ONCELIK = ("4h", "1h", "15m", "30m", "2h", "1d", "5m", "10m", "3m", "1m")   # ilk indirme sirasi
VARSAYILAN = {"aktif": list(ONCELIK), "bildirim": ["4h"], "takip": "hepsi"}
YARDIM = ("Füzyon Arena komutları:\n/durum — 4 saatlik tablo\n/durum 15m — başka aralık\n"
          "/araliklar — hangi aralıklar çalışıyor\n/yardim — bu mesaj\n\nKâğıt işlemdir; gerçek emir gönderilmez.")


def ozet_metni(d: dict, en_fazla: int = 8) -> str:
    """Telegram /durum yaniti icin kisa tablo."""
    if not d or d.get("yok"):
        return "Bu aralık için henüz sonuç yok."
    satirlar = [f"Füzyon {d['aralik']} · kâğıt · {time.strftime('%d.%m %H:%M', time.localtime(d['son_ts'] / 1000))}"]
    for i, r in enumerate(d["tablo"][:en_fazla], 1):
        satirlar.append(f"{i}. {r['ad']}: {r['ozsermaye']:.0f} ({r['getiri'] * 100:+.1f}%) · "
                        f"{r['islem']} işlem · {len(r['pozisyonlar'])} açık")
    acik = [f"{'L' if p['yon'] > 0 else 'S'} {p['sembol']} ({r['ad']})"
            for r in d["tablo"] for p in r["pozisyonlar"]]
    if acik:
        satirlar.append("Açık: " + ", ".join(acik[:12]) + (" …" if len(acik) > 12 else ""))
    return "\n".join(satirlar)


class Servis:
    def __init__(self, taban: dict):
        self.taban = taban
        self.kok = ayar_m.cikti_kok(taban)
        self.kilit = threading.RLock()
        self.dur = threading.Event()
        self.kuyruk: queue.Queue = queue.Queue()
        self.gunluk: collections.deque = collections.deque(maxlen=120)
        self.basladi = time.time()
        self.ayarlar = self._ayar_oku()
        self.hal = {ar: self._bos_hal() for ar in ayar_m.ON_AYAR}
        self.tg = {"bot": None, "aday": None, "hata": ""}
        for satir in ayar_m.eski_duzeni_tasi(taban):
            self.log("eski çıktı taşındı: " + satir)

    # ------------------------------------------------------------- ayarlar
    def _ayar_yolu(self) -> str:
        return os.path.join(self.kok, "servis.json")

    def _ayar_oku(self) -> dict:
        a = {k: (list(v) if isinstance(v, list) else v) for k, v in VARSAYILAN.items()}
        try:
            with open(self._ayar_yolu(), encoding="utf-8") as f:
                okunan = json.load(f)
            for k in ("aktif", "bildirim"):
                if isinstance(okunan.get(k), list):
                    a[k] = [x for x in okunan[k] if x in ayar_m.ON_AYAR]
            if isinstance(okunan.get("takip"), str):
                a["takip"] = okunan["takip"]
        except (OSError, ValueError):
            pass
        return a

    def _ayar_yaz(self) -> None:
        gecici = self._ayar_yolu() + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(self.ayarlar, f, indent=2)
        veri.degistir(gecici, self._ayar_yolu())

    @staticmethod
    def _bos_hal() -> dict:
        return {"hazir": False, "asama": "bekliyor", "sira": 0, "islenen": -1, "tekrar_ms": 0,
                "son_tur": 0, "sure": 0.0, "mum": 0, "lider": None, "lider_oz": None, "sinyal": 0,
                "hata": "", "backtest": {"asama": ""}}

    def a_icin(self, aralik: str) -> dict:
        a = dict(self.taban)
        ayar_m.aralik_uygula(a, aralik)
        with self.kilit:
            a["takip"] = self.ayarlar["takip"]
            a["telegram"] = aralik in self.ayarlar["bildirim"]
        return a

    def log(self, mesaj: str) -> None:
        satir = time.strftime("%d.%m %H:%M:%S ") + mesaj
        self.gunluk.append(satir)
        try:
            yol = os.path.join(self.kok, "servis.log")
            if os.path.exists(yol) and os.path.getsize(yol) > 1_000_000:
                os.replace(yol, yol + ".eski")
            with open(yol, "a", encoding="utf-8") as f:
                f.write(satir + "\n")
        except OSError:
            pass

    # ------------------------------------------------- panelden gelen istekler
    def aktif_yap(self, aralik: str, acik: bool) -> None:
        with self.kilit:
            kume = [x for x in self.ayarlar["aktif"] if x != aralik]
            if acik:
                kume.append(aralik)
                if not self.hal[aralik]["hazir"]:
                    self.hal[aralik].update(asama="bekliyor", tekrar_ms=0, hata="")
            self.ayarlar["aktif"] = kume
            self._ayar_yaz()
        self.log(f"{aralik}: canlı takip {'açıldı' if acik else 'kapatıldı'}")

    def bildirim_yap(self, aralik: str, acik: bool) -> None:
        with self.kilit:
            kume = [x for x in self.ayarlar["bildirim"] if x != aralik]
            if acik:
                kume.append(aralik)
            self.ayarlar["bildirim"] = kume
            self._ayar_yaz()
        self.log(f"{aralik}: Telegram bildirimi {'açıldı' if acik else 'kapatıldı'}")

    def takip_yap(self, takip: str) -> None:
        adlar = {"hepsi", "lider"} | {s.ad for s in stratejiler.hepsi(self.taban)}
        if takip not in adlar:
            raise ValueError("Bilinmeyen strateji.")
        with self.kilit:
            self.ayarlar["takip"] = takip
            self._ayar_yaz()
        self.log(f"sinyali iletilen strateji: {takip}")

    def backtest_iste(self, aralik: str) -> None:
        self.hal[aralik]["backtest"] = {"asama": "sirada"}
        self.kuyruk.put(("backtest", aralik))

    # ----------------------------------------------------------- calisan
    def adim(self) -> bool:
        """Tek is yapar; yapacak is yoksa False (cagiran kisa sure bekler)."""
        try:
            is_ = self.kuyruk.get_nowait()
        except queue.Empty:
            is_ = None
        if is_ is not None:
            self._is_yap(is_)
            return True
        simdi = veri.simdi_ms()
        with self.kilit:
            aktif = list(self.ayarlar["aktif"])
        yapildi = False
        for ar in sorted(aktif, key=veri.ARALIK_MS.get):        # kisa aralik gecikmeye en duyarli
            h = self.hal[ar]
            if h["hazir"] and simdi >= h["tekrar_ms"] and simdi // veri.ARALIK_MS[ar] > h["islenen"]:
                self._tur(ar)
                yapildi = True
        if yapildi:
            return True
        for ar in ONCELIK:
            h = self.hal[ar]
            if ar in aktif and not h["hazir"] and simdi >= h["tekrar_ms"]:
                self._hazirla_adim(ar)
                return True
        return False

    def _tur_sonucu(self, ar: str, d: dict, n: int, simdi: int, t0: float) -> None:
        h = self.hal[ar]
        adim = veri.ARALIK_MS[ar]
        en = d["tablo"][0] if d["tablo"] else None
        h.update(asama="calisiyor", hata=d.get("not", ""), son_tur=int(time.time() * 1000),
                 sure=round(time.time() - t0, 2), mum=d["bar_sayisi"], sinyal=h["sinyal"] + n,
                 lider=en["ad"] if en else None, lider_oz=en["ozsermaye"] if en else None)
        if d.get("son_ts") and d["son_ts"] >= (simdi // adim) * adim:
            h["islenen"] = simdi // adim
        else:
            h["tekrar_ms"] = simdi + 15_000                     # son mum henuz gelmemis: az sonra yine dene
        if n:
            self.log(f"{ar}: {n} yeni sinyal")

    def _tur(self, ar: str) -> None:
        h = self.hal[ar]
        a = self.a_icin(ar)
        simdi, t0 = veri.simdi_ms(), time.time()
        try:
            d, n = canli.tur(a, sessiz=True)
        except Exception as e:                                  # servis hicbir hatada durmamali
            h.update(hata=f"{type(e).__name__}: {e}", tekrar_ms=simdi + 30_000)
            canli._OTURUM.pop(canli._kayit_yolu(a), None)
            self.log(f"{ar}: HATA {h['hata']}")
            return
        self._tur_sonucu(ar, d, n, simdi, t0)

    def _hazirla_adim(self, ar: str) -> None:
        """Ilk hazirlik: her cagrida bir sembolun verisini indirir, sonunda ilk turu atar."""
        h = self.hal[ar]
        a = self.a_icin(ar)
        simdi, t0 = veri.simdi_ms(), time.time()
        semboller = a["semboller"]
        h["asama"] = "indiriliyor"
        try:
            if h["sira"] < len(semboller):
                veri.guncelle(semboller[h["sira"]], ar, a["gecmis_gun"], ayar_m.veri_klasoru(a))
                h["sira"] += 1
                h["hata"] = ""
                return
            d, n = canli.tur(a, indir=False, sessiz=True)
        except Exception as e:
            h.update(asama="hata", hata=f"{type(e).__name__}: {e}", tekrar_ms=simdi + 60_000, sira=0)
            self.log(f"{ar}: hazırlık hatası — {h['hata']}")
            return
        h["hazir"] = True
        self._tur_sonucu(ar, d, n, simdi, t0)
        self.log(f"{ar}: hazır ({d['bar_sayisi']} mum oynatıldı, {time.time() - t0:.1f} sn)")
        if self._backtest_eski_mi(a):
            self.backtest_iste(ar)

    @staticmethod
    def _backtest_eski_mi(a: dict) -> bool:
        """Backtest sonucu yoksa, baska coin listesiyle yapilmissa ya da 24 saatten eskiyse."""
        try:
            with open(os.path.join(ayar_m.cikti_klasoru(a), "durum_backtest.json"), encoding="utf-8") as f:
                d = json.load(f)
            return (d.get("mod") != "backtest" or d.get("semboller") != list(a["semboller"])
                    or time.time() * 1000 - d.get("guncelleme", 0) > 86_400_000)
        except (OSError, ValueError):
            return True

    def _is_yap(self, is_: tuple) -> None:
        tur, ar = is_
        if tur != "backtest":
            return
        h = self.hal[ar]
        h["backtest"] = {"asama": "calisiyor"}
        a = self.a_icin(ar)
        try:
            for s in a["semboller"]:
                veri.guncelle(s, ar, a["gecmis_gun"], ayar_m.veri_klasoru(a))
            d, sure, _ = islem.backtest(a)
            h["backtest"] = {"asama": "hazir", "zaman": int(time.time() * 1000), "sure": round(sure, 1)}
            self.log(f"{ar}: backtest bitti ({d['bar_sayisi']} mum, {sure:.1f} sn)")
        except Exception as e:
            h["backtest"] = {"asama": "hata", "hata": f"{type(e).__name__}: {e}"}
            self.log(f"{ar}: backtest hatası — {e}")

    def calis(self) -> None:
        self.log("servis başladı")
        while not self.dur.is_set():
            try:
                if not self.adim():
                    self.dur.wait(0.5)
            except Exception as e:                              # son savunma hatti
                self.log(f"beklenmeyen hata: {type(e).__name__}: {e}")
                self.dur.wait(5.0)
        self.log("servis durdu")

    # ---------------------------------------------------------- telegram
    def telegram_durumu(self) -> dict:
        token, chat = iletim.telegram_ayari()
        if not token:
            return {"durum": "yok", "hata": self.tg["hata"]}
        if not chat:
            aday = self.tg["aday"]
            return {"durum": "aday" if aday else "mesaj_bekleniyor", "bot": self.tg["bot"],
                    "aday": aday["ad"] if aday else None, "hata": self.tg["hata"]}
        return {"durum": "bagli", "bot": self.tg["bot"], "chat_id": chat, "hata": self.tg["hata"]}

    def telegram_token(self, token: str) -> dict:
        token = token.strip()
        if not token or ":" not in token or len(token) > 120 or any(c.isspace() for c in token):
            raise ValueError("Token biçimi geçersiz. BotFather'ın verdiği satırın tamamını yapıştır.")
        ben = iletim.tg(token, "getMe")                         # gecersizse RuntimeError
        iletim.env_yaz({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": None})
        self.tg.update(bot=ben.get("username"), aday=None, hata="")
        self.log(f"Telegram botu kaydedildi: @{ben.get('username')}")
        return self.telegram_durumu()

    def telegram_onayla(self) -> dict:
        aday = self.tg["aday"]
        if not aday:
            raise ValueError("Henüz bota yazılmış bir mesaj görülmedi.")
        iletim.env_yaz({"TELEGRAM_CHAT_ID": aday["id"]})
        self.tg["aday"] = None
        iletim.telegram_gonder("Füzyon Arena bağlandı. Sinyaller buraya gelecek.\n\n" + YARDIM)
        self.log("Telegram sohbeti bağlandı")
        return self.telegram_durumu()

    def telegram_kaldir(self) -> dict:
        iletim.env_yaz({"TELEGRAM_BOT_TOKEN": None, "TELEGRAM_CHAT_ID": None})
        self.tg.update(bot=None, aday=None, hata="")
        self.log("Telegram bağlantısı kaldırıldı")
        return self.telegram_durumu()

    def _durum_oku(self, aralik: str, mod: str = "canli") -> dict:
        try:
            with open(os.path.join(self.kok, aralik, f"durum_{mod}.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"yok": True}

    def komut_yaniti(self, metin_: str) -> str:
        parca = (metin_ or "").strip().split()
        komut = parca[0].split("@")[0].lower() if parca else ""
        if komut in ("/durum", "/status"):
            ar = parca[1].lower() if len(parca) > 1 else "4h"
            if ar not in ayar_m.ON_AYAR:
                return "Aralıklar: " + " ".join(ayar_m.ON_AYAR)
            return ozet_metni(self._durum_oku(ar))
        if komut == "/araliklar":
            with self.kilit:
                aktif, bildirim = list(self.ayarlar["aktif"]), list(self.ayarlar["bildirim"])
            return "\n".join(f"{ar}: {self.hal[ar]['asama'] if ar in aktif else 'kapalı'}"
                             + (" · bildirim açık" if ar in bildirim else "") for ar in ayar_m.ON_AYAR)
        return YARDIM

    def telegram_guncelleme(self, g: dict) -> None:
        """Tek bir getUpdates kaydini isler (testlerde dogrudan cagrilir)."""
        mesaj = g.get("message") or {}
        sohbet = mesaj.get("chat") or {}
        if "id" not in sohbet:
            return
        _, kayitli = iletim.telegram_ayari()
        if not kayitli:
            if sohbet.get("type", "private") == "private":
                self.tg["aday"] = {"id": sohbet["id"],
                                   "ad": sohbet.get("first_name") or sohbet.get("username") or "?"}
            return
        if str(sohbet["id"]) != str(kayitli):
            return                                              # yalniz bagli sohbet yanit alir
        iletim.telegram_gonder(self.komut_yaniti(mesaj.get("text", "")))

    def telegram_dinle(self) -> None:
        ofset = None
        while not self.dur.is_set():
            token, _ = iletim.telegram_ayari()
            if not token:
                ofset = None
                self.dur.wait(3.0)
                continue
            try:
                if self.tg["bot"] is None:
                    self.tg["bot"] = iletim.tg(token, "getMe").get("username")
                for g in iletim.tg(token, "getUpdates", zaman_asimi=35.0, timeout=25, offset=ofset):
                    ofset = g["update_id"] + 1
                    self.telegram_guncelleme(g)
                self.tg["hata"] = ""
            except Exception as e:
                self.tg["hata"] = str(e)
                self.dur.wait(15.0)

    # -------------------------------------------------------------- ozet
    def ozet(self) -> dict:
        simdi = veri.simdi_ms()
        with self.kilit:
            ayarlar = {k: (list(v) if isinstance(v, list) else v) for k, v in self.ayarlar.items()}
        araliklar = []
        for ar in ayar_m.ON_AYAR:
            h = self.hal[ar]
            adim = veri.ARALIK_MS[ar]
            aktif = ar in ayarlar["aktif"]
            n_sembol = len(self.taban["semboller"])
            araliklar.append({
                "aralik": ar, "aktif": aktif, "bildirim": ar in ayarlar["bildirim"],
                "asama": h["asama"] if aktif else "kapali", "hazir": h["hazir"],
                "ilerleme": f"{min(h['sira'], n_sembol)}/{n_sembol}", "son_tur": h["son_tur"],
                "sure": h["sure"], "mum": h["mum"], "lider": h["lider"], "lider_oz": h["lider_oz"],
                "sinyal": h["sinyal"], "hata": h["hata"], "sonraki_ms": (simdi // adim + 1) * adim,
                "backtest": h["backtest"], "on_ayar": ayar_m.ON_AYAR[ar],
                "turev": veri.TUREV.get(ar),
            })
        return {"simdi_ms": simdi, "calisma_sn": int(time.time() - self.basladi),
                "araliklar": araliklar, "takip": ayarlar["takip"],
                "stratejiler": [s.ad for s in stratejiler.hepsi(self.taban)],
                "telegram": self.telegram_durumu(), "otomatik": otomatik_durum(),
                "gunluk": list(self.gunluk)[-25:][::-1], "semboller": list(self.taban["semboller"])}


# ------------------------------------------------- Windows acilisinda baslatma
def _baslangic_dosyasi() -> str | None:
    appdata = os.environ.get("APPDATA")
    if os.name != "nt" or not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
                        "FuzyonArena.vbs")


def otomatik_durum() -> dict:
    yol = _baslangic_dosyasi()
    return {"destek": yol is not None, "acik": bool(yol and os.path.exists(yol))}


def otomatik_ayarla(acik: bool) -> dict:
    """Kullanicinin Baslangic klasorune, Fuzyon.vbs'i sessiz calistiran kucuk bir dosya koyar/kaldirir."""
    yol = _baslangic_dosyasi()
    if yol is None:
        raise ValueError("Bu özellik yalnız Windows'ta çalışır.")
    if acik:
        hedef = os.path.join(veri.KOK, "Fuzyon.vbs").replace('"', '""')
        icerik = f'CreateObject("WScript.Shell").Run "wscript.exe ""{hedef}"" sessiz", 0, False\r\n'
        with open(yol, "w", encoding="utf-16") as f:            # BOM'lu UTF-16: Turkce yol guvenli
            f.write(icerik)
    elif os.path.exists(yol):
        os.remove(yol)
    return otomatik_durum()


def baslat(taban: dict, tarayici: bool = True) -> int:
    """Servisi calistirir (engelleyici). Port doluysa zaten calisiyordur: yalniz paneli acar."""
    import webbrowser

    from . import panel
    adres = f"http://127.0.0.1:{taban['panel_port']}"
    servis = Servis(taban)
    try:
        sunucu = panel.sunucu(taban, servis)
    except OSError:
        if tarayici:
            webbrowser.open(adres)
        print(f"Füzyon zaten çalışıyor: {adres}")
        return 0
    servis.sunucu = sunucu
    threading.Thread(target=servis.calis, name="calisan", daemon=True).start()
    threading.Thread(target=servis.telegram_dinle, name="telegram", daemon=True).start()
    print(f"Füzyon servisi çalışıyor: {adres}  (durdurmak için paneldeki 'Servisi durdur')")
    if tarayici:
        threading.Timer(1.0, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servis.dur.set()
        sunucu.server_close()
        time.sleep(0.3)                     # calisan is parcacigi turunu bitirsin
        veri.bekleyenleri_yaz()
    return 0
