# Volume — Yaygın Hatalar

## 1. Volume'ü Sinyal Olarak Kullanmak
**Hata:** "Hacim yüksek, gireceğim."  
**Doğru:** Volume filtre/konfirmasyon rolündedir. Tek başına sinyal üretmez.

## 2. Crypto'da Spot ve Futures Hacmini Karıştırmak
**Hata:** Spot hacim düşük ama futures yüksek → "gerçek hacim var".  
**Doğru:** Trading yaptığın exchange'in kendi hacim datasını kullan.  
**Sonuç:** Yanıltıcı hacim analizi.

## 3. CVD'yi Gerçek Taker Data Olmadan Hesaplamak
**Hata:** Sadece mum rengi ile (yeşil = alım, kırmızı = satım) CVD hesaplamak.  
**Doğru:** Gerçek CVD için tick-level taker buy/sell verisi gerekir.  
**Sonuç:** CVD tahmin olur, kesin divergence analizi yapılamaz.

## 4. Düşük Hacimli Sweepleri Geçerli Saymak
**Hata:** Hacim olmadan SSL sweep gördün, entry açtın.  
**Doğru:** Sweep + yüksek hacim spike = kurumsal katılım. Düşük hacimli sweep = sahte.  
**Sonuç:** "Stop hunt"lar aslında random hareket olabilir.

## 5. Volume Profile'ı Yanlış Zaman Dilimine Uygulamak
**Hata:** Günlük Volume Profile kullanıp HTF kararı vermek.  
**Doğru:** Analiz TF'i ile VP zaman dilimi eşleşmeli.
