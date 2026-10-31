# Backtesting — Concept

## Temel Tanım

Backtest, bir stratejinin geçmiş veriye uygulanarak istatistiksel performansının ölçülmesidir. Canlı trade öncesindeki zorunlu doğrulama adımıdır. Roadmap kriteri: **en az yüzlerce işlem, PF > 1.3, DD < %15**.

---

## Backtest Türleri

| Tür | Açıklama | Güvenilirlik |
|-----|----------|--------------|
| **Manuel** | Her işlemi elle replay'de incele | Yüksek (subjektif unsur var) |
| **Coded (Pine Script)** | Strateji.pine ile otomatik | Orta (repaint riski) |
| **Python Engine** | Custom backtester | Yüksek (full kontrol) |

Sistem için: Pine Script backtest + Python konfirmasyon.

---

## Yasaklar (Roadmap'ten)

1. **Curve Fitting:** Parametreleri backtest'e göre optimize etme (overfitting)
2. **Future Data Leak:** Gelecekteki veriyi kullanma
3. **Sıfır Komisyon:** Her işleme taker fee + slippage eklenmeli
4. **Repaint:** `barstate.isconfirmed` olmadan Pine Script backtest geçersiz

---

## Zorunlu Metrikler

| Metrik | Hedef | Eşik |
|--------|-------|------|
| Profit Factor | > 1.5 | > 1.3 |
| Win Rate | > 45% | > 35% |
| Max Drawdown | < %10 | < %15 |
| Expectancy | > 0.3R | > 0 |
| Sharpe Ratio | > 1.5 | > 1.0 |
| Minimum İşlem Sayısı | 300+ | 100+ |

---

## Walk-Forward Validation

Overfitting'e karşı:
1. Veriyi İN-SAMPLE ve OUT-OF-SAMPLE olarak böl (örn. 70/30)
2. Strateji parametrelerini sadece in-sample'a göre belirle
3. Out-of-sample'da test et → performans düşüyorsa overfit var

---

## Monte Carlo Simülasyonu

Backtest sonuçlarının güvenilirliği:
- Aynı işlemleri rastgele sırayla tekrar simüle et (1000 kez)
- En kötü %5 senaryodaki drawdown = gerçekçi worst-case
- Hedefe ulaşamayan % → strateji risk değerlendirmesi

---

## Komisyon ve Slippage

Bybit/Binance varsayımları:
- Taker fee: %0.055 (her entry ve exit)
- Slippage: 1-2 pip (ortalama)
- Toplam maliyet per round trip: ~%0.15

```python
COMMISSION_PER_TRADE = 0.00055  # taker fee (tek yön)
SLIPPAGE_PCT = 0.0001           # %0.01 slippage
```
