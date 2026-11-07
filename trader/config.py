"""Merkezi ayarlar.

Tum degerler .env dosyasindan okunur; kaynak kodda sirlar (API anahtari,
token) bulunmaz. `load_env()` var olan ortam degiskenlerini EZMEZ — boylece
kabukta gecici olarak override edilebilir.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
DB_PATH = OUT_DIR / "trader.db"
REPORT_DIR = OUT_DIR / "reports"

# Dosya sonu/bolge kodlamasi: Windows'ta Turkce karakterler cp1252'ye duser.
# Raporlar ve .bat dosyalari icin utf-8 sabitlenir.
for _d in (DATA_DIR, OUT_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def load_env(path: str | Path = ROOT / ".env") -> None:
    """Bagimliliksiz .env yukleyici. Var olan env degiskenlerini EZMEZ."""
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if not raw:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "evet", "on")


@dataclass(frozen=True)
class CostModel:
    """Maliyet modeli — muhafazakar.

    Degerler borsa standartlarindan alindi; strateji sonucuna gore
    AYARLANMAZ (optimizasyon yasagi).
    """

    maker_fee: float = 0.0002        # %0.02 — limit emir giris / hedef cikis
    taker_fee: float = 0.00055       # %0.055 — market giris / stop cikis
    slippage_rate: float = 0.0003    # %0.03 — market emirlerde aleyhe
    funding_interval_hours: int = 8  # perpetual funding araligi (saat)


@dataclass(frozen=True)
class RiskSettings:
    """Canli/paper risk limitleri."""

    risk_per_trade: float = 0.005       # islem basina %0.5 (1R)
    max_positions: int = 6              # ayni anda en fazla 6 pozisyon
    max_gross_leverage: float = 2.0     # toplam |notional| / equity tavani
    max_net_leverage: float = 0.35      # net yon (uzun-kisa) / equity tavani
    daily_loss_limit_r: float = 3.0     # gunluk -3R -> kill switch
    weekly_loss_limit_r: float = 8.0    # haftalik -8R -> kill switch
    max_drawdown_pct: float = 0.10      # %10 -> kill switch


@dataclass(frozen=True)
class ExchangeSettings:
    """Borsa ayarlari. `testnet=True` iken gercek para HARCANAMAZ."""

    exchange_id: str = field(default_factory=lambda: _env("EXCHANGE_ID", "bybit"))
    api_key: str = field(default_factory=lambda: _env("EXCHANGE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: _env("EXCHANGE_API_SECRET", ""))
    testnet: bool = field(default_factory=lambda: _env("TRADING_MODE", "testnet") != "live")
    market: str = field(default_factory=lambda: _env("MARKET_KIND", "perp"))
    default_type: str = field(default_factory=lambda: _env("DEFAULT_TYPE", "swap"))
    recv_window_ms: int = field(default_factory=lambda: _env_int("RECV_WINDOW_MS", 20000))


@dataclass(frozen=True)
class NotifySettings:
    telegram_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", ""))


@dataclass(frozen=True)
class Settings:
    mode: str = field(default_factory=lambda: _env("TRADER_MODE", "paper"))  # paper|testnet|live
    initial_equity: float = field(default_factory=lambda: _env_float("INITIAL_EQUITY", 1000.0))
    exchange: ExchangeSettings = field(default_factory=ExchangeSettings)
    costs: CostModel = field(default_factory=CostModel)
    risk: RiskSettings = field(default_factory=RiskSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)
    db_path: str = field(default_factory=lambda: _env("TRADER_DB", str(DB_PATH)))
    dashboard_host: str = field(default_factory=lambda: _env("DASHBOARD_HOST", "127.0.0.1"))
    dashboard_port: int = field(default_factory=lambda: _env_int("DASHBOARD_PORT", 8765))

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def is_testnet(self) -> bool:
        return self.mode == "testnet"


def load_settings() -> Settings:
    load_env()
    return Settings()
