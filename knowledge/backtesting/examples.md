# Backtesting — Örnekler

## Örnek 1: Başarılı Backtest Sonucu

```
Strateji: HTF Bias + SSL Sweep + FVG Retest
Veri: BTC/USDT 15M, Ocak 2024 - Aralık 2024
Komisyon: %0.055 taker (her yön)
Slippage: %0.01

Sonuçlar:
  Toplam işlem: 312
  Win Rate: 46.8%
  Profit Factor: 1.54 ✓ (> 1.3)
  Max Drawdown: 9.2% ✓ (< 15%)
  Expectancy: +0.38R/trade ✓ (> 0)
  Sharpe Ratio: 1.72 ✓ (> 1.0)
  
ONAY → Paper trading aşamasına geç
```

---

## Örnek 2: Başarısız Backtest

```
Strateji: Aynı ama NY KZ filtresi yok (tüm saatler)
Sonuçlar:
  Toplam işlem: 589
  Win Rate: 37.4%
  Profit Factor: 0.89 ✗ (< 1.0)
  Max Drawdown: 22.1% ✗ (> 15%)
  
Sorun: Gece saatlerinde düşük kaliteli setuplara giriliyor
Çözüm: Session filter ekle → tekrar backtest
```

---

## Örnek 3: Walk-Forward Test

```
In-Sample: Ocak 2023 - Haziran 2024 (18 ay)
  PF: 1.61, Win Rate: 49%, DD: 8%
  
Out-of-Sample: Temmuz 2024 - Aralık 2024 (6 ay)
  PF: 1.48, Win Rate: 46%, DD: 11%

Değerlendirme:
  Performans düştü ama hâlâ pozitif → overfit yok
  OOS'da da kriterleri karşılıyor → strateji geçerli
```

---

## Örnek 4: Komisyon Farkı

```
Komisyon sıfır:
  Net PnL: +$3,240
  PF: 1.72
  
Komisyon + slippage dahil:
  Net PnL: +$1,890
  PF: 1.38

→ Komisyon PF'yi %20 düşürdü. Sıfır komisyonla çalışsaydın yanılırdın.
```
