# Aday değerlendirme — Cash-and-carry (spot–vadeli fark)

**Tarih:** 2 Kasım 2026 · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Karar:** Burak
**Kapsam (dar):** Yalnız ekonomik uygulanabilirlik. Kod, motor, backtest, yeni veri altyapısı
yok. Sonuç olumlu çıksa bile yalnız araştırmaya devam gerekçesidir; canlı işlem izni değildir.
Bu not getiri tahmini **değildir**; aşağıdaki oranlar ölçeği göstermek için parametredir.

## 1. Mekanizma ve ekonomik kaynak

- Aynı varlıktan **spot alınır** ve buna **§2'deki eşlemeyle** vadeli (vadesi olan, quarterly) satılır.
  Vadede iki fiyat yakınsar; başlangıçtaki prim (vadeli − spot), maliyetlerden arta kalırsa
  hedeflenen kazançtır.
- **Karşı taraf neden prim öder?** Kaldıraçlı long talebi ve teminat/sermaye kısıtları vadeli
  fiyatı spotun üstüne iter; primi kapatmak sermaye bağlamayı gerektirir. Bu farkın varlığı ve
  ekonomik nedenleri akademik olarak incelenmiştir (BIS Working Paper 1087), aynı çalışma
  teminat ihtiyacı ve zorunlu tasfiye risklerini de gösterir.
- **Yön riskine karşı korunmak risksiz olmak değildir** (§4).
- Vadesiz (perpetual) sözleşmede funding toplamak **ayrı bir modeldir**: funding değişken ve
  negatif olabilir, geleceği kilitlemez. Bu not yalnız vadeli (delivery) sözleşmeyi ele alır.
  Depodaki sabit funding modeli bu araştırma için kullanılamaz.

## 2. Pozisyon yapısı (COIN-M, ters sözleşme)

Binance COIN-M quarterly sözleşmeleri **ters (inverse)** sözleşmedir: büyüklük USD olarak
tanımlanır (BTC 100 USD, altcoin ör. ETH 10 USD / kontrat — tarihli kaynak, güncel şartlar
doğrulanmalı), kâr/zarar ve teminat coin cinsindendir. USD nominali D, giriş vadeli fiyatı
F₀ olan short'un coin cinsinden PnL'si (Binance formülü):

  PnL_short(coin) = D × (1/Fₜ − 1/F₀)

**Eşleme (ideal durum, maliyetsiz, uzlaşma fiyatı = spot):** q = D / F₀ coin tutulur ve D USD
nominal short açılır. Vadede uzlaşma fiyatı S_T ise:

- Coin toplamı = q + D × (1/S_T − 1/F₀) = D / S_T → USD değeri = **D**.
- Başlangıç spot maliyeti = q × S₀ = D × S₀ / F₀ (prim pozitifse D'den küçük).
- **Brüt kazanç (USD) = D × (F₀ − S₀) / F₀** — vade süresine yayılmış.

Alınan coin aynı zamanda teminattır; spot ve teminat zorunlu olarak iki ayrı sermaye kalemi
değildir. Ek USD/coin tamponu bırakılıp bırakılmayacağı, bakım teminatı oranı ve pozisyon
değeri **birlikte** hesaplanarak belirlenir (fiyat yükselişinde short'un coin zararı artarken
tutulan coinin USD değeri de artar; tasfiye riski yalnız coin miktarına bakılarak çıkarılamaz).

## 3. Dar kontrol listesi

| # | Soru | Bugünkü durum | Nasıl doğrulanır |
|---|---|---|---|
| 1 | 100 $ ile uygulanabilir sözleşme ve emir büyüklüğü var mı? | **Belirsiz.** BTC'de en küçük pozisyon 1 kontrat = D 100 USD; spot maliyeti ≈ 100 × S₀/F₀ USD, ücretler ve varsa tampon eklenir — 100 $'a sığıp sığmadığı hesap ve hesap koşullarına bağlıdır. ETH'de 10 USD'lik kontratlar daha küçük adımlara izin verir. Spot asgari emir tutarı ve **Burak'ın hesabında (bölge kısıtları dahil) COIN-M vadeli erişimi** bilinmiyor. | Burak'ın hesabında erişim, spot ve vadeli asgari emir koşullarının ekran görüntüsü. |
| 2 | Spot, teminat ve tampon birlikte karşılanabiliyor mu? | **Belirsiz.** §2: coin teminat olarak kullanılır; gerekli ek tampon, bakım teminatı oranı ve fiyat senaryolarıyla hesaplanmalı. | Borsa hesaplayıcısıyla tasfiye fiyatı ve bakım teminatı; ör. +%50 / +%100 fiyat senaryosu. |
| 3 | Bütün maliyetlerden sonra kalan tutar zaman ve riske değiyor mu? | Bkz. §4–§5; karar Burak'ındır. | Elle yapılmış nakit akışı hesabı. |
| 4 | Fiyatlar işlem yapılabilir alış/satış fiyatları mı? | **Hayır — henüz fiyat toplanmadı.** Son fiyat kullanılamaz: girişte spot **ask** ve vadeli **bid**, çıkışta spot **bid** (ve erken çıkışta vadeli **ask**) ile derinlik gerekir. | Aynı anda (± birkaç saniye) iki emir defteri görüntüsü, birkaç farklı günde. |

## 4. Nakit akışları (iki senaryo ayrı)

**A) Vadeye kadar tutma**
1. Spot alış: q coin, **spot ask** ile; spot ücreti.
2. Coin'in spot cüzdandan COIN-M cüzdanına transferi (ücret varsa).
3. Vadeli short açılış: D USD nominal, **vadeli bid** ile; vadeli ücreti.
4. Vade sonu uzlaşma: **uzlaşma (endeks) fiyatıyla**, nakit uzlaşmalı; uzlaşma ücreti (taker
   oranı). Sonuç coin cinsindendir.
5. Coin'in spot cüzdana geri transferi.
6. USD sonucunu gerçekleştirmek için **spot satış: spot bid** ile; spot ücreti.
- **Uzlaşma endeks fiyatı, gerçekleştirilebilir spot satış fiyatıyla aynı değildir.** Aradaki fark
  ve 6. adımın zamanlaması, küçük primli bir pozisyonda sonucu değiştirebilir.

**B) Erken kapanış**
1–3 aynı.
4. Vadeli short kapanış: **vadeli ask** ile; vadeli ücreti. Prim henüz kapanmamışsa (veya
   genişlemişse) bu bacak zarar edebilir.
5. Transfer + **spot satış: spot bid** ile; spot ücreti.

**Net kazanç (USD) = (iki bacağın gerçek giriş/çıkış fiyatlarıyla brüt sonucu) − tüm ücretler −
transferler.** Önce bu USD nakit akışı hesaplanır; **ardından** toplam bağlanan sermayeye
(spot maliyeti + varsa ek tampon) oranlanır. Piyasadaki prim oranı doğrudan "sermaye getirisi"
sayılamaz: boşta duran tampon prim kazanmaz.

## 5. Ölçek (getiri tahmini DEĞİL)

Yalnız büyüklük fikri için, iki varsayımla: pozisyon başına **maliyetler sonrası yıllık net prim
oranı p** (pozisyon nominaline göre) ve sermayenin pozisyona bağlanan payı **u** (geri kalanı
tampon). Toplam sermaye getirisi ≈ p × u. Hiçbiri ölçülmedi.

| Sermaye | p = %10, u = %100 | p = %10, u = %70 | Aylık karşılık (p %10, u %70) |
|---|---:|---:|---:|
| 100 $ | 10 $/yıl | 7 $/yıl | ~0,6 $ |
| 700 $ | 70 $/yıl | 49 $/yıl | ~4,1 $ |
| 1.200 $ | 120 $/yıl | 84 $/yıl | ~7 $ |

**Burak'ın hedefiyle karşılaştırma:** aylık ikiye katlama hedefi bu ölçeğin yüzlerce katıdır;
bu aday o hedefin çözümü **değildir.** Değerlendirme yalnız "küçük, sınırlı ve ölçülebilir bir
gelir yöntemi uygulanabilir mi" sorusunu cevaplar.

## 6. Eleme senaryoları (bunlardan biri doğrulanırsa aday elenir)

1. Burak'ın hesabından vadeli (delivery) sözleşmelere erişim yok veya asgari emir 100–300 $'a
   sığmıyor.
2. İşlem yapılabilir fiyatlarla ölçülen prim, bütün maliyetleri karşılamıyor (ölçülen birkaç
   günde net ≤ 0).
3. Güvenli bir tampon bırakıldığında (fiyatın ör. %50 yükselişine dayanacak teminat) sermayeye
   göre net getiri anlamsız kalıyor.
4. İki bacak farklı zamanlarda dolduğunda veya erken çıkışta oluşabilecek kayıp, beklenen net
   primi aşıyor.
5. Borsa/kurum riski (kesinti, çekim kısıtı) Burak için kabul edilemez.

## 7. Kod yazmaya değmesi için gereken kanıt

Hepsi **kod yazmadan, elle** toplanır ve bu belgeye eklenir:
- Burak'ın hesabında erişim + asgari emir koşulları (ekran görüntüsü).
- En az 5 farklı günde, aynı anda alınmış spot ask / vadeli bid görüntüleri ve vade tarihleri.
- Bunlarla §4'teki her iki senaryonun bütün ücretler dahil elle yapılmış USD nakit akışı ve
  toplam bağlanan sermayeye oranı; tasfiye fiyatı ve bakım teminatı hesabı.
- Sonucun, Burak'ın "zaman ve riske değer" eşiğini önceden yazılmış olarak geçmesi.

Bu kanıtlar olmadan, ya da bunlarla aday elenirse, **sonuç: aday yok** — motor, strateji veya
veri altyapısı yazılmaz ve otomatik olarak başka bir stratejiye geçilmez.

## Kaynaklar
- Binance — ters (COIN-M) sözleşme PnL formülü: https://www.binance.com/en/support/faq/detail/360036498511
- Binance — teslimat/uzlaşma: https://www.binance.com/en/support/faq/detail/a3401595e1734084959c61491bc0dbe3
- Binance — A Quick Guide to Coin-Margined Quarterly Contracts:
  https://www.binance.com/en/support/articles/d33f37e2c7fe4da3b35ffc904e8fbab5
- BIS Working Paper 1087 (kripto vadeli primi, teminat ve tasfiye riskleri):
  https://www.bis.org/publ/work1087.pdf
- Binance funding açıklaması: https://www.binance.com/en/support/faq/detail/360033525031
- Bailey, Borwein, López de Prado, Zhu — The Probability of Backtest Overfitting:
  https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
