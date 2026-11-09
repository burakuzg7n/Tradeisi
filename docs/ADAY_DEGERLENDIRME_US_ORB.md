# Aday değerlendirme — US ORB "Stocks in Play" (V-ORB v1)

**Sürüm:** v0.2 taslak (9 Kasım 2026) · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Karar:** Burak
**Statü:** TASLAK. Kurallar ve kapılar **hiçbir fiyat/getiri verisine bakılmadan** yazıldı.
Yalnız veri erişimi kontrol edildi (SPY 5dk bar SAYISI, 2016–2026; fiyat/getiri hesaplanmadı).
**Kâr garantisi yok.** RED geçerli bir sonuçtur.
**v0.1 → v0.2:** ChatGPT tasarım denetiminin 7 bulgusu ve kapı notlarının tamamı işlendi (§10).

## 1. Ekonomik kaynak ve bağımsız kanıt
- **Mekanizma:** Gece haberi/olayı olan ("in play") hisselerde açılıştaki olağandışı hacim, bilginin
  gün içinde kademeli fiyatlanmasına (underreaction + momentum) işaret eder. İlk 5 dakikanın yönünde
  kırılım bu akışa katılır; pozisyon gün sonunda kapanır.
- **Kanıt:** Zarattini, Barbon, Aziz, *A Profitable Day Trading Strategy for the U.S. Equity Market*,
  Swiss Finance Institute RP 24-98 (SSRN 4729284). Dönem 2016–2023; net komisyon yıllık %41,6,
  Sharpe 2,81 (CXO Advisory özeti). Bağımsız bir endeks tekrarında "brüt tekrarlandı, net sıfır".
- **Yayın tarihi:** SSRN yüklemesi ve yazar duyurusu 15 Mart 2024 (ChatGPT denetimi). Yayın sonrası
  ilk seans **18 Mart 2024** kabul edilir.

## 2. Veri
| # | Tanım |
|---|---|
| D1 | Kaynak: Alpaca Market Data, `feed=sip`, **`adjustment=raw`** (düzeltilmemiş; makaleyle aynı) |
| D2 | Günlük bar (gösterge), 5dk bar (09:30–09:35 seçim barı), 1dk bar (yürütme simülasyonu) |
| D3 | Bölünmeler: Alpaca corporate actions. 14 günlük pencerede, işlem tarihinde ex-date'i gelmiş bölünmeler varsa pencere o tarihin hisse ölçeğine çevrilir; **gelecekteki bölünme geçmişe uygulanmaz**. Temettü düzeltmesi yok. |
| D4 | Takvim: Alpaca `/v2/calendar` (yarım günler dahil) |
| D5 | Evren: Alpaca varlık listesi, `active` + `inactive`, `class=us_equity`. Sonuç **"Alpaca'da erişilebilen evrende araştırma"** diye sunulur; eksiksiz piyasa replikasyonu iddiası yok. |
| D6 | Isınma: Gösterge için 14 tam seans gerekir; bu geçmişi olmayan hisse o gün aday olamaz. |

## 3. Kurallar
| # | Kural | Değer |
|---|---|---|
| K1 | Evren | D5 |
| K2 | Fiyat | O günün 09:30 açılış fiyatı (raw) > 5 $ |
| K3 | Likidite | Önceki 14 seans ortalama günlük hacim ≥ 1.000.000 adet (D3 ölçeğinde) |
| K4 | Oynaklık | ATR(14) > 0,50 $. ATR = önceki 14 seansın True Range'lerinin **basit ortalaması** (D3 ölçeğinde) |
| K5 | RelVol | **Pay:** bugünün tamamlanmış 09:30–09:35 bar hacmi. **Payda:** önceki 14 seansın aynı bar hacimlerinin ortalaması. RelVol ≥ 1,00. 09:30–09:35 barı olmayan hisse aday olamaz. |
| K6 | Seçim | K2–K5'i geçenlerden RelVol'e göre ilk 20 |
| K7 | Yön | İlk 5dk bar kapanış > açılış → long; < → short; eşit → işlem yok |
| K8 | Giriş | Long: ilk 5dk barın tepesine buy-stop; short: dibine sell-stop. **Emirler 09:37'de etkin** (2 dk hesap + gecikme). **Son giriş 15:30**; tetiklenmeyen emirler 15:30'da iptal. Yarım günlerde son giriş 12:30. |
| K9 | Stop | Gerçekleşen giriş fiyatından 0,10 × ATR(14) |
| K10 | Gün sonu | Açık pozisyon **15:55'te piyasa emriyle** kapanır (yarım gün 12:55). Kapanış müzayedesi (`cls`) kullanılmaz. |
| K11 | Risk | Stop'ta kayıp = gün başı equity'nin **%0,5'i** [SAPMA: makale %1; Burak'ın kararı]. Adet aşağı yuvarlanır (tam hisse). |
| K12 | Sermaye | 09:37'de **tüm bekleyen giriş emirleri için** nominal ayrılır: Σ(adet × giriş seviyesi) ≤ 4 × gün başı equity. RelVol sırasıyla eklenir, sığmayan **atlanır ve o gün tekrar değerlendirilmez.** Tetiklenmeyen emrin ayrılan payı başka sinyale verilmez. |
| K13 | Likidite tavanı | Adet ≤ o hissenin 09:30–09:35 hacminin %1'i |
| K14 | Short kısıtı (Rule 201) | 09:37'ye kadar fiyat önceki kapanışın %90'ına inmişse ya da SSR önceki günden devrediyorsa **short sinyali atlanır**. |
| K15 | Ödünç (HTB) | Tarihsel ödünç verisi yok → ETB varsayılır (§8 sınır). Canlıda emir anında Alpaca `easy_to_borrow` bayrağı kontrol edilir. |

## 4. Yürütme ve maliyet modeli (1dk barlarla)
- **Kayma (her yön, her dolum):** k = max(0,01 $; 0,0005 × fiyat). Spread dahil kabul edilir.
  Alış dolumları +k, satış dolumları −k (short çıkışı alıştır → +k).
- **Giriş:** Tetik barında seviye bar açılışında gap ile geçilmişse dolum = bar açılışı ± k; değilse seviye ± k.
- **Giriş barında stop seviyesine de değilmişse:** stop varsayılır.
- **Stop:** Stop seviyesi ∓ k; bar açılışı stop'un ötesindeyse (gap) bar açılışı ∓ k. Long ve short simetrik.
- **Gün sonu:** 15:55 1dk barının açılışı ∓ k.
- **Durma (halt):** Çıkış saatinde bar yoksa ilk sonraki barın açılışında çıkılır; gece taşınan pozisyon raporda ayrı sayılır, PnL'e dahildir.
- **Komisyon:** 0,0035 $/adet **her yönde** (Alpaca sıfır olsa da muhafazakâr).
- **Düzenleyici ücretler (yalnız satış yönü):** SEC Section 31 ücreti işlem tarihindeki resmî oranla; FINRA TAF işlem tarihindeki adet başı oran ve tavanla. Her ücret işlem başına **yukarı** cent'e yuvarlanır.
- **Kısmi dolum:** Yok varsayılır; K13 tavanı bu varsayımı sınırlar.
- **Stres (G5/H4):** Kayma, komisyon ve düzenleyici ücretlerin **üçü birden ×2**; tüm simülasyon (boyutlama ve equity yolu dahil) baştan koşulur.
- **İşletme gideri (ayrı raporlanır):** Canlıda SIP gerçek zamanlı veri Alpaca Algo Trader Plus **99 $/ay** (ücretsiz plan canlıda yalnız IEX). Sonuçlar (a) işlem maliyetleri sonrası ve (b) 1.188 $/yıl veri gideri sonrası (2.000 $ ve 25.000 $ sermaye için) ayrı gösterilir.

## 5. Ölçüm tanımları
- **Başlangıç sermayesi:** 25.000 $ (makaleyle aynı; tam hisse yuvarlamasının etkisi küçük). 2.000 $ ile aynı koşu yalnız **betimleyici** raporlanır, kapı değildir.
- **PF:** İşlem bazında, tüm değişken maliyetler sonrası brüt kâr / brüt zarar.
- **DD:** Açık pozisyonlar 1dk kapanışlarla piyasa değerine getirilen equity'nin en yüksekten en büyük düşüşü (**1dk örneklemeli MTM DD**).
- **Günlük getiri:** Gün PnL'i / gün başı equity; işlemsiz günler 0 olarak dahil.
- **HAC t:** Günlük getiri ortalaması, Newey-West; gecikme = ⌊4·(T/100)^(2/9)⌋.

## 6. Kapılar (veriye bakmadan sabit)
**V0 — Veri ve yürütme geçerliliği (getiriye bakmadan, önce):** yıllara göre evren kapsamı (aktif/inaktif sembol sayısı), eksik bar oranı, 14 gün ısınma, takvim/yarım gün kontrolü, bölünme ölçeği testleri, birim testleri yeşil. **V0 geçmeden üretilen sonuç ne GEÇTİ ne RED sayılır.**

**In-sample (replikasyon) 2016-01-01 → 2023-12-31, tek atış:**
| Kapı | Eşik |
|---|---|
| G1 PF | > 1,30 |
| G2 1dk MTM DD | < %25 |
| G3 Net (değişken maliyetler sonrası) | > 0 |
| G4 Günlük getiri HAC t | > 2,0 |
| G5 Maliyetler ×2 iken net | > 0 |
| G6 Örneklem | ≥ 1.000 kapanmış işlem **ve** ≥ 500 işlemli gün |

**Hold-out (yayın sonrası) 2024-03-18 → 2026-10-30 — yalnız V0 ve G1–G6 geçerse açılır:**
H1 PF > 1,15 · H2 DD < %25 · H3 net > 0 · H4 maliyetler ×2 iken net > 0 · H5 ≥ 200 işlemli gün.
Günlük getiri ortalamasının %95 güven aralığı raporlanır (kapı değil).
2024-01-01 → 2024-03-15 arası **kullanılmaz** (ne in-sample ne yayın sonrası).

## 7. Uygulanabilirlik (Burak'ın sermayesi)
- **Komisyon:** Alpaca perakende hisse işlemleri komisyonsuz; Midas (1,5 $/işlem) bu stratejiyi imkânsız kılar.
- **PDT:** Alpaca dokümanına göre FINRA'nın yeni gün içi marjin kuralıyla 25.000 $ şartı ve işlem sayma kalktı; standart **2.000 $** asgari equity geçerli. Short ve kaldıraç için margin hesabı + ≥ 2.000 $ şart.
- **Canlı veri gideri:** 99 $/ay. Canlıya geçiş kuralı (önceden sabit): yıllık veri gideri sermayenin **%5'ini aşamaz → ≥ 23.760 $**, ya da ücretsiz IEX verisiyle çalışan **ayrı bir sürüm** kendi tek atış testini ve paper aşamasını geçer. SIP'te test edip canlıda IEX kullanmak aynı strateji sayılmaz.
- **Para transferi:** Türkiye'den SWIFT havale ücreti → seyrek ve toplu yatırım.
- **Emir:** 20 hisseye eşzamanlı emir elle girilemez → Alpaca API ile otomatik; Burak günlük "başlat/durdur" kararını verir.

## 8. Bilinen sınırlar
- Evren Alpaca'da erişilebilen sembollerle sınırlı; sembol yeniden kullanımı ve eski adlar eksik eşlenebilir.
- Tarihsel barlar sonradan raporlanan işlemlerle güncellenmiş olabilir; 09:35'te görülen değer bilinemez (2 dk gecikme ve %1 likidite tavanı kısmen hafifletir).
- Tarihsel ödünç (HTB) ve locate verisi yok; short sonuçları iyimser olabilir. Long ve short bacakları raporda **ayrı** gösterilir (betimleyici).
- 1dk bar içi sıra bilinmez (§4 muhafazakâr kural).

## 9. Eleme senaryoları ve tekrar kuralı
1. V0 geçmezse: sonuç yok; veri/kod düzeltilir, strateji kuralı değişmez.
2. G1–G6'dan biri tutmazsa RED; parametre ayarlanmaz, hold-out açılmaz.
3. Hold-out RED → bu uygulama belirlenen doğrulamayı geçemedi demektir (etkinin "yok olduğu" iddia edilmez).
4. Paper'da DD ≥ %25 → dur.
5. **Tekrar kuralı:** Kural değişirse yeni sürüm olur; ancak sonucu görülmüş dönemler (in-sample ve açılmışsa hold-out) yeni sürüm için **kullanılmış veridir**. Yeni sürüm yalnız ileriye dönük (paper) veriyle bağımsız doğrulanabilir.
6. Proje genelinde 6. strateji ailesi (V1, V2, Plan B, V3, Sepet momentum, V-ORB). ABD hisse verisi bu projede hiç kullanılmadı.

## 10. ChatGPT denetimi (9 Kasım 2026) — işleme tablosu
| # | Bulgu | Karşılık |
|---|---|---|
| 1 | Düzeltilmiş veri geçmiş seçimi değiştirir | D1 raw + D3 yalnız o tarihte bilinen bölünmeler |
| 2 | `inactive` survivorship'i çözmez | D5 adlandırması + V0 kapsam tablosu + §8 |
| 3 | 09:35 sınırı, emir/portföy sırası | K5 metni düzeltildi; K8 09:37 etkinleşme; K12 rezervasyon ve atlama kuralı; §8 bar revizyonu |
| 4 | Maliyet modeli eksik | §4 tümüyle yeniden; G5 tanımı; işletme gideri ayrı |
| 5 | Short uygulanabilirliği | K14 Rule 201, K15 HTB, §8 ve ayrı bacak raporu |
| 6 | Gün sonu emir akışı | K8 son giriş 15:30, K10 15:55 piyasa emri, yarım gün ve halt kuralları |
| 7 | Hold-out etiketi, tekrar kuralı | Hold-out 2024-03-18'den; ara dönem dışarıda; §9.3 ve §9.5 |
| Kapılar | Ölçüm tanımları | §5 ve §6 (V0, G6 gün sayısı, H5) |
| PDT | Güncelliğini yitirdi | §7 güncellendi (Alpaca dokümanı) |
