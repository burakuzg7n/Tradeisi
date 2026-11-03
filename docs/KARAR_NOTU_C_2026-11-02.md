# Karar notu — Yön C (2 Kasım 2026)

**Statü:** TASLAK — Burak'ın açık onayı ve bağımsız denetimle (ChatGPT) yürürlüğe girer.
**Hazırlayan:** Claude · **Kaynak tartışma:** ChatGPT'nin `main @ 3295611` incelemesi ve
Burak ile 2 Kasım 2026 yazışması.

## 1. Karar

- **Birikim:** Burak ayda yaklaşık 100 $ kenara ayırmaya devam eder. Bu para bir bot
  stratejisine bağlanmaz.
- **Araştırma:** Bot araştırması **gerçek para bağlamadan** sürer. Hedef "gerçek parayla
  kullanılabilir sistem" olarak kalır; ancak **henüz bulunmamış kâr hiçbir kişisel bütçe veya
  gelir planına yazılmaz.**
- **Aylık ikiye katlama** (100 → 200 → 600 → 1.400 …) bir kabul kriteri, tasarım hedefi veya
  strateji seçme ölçütü **değildir.** Gelir hedefine göre strateji seçmek sonuçları zorlamaya
  yöneltir.
- İşlem yapmamak botun zarar riskini kaldırır; paranın tutulduğu yere bağlı enflasyon, kur ve
  kurum riskleri ayrı konulardır ve bu notun kapsamı dışındadır.

## 2. Değişmeyenler

- V1, V2, Plan B v1 ve V3 **reddedildi**; kararlar, kilitler, mühürlü raporlar ve hold-out
  yasakları korunur. Hiçbir eski stratejinin hold-out'u açılmaz, parametresi değiştirilmez.
- `reports/` arşivdir; silinmez, değiştirilmez.

## 3. Yeni aday nasıl ele alınır

1. Her aday önce `docs/` altında bir **aday değerlendirme notu** ile, **kod yazmadan** ele alınır
   (ilk örnek: `ADAY_DEGERLENDIRME_CASH_AND_CARRY.md`). Not şu soruları cevaplar:
   - Kazancın **ekonomik kaynağı** nedir — işlemin karşı tarafı neden sistematik olarak para
     bırakır? Bunu destekleyen **bağımsız** kanıt nedir?
   - Burak'ın sermayesiyle (100 $ başlangıç, aylık +100 $), asgari emirler ve **bütün**
     maliyetlerden sonra uygulanabilir mi?
   - Hangi zarar/bozulma senaryosunda fikir elenir?
   - Hangi veriler daha önce görüldü; toplam kaç fikir/varyant denendi (§5)?
   - Kod yazmaya değmesi için hangi kanıt gerekir?
2. Not adayı elerse kod, motor, veri altyapısı **yazılmaz.** Olumlu sonuç yalnız araştırmaya
   devam gerekçesidir; canlıya geçiş izni değildir.
3. Değerlendirmede güçlü aday çıkmazsa sonuç **"aday yok"** olarak yazılır. Bir aday
   elendiğinde **otomatik olarak başka strateji denemesine geçilmez**; her yeni aday ayrı bir
   karar gerektirir. Projeyi sürdürmek için V4 üretilmez.
4. Tek atış protokolü gerekli ama yeterli değildir: aynı tarihsel dönemden etkilenerek ardışık
   aday seçmek, sürüm numarası değişse de seçim yanlılığı yaratır. Toplam deneme sayısı her
   yeni değerlendirmede hesaba katılır (bkz. Bailey ve diğ., "The Probability of Backtest
   Overfitting").

## 4. Eski canlı yürütme katmanı — kayıt

ChatGPT'nin `3295611` incelemesinde sentetik testlerle bildirdiği bulgular (Claude tarafından
**ayrıca yeniden üretilmedi**; kayıt amaçlıdır):

| Ciddiyet · yer | Bulgu |
|---|---|
| Yüksek · `tradebot/execution.py:92` | Borsa emri kabul edip yanıt kaybolursa emir yeniden gönderilir; istemci emir kimliği ve önceki emri sorgulama yok → çift emir. |
| Yüksek · `tradebot/live.py:208` | Kısmen dolmuş emrin kalanı iptal edilince kayıt takipten çıkar; dolmuş pozisyon takipsiz kalır. |
| Yüksek · `tradebot/live.py:98` | Yeniden başlatmada açık emir/pozisyon ve önceki zarar sınırları borsayla uzlaştırılmaz. |
| Yüksek · `tradebot/live.py:241` | Kapanış kaydı işlem kimliğiyle eşleşmez; sorgu başarısızsa sonuç fiyat yakınlığından +2R/−1R tahmin edilip risk hesabına yazılır. |

**Karar:** bu katman (`live.py`, `execution.py`, `server.py` ve demo çalıştırıcı) **gerçek para
için kullanılmaz.** Şimdi düzeltilmez; düzeltmeler, kullanılacak mimari bir aday doğrulandıktan
sonra belirlenir.

## 5. Deneme geçmişi (kayıtlardan)

**Dört ana strateji; toplam varyant/deneme sayısı kesin olarak doğrulanmadı.** Aşağıdaki
tablo kayıtlarda **görülen** değerlendirme ve varyantları listeler. Satır sayısı ayrı koşu
sayısının alt sınırı **değildir**: bazı satırlar aynı koşunun farklı görünümleri olabilir; kayıtta
izi kalmamış ek koşular da olabilir.

| # | Ne | Veri | Kayıt | Not |
|---|---|---|---|---|
| 1 | V1, seans filtresi AÇIK | Bitstamp BTC/USD, 18 ay | `reports/BACKTEST_RAPORU.md` | |
| 2 | V1, seans filtresi KAPALI | aynı | aynı | 1 ile karşılaştırmalı |
| 3 | V1, 70/30 walk-forward | aynı | aynı | 1'in dönem bölümlemesi; ayrı koşu olup olmadığı belirsiz |
| 4 | V1 + hacim filtresi (seans açık) | aynı | `BACKTEST_RAPORU.md`, `ANALIZ.md` | |
| 5 | V1, seans açık, hacim filtresiz — BTC ve ETH, yıl yıl | Binance BTCUSDT/ETHUSDT 2020–2026 | `reports/YILLIK_ANALIZ.md` | Kaynaktaki "394 + 423 işlem" toplam örneklem açıklaması bu satıra ait olabilir; ayrı bir koşu olduğu doğrulanmadı |
| 6 | V1, seans açık + hacim filtresi — BTC ve ETH, yıl yıl | aynı | aynı | |
| 7 | V2 in-sample tek atış | Binance BTCUSDT/ETHUSDT 2020–2024 (spot API) | `reports/V2_INSAMPLE.md` | |
| 8 | Plan B v1 in-sample tek atış | Binance perp günlük BTC/ETH/SOL/BNB 2020–2024 | `reports/PLANB_INSAMPLE.md` | |
| 9 | V3 in-sample tek atış | Binance perp 15m XRP/DOGE/ADA/AVAX/LINK 2021–2024 | `reports/V3_INSAMPLE.md` | |

Ayrıca: V1 dönemindeki maliyet modeli değişiklikleri (maker/taker ayrımı, %0,2 asgari stop)
ve V2/Plan B/V3'ün **V1 sonuçları görüldükten sonra** seçilmiş olması seçim etkisi taşır.
BTC/ETH 2020–2026 ve BTC/ETH/SOL/BNB günlük verisi **görülmüş** veridir.
