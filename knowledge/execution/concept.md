# Execution — Concept

## Sistem Mimarisi

Roadmap'ten:
```
TradingView → Webhook → FastAPI → Queue → Risk Engine → Execution Engine → Exchange → Journal
```

Her bileşen bağımsız çalışır ve hata yönetimi kendi içinde tamamlanır.

---

## Bileşenler

### TradingView (Sinyal Kaynağı)
- Pine Script sinyal üretir
- `barstate.isconfirmed` ile mum kapanışını bekler
- Webhook JSON formatında FastAPI'ya gönderir

### FastAPI (Webhook Alıcı)
- TradingView webhook'larını karşılar
- Gelen veriyi validate eder
- Redis queue'ya atar

### Redis Queue (Tampon)
- Sinyallerin sırayla işlenmesini sağlar
- Rate limit aşımını engeller
- Yeniden deneme mekanizması içerir

### Risk Engine (Filtre)
- can_trade() kontrolü
- Position size hesaplama
- Kill switch yönetimi

### Execution Engine (Order Manager)
- CCXT Async ile exchange'e bağlanır
- Market/Limit order yönetimi
- Stop loss ve take profit koyar

### Exchange (Bybit / Binance)
- Gerçek/testnet ortam
- API rate limit yönetimi

### Journal (Kayıt)
- Her işlemin tam geçmişi
- PostgreSQL'e yazar

---

## Webhook JSON Standardı

```json
{
  "symbol": "BTCUSDT",
  "direction": "long",
  "entry": 50000.0,
  "stop_loss": 49500.0,
  "take_profit": 51000.0,
  "setup": "ssl_sweep_fvg",
  "timeframe": "15",
  "htf_bias": "bullish",
  "session": "london_kz",
  "volume_ratio": 1.8,
  "fvg_top": 49900.0,
  "fvg_bottom": 49700.0,
  "timestamp": "2026-06-24T07:45:00Z"
}
```

---

## Order Türleri

| Durum | Order Tipi | Neden |
|-------|-----------|-------|
| FVG retest bekleniyorsa | Limit order | Daha iyi fiyat |
| Momentum sweep sonrası | Market order | Hız önemli |
| Stop Loss her zaman | Stop-Market | Slippage engeli |
| Take Profit | Limit order | Daha iyi fiyat |

---

## State Machine

```
IDLE → SIGNAL_RECEIVED → RISK_CHECKED → ORDER_PLACED
  ↓                           ↓
REJECTED               POSITION_OPEN
                            ↓
                    TAKE_PROFIT / STOP_LOSS
                            ↓
                         CLOSED → JOURNAL
```

---

## Hata Yönetimi Prensipleri

1. **Retry mekanizması:** API hatalarında 3 kez yeniden dene, exponential backoff
2. **Timeout:** Her API çağrısı maksimum 5 saniye
3. **Partial fill:** Order kısmen dolursa → tam dolana dek bekle ya da iptal et
4. **Network kesintisi:** Açık pozisyon varsa → reconnect sonrası pozisyon durumu sorgula
5. **Exchange down:** Queue'da beklet, sistemi durdurma
