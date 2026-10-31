# Liquidity — Concept

## Temel Tanım

Liquidity (likidite), büyük alıcı ve satıcıların emirlerini doldurmak için ihtiyaç duydukları bölgelerdir. Fiyat, stop loss emirlerinin yoğunlaştığı seviyelere yönelir — bu emirleri doldurur, sonra gerçek yönünde hareket eder.

**Temel ilke:** Fiyat likiditeyi arar, burada dolar, sonra döner.

---

## Liquidity Türleri

### Buy-Side Liquidity (BSL)
- Swing high'ların üzerinde biriken stop loss emirleri
- Short pozisyon tutanların stop'ları burada
- Fiyat yukarı sweep yaparsa bu emirleri tetikler → sonra aşağı döner (bearish sweep)

### Sell-Side Liquidity (SSL)
- Swing low'ların altında biriken stop loss emirleri
- Long pozisyon tutanların stop'ları burada
- Fiyat aşağı sweep yaparsa bu emirleri tetikler → sonra yukarı döner (bullish sweep)

---

## Equal Highs / Equal Lows

- Birbirine çok yakın iki veya daha fazla swing high → EQH (Equal Highs)
- Birbirine çok yakın iki veya daha fazla swing low → EQL (Equal Lows)
- Bu seviyeler stop loss yoğunlaşma noktasıdır
- **Fiyat EQH/EQL'e sweep yapmadan önce gerçek hareketi başlatmaz (çoğunlukla)**

---

## Liquidity Sweep (Stop Hunt)

**Senaryo:**
1. Fiyat belirgin swing low seviyesine yaklaşır
2. Kısa süreli spike ile o seviyenin altına iner (SSL'yi temizler)
3. Hızla geri döner ve yukarı hareket başlar

**Bu nedenle önemlidir:**
- Sweep sonrası entry, iyi bir risk/reward sunar
- Stop loss sweep altına koyulur → dar stop, geniş hedef

---

## Liquidity Pool vs Void

| Kavram | Açıklama |
|--------|----------|
| Liquidity Pool | Emir yoğunluğunun olduğu seviye |
| Void / Imbalance | Fiyatın hızlı geçtiği, iki tarafın da olmadığı bölge (FVG ile örtüşür) |

---

## Strateji ile Bağlantı

Roadmap stratejisi: **HTF Bias + Liquidity Sweep + FVG Retest**

1. HTF bias belirle (örn. bullish)
2. Sell-side liquidity seviyesini işaretle (önemli swing low'lar)
3. Fiyatın o seviyeye sweep yapmasını bekle
4. Sweep sonrası bullish CHoCH veya FVG oluşursa → long entry
