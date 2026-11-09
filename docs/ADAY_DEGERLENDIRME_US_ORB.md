# Aday değerlendirme — US ORB "Stocks in Play" (V-ORB v1)

**Sürüm:** v0.3 taslak (9 Kasım 2026) · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Karar:** Burak
**Statü:** TASLAK. Kurallar ve kapılar **hiçbir fiyat/getiri verisine bakılmadan** yazıldı.
Yalnız veri erişimi kontrol edildi (SPY 5dk bar SAYISI, 2016–2026; fiyat/getiri hesaplanmadı).
**Kâr garantisi yok.** RED geçerli bir sonuçtur.
**Değişiklik geçmişi:** v0.2 = ChatGPT 1. denetimi (§12.1) · v0.3 = ChatGPT 2. denetimi (§12.2).
`[TK]` = makalede olmayan, bu notta verilmiş **yeni tasarım kararı**.

## 1. Ekonomik kaynak ve bağımsız kanıt
- **Mekanizma:** Gece haberi/olayı olan ("in play") hisselerde açılıştaki olağandışı hacim, bilginin
  gün içinde kademeli fiyatlanmasına (underreaction + momentum) işaret eder. İlk 5 dakikanın yönünde
  kırılım bu akışa katılır; pozisyon gün sonunda kapanır.
- **Kanıt:** Zarattini, Barbon, Aziz, *A Profitable Day Trading Strategy for the U.S. Equity Market*,
  Swiss Finance Institute RP 24-98 (SSRN 4729284). Dönem 2016–2023; net komisyon yıllık %41,6,
  Sharpe 2,81 (CXO Advisory özeti). Bağımsız bir endeks tekrarında "brüt tekrarlandı, net sıfır".
- **Yayın tarihi:** SSRN yüklemesi ve yazar duyurusu 15 Mart 2024. Yayın sonrası ilk seans **18 Mart 2024**.

## 2. Veri
| # | Tanım |
|---|---|
| D1 | Kaynak: Alpaca Market Data, `feed=sip`, `adjustment=raw` (makaleyle aynı, düzeltilmemiş) |
| D2 | Günlük bar (gösterge), 5dk bar (09:30–09:35 seçim barı + tutarlılık kontrolü), 1dk bar (yürütme) |
| D3 | Bölünmeler: Alpaca corporate actions. Gösterge penceresinde, işlem tarihine kadar ex-date'i gelmiş bölünme varsa pencere o tarihin hisse ölçeğine çevrilir (fiyat ÷ oran, hacim × oran). Gelecekteki bölünme geçmişe uygulanmaz. Temettü düzeltmesi yok. |
| D4 | Zaman: tüm zamanlar `America/New_York`, yaz saati dahil. Alpaca bar zaman damgası **bar başlangıcıdır**; 1dk bar t = [t, t+1dk). Takvim ve yarım günler Alpaca `/v2/calendar`. |
| D5 | Evren: Alpaca varlıkları, `active` + `inactive`, `class=us_equity`. Kimlik = Alpaca **asset id**. Adında ETF/ETN/Fund/Trust/Warrant/Unit/Right/Preferred geçenler dışlanır ve dışlama nedeni kaydedilir `[TK]`. Sonuç **"Alpaca'da erişilebilen evrende araştırma"** diye sunulur. |
| D6 | Sembol yeniden kullanımı: aynı sembolün günlük verisinde ≥ 30 takvim günü boşluk varsa boşluktan sonrası **yeni seri** sayılır, ısınma baştan başlar `[TK]`. |
| D7 | Isınma: ATR(14) için 15 seans (14 True Range + ilk TR'nin önceki kapanışı); K3 ve K5 için önceki 14 seans. Yetersiz geçmiş → o gün aday değil. |

## 3. Kurallar
| # | Kural | Değer |
|---|---|---|
| K1 | Evren | D5–D6 |
| K2 | Fiyat | O günün 09:30 açılış fiyatı (raw) > 5 $ |
| K3 | Likidite | Önceki 14 seans ortalama günlük hacim ≥ 1.000.000 adet (D3 ölçeğinde) |
| K4 | Oynaklık | ATR(14) > 0,50 $; ATR = önceki 14 True Range'in basit ortalaması (D3 ölçeğinde) |
| K5 | RelVol | Pay: bugünün tamamlanmış 09:30–09:35 bar hacmi. Payda: önceki 14 seansın aynı bar hacimlerinin ortalaması. RelVol ≥ 1,00. Bu barı olmayan hisse aday değil. |
| K6 | Seçim | K2–K5'i geçenlerden RelVol'e göre ilk 20 |
| K7 | Yön | İlk 5dk bar kapanış > açılış → long; < → short; eşit → işlem yok |
| K8 | Giriş | Long: ilk barın tepesine buy-stop; short: dibine sell-stop. Emirler **09:37'de** etkin `[TK]`; son giriş **15:30**, tetiklenmeyenler 15:30'da iptal `[TK]`. Yarım gün: son giriş 12:30. |
| K9 | Stop | Gerçekleşen giriş fiyatından 0,10 × ATR(14). Stop yalnız seans içinde geçerli. |
| K10 | Gün sonu | Açık pozisyon **15:55'te piyasa emriyle** kapanır `[TK]` (yarım gün 12:55). `cls` kullanılmaz. Taşıma: §4.3. |
| K11 | Adet | adet = ⌊min(A, B, C)⌋: **A** = 0,005 × E / (0,10 × ATR) (hedef risk; maliyet ve stop kayması hariç), **B** = 0,01 × 09:30–09:35 hacmi `[TK]`, **C** = kalan kapasite / rezervasyon fiyatı (K12). E = gün başı equity. %0,5 **hedef** risktir; gerçekleşen kayıp daha büyük olabilir ve dağılımı raporlanır. [SAPMA: makale %1] |
| K12 | Kapasite | Kapasite = 4 × E − (önceki günden taşınan pozisyonların brüt piyasa değeri). 09:37'de bekleyen her emir için nominal ayrılır; rezervasyon fiyatı long'da seviye × 1,10, short'ta seviye `[TK]`. RelVol sırasıyla eklenir; sığmayan atlanır, gün içinde tekrar değerlendirilmez. Dolumda brüt pozisyon yine de 4 × E'yi aşacaksa adet sığacak kadar azaltılır ve olay kaydedilir. |
| K13 | Short kısıtı (Rule 201) | SSR o gün devraldıysa (önceki gün tetiklenmiş) veya gün içinde herhangi bir 1dk barın düşüğü ≤ 0,90 × önceki kapanış olduğunda **o dakikadan itibaren** bekleyen short emri iptal edilir; aynı dakikada hem SSR hem sell-stop tetiği varsa short **dolmamış** sayılır. SSR ertesi güne taşınır. |
| K14 | Ödünç | Tarihsel ödünç (ETB/HTB, locate) verisi yok → tarihsel sonuçlar **"ödünç erişimi varsayımı altında araştırma"**dır. Short uygulanabilirliği geçmiş testle doğrulanmış sayılmaz (§9). |

## 4. Yürütme ve maliyet modeli (1dk barlarla)
### 4.1 Dolum ve maliyet
- **Kayma (her dolumda, aleyhe):** k = max(0,01 $; 0,0005 × fiyat) `[TK]`; spread dahil kabul edilir. Alışlar +k, satışlar −k.
- **Giriş:** Tetik barının açılışı seviyeyi gap ile geçmişse dolum = açılış ± k; değilse seviye ± k.
- **Giriş barında stop seviyesine de değilmişse** stop varsayılır.
- **Stop:** seviye ∓ k; bar açılışı stop'un ötesindeyse açılış ∓ k. Long/short simetrik.
- **Gün sonu:** 15:55 1dk barının açılışı ∓ k.
- **Komisyon:** 0,0035 $/adet her yönde. **SEC Section 31** ve **FINRA TAF**: yalnız satış yönü, işlem tarihindeki resmî tarifeyle, işlem başına yukarı cent'e yuvarlanır.
- **Kısmi dolum yok** varsayılır; K11-B tavanı bu varsayımı sınırlar.
- **Stres (G5/H4):** kayma, komisyon, düzenleyici ücretler ve §4.3 finansman giderlerinin **hepsi ×2**; tüm simülasyon (boyutlama ve equity yolu dahil) baştan koşulur.

### 4.2 Eksik bar
Bar verisi tek başına "işlem yok", "durma (halt)" ve "veri kaybı"nı ayırt edemez. Bu yüzden:
- **Yürütme kuralı:** Bar olmayan dakikada hiçbir emir dolmaz (üç durum için de doğru davranış).
- **Veri kaybı testi:** Pozisyon açıkken her 5dk pencerede Σ(1dk hacim) ile Alpaca 5dk bar hacmi karşılaştırılır. Fark > %2 → o hisse-günü **"belirsiz yürütme"** işaretlenir. İşaretli işlem atlanmaz, kurallara göre yürütülür ve V0'da sayılır (§6).

### 4.3 Taşınan pozisyon (halt / bar yok)
1. 15:55'te bar yoksa piyasa emri 15:59'a kadar her dakika yeniden denenir (ilk bar = dolum).
2. 15:55–15:59 arası hiç bar yoksa pozisyon **taşınır**. Gece stop yoktur.
3. Ertesi seans pozisyon **açılış emriyle (`opg`)** kapanır: dolum = günün ilk RTH bar açılışı ∓ k. Açılışta da bar yoksa 2. adımdaki gibi dakika dakika denenir; seans sonuna kadar dolmazsa yine taşınır.
4. Taşınan pozisyon K12'de kapasiteden düşülür.
5. **Finansman `[TK]`:** taşınan her gece için long'da equity'yi aşan borç kısmına yıllık %10, short'ta pozisyon değerine yıllık %10 ödünç gideri (365 güne bölünerek).
6. **Dönem sonu:** dönemin son seansında hâlâ açıksa son mevcut barın kapanışı ∓ k ile kapatılır ve işaretlenir.
7. Taşıma olayları sayı, süre ve PnL olarak ayrı raporlanır; PnL'e dahildir.

## 5. Ölçüm tanımları
- **Başlangıç sermayesi:** 25.000 $ (makaleyle aynı). 2.000 $ ile aynı koşu yalnız betimleyicidir, kapı değildir.
- **PF:** işlem bazında, §4'teki tüm değişken maliyetler sonrası brüt kâr / brüt zarar.
- **DD:** açık pozisyonlar 1dk kapanışlarla piyasa değerine getirilen equity'nin en yüksekten en büyük düşüşü (**1dk örneklemeli MTM DD**).
- **Günlük getiri:** (gün sonu MTM equity − önceki gün sonu MTM equity) / önceki gün sonu MTM equity. Taşınan pozisyon veya gider varsa işlemsiz gün de sıfır değildir; ikisi de yoksa sıfırdır.
- **HAC t:** günlük getiri ortalaması, Newey-West, gecikme = ⌊4·(T/100)^(2/9)⌋.

## 6. V0 — veri ve yürütme geçerliliği kapısı
**Sıra:** V0_IS → (geçerse) G kapıları → (geçerse) V0_HO → (geçerse) H kapıları. V0 hiçbir PnL, getiri veya fiyat istatistiği üretmez; seçim ve emir zamanlaması çalıştırılabilir ama sonuç değerleri raporlanmaz. **Hold-out verisi V0_IS ve G kararından önce indirilmez.**

V0'ın her maddesi GEÇTİ/KALDI üretir; **tek bir KALDI = V0 KALDI.** V0 KALDI'da strateji için sonuç yoktur (ne GEÇTİ ne RED); veri/kod düzeltilir, strateji kuralı değişmez, başarısız V0 raporu arşivlenir.

| # | Alan | Kontrol | KALDI koşulu |
|---|---|---|---|
| V1 | Bütünlük | Kullanılan tüm barlarda NaN/∞, high < max(open, close), low > min(open, close), negatif hacim, aynı zaman damgasında çelişkili mükerrer kayıt | **≥ 1 kayıt** |
| V2 | Takvim | Her seansın tarihi, açılış/kapanış saati Alpaca takvimiyle eşleşir; seans dışı zaman damgalı bar kullanılmaz | ≥ 1 uyumsuz seans |
| V3 | Evren kapsamı | Her seansta K2–K4'ü geçen hisse sayısı | Herhangi bir seansta < 20, ya da bir seansta önceki seansa göre **> %50 düşüş** |
| V4 | Seçim barı | K6'ya giren hisselerin 09:30–09:35 5dk barı ile 1dk barlarının hacim toplamı | Fark > %2 olan seçim oranı > %1 |
| V5 | Belirsiz yürütme | §4.2 işaretli hisse-günü / tüm işlemli hisse-günleri | Dönem genelinde > %0,5 **veya** herhangi bir yılda > %2 |
| V6 | Ölçek | D3 dönüşümü: bölünme olan her hisse-günü için ex-date öncesi/sonrası fiyat ve hacim oranı bölünme oranının ±%25'i içinde | Uyumsuz oran > %5 |
| V7 | Isınma | D7'ye uymayan aday sayısı | ≥ 1 |
| V8 | Yürütme testleri | §7'deki sentetik testlerin tamamı beklenen sonucu verir | ≥ 1 başarısız test |
| V9 | Tekrarlanabilirlik | İndirme parametreleri, Alpaca API sürümü, takvim ve corporate actions dosyalarının sha256'sı, kod commit'i kaydedilir; aynı girdilerle ikinci koşu bit düzeyinde aynı çıktıyı verir | Eksik kayıt veya fark |

## 7. Zorunlu sentetik yürütme testleri (V8)
Her biri sabit girdi ve beklenen sonuçla birim testi olarak yazılır:
gap ile giriş dolumu (long ve short) · giriş barında stop · K12 rezervasyon sırası ve atlama · dolumda 4× aşımında adet azaltma (örn. 25.000 $, ATR 1,25, seviye 100, açılış 105) · K11 A/B/C'den hangisinin bağladığı · 09:37 öncesi dolum olmaması · 15:30 iptal · yarım gün saatleri · K13 SSR'nin gün içinde tetiklenmesi, aynı dakika çakışması ve ertesi güne taşınması · 15:55'te bar yokken yeniden deneme · taşınan pozisyonun `opg` kapanışı, kapasiteden düşülmesi ve finansmanı · dönem sonunda açık pozisyon · D3 bölünme ölçeği · D6 sembol yeniden kullanımı · D7 ısınma sınırı (14 TR + önceki kapanış) · işlemsiz ama taşınan pozisyonlu gün getirisi · maliyet ×2 stresinin yeniden simülasyonu.

## 8. Örneklem ve güç planı (SONRAKI_YON_KARAR_NOTU §3)
Gerçek getiri dağılımı bilinmiyor; varsayımlar açıktır.
- **Gözlem birimi:** aynı günün işlemleri ilişkili olduğundan **işlemli gün** (portföy günlük getirisi), işlem değil.
- **Asgari anlamlı etki:** yıllık Sharpe 1,0 (günlük ortalama/std = 1/√252).
- **Test:** iki yönlü α = 0,05, güç 0,80; otokorelasyon ve kalın kuyruk için varyans şişirme 1,3 varsayımı.
- **Gereken gün:** Sharpe 1,0 → ≈ 2.572 · Sharpe 1,5 → ≈ 1.143 · Sharpe 2,0 → ≈ 643.
- **Mevcut veri:** in-sample ≈ 1.990 işlem günü → güç ≈ %69 (Sharpe 1,0), %96 (1,5), ≈ %100 (≥ 2,0). Hold-out ≈ 655 gün → güç ≈ %29 (1,0), %56 (1,5), %81 (2,0), %98 (2,8).
- **Sonuç:** in-sample, makalenin iddia ettiği büyüklükteki (Sharpe ≈ 2,8) bir etkiyi ayırt etmeye yeter; Sharpe 1,0 civarındaki küçük bir etkiyi kaçırma olasılığı ≈ %31'dir. Hold-out yalnız büyük etkileri doğrulayabilir; H kapıları HAC t istemez, kesin kanıt sayılmaz. Asıl ileriye dönük doğrulama paper aşamasıdır.
- **İşlem sayısı tahmini:** günde ≤ 20 sinyal; tetiklenme oranı varsayımı %30–%70 → in-sample ≈ 12.000–28.000 işlem; G6 alt sınırı (1.000 işlem / 500 gün) bunun çok altında, veri sorunu olmadıkça bağlayıcı değil.

## 9. Kapılar (veriye bakmadan sabit)
**In-sample (replikasyon):** işlem ve performans 2016-01-01 → 2023-12-31 (ilk işlem günü D7 ısınmasından sonra), tek atış.
| Kapı | Eşik |
|---|---|
| G1 PF | > 1,30 |
| G2 1dk MTM DD | < %25 |
| G3 Net (değişken maliyetler sonrası) | > 0 |
| G4 Günlük getiri HAC t | > 2,0 |
| G5 Maliyetler ×2 iken net | > 0 |
| G6 Örneklem | ≥ 1.000 kapanmış işlem ve ≥ 500 işlemli gün |

**Hold-out (yayın sonrası):** işlem ve performans **2024-03-18 → 2026-10-30**. 2024-01-01 → 2024-03-15 arası **işlem ve performans hesabına alınmaz; yalnız gösterge ısınmasında** (D7) kullanılır. Yalnız V0_IS, G1–G6 ve V0_HO geçerse açılır.
H1 PF > 1,15 · H2 DD < %25 · H3 net > 0 · H4 maliyetler ×2 iken net > 0 · H5 ≥ 200 işlemli gün.
Günlük getiri ortalamasının %95 güven aralığı raporlanır (kapı değil).

**Kabul durumu (geçse bile):** "Ödünç erişimi varsayımı altında ve veri revizyonu riski kalan araştırma sonucu." Bu, canlı uygulanabilirlik kanıtı değildir.

## 10. Uygulanabilirlik ve canlıya geçiş koşulları
- **Komisyon:** Alpaca perakende hisse işlemleri komisyonsuz; Midas (1,5 $/işlem) bu stratejiyi imkânsız kılar.
- **PDT:** Alpaca dokümanına göre FINRA'nın yeni gün içi marjin kuralıyla 25.000 $ şartı ve işlem sayma kalktı; standart 2.000 $ asgari equity geçerli.
- **Canlı veri gideri `[TK]`:** SIP gerçek zamanlı veri 99 $/ay. Yıllık veri gideri sermayenin %5'ini aşamaz (≥ 23.760 $), ya da ücretsiz IEX verisiyle çalışan **ayrı bir sürüm** kendi testini ve paper aşamasını geçer. SIP'te test edip canlıda IEX kullanmak aynı strateji sayılmaz.
- **Paper aşamasında zorunlu ölçümler:** (a) short emirlerinin gerçek ETB/HTB, locate ve SSR reddi oranları; (b) 09:37'de canlı hesaplanan RelVol ile sonradan indirilen tarihsel barlardan hesaplanan RelVol farkı (veri revizyonu riskinin ölçümü); (c) gerçek ve modellenen kayma farkı.
- **Para transferi:** Türkiye'den SWIFT havale ücreti → seyrek ve toplu yatırım.
- **Emir:** 20 hisseye eşzamanlı emir elle girilemez → Alpaca API ile otomatik; Burak günlük "başlat/durdur" kararını verir.

## 11. Bilinen sınırlar, eleme ve tekrar kuralı
**Sınırlar:**
- Evren Alpaca'da erişilebilen sembollerle sınırlı; D5/D6 eşlemesi kusursuz değildir.
- **Veri revizyonu:** Tarihsel barlar sonradan raporlanan işlemlerle güncellenmiş olabilir; 09:37'deki veri sürümü doğrulanamaz. 2 dk gecikme bunu kapatmaz, K11-B tavanı düzeltmez. **V0'dan geçmek "lookahead sıfır" anlamına gelmez;** bu kalan risk kabul durumunda yazılıdır ve paper aşamasında ölçülür (§10).
- Tarihsel ödünç verisi yok (K14); short sonuçları iyimser olabilir. Long ve short bacakları ayrı raporlanır (betimleyici).
- 1dk bar içi sıra bilinmez (§4.1 muhafazakâr kural).

**Eleme:**
1. V0 KALDI → strateji sonucu yok (§6).
2. G1–G6'dan biri tutmazsa RED; parametre ayarlanmaz, hold-out indirilmez.
3. Hold-out RED → bu uygulama belirlenen doğrulamayı geçemedi.
4. Paper'da DD ≥ %25 → dur.

**Tekrar kuralı:** Kural değişirse yeni sürüm olur; ancak sonucu görülmüş dönemler yeni sürüm için **kullanılmış veridir**. Yeni sürüm yalnız ileriye dönük (paper) veriyle bağımsız doğrulanabilir.
Proje genelinde 6. strateji ailesi (V1, V2, Plan B, V3, Sepet momentum, V-ORB). ABD hisse verisi bu projede hiç kullanılmadı.

## 12. Denetim işleme tabloları
### 12.1 ChatGPT 1. denetim (v0.1 → v0.2)
| # | Bulgu | Karşılık |
|---|---|---|
| 1 | Düzeltilmiş veri geçmiş seçimi değiştirir | D1 raw + D3 |
| 2 | `inactive` survivorship'i çözmez | D5 adlandırması, V3, §11 |
| 3 | 09:35 sınırı, emir/portföy sırası | K5, K8, K12 |
| 4 | Maliyet modeli eksik | §4.1, G5, işletme gideri |
| 5 | Short uygulanabilirliği | K13, K14 |
| 6 | Gün sonu emir akışı | K8, K10 |
| 7 | Hold-out etiketi, tekrar kuralı | §9, §11 |

### 12.2 ChatGPT 2. denetim (v0.2 → v0.3)
| # | Bulgu | Karşılık |
|---|---|---|
| P1-1 | V0 koşulsuz kontrol listesi; dönem ayrımı yok | §6: V1–V9 sayısal KALDI koşulları, V0_IS → G → V0_HO → H sırası, hold-out verisi G kararından önce indirilmez |
| P1-2 | "Eksik bar = halt" hatalı; taşıma yaşam döngüsü yok | §4.2 eksik bar kuralı + veri kaybı testi; §4.3 taşıma, `opg`, kapasite, finansman, dönem sonu; §5 günlük getiri tanımı |
| P1-3 | K12 dolumda 4×'ü korumuyor; K11/K13 seçimi | K12 taşınanları düşer, long rezervasyonu × 1,10, dolumda adet azaltma; K11 A/B/C formülü, %0,5 = hedef risk; §7 sentetik örnek |
| P1-4 | Short çözülmemiş; SSR yalnız 09:37'de | K13 sürekli SSR ve aynı dakika kuralı; K14 + §9 kabul durumu; §10(a) paper ölçümü |
| P1-5 | Bar revizyonu riski | §11 kalan risk; §9 kabul durumu; §10(b) paper ölçümü |
| P2-6 | Hold-out ısınması / ATR önceki kapanış | §9 ara dönem yalnız ısınmada; D7 15 seans |
| Plan | Örneklem/güç planı eksik | §8 |
| TK | Yeni tasarım kararları işaretlenmeli | `[TK]` etiketleri |
