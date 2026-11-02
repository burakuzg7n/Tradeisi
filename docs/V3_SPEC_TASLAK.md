# V3 — Seans kırılımı (gün içi) · ÖN-KAYIT TASLAĞI

**Tarih:** 2 Kasım 2026 · **Karar veren:** Burak · **Hazırlayan:** Claude · **Denetim:** ChatGPT
**Statü:** TASLAK. Hiçbir V3 verisi indirilmeden ve hiçbir V3 sonucu görülmeden yazıldı.
Bu belge onaylanıp birleştirilene kadar kod yazılmaz, veri indirilmez.

## 0. Çerçeve

- Burak'ın kararları (2 Kasım 2026): gün içi, **ayda 40–75 işlem** üretebilecek bir sistem;
  mantık: **seans kırılımı**; gerçek paradan önce **projede hiç bakılmamış coinlerde tek atış
  test**. Burak işlem başına risk almayı kabul ediyor; teste ayıracağı gerçek para 200–300 $.
- V1, V2, Plan B v1 reddedildi; bu kararlar değişmez. V3 bunların düzeltmesi veya telafisi
  değildir; ayrı bir hipotezdir. Kazanç garantisi yoktur; V3'ün de reddedilmesi geçerli
  bir sonuçtur.
- Planlama yöntemi: `docs/SONRAKI_YON_KARAR_NOTU.md` §3 (önce zarar sınırı; sıklık ve
  örneklem fizibilitesi gerçek PnL'ye bakmadan; veri ayrımı önceden).

## 1. Hipotez (tek cümle)

Kripto perp piyasasında Asya seansı (00:00–07:00 UTC) aralığının, Londra/New York
saatlerinde günlük trend yönünde kırılması, maliyetler dahil pozitif net beklentili
gün içi hareket başlatır.

## 2. Veri ayrımı (bağımsızlık)

- **Evren:** XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT, LINKUSDT — Binance USDⓈ-M PERPETUAL.
  Bu beş sembolün hiçbir zaman dilimindeki verisi bu projede **indirilmemiş ve
  incelenmemiştir** (2 Kasım 2026 itibarıyla `data/` içinde yok). BTC/ETH/SOL/BNB
  kullanılmaz (V1/V2/Plan B'de görüldüler).
- **Zaman dilimi:** 15 dakika (işlem) + 1 gün (trend filtresi; 15m'den UTC günlerine
  toplanır, ayrı dosya kullanılmaz).
- **In-sample:** 2021-01-01 → 2024-12-31. **Hold-out:** 2025-01-01 → verideki son tam gün.
  Hold-out'a in-sample kararı verilmeden bakılmaz.
- **Bilinen sınırlama:** coinler birbirleriyle ve BTC ile yüksek korelasyonludur; "hiç
  bakılmamış" olmaları, piyasa rejimlerinin (2021 boğa, 2022 ayı vb.) bilinmediği
  anlamına gelmez. Bu genel piyasa bilgisi kuralı seçerken kullanılmamıştır.

## 3. Kurallar (her sembol, her UTC günü)

1. **Asya aralığı:** 00:00–06:45 UTC açılışlı 28 adet 15m mumun en yüksek HIGH (AH) ve en
   düşük LOW (AL) değeri. Mumlardan biri eksikse o gün o sembolde işlem yok.
2. **Trend filtresi:** dünkü günlük kapanış > dünkü günlük kapanışın 20 günlük basit
   ortalaması ise yalnız LONG; < ise yalnız SHORT; eşitse veya 20 gün yoksa işlem yok.
   (Yalnız dünün ve öncesinin verisi; bugünün hiçbir değeri kullanılmaz.)
3. **Tetik penceresi:** 07:00–19:45 UTC açılışlı 15m mumlar.
   - LONG: pencere içindeki **ilk** mum kapanışı > AH.
   - SHORT: pencere içindeki **ilk** mum kapanışı < AL.
   - Sembol başına günde **en fazla 1 işlem** (ilk tetik). Tetik mumu sonrası yeni tetik yok.
4. **Giriş:** tetik mumunun bir **sonraki** 15m mumunun açılışında market (taker + aleyhe
   slippage).
5. **Stop:** Asya aralığının orta noktası M = (AH + AL) / 2. Stop-market (taker).
   - **Asgari stop mesafesi:** |giriş − M| / giriş < %1,0 ise işlem **yapılmaz** (maliyet
     kısıtı: gidiş-dönüş maliyeti ≈ %0,17 → ≤ ~0,17R; optimizasyon değildir).
   - LONG'da M ≥ giriş veya SHORT'ta M ≤ giriş ise (açılış orta noktanın ötesinde) işlem yok.
6. **Hedef:** giriş ± 2 × |giriş − M| (limit, maker).
7. **Zaman çıkışı:** pozisyon 23:45 UTC açılışlı mumun kapanışında hâlâ açıksa market ile
   kapanır (taker + slippage). Gece pozisyon taşınmaz.
8. **Aynı mumda stop ve hedef:** stop (muhafazakâr, motor kuralı). Gap: açılış stopun
   ötesindeyse açılıştan (motor kuralı).

## 4. Hesap ve maliyet

- **Tek ortak hesap**, başlangıç 10.000 $ (test ölçeği; canlıda Burak'ın tutarı).
  İşlem başına risk = açılış öncesi gerçekleşmiş bakiyenin **%0,5**'i; miktar = risk ÷
  |giriş − M|. Sembol başına en fazla 1 açık pozisyon (zaten günde 1 işlem), eşzamanlı
  en fazla 5.
- **Ücret:** taker %0,055 (giriş, stop, zaman çıkışı), maker %0,02 (hedef).
- **Slippage:** %0,03 aleyhe (market giriş, stop, zaman çıkışı) — BTC varsayımının (%0,01)
  3 katı; altcoin likiditesi için muhafazakâr sabit.
- **Funding:** pozisyon 00:00 / 08:00 / 16:00 UTC funding anlarından birini açık geçerse her
  biri için nominalin %0,01'i (yöne bakılmaksızın maliyet; muhafazakâr).

## 5. Fizibilite (gerçek veriye bakmadan — kod PR'ında yapılacak)

- **İşlem sıklığı:** kural mekaniği + açıkça yazılmış varsayımlarla sentetik 15m veri
  (oynaklık düzeyleri, trend/yatay rejimler, kalın kuyruklar, semboller arası korelasyon)
  üzerinde aylık işlem sayısı **aralığı** tahmin edilir. Kaba üst sınır: 5 sembol × ~30 gün
  = ayda en fazla ~150 işlem; trend filtresi, asgari stop ve kırılım olmayan günler bunu
  düşürür. Hedef aralık (ayda 40–75) tahminle uyumsuzsa test **koşulmaz**; kural, sonuç
  görülmeden ve yeni ön-kayıtla değiştirilir.
- **Örneklem planı:** asgari etki, anlamlılık/test gücü, getiri dağılımı ve bağımlılık
  (aynı gün aynı yönde kırılan korelasyonlu coinler tek gözlem gibi davranabilir; analiz
  **günlük toplam PnL** üzerinden yapılır) fizibilite belgesinde yazılır.

## 6. Kapılar (TASLAK — fizibilite ve Burak'ın zarar sınırıyla kesinleşecek)

In-sample (2021–2024), birleşik portföy, maliyetler dahil:
- PF > 1,2 **VE**
- işlem sayısı ≥ [fizibilite tahmininin alt sınırına göre sabitlenecek] **VE**
- günlük net PnL serisinin ortalaması > 0, t-istatistiği > 2 (günlük toplamlarla;
  korelasyonlu işlemler ayrı gözlem sayılmaz) **VE**
- max DD (günlük MTM) < **[BURAK KARARI: Z1]**.

Hold-out (2025+): PF > 1,1 **VE** günlük net PnL ortalaması > 0 **VE** DD < Z1.
Geçerse sıradaki adım: TradingView paneli + küçük canlı test (kayıtlı); kalırsa V3
REDDEDİLDİ, parametre değiştirilmez.

## 7. Burak'ın kararları

| # | Konu | Öneri | Karar |
|---|---|---|---|
| Z1 | Kabul edilebilir en büyük düşüş (test ve canlı için DD sınırı) | %20 (işlem başına %0,5 riskte ~40 ardışık kayıp eşdeğeri) | `[BURAK KARARI]` |
| Z2 | Canlıda işlem başına risk | %0,5 (testle aynı) | `[BURAK KARARI]` |

## 8. Sıradaki adımlar (her biri ayrı PR + ChatGPT denetimi)

1. Bu taslağın denetimi ve Burak onayı (Z1, Z2).
2. Kod: strateji + çok sembollü gün içi motor + sentetik fizibilite raporu (gerçek veri yok);
   işlem sayısı kapısının sabitlenmesi.
3. Veri: 5 sembol 15m perp indirme + sağlık raporu (yalnız sağlık).
4. Tek atış koşucusu (kilit, mühür, parmak izi) ve in-sample tek atış.
