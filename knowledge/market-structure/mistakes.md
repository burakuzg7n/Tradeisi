# Market Structure — Yaygın Hatalar

## 1. Pivot Lookback'i Çok Küçük Seçmek
**Hata:** `pivothigh(high, 1, 1)` gibi çok hassas ayar → her mum swing sayılır.  
**Doğru:** En az sol 3, sağ 3 kullan. HTF için daha büyük değerler.  
**Sonuç:** Noise'dan sinyal üretilir, her gürültü BOS olarak işaretlenir.

## 2. HTF Bias Olmadan LTF Entry Aramak
**Hata:** 5M'de bullish yapı görünce long aç, ama 4H bearish.  
**Doğru:** HTF bias her zaman filtre olarak devrede olmalı.  
**Sonuç:** Countertrend trade → düşük win rate, yüksek drawdown.

## 3. BOS ile CHoCH'u Karıştırmak
**Hata:** Her kırılımı "reversal sinyali" olarak okumak.  
**Doğru:** BOS trend devamı, CHoCH trend değişimi. İkisi farklı işlemdir.  
**Sonuç:** Yanlış yönde entry alınır.

## 4. Close Yerine Wick ile Kırılım Saymak
**Hata:** Fiyat sadece wick ile seviyeyi geçti, ama close altında kapandı → BOS yok.  
**Doğru:** Kırılım close bazlı değerlendirilmeli (`barstate.isconfirmed`).  
**Sonuç:** Sahte BOS sinyalleri oluşur, repaint riski artar.

## 5. Tek TF'e Bakmak
**Hata:** Sadece 15M veya sadece 1H kullanmak.  
**Doğru:** En az iki TF: HTF bias + LTF entry.  
**Sonuç:** Context'siz trade → rastgele sonuçlar.

## 6. Range'de Trend Okumaya Çalışmak
**Hata:** Fiyat range'deyken HH-HL veya LH-LL zinciri yok, yine de trend iddiası.  
**Doğru:** Range tespit edilince beklenir ya da range stratejisi uygulanır.  
**Sonuç:** Sürekli kırılım bekleyen, sürekli yanılan pozisyonlar.
