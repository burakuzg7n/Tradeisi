# Sessions — Concept

## Temel Tanım

Forex ve crypto piyasaları 24 saat açık olsa da tüm saatler eşit değildir. Kurumsal oyuncular belirli seans saatlerinde aktiftir. Doğru seansta trade etmek win rate'i doğrudan etkiler.

---

## Ana Seanslar (UTC Saatleriyle)

| Seans | UTC | İstanbul (UTC+3) | Özellik |
|-------|-----|------------------|---------|
| **Asian** | 00:00 - 09:00 | 03:00 - 12:00 | Düşük hacim, range |
| **London** | 07:00 - 16:00 | 10:00 - 19:00 | Yüksek hacim, trend |
| **New York** | 13:00 - 22:00 | 16:00 - 01:00 | En yüksek hacim |
| **London+NY** | 13:00 - 16:00 | 16:00 - 19:00 | Çakışma = en hareketli |

---

## Seansa Göre Strateji

### Asian Session
- Genellikle range yapı
- Likiditeler birikir: EQH ve EQL oluşur
- London açılışında bu likiditeler sweep edilir
- Strateji: Asian range'ı işaretle, London sweepini bekle

### London Session (Killzone: 07:00-09:00 UTC)
- En önemli hareketin başladığı yer
- Asian range sweep → FVG/OB retest → büyük hareket
- BTC/ETH için de geçerli (kripto artık kurumsal kalıplara uyuyor)

### New York Session (Killzone: 13:00-15:00 UTC)
- Günün ikinci büyük hareketi
- London tersi ya da London devamı
- "New York Reversal": London trendinın tersine döner

### London Close (15:00-16:00 UTC)
- Trend zayıflar, pozisyonlar kapanır
- Bu saatte açılan pozisyonlar riskli

---

## Killzone Kavramı

Killzone = Seansın en hareketli ilk 1-2 saati. Trade'ler burada aranır.

- London KZ: 07:00 - 09:00 UTC
- NY KZ: 13:00 - 15:00 UTC

---

## BTC/ETH İçin Seans Önemi

Kripto teknik olarak 24 saat açık. Ancak:
- NY seansında hacim zirve yapar
- London KZ'de ciddi hareketler olur
- Asian'da range genellikle 2-3% içinde kalır
- Haber saatleri (NFP, FOMC vb.) NY seansına denk gelir

---

## Session Filter

Sistemde seans filtresi: **Sadece London KZ veya NY KZ sırasında entry aç.**
Gece (Asian) gelen sinyaller reddedilir.

```python
VALID_HOURS_UTC = [
    range(7, 10),   # London KZ
    range(13, 16),  # NY KZ
]
```
