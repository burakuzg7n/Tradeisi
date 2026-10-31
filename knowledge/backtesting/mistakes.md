# Backtesting — Yaygın Hatalar

## 1. Curve Fitting (Overfitting)
**Hata:** "RSI period 14 yerine 11 olunca PF 1.8'e çıkıyor, kullanalım."  
**Doğru:** Parametreler strateji mantığından gelir, backtest'ten optimize edilmez.  
**Sonuç:** Out-of-sample'da sistem çöker.

## 2. Sıfır Komisyon/Slippage
**Hata:** TradingView backtest varsayılanı → commission = 0.  
**Doğru:** Her işlem için taker fee + slippage ekle.  
**Sonuç:** Görünen PF 1.5 → gerçekte 1.0. Hatta zararda.

## 3. Look-Ahead Bias (Future Data Leak)
**Hata:** `close[0]` yerine `close[-1]` kullanmak (o mumu daha görmedin).  
**Doğru:** Her karar o mumun kapanışı bilinmeden yapılmış gibi modellenmeli.  
**Sonuç:** Gerçekçi olmayan sonuçlar → canlıda hayal kırıklığı.

## 4. Repaint Eden İndikatörler
**Hata:** Pine Script'te `security()` ile multi-TF data çekmek → repaint.  
**Doğru:** `security(..., lookahead=barmerge.lookahead_off)` kullan.  
**Sonuç:** Backtest perfect görünür, gerçek zamanda çalışmaz.

## 5. Çok Az İşlem Sayısı
**Hata:** 30 işlemle "PF 2.0, harika strateji!"  
**Doğru:** En az 100, tercihen 300+ işlem. İstatistiksel anlamlılık gerekir.  
**Sonuç:** 30 işlem şans eseri kârlı olabilir. 300'de gerçek performans görülür.

## 6. Tek Dönem Test
**Hata:** Sadece 2024-2025 bull market verisiyle test etmek.  
**Doğru:** Farklı market rejimleri: bull, bear, range. Walk-forward test.  
**Sonuç:** Strateji sadece bull'da çalışıyor ama bear için uygun değil.

## 7. Unrealistic Fill Assumption
**Hata:** Limit order verince her zaman dolar varsaymak.  
**Doğru:** Limit order bazen dolmaz. Başarısız fill oranını da dahil et.  
**Sonuç:** Backtest'teki tüm setuplara girmişsin gibi hesap yapar, gerçekte %80'ine girersin.
