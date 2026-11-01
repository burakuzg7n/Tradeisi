"""Plan B günlük verisini indirir ve E14 sağlık raporunu yazar (kendi makinende çalıştır).

Kullanım:  python scripts/download_daily.py
Çıktı:     data/{SEMBOL}_1d.csv, reports/PLANB_VERI_SAGLIK.json/.md
Strateji veya performans hesabı YAPMAZ.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tradebot import daily_data as dd  # noqa: E402


def main() -> int:
    import requests

    data_dir = ROOT / "data"
    report_dir = ROOT / "reports"
    data_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)
    session = requests.Session()
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    contracts = dd.fetch_contracts(session)
    frames, hashes = {}, {}
    for sym in dd.SYMBOLS:
        onboard = contracts[sym].get("onboardDate")
        start_ms = dd.day_index(dd.DOWNLOAD_FROM) * dd.DAY_MS
        if onboard is not None:  # listelemeden önce başla: ilk mum kaçmasın
            start_ms = min(start_ms, (int(onboard) // dd.DAY_MS) * dd.DAY_MS)
        print(f"İndiriliyor: {sym} 1d (PERPETUAL)")
        rows = dd.download_daily_rows(sym, session, now_ms, start_ms=start_ms)
        path = data_dir / f"{sym}_1d.csv"
        dd.save_daily(dd.rows_to_frame(rows), path)
        frames[sym] = dd.load_daily_raw(path)  # sağlık kontrolü diske yazılan dosyadan
        hashes[sym] = dd.file_sha256(path)
        print(f"  {path.name}: {len(frames[sym])} satır")

    rep = dd.build_report(frames, contracts, hashes)
    rep["downloaded_at_utc"] = datetime.now(timezone.utc).isoformat()
    (report_dir / "PLANB_VERI_SAGLIK.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "PLANB_VERI_SAGLIK.md").write_text(dd.render_markdown(rep), encoding="utf-8")

    print(f"\n=== {rep['verdict']} ===")
    for b in rep["blockers"]:
        print("  ENGEL:", b)
    print("Rapor: reports/PLANB_VERI_SAGLIK.md")
    return 0 if not rep["blockers"] else 1


if __name__ == "__main__":
    sys.exit(main())
