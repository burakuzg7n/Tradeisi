"""Sepet momentum arsivini dogrula (veya yeniden uret).

ARSIV NEDIR?
    `reports/SEPET_MOMENTUM/` — 5. adayin 16 kosusunun makine ciktisi,
    kapi defteri, tek atis kilidi ve parmak izleri. `AGENTS.md` kural 8:
    gecersiz kosular dahil HICBIR kosu kaydi silinmez.

NEDEN BU SCRIPT VAR?
    Git metin dosyalarini depoda LF ile saklar (`core.autocrlf=true`,
    `.gitattributes`). Arxiv klasorundeki dosyalar calisma kopyasinda CRLF
    olabilir; bu YALNIZCA satir sonu farkidir, icerik degismemis.
    Bu script, her dosyanin DEPOLANAN (kanonik) iceriginin SHA-256'sini
    hesaplayip `MANIFEST.json` ile karsilastirir. Boylece arsivin
    butunlugu her makinede tek komutla denetlenebilir.

KULLANIM
    python scripts/verify_archive.py            # dogrula (cikis kodu 0/1)
    python scripts/verify_archive.py --write    # MANIFEST.json'u yeniden uret
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "reports" / "SEPET_MOMENTUM"
MANIFEST = ARCHIVE / "MANIFEST.json"
MANIFEST_NAME = MANIFEST.name


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def canonical_bytes(raw: bytes) -> bytes:
    """Git'in metin temizleme filtresiyle ayni: CRLF -> LF, yalniz CR -> LF."""
    if b"\x00" in raw:          # ikili dosya -> degistirilmez
        return raw
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_canonical(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()


def blob_sha256(path: Path) -> str | None:
    """Depodaki blob iceriginin SHA-256'si; dosya yoksa None.

    Once INDEX'e (staged) bakar: commit edilmemis ama hazirlanmis degisiklikler
    de denetim altinda olsun. Index'te yoksa HEAD'e bakar.
    """
    rel = path.relative_to(ROOT).as_posix()
    for ref in (f":{rel}", f"HEAD:{rel}"):
        try:
            blob = subprocess.run(
                ["git", "show", ref], cwd=str(ROOT),
                capture_output=True, check=True).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        return hashlib.sha256(blob).hexdigest()
    return None


def collect() -> list[dict]:
    entries = []
    for p in sorted(ARCHIVE.iterdir()):
        if not p.is_file() or p.name == MANIFEST_NAME:
            continue
        entries.append({
            "name": p.name,
            "bytes": p.stat().st_size,
            "sha256": sha256_canonical(p),
        })
    return entries


def build() -> dict:
    return {
        "strategy": "sepet_momentum",
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Bu klasor 5. adayin TUM kosu gecmisini icerir: gecersiz (VOID) "
            "kosular da dahil. Dosyalar `out/reports/` altindan BIT BIT kopyalandi; "
            "hicbiri silinmedi, yeniden adlandirilmadi veya icerigi degistirilmedi. "
            "sha256 degerleri DEPOLANAN (kanonik, LF) icerigin ozetidir; "
            "calisma kopyasindaki CRLF satir sonlari fark yaratmaz. "
            "MANIFEST.json'in kendi ozeti listede yer almaz."
        ),
        "verify_command": "python scripts/verify_archive.py",
        "files": collect(),
    }


def verify() -> int:
    if not MANIFEST.exists():
        print("HATA: MANIFEST.json yok.")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    recorded = {e["name"]: e["sha256"] for e in manifest.get("files", [])}

    ok = True
    print("ARSIV DOGRULAMA - reports/SEPET_MOMENTUM")
    print("-" * 78)
    for name, want in recorded.items():
        p = ARCHIVE / name
        if not p.exists():
            print("  [KAYIP]    %s" % name)
            ok = False
            continue
        got = sha256_canonical(p)
        blob = blob_sha256(p)
        same = got == want
        blob_same = blob is None or blob == want
        flag = "OK " if (same and blob_same) else "FARKLI"
        print("  [%s] %-46s %s" % (flag, name, want[:16]))
        if not same:
            print("           bekl. %s / bulunan %s" % (want[:16], got[:16]))
            ok = False
        if not blob_same:
            print("           DEPO blob farkli: %s" % (blob or "?")[:16])
            ok = False

    # depodaki gercek kume ile manifesti karsilastir
    tracked = set()
    listing = _git("ls-files", "reports/SEPET_MOMENTUM/")
    if listing:
        for line in listing.splitlines():
            tracked.add(Path(line).name)
    if tracked:
        missing = tracked - set(recorded) - {MANIFEST_NAME}
        extra = set(recorded) - tracked
        if missing:
            print("  [EKSIK] depoda ama manifestte yok: %s" % ", ".join(sorted(missing)))
            ok = False
        if extra:
            print("  [FAZLA] manifestte ama depoda yok: %s" % ", ".join(sorted(extra)))
            ok = False

    print("-" * 78)
    print("SONUC:", "ARSIV BUTUN" if ok else "BUTUNLUK HATASI")
    return 0 if ok else 1


def main() -> int:
    if "--write" in sys.argv:
        data = build()
        MANIFEST.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("MANIFEST.json yeniden uretildi (%d dosya)." % len(data["files"]))
        return verify()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
