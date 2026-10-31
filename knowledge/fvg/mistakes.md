# FVG — Yaygın Hatalar

## 1. Küçük FVG'leri Sinyal Olarak Saymak
**Hata:** Her 1-2 pip'lik boşluğu FVG diye işaretlemek.  
**Doğru:** Minimum büyüklük filtresi koy (fiyatın %0.05'i gibi).  
**Sonuç:** Gürültü FVG'leri kalabalık oluşturur, gerçek sinyaller kaybolur.

## 2. Mitigate Edilmiş FVG'ye Girmek
**Hata:** Fiyat FVG'yi zaten %50+ doldurdu, tekrar döndüğünde yeniden entry.  
**Doğru:** Mitigate edilmiş FVG'ler artık daha zayıf. İlk retest en güçlüsüdür.  
**Sonuç:** Düşük olasılıklı setup'ta risk alınır.

## 3. FVG'yi Tek Başına Kullanmak (Bias Olmadan)
**Hata:** Bullish FVG gördüm → hemen long.  
**Doğru:** FVG + HTF bias + liquidity sweep üçü birlikte olmalı.  
**Sonuç:** HTF bearish iken bullish FVG'ye giren pozisyon trendde ezilir.

## 4. Stop'u FVG'nin Altına Koymamak
**Hata:** Rasgele stop koymak (örn. "10 pip altı").  
**Doğru:** Bullish FVG için stop = FVG bottom'ın biraz altı. Orayı geçerse FVG geçersiz.  
**Sonuç:** FVG kırılınca stop hit olması gerekir ama olmaz → büyük kayıp.

## 5. Repaint Riski
**Hata:** Pine Script'te `barstate.isconfirmed` kullanmadan FVG tespit etmek.  
**Doğru:** Her zaman `barstate.isconfirmed` ile mum kapanışını bekle.  
**Sonuç:** Backtest'te görünen sinyal gerçek zamanda olmaz (repaint).

## 6. Aynı Bölgede Çakışan FVG'leri Sayamamak
**Hata:** Üst üste 3 FVG var, hepsine ayrı ayrı girmek.  
**Doğru:** Çakışan FVG'leri tek bölge say, en geniş bölgeyi al.  
**Sonuç:** Aşırı pozisyon açılır, risk kontrolü bozulur.
