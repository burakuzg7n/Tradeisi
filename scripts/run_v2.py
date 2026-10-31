"""V2 test protokolü çalıştırıcısı (TEK ATIŞ).

    python scripts/run_v2.py insample    # 2020-01 → 2024-12, bir kez
    python scripts/run_v2.py holdout     # yalnız in-sample GEÇTİYSE, bir kez

Kurallar tradebot/protocol_v2.py içinde kod ile zorlanır.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tradebot.protocol_v2 import ProtocolError, run_protocol  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("insample", "holdout"):
        print(__doc__)
        return 1
    try:
        r = run_protocol(sys.argv[1], ROOT / "data", ROOT / "reports")
    except ProtocolError as e:
        print(f"\nREDDEDİLDİ (protokol): {e}")
        return 2
    c = r["combined"]
    print(f"\n=== V2 {r['phase']} : {r['verdict']} ===")
    for k, ok in r["gates"].items():
        print(f"  {'GEÇTİ' if ok else 'KALDI'}  {k}")
    print(f"  PF {c['profit_factor']} · işlem {c['total_trades']} · "
          f"DD %{float(c['max_drawdown'])*100:.2f}")
    print(f"\nRapor: reports/V2_{r['phase'].upper()}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
