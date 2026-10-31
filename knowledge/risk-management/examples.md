# Risk Management — Örnekler

## Örnek 1: Position Sizing Hesabı

**Durum:** 1000$ hesap, BTC/USDT, entry 50.000$, stop 49.500$

```
risk_amount = 1000 × 0.005 = 5$
stop_distance = 50.000 - 49.500 = 500$
position_size = 5 / 500 = 0.01 BTC
```

Target 51.000$ ise:
```
reward = 51.000 - 50.000 = 1000$
risk   = 500$
RR = 1000 / 500 = 2.0 ✓ (minimum karşılandı)
```

---

## Örnek 2: Kill Switch Senaryosu

**Durum:** Gün içinde 3 işlem, hepsi 1R kayıp = -3R

```
İşlem 1: -1R → daily_pnl = -1R
İşlem 2: -1R → daily_pnl = -2R
İşlem 3: -1R → daily_pnl = -3R → KILL SWITCH AKTİF
```

Sistem o gün için kapanır. Ertesi gün sıfırlanır.

---

## Örnek 3: Expectancy Hesabı

**45 işlemlik paper trade sonucu:**
- 20 kazanan işlem, ortalama +2.1R
- 25 kaybeden işlem, ortalama -1.0R

```
Win Rate = 20/45 = 0.444
Expectancy = (0.444 × 2.1) - (0.556 × 1.0)
           = 0.932 - 0.556
           = +0.376R per trade ✓
```

100 işlemde beklenen kazanç: **37.6R**

---

## Örnek 4: Drawdown Hesabı

| Gün | Balance | Peak | DD% |
|-----|---------|------|-----|
| 1   | 1000    | 1000 | 0%  |
| 2   | 1020    | 1020 | 0%  |
| 3   | 980     | 1020 | 3.9%|
| 4   | 950     | 1020 | 6.9%|
| 5   | 920     | 1020 | 9.8%|
| 6   | 915     | 1020 | **10.3% → KILL SWITCH** |

---

## Örnek 5: Kötü RR ile Expectancy Sorunu

**Win Rate %60, ama RR 1:0.8 (sık görülen hata)**

```
Expectancy = (0.60 × 0.8) - (0.40 × 1.0)
           = 0.48 - 0.40
           = +0.08R
```

Çok düşük. Komisyon eklenince negatife döner.

**Aynı Win Rate, RR 1:2 ile:**
```
Expectancy = (0.60 × 2.0) - (0.40 × 1.0)
           = 1.20 - 0.40
           = +0.80R ✓
```
