# V3 — Seans kırılımı (gün içi) · ÖN-KAYIT TASLAĞI (rev. 2)

**Tarih:** 2 Kasım 2026 · **Karar veren:** Burak · **Hazırlayan:** Claude · **Denetim:** ChatGPT
**Statü:** TASLAK. Hiçbir V3 verisi indirilmeden ve hiçbir V3 sonucu görülmeden yazıldı.
Bu belge onaylanıp birleştirilene kadar kod yazılmaz, veri indirilmez.
**Rev. 2:** ChatGPT'nin `8f22e9c` denetimindeki 9 bulgu ve Burak'ın Z1/Z2 kararları işlendi.
**Rev. 3:** `d50973f` denetimi: giriş mumu açılışı stop ötesi, gap hedef maliyeti, ertelenmiş
zaman çıkışı önceliği, gün ataması, örneklem gerekçesi, eksik mumda equity ve sermaye
tükenmesi anı.

Etiketler: **[KURAL]** bu belgenin kuralı · **[SAPMA]** AGENTS.md / önceki protokolden
bilinçli, gerekçeli sapma (Burak onayı + bağımsız denetim gerekir).

## 0. Çerçeve

- Burak'ın kararları (2 Kasım 2026): gün içi, portföy toplamında **ayda 40–75 işlem**
  hedefli bir sistem; mantık **seans kırılımı**; gerçek paradan önce projede **hiç
  indirilmemiş** coinlerde tek atış test.
- V1, V2, Plan B v1 reddedildi; değişmez. V3 bunların düzeltmesi veya telafisi değildir;
  ayrı bir hipotezdir. Kazanç garantisi yoktur; V3'ün reddedilmesi geçerli bir sonuçtur.
- Planlama yöntemi: `docs/SONRAKI_YON_KARAR_NOTU.md` §3.
- Testten sonraki aşamalar (paper/testnet/canlı) bu belgede değil, ayrı taslak
  `docs/V3_DOGRULAMA_PLANI.md`'dedir. **Hold-out'u geçmek tek başına canlıya geçiş hakkı
  vermez.**

## 1. Hipotez

Kripto perp piyasasında Asya seansı (00:00–07:00 UTC) aralığının, Londra/New York
saatlerinde günlük trend yönünde kırılması, maliyetler dahil pozitif net beklentili gün
içi hareket başlatır.

## 2. Veri ve bağımsızlığın sınırı

- **Evren:** XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT — Binance USDⓈ-M PERPETUAL,
  son işlem fiyatı OHLC, 15 dakika. Bu beş sembolün verisi bu projede indirilmemiştir.
- **Sunuş [KURAL]:** sonuç **"yeni sembollerde önceden kaydedilmiş test"** olarak sunulur;
  tam bağımsız piyasa kanıtı **sayılmaz**. Aynı tarihlerin genel piyasa sonuçları (BTC/ETH
  vb.) önceki araştırmalarda görülmüştür ve bu coinler onlarla yüksek korelasyonludur.
  "Genel piyasa bilgisinin kural seçiminde kullanılmadığı" iddiası bağımsız doğrulanamaz.
- **In-sample:** 2021-01-01 → 2024-12-31. **Hold-out:** 2025-01-01 → ortak bitiş (aşağıda).
  2020 verisi yalnız ısınma içindir.
- **Veri sağlığı ve engeller [KURAL]** (Plan B E14 ile aynı yaklaşım, 15m için):
  listeleme = min(onboardDate, ilk mum); listeleme öncesi eksik sayılmaz; dönem içi eksik
  15m mum oranı bir sembolde **%1'i aşarsa**, bozuk mum (tekrar, sonlu olmayan/sıfır/negatif
  fiyat, high < low, open/close aralık dışı) varsa, veya in-sample'da 2024-12-31 23:45 mumu
  yoksa koşu başlamaz. **Ortak bitiş** = sembollerin son TAM UTC gününün en erkeni; sonrası
  kullanılmaz. Eksikler raporda sembol başına listelenir.

## 3. Günlük gösterge (trend filtresi)

- **Günlük kapanış [KURAL]:** UTC günü d için C_d = o günün 23:45 açılışlı 15m mumunun
  kapanışı. Gün d'nin 96 mumundan **90'dan azı** mevcutsa veya 23:45 mumu yoksa gün d
  **geçersiz** sayılır (C_d yok).
- **SMA20 [KURAL]:** gün d'deki işlem için referans gün = d−1 (dün). SMA = son **20 geçerli**
  günlük kapanışın ortalaması, **C_{d−1} dahil** (d−1 ve öncesi). Dün geçersizse veya 20
  geçerli gün yoksa o gün işlem yok. Isınma dönem öncesi veriyle yapılır.
- Yön: C_{d−1} > SMA → yalnız LONG; C_{d−1} < SMA → yalnız SHORT; eşitse işlem yok.

## 4. Sinyal, emir ve yürütme (her sembol, her UTC günü)

1. **Asya aralığı:** 00:00–06:45 açılışlı 28 mumun en yüksek HIGH'ı (AH), en düşük LOW'u
   (AL); M = (AH + AL)/2. Bu 28 mumdan biri eksikse o gün o sembolde işlem yok.
2. **Tetik:** 07:00–19:45 açılışlı mumlardan **ilk** kapanışı LONG için > AH (SHORT için
   < AL) olan mum t. Sembol başına günde en fazla 1 tetik/işlem. Pencerede eksik mum
   olabilir; mevcut mumlar sırayla değerlendirilir.
3. **Emir kararı — yalnız t kapanışındaki bilgiyle [KURAL]:** referans fiyat P = t'nin
   kapanışı. Emir verilmez (maliyetsiz, çünkü emir yoktur) eğer:
   LONG'da P ≤ M veya SHORT'ta P ≥ M; ya da |P − M| / P < **%1,0** (asgari stop mesafesi;
   gidiş-dönüş maliyeti ≈ %0,17 olduğundan; optimizasyon değildir); ya da E16 karşılığı
   (bakiye ≤ 0, §5).
4. **Boyut [KURAL]:** miktar = (risk oranı × bakiye_t) ÷ |P − M|. bakiye_t = t kapanışındaki
   gerçekleşmiş bakiye (o ana kadar kapanmış işlemler). Boyut dolumdan sonra değişmez.
5. **Dolum:** t'den sonraki **ilk mevcut** mumun açılışında market, aleyhe slippage
   (F = open × (1 ± s)), taker. Bu mum t+1 değilse (eksik) veya 23:45'ten sonra ise emir
   **iptal** (dolum yok, maliyet yok).
6. **Dolum sonrası geometri [KURAL] — maliyetsiz iptal YOK:** dolum gerçekleştikten sonra,
   giriş mumunun **ham açılışı** VEYA dolum F stopun ötesindeyse (LONG: open ≤ M veya
   F ≤ M; SHORT: open ≥ M veya F ≥ M) pozisyon **aynı açılışta** acil çıkışla kapanır:
   çıkış = open × (1 ∓ s), taker; sebep `gap_through_stop`. (Slippage sonrası F'nin
   stopun içinde kalması, açılışı stopun ötesinde olan bir mumda M'den daha iyi bir
   çıkış hakkı vermez.) Gerçekleşen R, planlanan R'den sapabilir; raporlanır.
7. **Stop:** M, stop-market (taker). **Hedef:** T = F ± 2 × |F − M| (gerçek dolumdan),
   limit (maker), dolumdan hemen sonra emir olarak konmuş sayılır.
8. **Mum içi yürütme önceliği [KURAL]** (her mum; giriş mumu dahil):
   (0) Bekleyen zaman çıkışı varsa (§4.9, 23:45 mumu eksikti): **önce** o yürütülür —
   open × (1 ∓ s), taker; (a)–(d) o mumda uygulanmaz.
   (a) Giriş mumu dışındaki mumlarda açılış stopun ötesindeyse: çıkış = open × (1 ∓ s),
   taker (`gap_stop`). (b) Açılış hedefin ötesindeyse: dolum = **T** (lehe açılış farkı
   alınmaz), **maker, slippage yok** (`gap_target`). (c) Mum içinde stop teması (LONG: low ≤ M) varsa: stop
   × (1 ∓ s), taker — aynı mumda hedef teması da olsa **stop** önceliklidir. (d) Hedef için
   **katı aşım** gerekir (LONG: high > T; eşitlik dolum sayılmaz): dolum = T, maker.
   Giriş mumunda (c) ve (d) uygulanır (dolum açılışta olduğundan mum içi sıra bilinmez;
   ikisi birden → stop).
9. **Zaman çıkışı [KURAL]:** önceden planlanmış saat tabanlı tasfiye. Pozisyon 23:45
   açılışlı mumun sonunda açıksa, o mumda (a)–(d) uygulandıktan sonra **kapanışında**
   market: close × (1 ∓ s), taker (`time_exit`). 23:45 mumu eksikse zaman çıkışı
   **bekleyen** hale gelir ve sonraki ilk mevcut mumun açılışında (0) kuralıyla, gap
   stop/hedef kontrolünden **önce** yürütülür; arada stop/hedef kontrolü yapılamaz (fiyat
   yok) ve bu durum raporda sayılır. Pozisyon bu yüzden ertesi güne taşınırsa, o sembolde
   pozisyon kapanana kadar yeni emir verilmez; ertesi günün kendi işlem hakkı (§4.2)
   aksi halde etkilenmez.
   **Gün ataması [KURAL]:** zaman çıkışı, 23:45 mumunun ait olduğu UTC gününe (d) yazılır
   (kapanış zaman damgası d+1 00:00 olsa da). Diğer tüm çıkışlar, yürütüldükleri mumun
   açılış zaman damgasının UTC gününe yazılır. PF, işlem sayısı ve günlük seri aynı
   atamayı kullanır.
   **Dönem sonu [KURAL]:** dönemin son günü d_son'da açık pozisyon normalde o günün 23:45
   kapanışında zaman çıkışıyla kapanır ve d_son'a yazılır (dönem içinde). d_son'un 23:45
   mumu eksikse, dönem sonrasındaki veri kullanılmaz: pozisyon d_son'un **son mevcut
   mumunun kapanışında** (aleyhe slippage, taker) tasfiye edilir — Plan B E13'teki gibi
   dönem sonu verisine bakan onaylı bir varsayım; raporda ayrıca listelenir.
10. **Eksik mum (pozisyon açıkken):** o mum için kontrol yapılmaz; sonraki mevcut mumda
    (0)/(a)–(d) uygulanır.

## 5. Hesap, risk ve maliyet

- **Tek ortak hesap**, başlangıç 10.000 $ (test ölçeği). Sembol başına en fazla 1 açık
  pozisyon; eşzamanlı en fazla 5.
- **İşlem başına risk = %1 [SAPMA — Z2]:** AGENTS.md/önceki stratejiler %0,5 kullanıyordu.
  Burak'ın kararı (Z2 = %1): küçük hesapta (200–300 $) asgari emir sınırı ve kabul ettiği
  risk düzeyi. Test aynı riskle koşulur ki DD kapısı canlıdaki riskle aynı ölçekte olsun.
  Not: 5 eşzamanlı pozisyonda anlık toplam planlanan risk %5'e çıkabilir ve coinler
  korelasyonludur.
- **Muhasebe [KURAL]:** ücret ve funding işlem **kapanışında** gerçekleşmiş PnL'ye yazılır;
  bakiye yalnız kapanışlarda değişir. Aynı açılışta kapanan işlemlerin PnL'si, o açılışta
  dolan emirlerin boyutunu etkilemez (boyut t kapanışında belirlenmişti, §4.4).
- **Equity ve DD [KURAL]:** portföy zaman ekseni = en az bir sembolün mumu olan 15m zaman
  damgaları. Her damgada equity = bakiye + açık pozisyonların (sembolün **son mevcut**
  kapanışı − F) × miktar (yönlü) − giriş ücreti − tahakkuk etmiş funding. O damgada mumu
  olmayan sembolün pozisyonu son mevcut kapanışla değerlenir (taşıma; sayısı raporlanır).
  Max DD bu **15 dakikalık** seriden ölçülür (günlük kapanış DD'si gün içi düşüşü
  göstermediği için). Bu, mum içi en kötü anı göstermez; sınırlama raporda yazılır.
- **%30 DD kapısı bir durma garantisi değildir:** gap, gecikme ve yürütme farkları
  gerçekleşen kaybı herhangi bir eşiğin ötesine taşıyabilir.
- **Sermaye tükenmesi [KURAL]:** her 15m zaman damgasında, o damgadaki **tüm** çıkışlar
  işlendikten sonra (işlenme sırasından bağımsız) gerçekleşmiş bakiye denetlenir. Herhangi
  bir damgada bakiye ≤ 0 olursa: o andan sonra yeni emir yok ve koşu kapılardan bağımsız
  **KALDI** (sonradan toparlanması bunu değiştirmez). Emir kararındaki bakiye_t de aynı
  tanımla (t kapanışında, o damgadaki çıkışlar işlendikten sonra) okunur.
- **Ücret:** taker %0,055 (market giriş, stop, `gap_stop`, `gap_through_stop`, zaman
  çıkışı); maker %0,02 (hedef ve `gap_target`).
- **Slippage:** s = %0,03, sabit, aleyhe: market giriş, stop, `gap_stop`,
  `gap_through_stop`, zaman çıkışı. Hedef ve `gap_target` dolumlarına slippage
  **uygulanmaz** (limit emir, T fiyatından).
  **Sınırlama:** gerçek slippage'ın üst sınırı olduğu iddia edilmez (altcoin likiditesi,
  oynak anlar); yalnız sabit bir model varsayımıdır.
- **Funding:** nominal = F × miktar (sabit). Pozisyonun açık olduğu aralık [dolum anı,
  çıkış anı] içine düşen her 00:00/08:00/16:00 UTC anı için nominalin %0,01'i maliyet
  (yönden bağımsız). Dolum veya çıkış tam funding anına denk gelirse (ör. 08:00 açılışında
  dolum, 00:00'da = 23:45 kapanışında çıkış) o funding **ödenir** (muhafazakâr yön).
  **Sınırlama:** gerçek funding oranları ve aralıkları değişkendir (borsa değiştirebilir,
  %0,01'in üstüne çıkabilir); sabit model üst sınır değildir.

## 6. Kanıt planı (örneklem gereksinimi ile fizibilite AYRI)

**6a. Gerekli kanıt (sonuçtan bağımsız):**
- İstatistik serisi [KURAL]: dönemin **tüm UTC günleri** (işlemsiz günler 0 dahil) için
  r_d = o gün **kapanan** işlemlerin net PnL toplamı ÷ başlangıç bakiyesi (10.000 $).
- Test: ortalama(r) > 0 ve **Newey–West (HAC)** standart hatasıyla t = ortalama / SE > 2.
  Çekirdek Bartlett; gecikme L = floor(4 × (T/100)^(2/9)) (T = gün sayısı; in-sample
  ~1461 gün → L = 7); sabit, sonuç görülmeden. SE = 0 veya tanımsızsa → **KALDI**.
- **Asgari işlem sayısı = kapsam kararı, güç garantisi DEĞİL [KURAL]:** işlem kapısı
  **≥ 1.300**, stratejinin tasarlandığı gibi çalıştığını ve yeterli olay kapsadığını
  göstermek için konan bir asgari kapsam kararıdır.
  *Referans hesap (yalnız büyüklük fikri):* işlem başına net +0,10R asgari etki, işlem
  getirisi standart sapması ~1,3R (varsayım), tek yönlü %2,5 anlamlılık, %80 güç ve
  **bağımsız işlemler** varsayımıyla n ≈ ((1,96 + 0,84) × 1,3 / 0,10)² ≈ 1.325.
  İşlemler korelasyonlu olduğundan (aynı gün aynı yönde kırılan coinler) etkin örneklem
  ham sayıdan küçüktür; bu nedenle 1.300 işlem bu gücü **sağlamaz** ve öyle sunulmaz.
- **Kanıt ölçütü günlük HAC testidir** ve %80 gücü otomatik sağlamaz; güç, gerçek
  korelasyon ve oynaklığa bağlıdır. İşlem başına R varsayımı günlük seriye şöyle taşınır:
  %1 risk ve değişen bakiyeyle her işlemin USD sonucu ≈ R × %1 × bakiye_t; r_d bunların
  günlük toplamının 10.000 $'a oranıdır. Bakiye değiştikçe aynı R farklı USD üretir; bu,
  testi R serisiyle birebir eşdeğer yapmaz. R cinsinden günlük toplam seri **bilgi
  amaçlı** ayrıca raporlanır; kapı, yukarıdaki r_d serisidir.

**6b. Fizibilite (gerçek veriye bakmadan, kod PR'ında):**
- Sentetik 15m veri üzerinde, yazılı varsayımlarla (oynaklık rejimleri, trend/yatay
  dönemler, kalın kuyruklar, semboller arası korelasyon ρ ∈ {0,5; 0,8}) 48 aylık in-sample
  için işlem sayısı **aralığı** tahmin edilir.
- Tahminin alt ucu 1.300'ün altındaysa koşu **başlamaz**; kural sonuç görülmeden yeni
  ön-kayıtla değiştirilir (frekansı artırmak için coin/risk eklenmez).
- "Ayda 40–75" Burak'ın **portföy toplamı** hedefidir; tasarım hedefidir, kapı değildir.
  Gerçek sonucun bu aralık dışında kalması tek başına ret sebebi değildir; ret sebepleri
  yalnız §7'deki kapılardır.

## 7. Kapılar

**In-sample (2021–2024), portföy, maliyetler dahil — hepsi:**
- PF (net) **> 1,3** (AGENTS.md ile aynı; düşürülmedi)
- işlem sayısı **≥ 1.300** (§6a)
- günlük seri ortalaması > 0 **ve** HAC t > 2 (§6a)
- max DD (15m MTM equity) **< %30 [SAPMA — Z1]**
- sermaye tükenmedi

**Hold-out (2025-01-01 → ortak bitiş) — hepsi:** PF > 1,15 (AGENTS.md/V2 ile aynı);
günlük seri ortalaması > 0; max DD < %30; sermaye tükenmedi. (Hold-out ~22 ay; HAC t
raporlanır ama kapı değildir — kısa dönemde güç düşük.)

**Z1 = %30 [SAPMA]:** AGENTS.md DD < %15 diyor. Burak'ın kararı: küçük test hesabını
kaybetmeyi göze alıyor ve işlem başına %1 risk (Z2) seçti; %1 riskte ~30 ardışık kayıp ≈
%26 düşüş. Bu sapma DD kapısını gevşetir; açıkça kayda geçer.

KALDI → V3 REDDEDİLDİ, parametre değiştirilmez. GEÇTİ → yalnız `docs/V3_DOGRULAMA_PLANI.md`
aşamaları açılır (o plan ayrıca onaylanmadıkça hiçbiri başlamaz).

## 8. Burak'ın kararları

| # | Konu | Karar |
|---|---|---|
| Z1 | DD sınırı (test ve canlı) | **%30** (2 Kasım 2026) — [SAPMA] |
| Z2 | İşlem başına risk (test ve canlı) | **%1** (2 Kasım 2026) — [SAPMA] |

## 9. Sıradaki adımlar (her biri ayrı PR + ChatGPT denetimi + Burak onayı)

1. Bu taslak ve `docs/V3_DOGRULAMA_PLANI.md` denetimi.
2. Kod: strateji + çok sembollü 15m motor + sentetik fizibilite raporu (gerçek veri yok).
3. Veri: 5 sembol 15m perp indirme + sağlık raporu.
4. Tek atış koşucusu ve in-sample tek atış.
