# Economic Events — Concept

## Temel Tanım

Ekonomik haberler fiyatta ani, büyük hareketler yaratır. Spread genişler, slippage artar, teknik analiz kısa süre işlevsizleşir. Haber yönetimi bir risk kontrol meselesidir.

---

## High Impact Haberler (BTC/ETH'yi Etkiler)

| Haber | Açıklama | Frekans |
|-------|----------|---------|
| **FOMC** | Fed faiz kararı | 6-8 haftada bir |
| **NFP** | ABD tarım dışı istihdam | Ayda bir (İlk Cuma) |
| **CPI** | ABD enflasyon verisi | Ayda bir |
| **PCE** | Fed'in tercih ettiği enflasyon göstergesi | Ayda bir |
| **GDP** | ABD büyüme verisi | Çeyreklik |
| **Fed Chair Konuşması** | Powell vb. açıklamalar | Düzensiz |

---

## Haber Öncesi/Sonrası Davranış

### Haber Öncesi (30-60 dakika)
- Spread genişler
- Volatilite artar ama yön belirsiz
- Sistem: **yeni trade açmaz**

### Haber Sırasında (0-5 dakika)
- Çok yüksek volatilite
- Sahte spike olabilir
- Sistem: **kesinlikle trade yok**

### Haber Sonrası (5-30 dakika)
- Gerçek yön oluşur
- Sweep → reversal fırsatı olabilir
- Sistem: **sinyal arıyor ama dikkatli**

---

## Sistem Entegrasyonu

1. Her gün sabah haber takvimi çekilir (economic calendar API)
2. Yüksek etkili haberler 30 dakika öncesinden sisteme kaydedilir
3. O zaman diliminde gelen sinyaller otomatik reddedilir
4. Haber geçtikten 15 dakika sonra sistem tekrar aktif olur

---

## API Kaynakları

- **ForexFactory API** (gayri resmi): Ücretsiz, kapsamlı
- **Investing.com API**: Ücretli ama güvenilir
- **TradingEconomics API**: Kapsamlı, ücretli
- **FMP (Financial Modeling Prep)**: Ekonomik takvim endpoint'i var

---

## Önemli Kural

FOMC ve NFP günleri crypto'da da sert hareket yaratır. BTC dolar bazlı varlık olduğundan ABD makro verileri direkt etkiler.
