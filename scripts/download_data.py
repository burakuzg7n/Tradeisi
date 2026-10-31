"""Binance'ten BTC/ETH 15m + 4h verisi indirir (kendi makinende çalıştır).

Kullanım:
    python scripts/download_data.py            # son 18 ay
    python scripts/download_data.py 2024-01-01 # belirli başlangıç
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradebot.data import download_binance, save_csv, validate_ohlcv

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVALS = ["15m", "4h"]


def main() -> None:
    if len(sys.argv) > 1:
        start = datetime.fromisoformat(sys.argv[1]).replace(tzinfo=timezone.utc)
    else:
        start = datetime.now(timezone.utc) - timedelta(days=548)  # ~18 ay
    end = datetime.now(timezone.utc)

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            print(f"İndiriliyor: {symbol} {interval} ({start.date()} → {end.date()})")
            df = download_binance(
                symbol,
                interval,
                int(start.timestamp() * 1000),
                int(end.timestamp() * 1000),
            )
            path = DATA_DIR / f"{symbol}_{interval}.csv"
            save_csv(df, path)
            print(f"  {path.name}: {validate_ohlcv(df, interval)}")


if __name__ == "__main__":
    main()
