"""Arsiv butunlugu — 5. adayin kosu kayitlari bozulmus mu?

`AGENTS.md` kural 8: "Basarisizlik verileri/raporlari silinmez. `reports/`
arsivdir." Bu test, arsivdeki her dosyanin SHA-256 ozetinin
`reports/SEPET_MOMENTUM/MANIFEST.json` ile ortusmasi gerektigini denetler.

Boylece:
  * bir kosu raporu silinirse/degistirilirse test KIRMIZI olur,
  * gecersiz (VOID) kosularin kaydi kaybolursa test KIRMIZI olur,
  * manifest ile gercek dosyalar ayrilirsa test KIRMIZI olur.

Degisiklik yapildiysa: `python scripts/verify_archive.py --write`
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "reports" / "SEPET_MOMENTUM"
SCRIPT = ROOT / "scripts" / "verify_archive.py"


def test_archive_exists_with_manifest():
    assert ARCHIVE.is_dir(), "arsiv klasoru eksik"
    assert (ARCHIVE / "MANIFEST.json").is_file(), "MANIFEST.json eksik"


def test_archive_manifest_matches_files():
    """MANIFEST.json'deki her dosya diskte ayni icerikle bulunmali."""
    manifest = json.loads((ARCHIVE / "MANIFEST.json").read_text(encoding="utf-8"))
    recorded = {e["name"]: e["sha256"] for e in manifest["files"]}
    assert recorded, "manifest bos"

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import verify_archive as va
    finally:
        sys.path.pop(0)

    missing = []
    mismatched = []
    for name, want in recorded.items():
        p = ARCHIVE / name
        if not p.exists():
            missing.append(name)
            continue
        if va.sha256_canonical(p) != want:
            mismatched.append(name)

    assert not missing, f"arsivde dosya yok: {missing}"
    assert not mismatched, (
        "arsiv dosyalari MANIFEST.json ile uyusmuyor (degistirilmis olabilir): "
        f"{mismatched}\nDuzeltme: python scripts/verify_archive.py --write"
    )


def test_all_four_runs_are_archived():
    """Koşu 1-4 (VOID'lar dahil) arsivde bulunmali — hicbiri silinmemis."""
    names = {p.name for p in ARCHIVE.iterdir() if p.is_file()}
    expected = {
        # Kosu 1 - VOID (3 motor hatasi)
        "sepet_momentum_insample_20261107_193859.json",
        "sepet_momentum_insample_20261107_193859.md",
        # Kosu 2 - VOID (deterministik degil)
        "sepet_momentum_insample_20261108_105543.json",
        "sepet_momentum_insample_20261108_105543.md",
        # Kosu 3 - VOID (ayni komut, farkli sonuc)
        "sepet_momentum_none_20261108_112058.json",
        "sepet_momentum_none_20261108_112058.md",
        # Kosu 4 - GECERLI TEK ATIS (RED)
        "sepet_momentum_insample_20261108_132730.json",
        "sepet_momentum_insample_20261108_132730.md",
    }
    assert expected <= names, f"eksik arsiv dosyalari: {sorted(expected - names)}"


def test_valid_single_shot_metrics_are_frozen():
    """Gecerli tek atisin metrikleri arsivde degismemis olmali (RED karari)."""
    d = json.loads(
        (ARCHIVE / "sepet_momentum_insample_20261108_132730.json")
        .read_text(encoding="utf-8"))
    s = d["summary"]
    assert s["total_trades"] == 823
    assert abs(s["profit_factor"] - 1.1404915344830064) < 1e-9
    assert abs(s["max_drawdown"] - 0.552004246692208) < 1e-9
    assert abs(d["final_equity"] - 35203.905674802074) < 1e-6


def test_gate_ledger_records_red_and_void_history():
    """Kapi defterinde: gecerli kosu RED + gecersiz kosu gecmisi korunmali."""
    g = json.loads((ARCHIVE / "GATES.json").read_text(encoding="utf-8"))
    entry = g["sepet_momentum"]
    assert entry["backtest"]["passed"] is False
    assert entry["backtest"]["metrics"]["trades"] == 823

    history = entry.get("history") or []
    assert history, "gecersiz kosu gecmisi silinmis olamaz"
    assert all("void_reason" in h for h in history)


def test_verify_script_passes():
    """Denetim araci kendisi de yesil olmali."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=str(ROOT),
        capture_output=True, text=True, timeout=300)
    if "not recognized" in (proc.stderr or "") or "not found" in (proc.stderr or ""):
        pytest.skip("git bulunamadi; depo blob karsilastirmasi atlandi")
    assert proc.returncode == 0, (
        "arsiv dogrulamasi basarisiz:\n" + (proc.stdout or "") + (proc.stderr or "")
    )
