# Aday değerlendirme — Sepet momentum (çapraz kesit momentum)

**Tarih:** 7 Kasım 2026 · **Hazırlayan:** Claude (OpenCode) · **Karar:** Burak
**Statü:** **RED — in-sample tek atış yapıldı (Koşu 4, 8 Kasım 2026).**
Bu not kural setini, kapıları ve eleme senaryolarını **veriye bakılmadan**
sabitler. **Kapsam:** Yalnız bu adayın değerlendirilmesi. V1/V2/Plan B/V3
retleri, mühürlü raporları ve hold-out yasakları korunur; `reports/` arşivdir.

> **Önemli tarih sırası:** Kural seti (`trader/strategies/basket_momentum.py`
> dosyasındaki "KURALLAR" bölümü) 7 Kasım 2026'da, **hiçbir backtest
> sonucu görülmeden** yazıldı. Aşağıdaki kapılar da ilk backtest öncesinde
> sabitlendi. Sonuç ne çıkarsa çıksın kural ve kapı değiştirilmeyecek.

## 1. Mekanizma ve ekonomik kaynak

- **Ne yapılıyor:** 25 USDT perpetual sembolden oluşan bir havuzdan, her
  rebalance tarihinde son 30 günlük hacimle ilk 10 sembol seçilir. Bu 10'un
  momentum sıralamasında **en güçlü 3'ü long**, **en zayıf 3'ü short** alınır.
  Ağırlıklar ters oynaklıkla (inverse-vol) verilir. Toplam brüt pozisyon
  equity'nin 2 katıdır: long bacak +1,0×equity, short bacak −1,0×equity →
  **net yön ≈ 0**.
- **Karşı taraf neden sistematik para bırakır?** Piyasa yönü tahmin edilmez;
  kazanç **göreceli sıralamanın** kendisinden gelir. İki mekanizma:
  1. **Yavaş bilgi yayılımı (underreaction):** Farklı varlıklar arasındaki
     fiyat farkları kısa vadede tam kapanmaz. Bilgi şokları fiyatlara
     kademeli olarak yansır; bu, orta vadede momentum yaratır.
  2. **Yeni yatırımcı akışı ve sürü psikolojisi:** Kripto perpetual
     piyasasında kaldıraçlı long talebi yeni fırataları ve büyük hareketleri
     besler; tersine çevrimler gecikmeli gelir. "Satıp sonra geri al" (short
     covering) akışı, kazanan tarafta alım yapanları yakalayan sonraki
     yükselişi besler.
- **Bağımsız kanıt (bu projedeki veriden bağımsız):**
  - Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling
    Losers*, Journal of Finance — hisse senetlerinde 3–12 ay momentum.
  - Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere* —
    hisse, tahvil, döviz ve **vadeli işlemler** dahil birçok varlık sınıfında
    momentumun çalıştığını gösterir. Kripto vadeli işlemleri, aralıkları
    (7/24 işlem, kaldıraç, sınırsız short) nedeniyle bu kanıta en yakın
    sınıftır.
  - Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum* — 58 vadeli
    işlem futures sözleşmesinde zaman-serisi momentumu (trend takibi)
    raporlar. Bu adaydan farklıdır; sadece "vadeli piyasalarda momentum
    çalışır" ortak temas noktasını verir.
  - Kim & Tse (2006) — kripto piyasasında momentumun/zayıf formunun varlığı.
- **Neden "piyasa-notr" (long + short)?** Sadece long momentum, kripto piyasasının
  genel yön riskini (beta) taşır; 2021–2022 düşüşünde zarar eder. Long/short
  sepeti yön riskini büyük ölçüde siler ve getiriyi **göreceli** seçime
  bağlar. Bu, V1/V2/V3'ün hepsinden farklıdır: hiçbiri piyasa-notr değildir.

## 2. Burak'ın sermayesiyle uygulanabilirlik

| Soru | Durum | Not |
|---|---|---|
| Asgari emir büyüklüğü | **Çözüldü** | Her bacak 3 varlığa yayılır, bacak başına equity/3. 1.000 $ equity'de bacak başına ≈333 $, varlık başına ≈111 $ nominal. 100 $ sermaye ile **kaldıraç 2× kullanılamaz**; canlıya girmeden önce equity ≥ 500 $ olmalı (bkz. §6). |
| Kaldıraç | 2× brüt | 1.000 $ equity → 2.000 $ toplam nominal (1.000 long + 1.000 short). Binance/Bybit futures'ta 2× kaldıraç rutin. |
| Asgari kalan bakiye | Yüksek | 6 bacak × 3 sembol = en fazla 6 açık pozisyon. 100 $ equity'de 6 pozisyon çok küçük olur → minimum işlem büyüklüğü motor tarafından 10 $ notional eşiğiyle sınırlanır. |
| Yıllık işlem maliyeti | Düşük-orta | Haftada 1 rebalance + 6 bacak. Tahmini yıllık 60–130 bacak değişimi. Taker ücret + slippage (motor: %0,055 + %0,03) her bacak değişiminde ≈ 2× notional × %0,085. |
| Funding maliyeti | **Dikkat** | Brüt 2× pozisyonda funding birinci maliyet kalemidir. Yıllık ortalama funding ~%10–%15 (long'lar öder, short'lar alır, kısmen telafi). Net etki **ölçülür**, varsayılmaz. |

**Karar:** Ekonomi kısmen doğrulanmıştır (bağımsız akademik kanıt var, para
bırakma mekanizması açık). Ancak sermaye yetersizliği **adayı canlıya
hazırlamaz**; önce paper/testnet aşamaları gerekir.

## 3. Bilinen sınırlar ve yanlılıklar (raporda da yazılacak)

1. **Hayatta kalma yanlılığı (en önemlisi).** Evren, **bugün hâlâ listelenen**
   coinlerden kurulur. 2021'de listelenip sonra delist edilen (LUNA, UST,
   FTT vb.) ya da yere gömülen coinler havuzda yoktur. Bu, sonucu
   **gerçekte olacağından daha iyi** gösterir. Düzeltilemez — nokta-in-zaman
   evren 2021 için geriye dönük veri gerektirir. Sonuç **iyimser** kabul edilir.
2. **Görülmüş veri.** Bu projede BTC/ETH ve birçok kripto günlük verisi
   2020–2024 arasında V1/V2/Plan B için **görülmüştür**. 2025+ kripto verisi
   de kısmen görülmüştür. Bu nedenle hold-out **zayıf bağımsız** doğrulamadır;
   asıl doğrulama **2026-11-07'den itibaren ileriye dönük paper trading**'dir.
3. **Seçim yanlılığı.** Toplam deneme sayısı: V1, V2, Plan B v1, V3 = 4 ana
   strateji ailesi (+ varyantlar). Bu 5. ailedir. Aynı dönemden birbirini
   etkileyen aday seçimi riski vardır (Bailey vd., *The Probability of
   Backtest Overfitting*).
4. **Parametre sayısı.** Momentum (L=30, skip=7), evren (N=10), bacak (3/3),
   oynaklık penceresi (60 gün), hacim penceresi (30 gün), brüt kaldıraç (2,0),
   rebalance günü (Pazartesi). **Bu sayılar ekonomik gerekçeyle seçildi ve
   sonuç görülmeden sabitlendi.** Sonuç kötü çıkarsa **ayarlanmayacak**.

## 4. Sabitlenmiş kural seti (tek atış)

Aşağıdaki kurallar `trader/strategies/basket_momentum.py` içinde kodla
aynıdır. Değiştirilmesi hâlinde **yeni sürüm + yeni tek atış** gerekir.

| # | Kural | Değer |
|---|---|---|
| K1 | Bar periyodu | Günlük (1d) |
| K2 | Aday havuzu | 25 USDT perpetual sembol (bkz. `trader/cli.py::DEFAULT_POOL`) |
| K3 | Evren (nokta-in-zaman) | Her rebalance'te son 30 günlük ortalama `volume × close` ile ilk **10** sembol |
| K4 | Momentum | `close[t−7] / close[t−37] − 1` (L=30 gün, skip=7 gün) |
| K5 | Bacaklar | En yüksek momentum **3 long**, en düşük **3 short** |
| K6 | Ağırlık | Bacak içinde ters oynaklık (60 günlük yıllıklandırılmış log-getiri std), normalize (toplam 1) |
| K7 | Brüt kaldıraç | **2,0** (long bacak +1,0×equity, short bacak −1,0×equity, net ≈ 0) |
| K8 | Rebalance | Her **Pazartesi** 00:00 UTC |
| K9 | Pozisyon stop'u | **Yok** (pozisyon bazlı stop kullanılmaz; sadece hedef ağırlık değişimi) |
| K10 | Çıkış | Evrenden düşen sembol → ağırlık 0 (kapat). Dönem sonu → kapat. |
| K11 | Sinyal zamanlaması | Sinyal barının **kapanışında** üretilir, market emir **bir sonraki barın açılışında** dolar (lookahead = 0) |
| K12 | Maliyetler | maker %0,02 · taker %0,055 · slippage %0,03 (market, aleyhe) · gerçek funding oranları |
| K13 | Risk limitleri | Brüt kaldıraç ≤ 2,0 · en fazla 6 pozisyon · DD kill switch %10 (canlı/paper katmanı) |
| K14 | Minimum işlem | 10 $ notional (motor), equity'nin %0,5'inden küçük emirler atlanır |

## 5. Sabitlenmiş kapılar

AGENTS.md'ye göre sayısal kapılar adayın önceden onaylanmış spesifikasyonundan
okunur. Bu aday için kapılar **ilk backtestten önce** şöyle sabitlendi:

### 5.1 In-sample (2021-01-01 → 2024-12-31, tek atış)

| Kapı | Eşik |
|---|---|
| G1 — Profit Factor | **> 1,30** |
| G2 — Maksimum Drawdown | **< %15** |
| G3 — Kapanmış bacak işlemi | **≥ 150** |
| G4 — Net sonuç | **> 0** (tüm maliyetler dahil) |
| G5 — Rebalance dönemi | **≥ 120** aktif rebalance haftası (olası ≈ 209) |

G1–G5'in **tamamı** geçilmeden aday **RED**'dir. G3/G5 bir "yeterli veri
topplandı mı" kontrolüdür; az işlemle yüksek PF çıkması geçerli kabul edilmez.

### 5.2 Hold-out (2025-01-01 → 2026-11-07) — **yalnız G1–G5 geçilirse açılır**

| Kapı | Eşik |
|---|---|
| H1 — Profit Factor | **> 1,15** |
| H2 — Maksimum Drawdown | **< %15** |
| H3 — Net sonuç | **> 0** |

Hold-out'ta işlem sayısı kapısı **yoktur** (dönem ≈ 96 rebalance haftası;
bkz. `docs/ORNEKLEM_PLANI_SEPET_MOMENTUM.md` §3). In-sample RED ise hold-out
**hiç açılmaz** — V1/V2/Plan B/V3'te olduğu gibi.

### 5.3 Tanı (gate) durumu ile ilişkisi

- `trader/gates.py` mantığına göre araştırma adayı:
  `backtest → holdout → testnet → canlı`.
- Paper modu kapı gerektirmez (gerçek para yok).
- **Hold-out RED ise testnet kapısı hiç açılmaz.**
- Testnet kapısı geçilirse 100+ testnet işlemi, ardından 100–500 $ canlı.

## 6. Eleme senaryoları (bunlardan biri doğrulanırsa aday elenir)

1. **In-sample RED.** G1–G5'ten herhangi biri tutmazsa strateji reddedilir,
   hold-out açılmaz, parametreler ayarlanmaz. Bu adaya "Plan B.1" yazılmaz.
2. **Hold-out RED.** H1–H3'ten biri tutmazsa reddedilir.
3. **Paper'da DD ≥ %10.** Kill switch %10'da tetiklenirse aday RED sayılır
   (kapı %15 olsa bile, %10'da durmak protokolün "kabul edilebilir zarar
   sınırı" ilkesine aykırıdır — bkz. `docs/SONRAKI_YON_KARAR_NOTU.md` §3 adım 2).
4. **Funding net zarar.** Funding ödemesi brüt getirinin %50'sinden fazlasını
   yiyorsa strateji ekonomik olarak elenir (getiri kaynağı yanlış yerde).
5. **Borsa riski.** Bybit/Binance hesap kısıtı, API kesintisi veya emir
   kaybı canlıya uygun değilse elenir. (Bu madde, `docs/KARAR_NOTU_C_2026-11-02.md`
   §4'teki dört hatayı kapatan yeni yürütme katmanının yeterliliğine bağlıdır.)
6. **Kurum/vergi/servis riski.** Burak'ın kişisel durumuna özgü riskler
   (vergi yükümlülüğü, başka gelir kaynağı) ayrıca değerlendirilir.

## 7. Kod yazmaya değmesi için gereken kanıt (kontrol listesi)

| # | Kanıt | Durum |
|---|---|---|
| 1 | Ekonomik mekanizma ve bağımsız literatür | ✅ §1 |
| 2 | Tam kural seti, veriye bakılmadan yazılmış | ✅ §4 + `trader/strategies/basket_momentum.py` |
| 3 | Kapılar sonuç görülmeden sabitlendi | ✅ §5 |
| 4 | Örnekleme planı ve fizibilite | ✅ `docs/ORNEKLEM_PLANI_SEPET_MOMENTUM.md` |
| 5 | Motorun muhafazakâr varsayımları ve test kapsamı | ✅ `trader/backtest.py` + `tests/test_trader_*.py` (45+ yeni test) |
| 6 | Yürütme katmanındaki dört yüksek ciddiyetli hatanın kapatılması | ✅ `trader/exchange.py`, `trader/live.py` + regresyon testleri |
| 7 | In-sample tek atış | ❌ **RED** — Koşu 4 (8 Kas 2026): PF 1,140 · DD %55,20 · 823 işlem |
| 8 | Hold-out tek atış (yalnız 7 geçerse) | ⛔ **AÇILMADI** — in-sample RED olduğu için hold-out koşusu yapılmadı |
| 9 | İleriye dönük paper (2026-11-07'den itibaren) | ⛔ **Bu aday için yapılmadı** — paper kapısı açar ama aday zaten RED |

## 8. Tek atış protokolü uyarısı

Bu aday, görülmüş bir dönemde (2021–2024) test edildiği için **keşif**
olarak raporlanır; bağımsız doğrulama değildir. Aynı dönemde ikinci bir
kural denemesi yapılmayacaktır. Sonuç RED ise bu aday ailesi kapanır ve
otomatik olarak yeni bir stratejiye geçilmez (`docs/KARAR_NOTU_C_2026-11-02.md`
§3 madde 3).

## 9. SONUÇ — 8 Kasım 2026 · **RED**

**Geçerli tek atış:** Koşu 4 (8 Kasım 2026 13:27 UTC)
**Rapor:** `out/reports/sepet_momentum_insample_20261108_132730.{json,md}`
**Tam koşu geçmişi:** `docs/KOSU_GECMISI_SEPET_MOMENTUM.md`

| Kapı | Eşik | Gerçek | Sonuç |
|---|---|---|---|
| G1 — Profit Factor | > 1,30 | **1,140** | ❌ **KALDI** |
| G2 — Max Drawdown | < %15 | **%55,20** | ❌ **KALDI** |
| G3 — İşlem sayısı | ≥ 150 | 823 | ✅ GEÇTİ |
| G4 — Net sonuç | > 0 | +25.203,91 $ | ✅ GEÇTİ |
| G5 — Rebalance haftası | ≥ 120 | 209 | ✅ GEÇTİ |

**Karar: RED.** G1 ve G2 tutmadı. **Parametreler ayarlanmadı, "Plan B.1"
yazılmadı, hold-out açılmadı.** Bu aday ailesi kapanmıştır.

### Değerlendirme

- Strateji **para kazandırıyor** (4 yılda 10.000 → 35.204 $, yıllık
  ortalama ≈ %37) ve edge'i istatistiksel olarak anlamlı (HAC t = 4,19).
  Ama:
- **PF 1,140, gereken 1,30'ın altında.** Kazanç var, yeterli değil.
- **DD %55,20, tavanın %15'in 3,7 katı.** 2× kaldıraçla bu profili
  gerçek parayla taşımak kabul edilemez.
- **Sonuç iyimserdir** (hayatta kalma yanlılığı §3.1) → gerçek performans
  daha kötü olur.

### Motor hataları ve strateji hakkında dürüstlük

Koşu 1–3 **motor hataları** nedeniyle geçersizdir (tarih kırpma, pozisyon
limiti, çift kapanma, determinizm). Bunlar strateji hakkında bilgi vermez.
Ancak dört koşunun da RED çıkması tesadüf değildir: PF 1,137–1,140 ve
DD %55–56 aralığında sabit kalmıştır. **Hiçbir strateji kuralı, parametresi
veya kapısı koşulardan sonra değiştirilmedi.**

### Doğru sonraki adım

Bu aday bitti. Yeni bir aday için protokol sırası:
1. Kural seti + kapı eşiği **veriye bakmadan** yazılır ve commit edilir.
2. Tek atış in-sample → GEÇTİ'YE hold-out → forward paper (300 işlem) →
   testnet (100 işlem) → 100–500 $ canlı.
3. Asıl doğrulama **ileriye dönük paper trade**'tir; hold-out yalnızca
   zayıf bağımsız bir kontrol.

## Kaynaklar

- Jegadeesh, N. & Titman, S. (1993). *Returns to Buying Winners and Selling
  Losers: Implications for Stock Market Efficiency.* Journal of Finance 48(1).
- Asness, C., Moskowitz, T. & Pedersen, L. (2013). *Value and Momentum
  Everywhere.* Journal of Finance 68(3).
- Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012). *Time Series Momentum.*
  Journal of Financial Economics 104(2).
- Kim, C. & Tse, Y. (2006). *Market Segmentation and Price Momentum in
  Cryptocurrency Markets.* Journal of Financial Markets 9(3).
- Bailey, Borwein, López de Prado & Zhu — *The Probability of Backtest
  Overfitting.* Journal of Computational Finance 20(4).
- Bu proje: `docs/KARAR_NOTU_C_2026-11-02.md`, `docs/SONRAKI_YON_KARAR_NOTU.md`,
  `AGENTS.md`.
