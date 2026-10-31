# FVG — Örnekler

## Örnek 1: Bullish FVG Tespiti

```
Mum 1: High = 49.800
Mum 2: Büyük bullish (momentum)
Mum 3: Low = 50.100

FVG: 49.800 → 50.100 (300$ genişlik)
Midpoint: 49.950
OTE zone (%50-%79 doluluk): 49.863 → 49.950
  (%50 doluluk = midpoint 49.950, %79 doluluk = 49.800 + 300×0.21 = 49.863)
```

Senaryo: Fiyat 50.500'e çıktı, sonra 49.940'a geri döndü → OTE zone içinde → long entry.
Not: OTE bölgesi midpoint'in ALTINDADIR — daha derin retrace = daha iyi fiyat + daha dar stop.

---

## Örnek 2: Tam Setup (Strateji Bütünü)

```
4H: Bullish BOS, HL oluşuyor → BIAS: BULLISH
15M: 
  1. Swing low 48.500'e SSL sweep oluştu (wick 48.200, close 48.700)
  2. Sweep sonrası momentum yukarı → Bullish FVG oluştu: 48.700 - 49.000
  3. Fiyat 49.200'e gitti
  4. Geri dönerek FVG'ye retest: 48.840 (OTE zone içi)
  
ENTRY: 48.840 (barstate.isconfirmed sonrası)
STOP:  48.680 (FVG bottom altı)
TARGET: 50.500 (yakın BSL / swing high)

Risk:   48.840 - 48.680 = 160$
Reward: 50.500 - 48.840 = 1660$
RR: 1660/160 = 10.4R ✓✓✓
```

---

## Örnek 3: Geçersiz FVG (Mitigasyon)

```
Bullish FVG: 49.000 - 49.300
Fiyat 49.000'in ALTINA indi (48.900) → FVG tamamen doldu ve geçildi
FVG → Mitigated (geçersiz)

Artık bu FVG long için kullanılmaz.
Inverse FVG olarak kısa vadeli direnç olabilir.
NOT: Fiyatın entry zone'a (%50-%79 doluluk) inmesi mitigasyon DEĞİLDİR —
o, beklenen retest'tir. Mitigasyon = karşı sınırın tamamen geçilmesi.
```

---

## Örnek 4: Bearish FVG

```
Mum 1: Low = 52.000
Mum 2: Büyük bearish (momentum aşağı)
Mum 3: High = 51.500

FVG: 51.500 → 52.000
Midpoint: 51.750
OTE zone (%50-%79 doluluk): 51.750 → 51.895 (midpoint'in ÜSTÜ — alttan dolar)
```

HTF bearish + BSL sweep olduktan sonra fiyat bu FVG'ye retest yaparsa → short entry.
Stop: FVG top üzeri (52.050)
