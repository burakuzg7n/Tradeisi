# Execution — Örnekler

## Örnek 1: Tam Sinyal Akışı

```
1. Pine Script: FVG retest + HTF bullish bias → signal üret
2. barstate.isconfirmed = true → webhook gönder

POST /webhook
{
  "symbol": "BTCUSDT",
  "direction": "long",
  "entry": 49850.0,
  "stop_loss": 49480.0,
  "take_profit": 50960.0,
  ...
}

3. FastAPI → validate → Redis queue
4. Consumer → can_trade() → True
5. Position size:
   balance=1000$, risk=0.5%
   risk_amount = 5$
   stop_distance = 49850 - 49480 = 370$
   size = 5 / 370 = 0.0135 BTC

6. Bybit order:
   Limit buy 0.0135 BTC @ 49850
   SL: 49480 (stop-market)
   TP: 50960 (limit)

7. Dolduktan sonra journal'a kayıt
```

---

## Örnek 2: Retry Senaryosu

```python
# Rate limit hatası
result = await exec_engine.place_order(...)
# → {"status": "retry"}

# Retry logic
for attempt in range(3):
    result = await exec_engine.place_order(...)
    if result['status'] == 'ok':
        break
    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
else:
    # 3 deneme başarısız → log + alert
    log.error("Order failed after 3 retries")
```

---

## Örnek 3: Testnet → Canlı Geçiş Checklist

```
Environment değişkeni:
  TRADING_MODE=testnet → testnet=True
  TRADING_MODE=live    → testnet=False

.env.testnet:
  BYBIT_API_KEY=testnet_key_xxx
  BYBIT_SECRET=testnet_secret_xxx

.env.live:
  BYBIT_API_KEY=live_key_xxx
  BYBIT_SECRET=live_secret_xxx

Kontrol:
  ✓ API key tipi doğru mu?
  ✓ Exchange sandbox mode doğru mu?
  ✓ Position size limitleri kontrol edildi mi?
  ✓ İlk işlem minimum (0.001 BTC) olarak test edildi mi?
```
