"""V3 işlem sıklığı fizibilitesi — YALNIZ sentetik veri (docs/V3_SPEC_TASLAK.md §6b).

Gerçek fiyat verisi kullanılmaz; PnL/PF/DD raporlanmaz (sentetik veride anlamsız).
Çıktı: reports/V3_FIZIBILITE.md
Senaryo ızgarası ve tohumlar sonuç görülmeden sabittir: σ_d × ρ × rejim × 3 tohum.
Tam veride (eksik mum yok) her niyet bir işlemdir (dolum mumu daima vardır); bu,
bir senaryoda motorla doğrulanır. Maliyet ve bakiye işlem SAYISINI etkilemez (tetikler
fiyattan gelir); sermaye tükenmesinin sayıyı düşürmesi bu tahminin dışındadır.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from tradebot import strategy_v3 as sv  # noqa: E402
from tradebot.engine_v3 import V3Params, run_v3  # noqa: E402
from tradebot.synthetic_v3 import generate  # noqa: E402

SYMS = ("XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT")
START = (date(2021, 1, 1) - date(1970, 1, 1)).days
END = (date(2024, 12, 31) - date(1970, 1, 1)).days
WARM = 40
MONTHS = 48
SIGMAS = (0.025, 0.04, 0.06)
RHOS = (0.5, 0.8)
REGIMES = ("trend", "yatay")
SEEDS = (1, 2, 3)
MIN_TRADES = 1300


def run_one(sig, rho, reg, seed, check_engine=False):
    data = generate(SYMS, START - WARM, END - START + 1 + WARM, sig, rho, reg, seed)
    total, reasons = 0, Counter()
    intents = {}
    for s in SYMS:
        log = []
        intents[s] = sv.generate_intents(s, data[s], START, END, log)
        total += len(intents[s])
        reasons.update(x.status for x in log)
    if check_engine:
        nocost = V3Params(taker_fee=0, maker_fee=0, slippage=0, funding_rate=0)
        res = run_v3(data, intents, START, END, nocost)
        assert len(res.trades) == total, (len(res.trades), total)
    return total, reasons


def main():
    rows = []
    all_reasons = Counter()
    first = True
    for sig, rho, reg in product(SIGMAS, RHOS, REGIMES):
        counts = []
        for seed in SEEDS:
            n, rs = run_one(sig, rho, reg, seed, check_engine=first)
            first = False
            counts.append(n)
            all_reasons.update(rs)
        rows.append((sig, rho, reg, min(counts), int(np.median(counts)), max(counts)))
        print(sig, rho, reg, counts, flush=True)
    lo = min(r[3] for r in rows)
    hi = max(r[5] for r in rows)
    L = ["# V3 — işlem sıklığı fizibilitesi (SENTETİK veri)", "",
         "Gerçek fiyat verisi kullanılmadı; PnL/PF/DD raporlanmaz. Varsayımlar:",
         "`tradebot/synthetic_v3.py` (sonuç görülmeden sabit). Dönem uzunluğu: in-sample ile",
         f"aynı 48 ay (1.461 gün), 5 sembol, {len(SEEDS)} tohum/senaryo.", "",
         "| σ_günlük | ρ | rejim | 48 ay işlem (min / medyan / maks) | ay başına (medyan) |",
         "|---:|---:|---|---|---:|"]
    for sig, rho, reg, mn, md, mx in rows:
        L.append(f"| {sig} | {rho} | {reg} | {mn} / {md} / {mx} | {md / MONTHS:.1f} |")
    tot = sum(all_reasons.values())
    L += ["", f"**Tüm senaryolar aralığı:** {lo} – {hi} işlem / 48 ay "
          f"({lo / MONTHS:.1f} – {hi / MONTHS:.1f} / ay).",
          f"**İşlem kapısı:** ≥ {MIN_TRADES}. "
          f"Aralığın alt ucu kapının {'ÜSTÜNDE' if lo >= MIN_TRADES else 'ALTINDA'}.", "",
          "## Gün durumları (tüm senaryolar, sembol-gün başına pay)", "",
          "| durum | pay |", "|---|---:|"]
    for k, v in all_reasons.most_common():
        L.append(f"| {k} | %{v / tot * 100:.1f} |")
    L += ["", "## Sınırlamalar",
          "- Aralık, seçilmiş 36 sentetik koşunun **gözlenen** aralığıdır; güven aralığı veya",
          "  gerçek piyasada ≥ 1.300 işlem garantisi değildir. Gerçek rejimler, oynaklık ve",
          "  korelasyon bu aralığın dışına düşebilir.",
          "- Sayılar **niyet** sayısıdır. Tam veride (eksik mum yok) her niyet bir işlemdir;",
          "  motorla eşlik yalnız **bir** senaryoda ve **maliyetler kapalı** doğrulandı.",
          "- **Sermaye tükenmesinin** (E16 karşılığı) işlem sayısını düşürmesi bu tahminin",
          "  dışındadır; maliyetli gerçek koşuda sayı daha düşük olabilir.",
          "- Eksik mumlar (dolum mumu yoksa iptal) sentetik veride yoktur.",
          "", "Karar kuralı (§6b): alt uç < 1.300 ise koşu başlamaz; kural sonuç görülmeden yeni",
          "ön-kayıtla değiştirilir (coin/risk eklenmez)."]
    out = ROOT / "reports" / "V3_FIZIBILITE.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"aralık {lo}-{hi}; rapor {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
