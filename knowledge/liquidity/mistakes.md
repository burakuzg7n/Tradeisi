# Liquidity — Yaygın Hatalar

## 1. Her Swing Low'u SSL Saymak
**Hata:** Her pivot low'u "likidite var" diye işaretlemek.  
**Doğru:** Belirgin, öne çıkan swing low'lar önemlidir. Gürültü içindekiler değil.  
**Sonuç:** Sahte sinyal bombardımanı.

## 2. Sweep Olmadan Entry Açmak
**Hata:** "Likidite seviyesine yaklaştı, artık döner" diye önden girmek.  
**Doğru:** Sweep tamamlanmalı (wick geçti, close geri döndü). Konfirmasyon lazım.  
**Sonuç:** Seviye geçilince stop hit olur, piyasa devam eder.

## 3. Sweep Sonrası Hemen Entry (Konfirmasyonsuz)
**Hata:** Sweep mumunda anında market order.  
**Doğru:** Sweep + LTF CHoCH veya FVG oluşumu bekle, sonra gir.  
**Sonuç:** Sweep devam edebilir, ikinci sweep olabilir.

## 4. HTF Bias'a Karşı Sweep Oynamak
**Hata:** HTF bearish, ama SSL sweep gördün diye long açtın.  
**Doğru:** Sweep, HTF bias yönünde anlam taşır.  
**Sonuç:** Küçük retracement'ta stop yenir, trend devam eder.

## 5. Equal Highs/Lows'u Yanlış Ölçmek
**Hata:** Çok geniş toleransla "bunlar eşit" demek.  
**Doğru:** Tolerans fiyat %0.1-0.2 bandında olmalı.  
**Sonuç:** Olmayan likidite seviyeleri işaretlenir.
