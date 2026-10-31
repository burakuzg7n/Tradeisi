# Risk Management — Yaygın Hatalar

## 1. Stop Loss'u Sonradan Belirlemek
**Hata:** Önce pozisyon aç, sonra "stop nereye koyayım?" diye sor.  
**Doğru:** Stop loss önce belirlenir, position size ona göre hesaplanır.  
**Sonuç:** Tersine yapıldığında risk kontrolsüz olur, her işlemde farklı gerçek risk taşırsın.

---

## 2. Loss Streak'te Pozisyon Büyütmek (Martingale)
**Hata:** 3 işlem kaybettikten sonra "geri almak için" 2x pozisyon aç.  
**Doğru:** Her işlem bağımsızdır, risk per trade sabit kalır.  
**Sonuç:** Martingale hesabı sıfırlar. Matematiksel olarak kaçınılmazdır.

---

## 3. Daily/Weekly Limit Dolduğunda Devam Etmek
**Hata:** "Bir tane daha, telafi ederim."  
**Doğru:** Kill switch tetiklendiğinde sistem kapanır, manuel override yapılmaz.  
**Sonuç:** Duygusal trading başlar, kayıplar katlanır.

---

## 4. RR'yi Trade Esnasında Değiştirmek
**Hata:** İşlem açıldıktan sonra target'ı küçültmek ("şimdilik kapatayım").  
**Doğru:** Entry öncesinde belirlenen target'a sadık kalınır.  
**Sonuç:** Expectancy düşer, uzun vadede sistem zarara döner.

---

## 5. Drawdown'ı Yüzde Yerine Para Birimi ile Ölçmek
**Hata:** "500 dolar düştüm, fena değil."  
**Doğru:** Her zaman yüzde ile ölç: 500$ / 5000$ = %10 drawdown.  
**Sonuç:** Gerçek hasar gizlenir, erken uyarı sistemi çalışmaz.

---

## 6. Backtestte Komisyon/Slippage Sıfır Bırakmak
**Hata:** Backtest'te gerçekçi maliyet yok → "mükemmel" sonuçlar.  
**Doğru:** Her işleme taker fee (%0.05-0.1) + slippage ekle.  
**Sonuç:** Gerçek trading'de PF 1.4 görünen strateji 1.0 çıkar.

---

## 7. Risk Engine'i Bypass Etmek
**Hata:** "Bu sefer özel durum, sistemi pas geçeceğim."  
**Doğru:** Risk engine her zaman araya girer, istisna yoktur.  
**Sonuç:** Bypass alışkanlık olur, sistem anlamsızlaşır.
