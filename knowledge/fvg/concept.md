# Fair Value Gap (FVG) — Concept

## Temel Tanım

Fair Value Gap (FVG), fiyatın çok hızlı hareket ettiği ve arz-talep dengesinin kurulmadığı boşluklardır. Üç ardışık mum ile oluşur. Fiyat bu bölgelere geri döner ve genellikle retest yapar.

**Diğer isimler:** Imbalance, Gap, IFVG (Inverse FVG)

---

## Oluşum Kuralı

### Bullish FVG
```
Mum 1: Normal mum
Mum 2: Büyük yükseliş mumu (momentum)
Mum 3: Yukarı devam

FVG bölgesi = Mum 1'in HIGH ile Mum 3'ün LOW arasındaki boşluk
Koşul: Mum 3 LOW > Mum 1 HIGH → boşluk var
```

### Bearish FVG
```
Mum 1: Normal mum
Mum 2: Büyük düşüş mumu (momentum)
Mum 3: Aşağı devam

FVG bölgesi = Mum 1'in LOW ile Mum 3'ün HIGH arasındaki boşluk
Koşul: Mum 3 HIGH < Mum 1 LOW → boşluk var
```

---

## FVG'nin Önemi

1. **Kurumsal emir doldurmak:** Büyük oyuncular pozisyonlarını bu bölgelerde tamamlar
2. **Support/Resistance:** FVG seviyeleri güçlü S/R noktası oluşturur
3. **Entry bölgesi:** Fiyat FVG'ye döndüğünde entry aranır

---

## FVG Türleri ve Güç Sıralaması

| Tür | Açıklama | Güç |
|-----|----------|-----|
| HTF FVG | 4H, Daily'de oluşan | Çok güçlü |
| LTF FVG | 15M, 1H'de oluşan | Orta |
| Mitigated FVG | Fiyat içine girdi, ama geçmedi | Zayıflıyor |
| Inverse FVG (IFVG) | FVG kırıldı, artık ters taraftan S/R | Orta |

---

## FVG Mitigasyon

- Fiyat FVG'nin **50%'sine** kadar dolduğunda mitigasyon başlamış sayılır
- **Tam doldurmak zorunda değil:** Fiyat FVG'nin ortasından dönebilir
- FVG tamamen geçilirse → o FVG geçersiz, artık destek/direnç olarak çalışmaz (IFVG'ye dönebilir)

---

## Strateji ile Bağlantısı

**HTF Bias + Liquidity Sweep + FVG Retest:**
1. HTF bias al (bullish)
2. SSL sweep bekle
3. Sweep sonrası oluşan bullish FVG'yi işaretle
4. Fiyat FVG'ye retest yaparsa → long entry
5. Stop: FVG'nin altı
6. Target: Yakın swing high / BSL

---

## Optimal Entry Zone (OTE)

FVG içinde en iyi entry bölgesi: **%50 - %79 arası**
- %50: FVG ortası (güvenli)
- %79: Fibonacci 0.79 seviyesi (agresif ama dar stop)
