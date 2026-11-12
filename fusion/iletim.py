"""Sinyal iletimi (StrategyEase SDK'nin 'stratejiyi dis yurutucuye REST ile bagla / lideri takip et'
fikrinden esinli). Gercek emir GONDERMEZ: sinyali dosyaya, konsola, Telegram'a ve istege bagli
bir webhook adresine iletir; emri kimin/neyin girecegi size kalir."""
from __future__ import annotations

import json
import os
import time
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
    e = _env()
    token, chat = e.get("TELEGRAM_BOT_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", "")
    if token and chat:
        _gonder(f"https://api.telegram.org/bot{token}/sendMessage",
                urllib.parse.urlencode({"chat_id": chat, "text": "Füzyon (kâğıt)\n" + "\n".join(satirlar)[:3800]}).encode(),
                "application/x-www-form-urlencoded", "Telegram")
    if a.get("webhook_url"):
        _gonder(a["webhook_url"], json.dumps({"kaynak": "fuzyon", "kagit": True, "sinyaller": olaylar},
                                             ensure_ascii=False).encode("utf-8"),
                "application/json", "Webhook")
    return len(olaylar)


def _gonder(url: str, govde: bytes, tur: str, ad: str) -> None:
    try:
        istek = urllib.request.Request(url, data=govde, headers={"Content-Type": tur})
        urllib.request.urlopen(istek, timeout=10).read()
    except Exception as ex:  # iletim hatasi botu durdurmamali
        print(f"  UYARI: {ad} iletimi basarisiz ({type(ex).__name__}).")
