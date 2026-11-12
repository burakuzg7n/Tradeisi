"""Sinyal iletimi (StrategyEase SDK'nin 'stratejiyi dis yurutucuye REST ile bagla / lideri takip et'
fikrinden esinli). Gercek emir GONDERMEZ: sinyali dosyaya, konsola, Telegram'a ve istege bagli
bir webhook adresine iletir; emri kimin/neyin girecegi size kalir."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .ayar import cikti_klasoru
from .veri import KOK

YON_AD = {1: "LONG", -1: "SHORT", 0: "KAPAT"}


def _env() -> dict:
    """Ortam degiskenleri + kokteki .env (varsa). Degerler hicbir yere yazdirilmaz."""
    e = dict(os.environ)
    yol = os.path.join(KOK, ".env")
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8-sig") as f:
                for satir in f:
                    satir = satir.split("#", 1)[0].strip()
                    if "=" in satir:
                        k, v = satir.split("=", 1)
                        e.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except OSError:
            pass
    return e


def metin(o: dict) -> str:
    zaman = time.strftime("%d.%m %H:%M", time.localtime(o["ts"] / 1000))
    if o["tur"] == "KILIT":
        return f"[{zaman}] {o['strateji']}: HESAP KİLİDİ — {o['neden']}"
    fiyat = "" if o.get("fiyat") is None else f" @ {o['fiyat']:.6g}"
    ek = ""
    if o.get("stop_mesafe") and o.get("fiyat"):
        ek += f" | stop ≈ {o['fiyat'] - o['yon'] * o['stop_mesafe']:.6g}"
    if o.get("kar_mesafe") and o.get("fiyat"):
        ek += f" | hedef ≈ {o['fiyat'] + o['yon'] * o['kar_mesafe']:.6g}"
    return f"[{zaman}] {o['strateji']}: {YON_AD[o['yon']]} {o['sembol']}{fiyat}{ek} — {o['neden']}"


def sec(olaylar: list, takip, lider: str | None) -> list:
    out = [o for o in olaylar if o["tur"] in ("SINYAL", "KILIT")]
    if takip in (None, "", "hepsi"):
        return out
    hedef = lider if takip == "lider" else takip
    return [o for o in out if o["strateji"] == hedef]


def ilet(olaylar: list, a: dict, sessiz: bool = False) -> int:
    if not olaylar:
        return 0
    yol = os.path.join(cikti_klasoru(a), "sinyaller.jsonl")
    with open(yol, "a", encoding="utf-8") as f:
        for o in olaylar:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    satirlar = [metin(o) for o in olaylar]
    if not sessiz:
        for s in satirlar:
            print("  SİNYAL " + s)
    if a.get("telegram", True):                       # servis, bildirimi kapali araliklarda False verir
        telegram_gonder(f"Füzyon {a['aralik']} (kâğıt)\n" + "\n".join(satirlar), sessiz=sessiz)
    if a.get("webhook_url"):
        _gonder(a["webhook_url"], json.dumps({"kaynak": "fuzyon", "kagit": True, "sinyaller": olaylar},
                                             ensure_ascii=False).encode("utf-8"),
                "application/json", "Webhook", sessiz)
    return len(olaylar)


def _gonder(url: str, govde: bytes, tur: str, ad: str, sessiz: bool = False) -> bool:
    try:
        istek = urllib.request.Request(url, data=govde, headers={"Content-Type": tur})
        urllib.request.urlopen(istek, timeout=10).read()
        return True
    except Exception as ex:  # iletim hatasi botu durdurmamali
        if not sessiz:
            print(f"  UYARI: {ad} iletimi basarisiz ({type(ex).__name__}).")
        return False


# ------------------------------------------------------------------ Telegram
def telegram_ayari() -> tuple:
    """(token, chat_id) — yoksa bos metin. Degerler hicbir yere yazdirilmaz."""
    e = _env()
    return e.get("TELEGRAM_BOT_TOKEN", "").strip(), str(e.get("TELEGRAM_CHAT_ID", "")).strip()


def tg(token: str, metod: str, zaman_asimi: float = 15.0, **parametreler):
    """Telegram Bot API cagrisi; 'result' alanini dondurur, hata durumunda RuntimeError.
    Hata metninde token YER ALMAZ."""
    veri_ = urllib.parse.urlencode({k: v for k, v in parametreler.items() if v is not None}).encode()
    istek = urllib.request.Request(f"https://api.telegram.org/bot{token}/{metod}", data=veri_)
    try:
        with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
            yanit = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"Telegram {metod}: HTTP {ex.code}") from None
    except Exception as ex:
        raise RuntimeError(f"Telegram {metod}: {type(ex).__name__}") from None
    if not yanit.get("ok"):
        raise RuntimeError(f"Telegram {metod}: {yanit.get('description', 'hata')}")
    return yanit.get("result")


def telegram_gonder(metin_: str, sessiz: bool = True, chat_id=None) -> bool:
    token, chat = telegram_ayari()
    chat = chat_id or chat
    if not token or not chat:
        return False
    try:
        tg(token, "sendMessage", chat_id=chat, text=metin_[:3900], disable_web_page_preview="true")
        return True
    except RuntimeError as ex:
        if not sessiz:
            print(f"  UYARI: {ex}")
        return False


def env_yaz(degerler: dict) -> None:
    """Kokteki .env dosyasinda verilen anahtarlari gunceller (digerlerine dokunmaz).
    Deger None ise anahtar silinir. .env, .gitignore'dadir; GitHub'a gitmez."""
    yol = os.path.join(KOK, ".env")
    satirlar = []
    if os.path.exists(yol):
        with open(yol, encoding="utf-8-sig") as f:
            satirlar = f.read().splitlines()
    kalan = dict(degerler)
    yeni = []
    for satir in satirlar:
        anahtar = satir.split("=", 1)[0].strip() if "=" in satir and not satir.lstrip().startswith("#") else None
        if anahtar in kalan:
            deger = kalan.pop(anahtar)
            if deger is not None:
                yeni.append(f"{anahtar}={deger}")
        else:
            yeni.append(satir)
    yeni += [f"{k}={v}" for k, v in kalan.items() if v is not None]
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(yeni) + "\n")
    for k, v in degerler.items():                      # ortam degiskeni .env'i golgelemesin
        if v is None:
            os.environ.pop(k, None)
        elif k in os.environ:
            os.environ[k] = str(v)
