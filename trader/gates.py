"""Protokol kapilari — hangi strateji hangi asamada calisabilir?

Ag mantigi:
  * `sistem_testi` gibi arastirma adayi OLMAYAN stratejiler yalnizca
    TESTNET'te calisir (testnet parasI sahtedir) — CANLI hicbir zaman.
  * Arastirma adayi olan stratejiler:
        backtest kapilari gecti  -> testnet
        testnet kapisi gecti     -> canli
    Kapilar `out/gates.json` dosyasinda kayitlidir; protokol kosucusu yazar.

Dosya elle duzenlenebilir ama her degisiklik `recorded_at` ve `note` ile
kayit altina alinir (denetim izi).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import OUT_DIR

GATE_FILE = OUT_DIR / "gates.json"

# Asama sirasi
STAGES = ("backtest", "holdout", "paper", "testnet", "live")


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    stage: str = ""


def load_gates() -> dict:
    if not GATE_FILE.exists():
        return {}
    try:
        return json.loads(GATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_gates(gates: dict) -> None:
    GATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GATE_FILE.write_text(
        json.dumps(gates, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def record_gate(strategy: str, stage: str, passed: bool, metrics: dict | None = None,
                note: str = "") -> dict:
    gates = load_gates()
    entry = gates.setdefault(strategy, {})
    entry[stage] = {
        "passed": bool(passed),
        "metrics": metrics or {},
        "note": note,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    save_gates(gates)
    return entry


def check(strategy, mode: str) -> GateDecision:
    """Bu strateji bu modda calisabilir mi?"""
    name = getattr(strategy, "name", str(strategy))
    research = bool(getattr(strategy, "research_candidate", False))
    gates = load_gates().get(name, {})

    if not research:
        if mode == "live":
            return GateDecision(False,
                                "Bu strateji bir arastirma adayi degildir; CANLI modda "
                                "calistirilamaz. (Arastirma adayi olmayan stratejiler "
                                "yalnizca testnet/paper icindir.)")
        if mode == "testnet":
            return GateDecision(True, "Altyapi testi (testnet) — arastirma adayi degil.")
        return GateDecision(True, "Altyapi testi (paper).")

    if mode == "paper":
        return GateDecision(True, "Paper modu — gercek para yok, kapı gerekmez.")

    if mode == "testnet":
        ok = bool(gates.get("backtest", {}).get("passed")) and \
            bool(gates.get("holdout", {}).get("passed"))
        if ok:
            return GateDecision(True, "Backtest + hold-out kapıları geçti.")
        return GateDecision(
            False,
            "TESTNET kapısı kapalı: backtest ve hold-out kapıları geçilmeli. "
            "(AGENTS.md: backtest -> 300 paper -> 100 testnet)",
            stage="testnet",
        )

    if mode == "live":
        ok = bool(gates.get("testnet", {}).get("passed"))
        if ok:
            return GateDecision(True, "Testnet kapısı geçti.")
        return GateDecision(
            False,
            "CANLI kapısı kapalı: testnet aşaması geçilmeli "
            "(AGENTS.md: 100+ testnet işlem).",
            stage="live",
        )

    return GateDecision(False, f"Bilinmeyen mod: {mode}")
