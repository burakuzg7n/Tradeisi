# Market Structure — Concept

## Temel Tanım

Market structure, fiyatın oluşturduğu Higher High (HH), Higher Low (HL), Lower High (LH), Lower Low (LL) zincirinin okunmasıdır. Her şey buradan başlar — bias (yön) belirlemeden entry aramak kör atış olur.

---

## Temel Yapı Taşları

### Swing High / Swing Low
- **Swing High:** Sol ve sağındaki mumlardan yüksek olan mum
- **Swing Low:** Sol ve sağındaki mumlardan düşük olan mum
- Pine Script'te: `ta.pivothigh()` ve `ta.pivotlow()` ile tespit edilir

### Trend Tanımı (SMC)
| Yapı | Trend |
|------|-------|
| HH + HL | Bullish |
| LH + LL | Bearish |
| Karışık | Range / Belirsiz |

---

## Break of Structure (BOS)

**Tanım:** Mevcut trendin devamını onaylayan kırılım.

- Bullish BOS: Fiyat son Swing High'ı kırar → trend devam ediyor
- Bearish BOS: Fiyat son Swing Low'u kırar → trend devam ediyor

**Önemli:** BOS, trendin içinde oluşan normal bir momentum hareketidir. Reversal anlamına gelmez.

```
Bullish trend örneği:
  HL → HH (BOS) → HL → HH (BOS) → ...
```

---

## Change of Character (CHoCH)

**Tanım:** Trendin tersine dönme sinyali. Mevcut yapıya aykırı kırılım.

- Bullish CHoCH: Bearish trendde fiyat son LH'ı kırar yukarı → olası reversal
- Bearish CHoCH: Bullish trendde fiyat son HL'ı kırar aşağı → olası reversal

**Fark:** BOS = trend devamı, CHoCH = trend değişimi

---

## HTF vs LTF Bias

### HTF (Higher Time Frame) Bias
- Kullanılan TF: Weekly, Daily, 4H
- Amaç: Genel yön belirle (bullish mi, bearish mi?)
- Bu yöne karşı trade yapılmaz

### LTF (Lower Time Frame) Entry
- Kullanılan TF: 1H, 15M, 5M
- Amaç: HTF bias yönünde optimal entry bul
- HTF bearish → LTF'de sadece short aranır

---

## SMC'nin Klasik TA'dan Farkı

| Klasik TA | SMC |
|-----------|-----|
| Trendline kırılımı | BOS/CHoCH |
| Support/Resistance | Order Block / FVG |
| Double Top/Bottom | Liquidity sweep + reversal |
| Volume spike | Imbalance / institutional order |

---

## İç Yapı (Internal Structure) vs Dış Yapı (External Structure)

- **External Structure:** Büyük swing high/low'lar (HTF görünür)
- **Internal Structure:** Küçük kırılımlar (LTF momentum, entry için)

Strateji: External structure bias verir, internal structure timing verir.

---

## Kullanılmayacak Kavramlar (Roadmap Notu)

Roadmap'e göre aşağıdakiler subjektif olduğundan sistemde yer almaz:
- AMD (Accumulation, Manipulation, Distribution) döngüleri
- PO3 (Power of Three)
- Inducement yorumları (subjektif olanlar)
- Tam subjektif ICT anlatımları
