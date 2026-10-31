# Risk Management — Concept

## Temel Tanım

Risk yönetimi, bir trade botunun hayatta kalmasını sağlayan sistemin kalbidir. Strateji ne kadar iyi olursa olsun, risk kontrolsüzse hesap sıfırlanır. Öncelik sırası: **Risk > Her şey**.

---

## Temel Kavramlar

### R Değeri (Risk Unit)
- 1R = bir işlemde riske edilen sermaye miktarı
- Örnek: 1000$ hesap, %0.5 risk → 1R = 5$
- Tüm P&L R cinsinden ifade edilir (para birimi değil)
- Bu sayede farklı sermaye büyüklükleri karşılaştırılabilir

### Risk Per Trade
- Roadmap hedefi: **%0.5 per trade**
- Maksimum: hiçbir zaman %1'i geçme
- Hesaplama: `risk_amount = account_balance * 0.005`

### Position Sizing
```
position_size = risk_amount / (entry_price - stop_loss_price)
```
- Stop loss **önce** belirlenir, position size **sonra** hesaplanır
- Asla "kaç lot alalım?" sorusundan başlanmaz

### Risk/Reward Ratio (RR)
- Minimum hedef: **1:2** (1R riske karşı 2R kazanç)
- Roadmap hedefi: 1:2 ve üzeri işlemler
- Beklenti formülü: `Expectancy = (Win% × Avg_Win_R) - (Loss% × Avg_Loss_R)`

---

## Hesap Koruma Seviyeleri

### Daily Loss Limit
- Günlük maksimum kayıp: **-3R**
- 3R kaybedildiğinde o gün trading durur
- Sisteme kill switch olarak kodlanır

### Weekly Loss Limit
- Haftalık maksimum kayıp: **-8R**
- 8R kaybedildiğinde haftalık trading durur

### Max Drawdown Kill Switch
- Hesap maksimum **%10** düşerse sistem kapanır
- Manuel inceleme gerektirir, otomatik devam etmez

---

## Drawdown Türleri

| Tür | Açıklama |
|-----|----------|
| Peak-to-Trough DD | Zirve ile dip arasındaki fark |
| Max Drawdown | Tarihsel en büyük düşüş |
| Current Drawdown | Şu anki zirveye göre düşüş |

---

## Expectancy Formülü

```
Expectancy = (Win_Rate × Avg_Win) - (Loss_Rate × Avg_Loss)
```

Pozitif expectancy → sistem uzun vadede kazanır.

Örnek:
- Win Rate: %45, Avg Win: 2R, Avg Loss: 1R
- Expectancy = (0.45 × 2) - (0.55 × 1) = 0.90 - 0.55 = **+0.35R per trade**

---

## Profit Factor

```
Profit Factor = Gross Profit / Gross Loss
```

- PF > 1.3 → kabul edilebilir minimum (roadmap hedefi)
- PF > 1.5 → iyi
- PF > 2.0 → mükemmel
- PF < 1.0 → sistem zararda

---

## Margin ve Leverage

- Yüksek leverage = pozisyon başına daha az sermaye gereksinimi ≠ daha az risk
- Risk her zaman stop distance × position size'dır
- Leverage sadece position sizing hesabında araçtır, risk artırmak için değil
