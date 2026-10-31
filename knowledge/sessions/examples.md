# Sessions — Örnekler

## Örnek 1: Asian Range → London Sweep → Entry

```
Asian seans (00:00-07:00 UTC):
  Range oluştu: High 50.200, Low 49.800
  EQL: 49.800 (iki kez test edildi)
  EQH: 50.200 (iki kez test edildi)

London KZ başladı (07:00 UTC):
  07:15 → fiyat 49.650'ye spike (Asian Low sweep)
  07:20 → close 49.850 (sweep tamamlandı)
  07:25 → 15M bullish CHoCH oluştu

ENTRY: 49.870 (London KZ içi, seans aktif ✓)
STOP: 49.620 (sweep altı)
TARGET: 50.500 (Asian High + üzeri BSL)
```

---

## Örnek 2: NY KZ Reversal

```
London seans: 48.000'den 50.000'e yükseliş (+2000$)
NY KZ başladı (13:00 UTC):
  Bearish FVG oluştu: 49.500-49.800
  BSL sweep: 50.200'e spike, close 49.900
  NY KZ aktif + bearish CHoCH

ENTRY (short): 49.870 (NY KZ ✓)
STOP: 50.250
TARGET: 48.500
```

---

## Örnek 3: Killzone Dışı Sinyal → Reddedildi

```
Zaman: 22:00 UTC (Asian başlangıcı)
Sinyal: SSL sweep + bullish FVG
can_enter_trade() → False ("Killzone dışı, entry bekleniyor")

Aksiyon: Sinyal loglandı ama trade açılmadı.
Sonuç doğru: Fiyat gece boyunca range'de kaldı, sabah gerçek harekete başladı.
```

---

## Seans-Performans Takibi

Journal'da her işlemin seans bilgisi tutulur. Örnek analiz:
```
London KZ: 45 işlem, Win Rate %58, PF 1.6
NY KZ:     38 işlem, Win Rate %55, PF 1.4
Overlap:   12 işlem, Win Rate %50, PF 1.1
Off-hours:  5 işlem, Win Rate %30, PF 0.7 ← kapatıldı
```
→ Off-hours trade etmeyi durdur. Overlap'i monitör et.
