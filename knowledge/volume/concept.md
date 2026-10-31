# Volume Analysis — Concept

## Temel Tanım

Hacim, bir zaman diliminde el değiştiren işlem miktarıdır. Fiyat hareketi + hacim = gerçek anlamı olan hareket. Hacim olmadan fiyat hareketi güvenilir değildir.

---

## Temel Kurallar

| Durum | Anlam |
|-------|-------|
| Fiyat ↑ + Hacim ↑ | Güçlü bullish hareket (kurumsal katılım) |
| Fiyat ↑ + Hacim ↓ | Zayıf yükseliş, reversal yakın olabilir |
| Fiyat ↓ + Hacim ↑ | Güçlü bearish hareket (satış baskısı) |
| Fiyat ↓ + Hacim ↓ | Zayıf düşüş, toparlanma yakın olabilir |

---

## Delta Volume (CVD)

**Cumulative Volume Delta (CVD):** Alım emirleri - satım emirleri birikimli toplamı.

- CVD ↑ + Fiyat ↑ → Güçlü bullish momentum
- CVD ↓ + Fiyat ↑ → Divergence → yakın reversal sinyali
- CVD ↑ + Fiyat ↓ → Divergence → yakın bullish reversal

---

## Volume Profile

Belirli bir fiyat seviyesinde gerçekleşen işlem hacmini gösterir.

- **HVN (High Volume Node):** Çok işlem yapılan seviye → güçlü S/R
- **LVN (Low Volume Node):** Az işlem yapılan seviye → fiyat hızlı geçer
- **POC (Point of Control):** En yüksek hacmin olduğu tek fiyat seviyesi
- **VAH/VAL (Value Area High/Low):** Toplam hacmin %70'inin gerçekleştiği bölge

---

## SMC ile Volume Entegrasyonu

- FVG bölgeleri → genellikle LVN'ye karşılık gelir (boşluk = imbalance)
- Order Block bölgeleri → HVN ile çakışıyorsa çok güçlü
- Liquidity sweep + yüksek hacim → sweep'in kurumsal olduğunu doğrular

---

## Filtre Olarak Kullanım

Sistemde volume, sinyal üretmez; **filtre** olarak çalışır:
- BOS + düşük hacim → şüpheli, bekle
- SSL sweep + yüksek hacim spike → güvenilir sweep
- FVG'ye retest + hacim azalıyor → fiyat FVG'den geri dönebilir
