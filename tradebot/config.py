"""Merkezi konfigürasyon.

Tüm parametreler tek yerde; strateji parametreleri backtest'e göre
optimize EDİLMEZ (curve fitting yasağı) — mantıktan gelir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyParams:
    """HTF Bias + Liquidity Sweep + FVG Retest parametreleri."""

    htf_timeframe: str = "4h"        # bias TF'i
    ltf_timeframe: str = "15m"       # entry TF'i

    # Swing / pivot
    htf_pivot: int = 3               # 4H pivot sol/sağ mum
    ltf_pivot: int = 10              # 15M pivot sol/sağ mum (likidite seviyeleri)

    # FVG
    fvg_min_size_pct: float = 0.0005   # fiyatın %0.05'i altındaki FVG'ler gürültü
    fvg_fill_entry: float = 0.50       # FVG %50 dolulukta limit entry (midpoint)

    # Setup pencereleri (15M bar sayısı)
    setup_window: int = 24           # sweep sonrası FVG bekleme (24 bar = 6 saat)
    entry_window: int = 32           # FVG sonrası fill bekleme (32 bar = 8 saat)

    # Risk / hedef
    rr_target: float = 2.0           # minimum 1:2
    stop_buffer_pct: float = 0.001   # stop'a %0.1 tampon
    # Maliyet rasyonalitesi: stop mesafesi fiyatın %0.2'sinden darsa
    # komisyon+slippage R cinsinden 0.5R'yi aşar → setup ekonomik değil.
    # (Optimizasyon değil, maliyet kısıtı — round-trip maliyetten türetildi.)
    min_risk_pct: float = 0.002

    # Volume konfirmasyonu (knowledge/volume: sweep + hacim spike = kurumsal).
    # YAPISAL filtre — eşik knowledge base'deki 1.5x tanımından gelir,
    # backtest'e göre AYARLANMAZ (curve fitting yasağı).
    use_volume_filter: bool = False
    vol_spike_mult: float = 1.5
    vol_ma_window: int = 20

    # Session filtresi (UTC saat aralıkları [start, end))
    use_session_filter: bool = True
    killzones_utc: tuple = ((7, 10), (13, 16))  # London KZ + NY KZ


@dataclass(frozen=True)
class RiskParams:
    risk_per_trade: float = 0.005    # %0.5
    min_rr: float = 2.0
    daily_loss_limit_r: float = 3.0
    weekly_loss_limit_r: float = 8.0
    max_drawdown_pct: float = 0.10   # canlı kill switch (backtest kabul eşiği %15)


@dataclass(frozen=True)
class BacktestParams:
    initial_balance: float = 10_000.0
    risk_per_trade: float = 0.005    # %0.5 (RiskParams ile aynı)
    # Ücret modeli: entry limit emir (maker), target limit (maker),
    # stop-market (taker). Dar SMC stoplarında taker/taker varsayımı
    # R cinsinden maliyeti 2-3 katına çıkarıp sonucu anlamsızlaştırır.
    maker_fee: float = 0.0002        # %0.02
    taker_fee: float = 0.00055       # %0.055
    slippage_rate: float = 0.0001    # stop-market çıkışlarında aleyhe
    max_open_positions: int = 1


@dataclass(frozen=True)
class ExchangeConfig:
    """Borsa-bağımsız: ccxt exchange id config'den seçilir."""

    exchange_id: str = field(default_factory=lambda: os.getenv("EXCHANGE_ID", "bybit"))
    api_key: str = field(default_factory=lambda: os.getenv("EXCHANGE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("EXCHANGE_API_SECRET", ""))
    testnet: bool = field(default_factory=lambda: os.getenv("TRADING_MODE", "testnet") != "live")


@dataclass(frozen=True)
class ServerConfig:
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))
    paper_mode: bool = field(default_factory=lambda: os.getenv("PAPER_MODE", "1") == "1")
    journal_db: str = field(default_factory=lambda: os.getenv("JOURNAL_DB", "journal.db"))


SYMBOLS = ("BTCUSDT", "ETHUSDT")

# Canlı/demo çalıştırıcının izlediği semboller (ccxt unified format, USDT perp)
LIVE_SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT")


def load_env(path: str = ".env") -> None:
    """Bağımlılıksız .env yükleyici. Var olan env değişkenlerini EZMEZ."""
    import pathlib

    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
