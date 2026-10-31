# Liquidity — Örnekler

## Örnek 1: Klasik SSL Sweep + Reversal

```
HTF: Bullish bias (4H HH-HL zinciri devam ediyor)

Fiyat hareketi (15M):
  48500 (swing low kuruldu)
  → fiyat 48200'e düştü (SSL sweep, wick)
  → close 48600'de kapandı (sweep tamamlandı)
  → 15M bullish CHoCH oluştu
  → LONG entry: 48620
  → Stop: 48150 (sweep altı)
  → Target: 49500 (swing high, BSL)
```

Risk hesabı:
```
stop distance = 48620 - 48150 = 470$
risk = 5$ (1000$ hesap, %0.5)
position = 5 / 470 = 0.0106 BTC
reward (1:2) = target 49560
RR = (49500 - 48620) / 470 = 1.87 ≈ 2R ✓
```

---

## Örnek 2: Equal Lows Sweep

```
Fiyat 3 kez 49.000$ seviyesine geldi, hep tuttu:
  EQL: 49.010, 48.995, 49.005 → yaklaşık 49.000

Sonraki seferde:
  → 48.850'ye spike (EQL sweep)
  → close 49.100'de geri döndü
  → Güçlü SSL sweep sinyali
```

---

## Örnek 3: Sahte Sweep (Devam Eden)

```
Swing low: 47.000
Fiyat 46.800'e indi (sweep gibi görünüyor)
Ama close 46.750'de kapandı (close hâlâ altında!)

→ Bu sweep DEĞİL → hâlâ düşüş devam ediyor
→ Entry yok, bekle
```

**Kural:** Sweep = wick geçti + close geri döndü. İkisi birlikte olmak zorunda.
