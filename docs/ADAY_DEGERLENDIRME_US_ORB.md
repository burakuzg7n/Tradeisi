# Aday değerlendirme — US ORB "Stocks in Play" (V-ORB v1)

**Sürüm:** v0.5 taslak (9 Kasım 2026) · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Karar:** Burak
**Statü:** TASLAK. Kurallar ve kapılar **hiçbir fiyat/getiri verisine bakılmadan** yazıldı.
Yalnız veri erişimi kontrol edildi (SPY 5dk bar SAYISI, 2016–2026; fiyat/getiri hesaplanmadı).
**Kâr garantisi yok.** RED geçerli bir sonuçtur.
**Değişiklik geçmişi:** v0.2 = ChatGPT 1. denetimi (§12.1) · v0.3 = 2. denetim (§12.2) · v0.4 = 3. denetim (§12.3) · v0.5 = 4. denetim (§12.4).
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
| D7 | Isınma: ATR(14) için 15 seans (14 True Range + ilk TR'nin önceki kapanışı); K3 için önceki 14 seansın tamamı; K5 paydası için önceki 14 seansın ilk barlarından **en az 10'u** (K5). Yetersiz geçmiş → o gün aday değil. |

## 3. Kurallar
| # | Kural | Değer |
|---|---|---|
| K1 | Evren | D5–D6 |
| K2 | Fiyat | O günün 09:30 açılış fiyatı (raw) > 5 $ |
| K3 | Likidite | Önceki 14 seans ortalama günlük hacim ≥ 1.000.000 adet (D3 ölçeğinde) |
| K4 | Oynaklık | ATR(14) > 0,50 $; ATR = önceki 14 True Range'in basit ortalaması (D3 ölçeğinde) |
| K5 | RelVol | Pay: bugünün tamamlanmış 09:30–09:35 bar hacmi. Payda: önceki 14 seansta bu bar mevcut olanların (en az 10) hacim ortalaması; 10'dan az ya da payda 0 → aday değil `[TK]`. RelVol ≥ 1,00. Bugünün bu barı yoksa aday değil. |
| K6 | Seçim | K2–K5'i geçenlerden RelVol'e göre ilk 20; eşit RelVol'de sembol alfabetik sırası `[TK]` |
| K7 | Yön | **Yalnız long:** ilk 5dk bar kapanış > açılış → long adayı; kapanış ≤ açılış → işlem yok. **[SAPMA: makale long + short; gerekçe §3.1]** |
| K8 | Giriş | İlk 5dk barın tepesine buy-stop. Emirler **09:37'de** etkin `[TK]`; son giriş **15:30**, tetiklenmeyenler 15:30'da iptal `[TK]`. Yarım gün: son giriş 12:30. |
| K9 | Stop | Gerçekleşen giriş fiyatından 0,10 × ATR(14). Stop yalnız seans içinde geçerli. |
| K10 | Gün sonu | Açık pozisyon **15:55'te piyasa emriyle** kapanır `[TK]` (yarım gün 12:55). `cls` kullanılmaz. Taşıma: §4.3. |
| K11 | Adet | adet = ⌊min(A, B, C)⌋: **A** = 0,005 × E / (0,10 × ATR) (hedef risk; maliyet ve stop kayması hariç), **B** = 0,01 × 09:30–09:35 hacmi `[TK]`, **C** = kalan kapasite / rezervasyon fiyatı (K12). E = gün başı equity. %0,5 **hedef** risktir; gerçekleşen kayıp daha büyük olabilir ve dağılımı raporlanır. [SAPMA: makale %1] |
| K12 | Kapasite | Kapasite = 4 × E − (önceki günden taşınan pozisyonların brüt piyasa değeri). 09:37'de bekleyen her emir için nominal ayrılır; rezervasyon fiyatı seviye × 1,10 `[TK]`. RelVol sırasıyla eklenir; sığmayan atlanır, gün içinde tekrar değerlendirilmez. Dolumda brüt pozisyon yine de 4 × E'yi aşacaksa adet sığacak kadar azaltılır ve olay kaydedilir. |

### 3.1 Neden yalnız long (v0.5 kararı, veriye bakılmadan)
- Tarihsel ödünç (ETB/HTB, locate) verisi yok; short bacağın geçmişte **yapılabilir** olduğu doğrulanamaz (2. ve 3. denetim).
- Rule 201 (SSR) tetiği ile sell-stop tetiğinin aynı dakikadaki sırası dakikalık OHLC'den kesinleştirilemez (4. denetim P1-2).
- Bu iki belirsizlik short bacağını, sonucu ne çıkarsa çıksın yorumlanamaz kılar. Long bacağında ikisi de yoktur.
- Bedeli: sonuç makalenin tam replikasyonu değil, **long bacağının replikasyonu**dur. Short bacağı ayrı bir sürümde, ancak trade seviyesi ödünç/SSR verisiyle ele alınabilir.
- İşlem sayısına etkisi sınırlı: K12 kapasitesi günde zaten yalnız birkaç emre yer verdiği için (§8) bağlayıcı kısıt sinyal sayısı değil sermayedir.

## 4. Yürütme ve maliyet modeli (1dk barlarla)
### 4.1 Dolum ve maliyet
- **Kayma (her dolumda, aleyhe):** k = max(0,01 $; 0,0005 × fiyat) `[TK]`; spread dahil kabul edilir. Alışlar +k, satışlar −k.
- **Giriş:** Tetik barının açılışı seviyenin üstündeyse (gap) dolum = açılış + k; değilse seviye + k.
- **Giriş barında stop seviyesine de değilmişse** stop varsayılır.
- **Stop:** stop seviyesi − k; bar açılışı stop'un altındaysa açılış − k.
- **Gün sonu:** 15:55 1dk barının açılışı ∓ k.
- **Komisyon:** 0,0035 $/adet her yönde. **SEC Section 31** ve **FINRA TAF**: yalnız satış yönü, işlem tarihindeki resmî tarifeyle, işlem başına yukarı cent'e yuvarlanır.
- **Kısmi dolum yok** varsayılır; K11-B tavanı bu varsayımı sınırlar.
- **Stres (G5/H4):** kayma, komisyon, düzenleyici ücretler ve §4.3 finansman giderlerinin **hepsi ×2**; tüm simülasyon (boyutlama ve equity yolu dahil) baştan koşulur.
- **İşletme gideri:** canlı SIP verisi 99 $/ay = 1.188 $/yıl. Sonuçlar ayrıca **veri gideri sonrası** net olarak (25.000 $ ve 2.000 $ başlangıç için) raporlanır (betimleyici; §10 kuralı ayrıdır ve gider sonrası kârlılık anlamına gelmez).

### 4.2 Eksik bar — mutabakat ya da KALDI
Bar verisi tek başına "işlem yok", "durma" ve "veri kaybı"nı ayırt edemez; bir veri kaybı stop'u ya da gerçek kayıp büyüklüğünü gizleyebilir. v0.4'teki "5dk barla tamamla" yaklaşımı bunu çözmedi (4. denetim P1-1). v0.5 ilkesi: **eksik veriyi tahminle tamamlama yok; ya hacim mutabakatıyla eksiksiz olduğu gösterilir ya da V0 KALDI.**
- **Kaynaklar:** A = 1dk barlar, B = 5dk barlar, Dg = günlük bar (üçü de Alpaca SIP, raw).
- **Pencere mutabakatı:** Emir veya pozisyonun etkin olduğu her 5dk pencerede Σ(A hacmi) = B hacmi (**tam eşitlik**, hacimler tam sayıdır). Eşitse A o pencerede eksiksiz kabul edilir; barı olmayan dakika **gerçekten işlem görmemiş** dakikadır ve o dakikada dolum olmaz.
- **Gün mutabakatı:** İşlem yapılan her hisse-günde Σ(o günün tüm A barlarının hacmi, seans dışı dahil) = Dg hacmi (tam eşitlik). İki agregasyonun birlikte boş olduğu pencereler bu sayede bağımsız bir kaynakla sınanır.
- **Etkin emir veya pozisyonu etkileyen herhangi bir mutabakatsızlık = tek olay V0 KALDI** (V5). Etkinin yönünü veya büyüklüğünü tahmin etmeye çalışılmaz; düşük olay oranı düşük etki kanıtı sayılmaz.
- **Bilinen risk:** Agregasyon tanımları (işlem koşulu filtreleri) kaynaklar arasında sistematik olarak farklıysa V0 bu maddeden kalır. Bu durumda strateji kuralı değişmez; **veri yöntemi v2** (Alpaca trade seviyesi veriden bar üretimi) ayrı bir notla yazılır ve V0 yeniden koşulur.
- **Aynı 1dk barda giriş ve stop:** stop varsayılır (bilinen en kötü sıra).

### 4.3 Taşınan pozisyon (halt / bar yok)
1. 15:55'te bar yoksa piyasa emri 15:59'a kadar her dakika yeniden denenir (ilk bar = dolum).
2. 15:55–15:59 arası hiç bar yoksa pozisyon **taşınır**. Gece stop yoktur.
3. Ertesi seans pozisyon **açılış emriyle (`opg`)** kapanır: dolum = günün ilk RTH bar açılışı ∓ k. Açılışta da bar yoksa 2. adımdaki gibi dakika dakika denenir; seans sonuna kadar dolmazsa yine taşınır.
4. Taşınan pozisyon K12'de kapasiteden düşülür.
5. **Finansman `[TK]`:** taşınan her gece için equity'yi aşan borç kısmına yıllık %10 (365 güne bölünerek).
6. **Dönem sonu (tasfiye uzantısı):** Dönemin son seansında açık kalan pozisyon geriye dönük kapatılmaz. Dönemin son seansını izleyen en fazla **5 seans** "tasfiye uzantısı"dır: bu seanslarda **yeni emir verilmez**, yalnız açık pozisyon 3. adımdaki gibi gerçek bir çıkış emriyle kapatılır. Uzantı seansları dönemin günlük getiri, DD ve HAC serisine eklenir; kapanan işlem PF ve net sonuca girer; bu seanslar ilgili sembol için V0 kapsamındadır. Açık pozisyon yoksa uzantı yoktur. In-sample uzantısı 2024 Ocak başına, hold-out uzantısı 2026 Kasım başına düşer. 5 seans içinde kapanamayan pozisyon kalırsa: equity ve DD'de son mevcut fiyatla **değerlenir** ama **kapanmış işlem sayılmaz** (PF'ye girmez) ve o dönem için **KARAR YOK** (G veya H kararı verilmez, durum arşivlenir).
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
| V3 | Veri varlığı | Ölçüm, dönemin **ısınma sonrası ilk seansından** başlar. Her seansta günlük barı olan evren sembolü sayısı (piyasadan değil veriden kaynaklanan kopuşu yakalamak için). K2–K4'ü geçen hisse sayısı yalnız raporlanır, kapı değildir (aday azlığı veri bozukluğu kanıtı değildir; K6 o gün daha az hisse alır). | Herhangi bir seansta günlük barı olan sembol sayısı, önceki 20 seansın medyanının **%50'sinin altında** |
| V4 | Seçim ve emir kararı | K2–K4'ü geçen **tüm** hisse-günleri için 09:30–09:35 penceresi A ve B'de karşılaştırılır (bugün ve K5 paydasına giren önceki 14 seans). Her gün için seçim zinciri **iki kez** kurulur: RelVol yalnız A hacimleriyle ve yalnız B hacimleriyle → K6 sıralı liste → K7 yön → K12 kabul edilen emirler → K11 adetleri. | İki zincirin herhangi bir günde **sıralı kabul listesi veya herhangi bir emrin adedi** farklıysa → **tek olay KALDI** (sıra değişikliği kapasiteyi kimin kullandığını değiştirebilir). Ayrıca B'de var A'da yok (veya tersi) ilk bar olan hisse-günleri K2–K4 hisse-günlerinin > %0,5'i ise KALDI. |
| V5 | Yürütme mutabakatı | §4.2 pencere ve gün mutabakatı, etkin emir/pozisyonu olan her pencere ve hisse-gün (tasfiye uzantısı dahil) | **≥ 1 mutabakatsızlık** |
| V6 | Ölçek | Bölünmeden etkilenen her gösterge penceresinde **aynı geçmiş barın** ham ve dönüştürülmüş değerleri karşılaştırılır: dönüştürülmüş fiyat = ham ÷ oran, hacim = ham × oran (yalnız yuvarlama farkı, göreli 1e-9). Bağımsız çapraz kontrol: ex-date'inden sonra başka bölünme olmamış her olayda dönüştürülmüş barlar Alpaca `adjustment=split` barlarıyla karşılaştırılır (göreli 1e-4). Ayrıca yalnız işlem tarihine kadar ex-date'i gelmiş bölünmelerin kullanıldığı test edilir. | **≥ 1 uyumsuzluk** |
| V7 | Isınma | D7'ye uymayan aday sayısı | ≥ 1 |
| V8 | Yürütme testleri | §7'deki sentetik testlerin tamamı beklenen sonucu verir | ≥ 1 başarısız test |
| V9 | Tekrarlanabilirlik | İndirilen **ham veri dosyaları** (günlük, 5dk, 1dk), evren/varlık listesi, corporate actions, takvim ve SEC/FINRA tarife tablosu **bir kez indirilip yerelde arşivlenir**; her dosyanın sha256'sı ve indirme parametreleri (tarih aralığı, feed, adjustment, API sürümü, indirme zamanı) manifest'e yazılır; manifest repoya commit edilir. Tüm koşular bu arşivden yapılır, **yeniden indirme yapılmaz**. Aynı arşiv ve kod commit'iyle ikinci koşu bit düzeyinde aynı çıktıyı verir. Başarısız V0 raporları da arşivlenir. | Eksik kayıt, hash uyuşmazlığı veya çıktı farkı |

## 7. Zorunlu sentetik yürütme testleri (V8)
Her biri sabit girdi ve beklenen sonuçla birim testi olarak yazılır:
gap ile giriş dolumu · giriş barında stop · K12 rezervasyon sırası ve atlama · dolumda 4× aşımında adet azaltma: 25.000 $ equity, ATR 1,25, long seviye 100, hacim tavanı bağlamıyor → A = 1.000, C = ⌊100.000 / 110⌋ = **909 adet** ayrılır; açılış 105'te dolum 105,0525 → 95.493 $, azaltma **yok**; açılış 120'de dolum 120,06 → 909 adet 109.135 $ olurdu, adet **⌊100.000 / 120,06⌋ = 832**'ye düşer · K11 A/B/C'den hangisinin bağladığı · 09:37 öncesi dolum olmaması · 15:30 iptal · yarım gün saatleri · K7 kapanış = açılış ve kapanış < açılış → emir yok · §4.2 mutabakat: (i) 10:00'da 98, 10:02'de giriş 100,05 / stop 99,05, 10:03 A'da eksik ama B hacmi Σ A'dan büyük → **V5 KALDI** (aralıklar aynı olsa bile); (ii) önceden açık long, stop 99, B 101'den açılıyor, eksik dakika 90'dan açılmış → hacim farkı → **V5 KALDI**; (iii) eksik dakika ama Σ A = B ve gün mutabakatı tutuyor → o dakikada dolum yok, geçerli · V4: A ve B'de aynı 20 hisse, ilk ikisinin sırası farklı ve birincisi kapasiteyi tüketiyor → **V4 KALDI** · 15:55'te bar yokken yeniden deneme · taşınan pozisyonun `opg` kapanışı, kapasiteden düşülmesi ve finansmanı · dönem sonunda açık pozisyonun dönem sonrası seanslarda gerçek emirle kapanması ve 5 seans sonra KARAR YOK · D3 bölünme ölçeği · D6 sembol yeniden kullanımı · D7 ısınma sınırı (14 TR + önceki kapanış) · işlemsiz ama taşınan pozisyonlu gün getirisi · maliyet ×2 stresinin yeniden simülasyonu.

## 8. Örneklem ve güç planı (SONRAKI_YON_KARAR_NOTU §3)
Gerçek getiri dağılımı bilinmiyor; varsayımlar açıktır.
- **Gözlem birimi:** aynı günün işlemleri ilişkili olduğundan **seans** (tüm seanslarda portföy günlük getirisi, §5), işlem değil.
- **Asgari anlamlı etki:** yıllık Sharpe 1,0 (günlük ortalama/std = 1/√252).
- **Test:** iki yönlü α = 0,05, güç 0,80; otokorelasyon ve kalın kuyruk için varyans şişirme 1,3 varsayımı.
- **Gereken gün:** Sharpe 1,0 → ≈ 2.572 · Sharpe 1,5 → ≈ 1.143 · Sharpe 2,0 → ≈ 643.
- **Mevcut veri:** in-sample ≈ 1.990 seans → güç ≈ %69 (Sharpe 1,0), %96 (1,5), ≈ %100 (≥ 2,0). Hold-out ≈ 655 seans → güç ≈ %29 (1,0), %56 (1,5), %81 (2,0), %98 (2,8).
- **Sonuç:** in-sample, makalenin iddia ettiği büyüklükteki (Sharpe ≈ 2,8) bir etkiyi ayırt etmeye yeter; Sharpe 1,0 civarındaki küçük bir etkiyi kaçırma olasılığı ≈ %31'dir. Hold-out yalnız büyük etkileri doğrulayabilir; H kapıları HAC t istemez, kesin kanıt sayılmaz. Asıl ileriye dönük doğrulama paper aşamasıdır.
- **İşlem sayısı tahmini (sermaye kısıtıyla; ölçüm değil, fiyat/ATR ve tetiklenme varsayımlarına dayalı tahmin):** K11-A'ya göre bir pozisyonun nominali = 0,05 × E × (fiyat / ATR). Fiyat/ATR'nin 20–50 arasında olduğu varsayımıyla tek emir **1× – 2,5× E** nominal ayırır; 4× kapasiteye günde yalnız **tahminen ≈ 2–4 emir** sığar (20 sinyalin çoğu atlanır). Tetiklenme oranı %30–%70 varsayımıyla günde ≈ 0,6–2,8 işlem → in-sample ≈ **1.200–5.600 işlem**, işlemli gün ≈ **900–1.700**. G6 (1.000 işlem / 500 gün) bu aralığın alt ucuna yakındır ve **bağlayıcı olabilir**; G6 kalırsa sonuç RED'dir, eşik değiştirilmez. Güç planı işlemli günler üzerinden değil, tüm seanslardaki günlük portföy getirisi (işlemsiz günler §5'e göre) üzerinden yapıldığı için §8 güç sayıları değişmez; ancak işlemli gün azaldıkça günlük getiri dağılımı daha seyrek ve kalın kuyruklu olur (1,3 şişirme varsayımının iyimser kalma riski).

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

**Hold-out (yayın sonrası):** işlem ve performans **2024-03-18 → 2026-10-30**. 2024-01-01 → 2024-03-15 arasında **yeni işlem açılmaz**; bu aralık yalnız (a) hold-out gösterge ısınması (D7) ve (b) in-sample tasfiye uzantısı (§4.3/6) için kullanılır. Yalnız V0_IS, G1–G6 ve V0_HO geçerse açılır.
H1 PF > 1,15 · H2 DD < %25 · H3 net > 0 · H4 maliyetler ×2 iken net > 0 · H5 ≥ 200 işlemli gün.
Günlük getiri ortalamasının %95 güven aralığı raporlanır (kapı değil).

**Kabul durumu (geçse bile):** "Yalnız long bacağında, veri revizyonu riski kalan araştırma sonucu." Bu, canlı uygulanabilirlik kanıtı değildir.

## 10. Uygulanabilirlik ve canlıya geçiş koşulları
- **Komisyon:** Alpaca perakende hisse işlemleri komisyonsuz; Midas (1,5 $/işlem) bu stratejiyi imkânsız kılar.
- **PDT:** Alpaca dokümanına göre FINRA'nın yeni gün içi marjin kuralıyla 25.000 $ şartı ve işlem sayma kalktı; standart 2.000 $ asgari equity geçerli.
- **Canlı veri gideri `[TK]`:** SIP gerçek zamanlı veri 99 $/ay. Yıllık veri gideri sermayenin %5'ini aşamaz (≥ 23.760 $), ya da ücretsiz IEX verisiyle çalışan **ayrı bir sürüm** kendi testini ve paper aşamasını geçer. SIP'te test edip canlıda IEX kullanmak aynı strateji sayılmaz.
- **Paper aşamasında zorunlu ölçümler:** (a) emir reddi ve kısmi dolum oranları; (b) 09:37'de canlı hesaplanan RelVol ile sonradan indirilen tarihsel barlardan hesaplanan RelVol farkı (veri revizyonu riskinin ölçümü); (c) gerçek ve modellenen kayma farkı.
- **Para transferi:** Türkiye'den SWIFT havale ücreti → seyrek ve toplu yatırım.
- **Emir:** 20 hisseye eşzamanlı emir elle girilemez → Alpaca API ile otomatik; Burak günlük "başlat/durdur" kararını verir.

## 11. Bilinen sınırlar, eleme ve tekrar kuralı
**Sınırlar:**
- Evren Alpaca'da erişilebilen sembollerle sınırlı; D5/D6 eşlemesi kusursuz değildir.
- **Veri revizyonu:** Tarihsel barlar sonradan raporlanan işlemlerle güncellenmiş olabilir; 09:37'deki veri sürümü doğrulanamaz. 2 dk gecikme bunu kapatmaz, K11-B tavanı düzeltmez. **V0'dan geçmek "lookahead sıfır" anlamına gelmez;** bu kalan risk kabul durumunda yazılıdır ve paper aşamasında ölçülür (§10).
- Yalnız long (§3.1): sonuç makalenin tam replikasyonu değildir.
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

### 12.3 ChatGPT 3. denetim (v0.3 → v0.4)
| # | Bulgu | Karşılık |
|---|---|---|
| P1-1 | Veri kaybında "emir dolmaz" yanlış; V5 oranı tek olayı geçirebilir | §4.2 iki kaynaklı (1dk + 5dk) muhafazakâr kural; "hiçbir veri sorunu strateji lehine sonuç üretemez" ilkesi; yönü bilinmeyen (giriş kararı kaynağa bağlı) tek olay V0 KALDI (V5) |
| P1-2 | Dönem sonunda geriye dönük, gerçekleşemeyen çıkış | §4.3/6: dönem sonrası en fazla 5 seansta gerçek emirle kapanış; kapanamazsa değerleme ≠ kapanmış işlem ve KARAR YOK |
| P1-3 | SSR, dakikanın sonraki düşüğüyle açılıştaki girişi siliyordu | K13 bar içi işlem sırası (açılış → bar içi seviye/eşik geometrisi → yalnız bekleyen emirler); §7 sayısal örnekler |
| P1-4 | V6 bölünme dönüşümünü doğrulamıyordu | V6: aynı barın ham/dönüştürülmüş karşılaştırması (sıfır tolerans) + Alpaca `adjustment=split` çapraz kontrolü + ex-date zamanlama testi |
| V3 | Isınma günleri; aday düşüşü veri kanıtı değil | V3 ısınma sonrası başlar, veri varlığını ölçer; aday sayısı yalnız rapor |
| V4 | K5'te elenen eksik kayıtlar görünmüyordu; boş payda | V4 tüm K2–K4 hisse-günleri; (a)/(b)/(c) sınıfları; payda kuralı (≥ 10/14) |
| V9 | Ham veri ve evren hash'i yok; yeniden indirme aynı sürümü garanti etmez | V9 ham dosyalar + evren arşivlenir, manifest commit edilir, yeniden indirme yapılmaz |
| §7 | Kapasite örneği azaltmayı sınamıyordu | 105 (azaltma yok) ve 120 (909 → 832) örnekleri |
| §8 | İşlem tahmini sermaye kısıtını atlıyordu; G6 "bağlayıcı değil" desteklenmiyor | Sermaye kısıtlı tahmin (≈ 1.200–5.600 işlem); G6 bağlayıcı olabilir |
| Gerileme | Veri gideri sonrası net rapor kaybolmuştu | §4.1 işletme gideri satırı geri kondu |

### 12.4 ChatGPT 4. denetim (v0.4 → v0.5)
| # | Bulgu | Karşılık |
|---|---|---|
| P1-1 | 5dk ile tamamlama stop'u ve kayıp büyüklüğünü gizleyebiliyor; iki kaynak boşken "işlem yok" kabulü | §4.2 tümüyle değişti: tahminle tamamlama yok; pencere (Σ1dk = 5dk) ve gün (Σ1dk = günlük) hacim mutabakatı; etkin emir/pozisyonu etkileyen tek mutabakatsızlık V0 KALDI (V5); başarısızlıkta veri yöntemi v2 |
| P1-2 | SSR sıralaması fiyatın sürekli hareketini varsayıyor | Short bacağı kaldırıldı (K7, §3.1); K13–K14 silindi. SSR ve ödünç belirsizliği tümden ortadan kalktı |
| P1-3 | V4 ilk 20 içi sıra değişikliğini kaçırıyor | V4: A ve B hacimleriyle iki seçim zinciri; kabul listesi veya adet farkı tek olayda KALDI |
| Metin | Tasfiye uzantısı ile §9 dışlama çelişkisi | §4.3/6 tasfiye uzantısı tanımı (yeni emir yok, seriye dahil, V0 kapsamı) + §9 metni |
| Metin | 10/14 kuralı D7 ve K5'te yok | D7 ve K5 güncellendi; K6 eşitlik kuralı |
| §8 | "2–4 emir" ölçüm değil | Tahmin olarak etiketlendi |
| Not | §12.1–12.3'teki K13/K14 atıfları tarihsel kayıttır; v0.5'te bu kurallar yoktur. | — |

