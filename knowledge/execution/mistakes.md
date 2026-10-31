# Execution — Yaygın Hatalar

## 1. Market Order Her Yerde Kullanmak
**Hata:** Her entry için market order → spread + slippage her seferinde ödenir.  
**Doğru:** FVG retest gibi beklenebilir setuplarda limit order kullan.  
**Sonuç:** Yüksek frekanslı bot yüzlerce işlemde fazladan %0.1 öder → PF erir.

## 2. Stop Loss'u Exchange'e Koymamak
**Hata:** Stop loss'u bot'ta yazılı tutmak, exchange'de yok.  
**Doğru:** Her pozisyonla birlikte exchange'e stop-market gönder.  
**Sonuç:** Bot çökerse veya bağlantı kesilirse korumasız açık pozisyon kalır.

## 3. Rate Limit'i Göz Ardı Etmek
**Hata:** Çok sayıda API çağrısı → 429 Too Many Requests.  
**Doğru:** ccxt'nin `enableRateLimit: True` ayarını aç. Exponential backoff ekle.  
**Sonuç:** Exchange bağlantısı kesilir, kritik anda order gönderilemez.

## 4. Testnet'ten Canlıya Geçişte API Key Değiştirmeyi Unutmak
**Hata:** Canlı API key yanlışlıkla testnet endpoint'ine gönderilir (veya tersi).  
**Doğru:** `testnet=True/False` flag'ini env variable'dan al, hardcode etme.  
**Sonuç:** Ya gerçek para testnet'e gider ya da testnet orderi canlıya.

## 5. Partial Fill'i Görmezden Gelmek
**Hata:** Limit order kısmen doldu, sistemi tam dolmuş gibi davranıyor.  
**Doğru:** Order status kontrol et: 'open', 'partially_filled', 'closed'.  
**Sonuç:** Stop loss tam pozisyon için konulur ama sadece yarısı açık → yanlış risk.

## 6. Webhook Authentication Olmadan Çalışmak
**Hata:** FastAPI endpoint'i herkese açık → herkes sinyal gönderebilir.  
**Doğru:** Bearer token veya HMAC imzalama zorunlu.  
**Sonuç:** Kötü niyetli istek → sahte trade.

## 7. Async/Await Karışıklığı
**Hata:** CCXT async'i sync bağlamda çağırmak → `RuntimeError`.  
**Doğru:** Tüm execution pipeline async/await zincirine uymalı.  
**Sonuç:** Order gönderilmez, sessizce başarısız olur.
