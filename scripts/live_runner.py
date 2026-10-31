"""Demo/testnet canlı çalıştırıcı giriş noktası.

Kullanım (kendi makinende, .env doldurduktan sonra):
    python scripts/live_runner.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradebot.live import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDurduruldu.")
