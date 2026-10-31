# TradeBot — HTF Bias + Liquidity Sweep + FVG Retest

Sıfırdan yazılmış, kural bazlı, risk kontrollü kripto trade sistemi.
BTC/ETH · TradingView (Pine) + Python + CCXT · Tüm sistem UTC.

## Yapı

```
knowledge/     10 konu × 4 dosya — eğitim tabanı (Aşama 1 ✅)
docs/          STRATEGY_BIBLE.md — stratejinin tek gerçek kaynağı (Aşama 2 ✅)
pine/          TradingView indikatörü + webhook alert (Aşama 3 ✅)
tradebot/      Python paketi:
  config.py      tüm parametreler (tek yer)
  structure.py   swing / BOS / CHoCH / HTF bias (lookahead'siz)
  fvg.py         FVG tespiti
  strategy.py    sinyal üretimi (Strategy Bible'ın kodu)
  backtest.py    event-driven motor + metrikler + Monte Carlo
  risk.py        risk engine (kill switch, position sizing)
  journal.py     SQLite journal (sinyal + işlem kaydı)
  server.py      FastAPI webhook + consumer (paper mode varsayılan)
  execution.py   PaperExecutor + CcxtExecutor (borsa config'den)
  data.py        veri indirme / yükleme / doğrulama
scripts/       download_data.py, run_backtest.py
tests/         29 test (lookahead, muhafazakârlık, kill switch, webhook...)
reports/       backtest çıktıları
```

## En Hızlı Yol: Demo Bakiye (Bybit testnet, sahte para)

**KURULUM.md'yi takip et** — TradingView gerekmez:
`1_kurulum.bat` → Bybit testnet API anahtarı → `.env` doldur → `3_demo_baslat.bat`
Bot her 15dk bar kapanışında tarar, setup olursa testnet'e emir atar,
Telegram'a bildirir, journal.db'ye kaydeder (`scripts/live_runner.py`).

## Hızlı Başlangıç

```bash
pip install -r requirements.txt

# 1) Veri indir (Binance public, API key gerekmez, ~5 dk)
python scripts/download_data.py

# 2) Backtest (komisyon + slippage dahil, kabul kriterleri otomatik)
python scripts/run_backtest.py
python scripts/run_backtest.py BTCUSDT --no-session   # filtresiz karşılaştırma

# 3) Testler
python -m pytest tests/

# 4) Webhook sunucusu (paper mode)
cp .env.example .env   # düzenle
uvicorn tradebot.server:app --port 8000
```

## Sıradaki Adımlar (roadmap)

1. `download_data.py` + `run_backtest.py` → gerçek veride sonuçlar
2. Kriterler geçerse (PF>1.3, DD<%15, 300+ işlem): Pine'ı TradingView'a kur,
   webhook'u sunucuya bağla, 300+ paper trade
3. Testnet 100+ işlem → canlı 100-500$

## İlkeler

- Backtest her zaman gerçekten KÖTÜ olmalı (muhafazakâr varsayımlar)
- Parametre optimizasyonu = curve fitting = yasak
- Stop her zaman borsada · 1R açılışta sabitlenir · kill switch manuel açılır
- AI analiz eder, trade AÇMAZ
