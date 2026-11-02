"""V3 verisini indirir ve sağlık raporunu yazar (kendi makinende çalıştır).

Kullanım:  python scripts/download_v3.py
Çıktı:     data/{SEMBOL}_15m.csv, reports/V3_VERI_SAGLIK.json/.md
Strateji veya performans hesabı YAPMAZ. Bir kez çalıştırılır; dosyalar yeniden indirilmez.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tradebot import daily_data as dd  # noqa: E402
from tradebot import v3_data as vd  # noqa: E402


def main() -> int:
    import requests

    data_dir, report_dir = ROOT / "data", ROOT / "reports"
    data_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)
    if (report_dir / "V3_VERI_SAGLIK.json").exists():
        print("V3_VERI_SAGLIK.json zaten var: veri bir kez indirilir, yeniden indirilmez.")
        return 2
    existing = [s for s in vd.SYMBOLS if (data_dir / f"{s}_15m.csv").exists()]
    if existing:
        print(f"Rapor yok ama {existing} CSV'leri var (yarım kalmış/elle eklenmiş?). "
              "Üzerine yazılmaz; Claude'a haber ver.")
        return 2
    session = requests.Session()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    contracts = dd.fetch_contracts(session, vd.SYMBOLS)
    frames, hashes = {}, {}
    start = vd.day_index(vd.DOWNLOAD_FROM) * vd.DAY_MS
    for sym in vd.SYMBOLS:
        print(f"İndiriliyor: {sym} 15m (PERPETUAL) — birkaç dakika sürebilir", flush=True)
        rows = vd.download_15m_rows(sym, session, now_ms, start)
        tmp = data_dir / f"{sym}_15m.csv.indiriliyor"      # yarım kalırsa asıl dosya oluşmaz
        dd.save_daily(dd.rows_to_frame(rows), tmp)
        frames[sym] = dd.load_daily_raw(tmp)
        hashes[sym] = dd.file_sha256(tmp)
        print(f"  {sym}: {len(frames[sym])} satır", flush=True)
    rep = vd.build_report(frames, contracts, hashes)
    rep["downloaded_at_utc"] = datetime.now(timezone.utc).isoformat()
    (report_dir / "V3_VERI_SAGLIK.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "V3_VERI_SAGLIK.md").write_text(vd.render_markdown(rep), encoding="utf-8")
    for sym in vd.SYMBOLS:                                  # rapor yazıldıktan SONRA yerine koy
        (data_dir / f"{sym}_15m.csv.indiriliyor").replace(data_dir / f"{sym}_15m.csv")
    print(f"\n=== {rep['verdict']} ===")
    for b in rep["blockers"]:
        print("  ENGEL:", b)
    print("Rapor: reports/V3_VERI_SAGLIK.md")
    return 0 if not rep["blockers"] else 1


if __name__ == "__main__":
    sys.exit(main())
