# Aday değerlendirme — Cash-and-carry (spot–vadeli fark)

**Tarih:** 2 Kasım 2026 · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Karar:** Burak
**Kapsam (dar):** Yalnız ekonomik uygulanabilirlik. Kod, motor, backtest, yeni veri altyapısı
yok. Sonuç olumlu çıksa bile yalnız araştırmaya devam gerekçesidir; canlı işlem izni değildir.
Bu not getiri tahmini **değildir**; aşağıdaki oranlar ölçeği göstermek için parametredir.

## 1. Mekanizma ve ekonomik kaynak

- Aynı varlıktan **spot alınır** ve **eşit büyüklükte vadeli (vadesi olan, quarterly) satılır.**
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

## 2. Dar kontrol listesi

| # | Soru | Bugünkü durum | Nasıl doğrulanır |
|---|---|---|---|
| 1 | 100 $ ile uygulanabilir sözleşme ve emir büyüklüğü var mı? | **Belirsiz, kısmen olası.** Binance COIN-M quarterly kontratlarında sözleşme birimi BTC için 100 USD, altcoinlerde (ör. ETH) 10 USD (kaynak tarihli; güncel şartlar doğrulanmalı). BTC'de tek kontrat 100 $ eder; spot + teminatla 100 $'a sığmaz. ETH'de 10 $'lık kontratlarla teknik olarak mümkün görünüyor. **Burak'ın hesabında (bölge kısıtları dahil) vadeli işlemlere erişim olup olmadığı bilinmiyor.** | Burak, kendi hesabında COIN-M quarterly erişimini, asgari emir/spot asgari tutarı ekran görüntüsüyle gösterir. |
| 2 | Spot alımı, teminat ve nakit tamponu birlikte karşılanabiliyor mu? | **Belirsiz.** COIN-M'de spot alınan coin teminat olarak kullanılabildiği için ayrı USD teminatı gerekmeyebilir; ancak fiyat sert yükselirse short bacağın zararı coin teminatını eritir ve tasfiye riski doğar. Güvenli kaldıraç düşük tutulursa sermayenin bir kısmı tampon olarak boşta kalmalıdır. | Hesap: spot miktarı, kontrat sayısı, bakım teminatı oranı ve tasfiye fiyatı borsa hesaplayıcısıyla çıkarılır. |
| 3 | Bütün maliyetlerden sonra kalan tutar zaman ve riske değiyor mu? | **Ölçek olarak çok küçük.** Bkz. §3. | Kullanıcı kararı (Burak). |
| 4 | Fiyatlar işlem yapılabilir alış/satış fiyatları mı? | **Hayır — henüz hiç fiyat toplanmadı.** Ekrandaki son fiyat kullanılamaz; spot için **satış (ask)**, vadeli için **alış (bid)** fiyatı ve emir defteri derinliği gerekir. | Aynı anda (± birkaç saniye) iki ekranın emir defteri görüntüsü; birkaç farklı günde. |

## 3. Ölçek hesabı (getiri tahmini DEĞİL)

Net kazanç ≈ sermaye × (yıllıklandırılmış prim − yıllıklandırılmış toplam maliyet) × süre.
Toplam maliyet en az dört bacaklı komisyondan (spot alış, vadeli satış, vade sonu uzlaşma
ücreti veya erken kapanışta iki bacak daha) ve alış/satış farkından oluşur; transfer ücretleri
ayrıca eklenir. Prim piyasaya göre değişir; düşük, sıfır veya negatif olabilir.

Yalnız ölçek için, maliyetler düşüldükten sonra **yıllık net %5 / %10 / %15** varsayımlarıyla
(hiçbiri ölçülmedi):

| Sermaye | Yıllık net %5 | %10 | %15 | Aylık karşılık (%10 ile) |
|---|---:|---:|---:|---:|
| 100 $ | 5 $ | 10 $ | 15 $ | ~0,8 $ |
| 700 $ | 35 $ | 70 $ | 105 $ | ~5,8 $ |
| 1.200 $ | 60 $ | 120 $ | 180 $ | ~10 $ |

**Burak'ın hedefiyle karşılaştırma:** aylık ikiye katlama hedefi bu ölçeğin yüzlerce katıdır;
bu aday o hedefin çözümü **değildir.** Değerlendirme yalnız "küçük, sınırlı ve ölçülebilir bir
gelir yöntemi uygulanabilir mi" sorusunu cevaplar.

## 4. Eleme senaryoları (bunlardan biri doğrulanırsa aday elenir)

1. Burak'ın hesabından vadeli (delivery) sözleşmelere erişim yok veya asgari emir 100–300 $'a
   sığmıyor.
2. İşlem yapılabilir fiyatlarla ölçülen prim, bütün maliyetleri karşılamıyor (ölçülen birkaç
   günde net ≤ 0).
3. Güvenli bir tampon bırakıldığında (fiyatın ör. %50 yükselişine dayanacak teminat) sermayeye
   göre net getiri anlamsız kalıyor.
4. İki bacak farklı zamanlarda dolduğunda veya erken çıkışta oluşabilecek kayıp, beklenen net
   primi aşıyor.
5. Borsa/kurum riski (kesinti, çekim kısıtı) Burak için kabul edilemez.

## 5. Kod yazmaya değmesi için gereken kanıt

Hepsi **kod yazmadan, elle** toplanır ve bu belgeye eklenir:
- Burak'ın hesabında erişim + asgari emir koşulları (ekran görüntüsü).
- En az 5 farklı günde, aynı anda alınmış spot ask / vadeli bid görüntüleri ve vade tarihleri.
- Bunlarla bütün ücretler dahil elle yapılmış net hesap; tasfiye fiyatı hesabı.
- Sonucun, Burak'ın "zaman ve riske değer" eşiğini önceden yazılmış olarak geçmesi.

Bu kanıtlar olmadan, ya da bunlarla aday elenirse, **sonuç: aday yok** — motor, strateji veya
veri altyapısı yazılmaz ve otomatik olarak başka bir stratejiye geçilmez.

## Kaynaklar
- Binance — A Quick Guide to Coin-Margined Quarterly Contracts:
  https://www.binance.com/en/support/articles/d33f37e2c7fe4da3b35ffc904e8fbab5
- BIS Working Paper 1087 (kripto vadeli primi, teminat ve tasfiye riskleri):
  https://www.bis.org/publ/work1087.pdf
- Binance funding açıklaması: https://www.binance.com/en/support/faq/detail/360033525031
- Bailey, Borwein, López de Prado, Zhu — The Probability of Backtest Overfitting:
  https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
