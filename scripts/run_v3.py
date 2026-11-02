"""V3 tek atış çalıştırıcısı.

    python scripts/run_v3.py insample    # 2021-01-01 → 2024-12-31, bir kez
    python scripts/run_v3.py holdout     # yalnız in-sample GEÇTİYSE, bir kez
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tradebot.protocol_v3 import ProtocolError, run_protocol  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("insample", "holdout"):
        print(__doc__)
        return 1
    try:
        r = run_protocol(sys.argv[1], ROOT / "data", ROOT / "reports")
    except ProtocolError as e:
        print(f"\nREDDEDİLDİ (protokol): {e}")
        return 2
    m = r["metrics"]
    print(f"\n=== V3 {r['phase']} : {r['verdict']} ===")
    for k, ok in r["gates"].items():
        print(f"  {'GEÇTİ' if ok else 'KALDI'}  {k}")
    print(f"  PF {m['profit_factor']} · işlem {m['total_trades']} · DD %{float(m['max_drawdown'])*100:.2f}"
          f" · HAC t {m['daily']['hac_t']}")
    print(f"\nRapor: reports/V3_{r['phase'].upper()}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
