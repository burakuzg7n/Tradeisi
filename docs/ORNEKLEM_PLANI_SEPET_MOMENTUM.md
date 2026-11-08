# Örnekleme planı — Sepet momentum

**Tarih:** 7 Kasım 2026 · **Hazırlayan:** Claude (OpenCode)
**Bağlı not:** `docs/ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md`
**Yöntem:** `docs/SONRAKI_YON_KARAR_NOTU.md` §3, adım 1–7.

> Bu plan **hiçbir backtest çalıştırılmadan** yazıldı. Buradaki tahminler
> kural mekaniğinden ve sentetik varsayımlardan çıkarıldı; gerçek P&L'ye
> bakılarak düzeltilmedi ve düzeltilmeyecek.

## 1. Ölçülmek istenen soru

**Soru:** "Bu sepet stratejisi, tüm maliyetler (taker ücret, slippage,
funding) sonrası **işlem başına pozitif beklenti** taşıyor mu, ve bu
beklenti kripto piyasasının genel yönünden (beta) bağımsız mı?"

**Birincil ölçüt:** Kapanmış bacak işlemlerinin net P&L'i (PF, expectancy).
**İkincil ölçüt:** Equity eğrisinin maksimum drawdown'u.
**Yan ölçütler:** Yıllık getiri, Sharpe/HAC-t, funding net, işlem sayısı.

## 2. Kabul edilebilir zarar sınırı (ÖNCE konur)

- Protokol DD kapısı: **< %15** (AGENTS.md, tüm sürümlere ortak).
- Canlı/paper risk katmanı: **%10 kill switch** (pozisyon büyütme durur).
- Burak'ın canlı sermayesi 100–500 $ bandında. %10 DD = 10–50 $ gerçek
  kayıp. Bu, "kabul edilebilir zarar" eşiği olarak **canlı öncesi**
  ayrıca Burak'ın onayına sunulur.
- **DD eşiği bir simülasyonun DD'sine göre seçilmez.** Eşik protokolde
  sabittir; simülasyon ona göre değerlendirilir.

## 3. İşlem sıklığı tahmini (sonuçlardan bağımsız)

### 3.1 Kural mekaniğinden kesin olan kısım

| Kalem | Değer |
|---|---|
| Rebample sıklığı | Haftada 1 (Pazartesi) |
| In-sample takvim | 2021-01-01 → 2024-12-31 = 1.461 gün = **209 Pazartesi** |
| Hold-out takvim | 2025-01-01 → 2026-11-07 = 676 gün = **96 Pazartesi** |
| Bacak sayısı | 6 (3 long + 3 short) |
| Evren | 10 sembol (4'ü sepet dışı, ağırlık 0) |

### 3.2 Değişim sıklığı için **aralık** (tek sayı değil)

Momentum sıralaması haftalık olarak "yapışkan"dır (bir coin 30 günlük
güçlü momentumunu bir haftada kaybetmez), ama günlük oynaklık sırayı
değiştirebilir. Kural mekaniğinden çıkarılan **öncül olasılık**: bir bacak
girdiği hafta içinde **%10–%25** olasılıkla evrenden çıkar.

- Haftalık beklenen bacak değişimi = 6 bacak × %10–%25 = **0,6–1,5 değişim**
- Yani **haftada ~1 bacak** değişimi (merkez değer), aralık **0,5–2,0**.

Bu, veriye bakmadan "momentum sıralamasının haftalık kalıcılığı" varsayımına
dayanır. Gerçek veriye bakılarak bu aralık **daraltılmayacaktır**.

### 3.3 Beklenen işlem sayısı (aralık)

| Dönem | Rebalance haftası | Beklenen kapanmış bacak işlemi (aralık) | Dönem sonu tasfiyesi |
|---|---|---|---|
| In-sample | 209 | **104 – 418** (merkez ≈ 209) | +6 |
| Hold-out | 96 | **48 – 192** (merkez ≈ 96) | +6 |

### 3.4 Bu tahmin kapılarla tutarlı mı?

- G3 eşiği (in-sample ≥ 150 işlem) **merkez tahminin (209) altında**, ancak
  aralığın içinde. Yani kapı, mekanik olarak **ulaşılabilir** bir eşiktir;
  imkânsız değildir. İşlem sayısı az çıkarsa aday **RED/inconclusive** olur
  (kapı gevşetilmez) — bu, bilinçli bir sonuçtur.
- Hold-out'ta işlem sayısı kapısı **konulmaz**; 48–192 aralığı istatistiksel
  güç için yetersizdir (bkz. §4).

## 4. Gerekli örneklem büyüklüğü (güven düzeyinden)

### 4.1 Etkin örneklem = bacak değil, rebalance dönemi

Bir rebalance haftasındaki 6 bacak **aynı piyasa hareketinden** etkilenir:
aynı gün açılır, aynı hafta kapanır, aynı makro haberine bağlıdır. Bu
gözlemler **bağımsız değildir**. Bailey vd.'nin "effective number of
trials" uyarısı burada doğrudan geçerlidir.

- Ham bacak işlemi: 104–418 (in-sample)
- **Etkin örneklem: rebalance haftası ≈ 209** (in-sample), ≈ 96 (hold-out)

### 4.2 İstatistiksel güç

Varsayım (kural mekaniğinden, veriye bakmadan):
- Haftalık portföy getirisinin yıllık std'ı **%35–%60** (2× brüt kaldıraç,
  6 kripto varlığı, haftalık rebalance; kripto yıllık oynaklığı %60–%120).
  Haftalık std ≈ yıllık / √52 ≈ **%4,9–%8,3**.
- Test edilen asgari etki: yıllık net **%8** getiri (haftada ≈ %0,15).

Bu varsayımla, 209 haftalık gözlemde %8 yıllık etkiyi "anlamlı" sayan
minimum istatistiksel güç **≈ %40–55** aralığındadır. Yani:

> **In-sample tek atış, %8 yıllık etkiyi %95 güvenle kanıtlamak için
> YETERLİ DEĞİLDİR.** Bu bilinçli olarak kabul edilmiştir; çünkü protokol
> tek atışı ve sabit kapıları zorunlu kılar. In-sample sonucu bir **tarama**
> (keşif) sonucudur, kesin kanıt değil.

### 4.3 Hold-out gücü daha da zayıf

96 haftalık gözlemde etkin örneklem küçüktür. Hold-out **"çelişki yok"
kontrolüdür**, güçlü bir istatistiksel test değil. Bu yüzden hold-out
kapıları (H1–H3) bilinçli olarak in-sample kapılarından **daha gevşektir**
(PF 1,15) ve **işlem sayısı kapısı içermez**.

### 4.4 Asıl doğrulama: ileriye dönük paper

Bağımsız doğrulama yalnız **hiç görülmemiş gelecek verisiyle** mümkündür.
Bu adayın asıl doğrulaması **2026-11-07'den itibaren ileriye dönük paper
trading**'dir. Beklenen süre:

| Aşama | Protokol hedefi | Bu strateji ailesinde beklenen süre |
|---|---|---|
| Paper | 300 işlem | ≈ **5–6 yıl** (yılda ~50–130 bacak işlemi) |
| Testnet | 100 işlem | ≈ **1–2 yıl** |

### 4.5 Bu bulgunun dürüst yorumu

AGENTS.md'deki "300 paper → 100 testnet" sayıları, günlük 15 dakikalık
barlarda üreten stratejiler (V2: 490 işlem / 5 yıl) için yazılmıştır.
Haftada bir kez rebalance eden bir portföy stratejisinde **300 işlem 5–6 yıl
sürer**. Bu:

- Protokolü **değiştirmez** (eşikler sabittir).
- Adayın reddi için tek başına gerekçe **değildir**.
- Ama **Burak'ın beklentisini yönetmek için** burada yazılır: bu aday
  ancak uzun vadeli bir sözleşmeye razıysa anlamlıdır. Eğer Burak "6 ayda
  sonuç" beklentisiyle bu programa girdiyse, beklenti yazıya geçirilmelidir.

## 5. Risk fizibilitesi (senaryo tabanlı)

Brüt 2,0 kaldıraç, net ≈ 0, 6 bacak, bacak başına ≈ 1/3 × equity notional.
Senaryolar (varsayım, ölçüm değil):

| Senaryo | Long bacak | Short bacak | Net etki (equity) |
|---|---|---|---|
| Genel piyasa −%30 (kripto çöküşü) | −%30 → −0,30 | +%30 → +0,30 | ≈ **0** (betasız) |
| Sadece altcoinler −%50, BTC −%10 | long bacak altcoin ağırlıklı: −0,35 | short bacak da altcoin: +0,25 | ≈ **−0,10 → DD %10** |
| Tek bir short leg coin +%100 (short squeeze) | 0 | short bacakın 1/3'ü: −0,33 | ≈ **−%33** tek bacak kaybı |
| Tek bir long leg coin −%70 (rug/olay) | long bacakın 1/3'ü: −0,23 | 0 | ≈ **−%23** |

**Sonuç:** Piyasa-notr yapı **genel yön riskini** kaldırır ama **tek varlık
olay riskini** kaldırmaz. %15 DD kapısı bu yapıda ulaşılabilir bir eşiktir,
ama tek bir uçuk coin %20–30'luk tek hamle DD üretebilir. Bu nedenle:

- Evren hacimle sınırlandırılır (likit coinler) — bu, olay riskini azaltır
  ama tamamen kaldırmaz.
- Canlıda %10 kill switch zorunludur.
- Bir short legin %100 yükselmesi senaryosu, **canlı öncesi Burak'ın
  kabul etmesi gereken bir risk** olarak dokümana yazılır.

## 6. Fizibilite kontrolünün kaydı

| Adım | Sonuç |
|---|---|
| 1. Soru | §1'de yazıldı |
| 2. Zarar sınırı | %15 protokol / %10 canlı kill switch — §2 |
| 3. Sıklık tahmini (aralık) | §3 — in-sample 104–418 bacak işlemi |
| 4. Gerekli örneklem | §4 — in-sample gücü yetersiz, asıl doğrulama ileri paper |
| 5. Risk senaryoları | §5 |
| 6. Kayıt | Bu belge (backtest öncesi) |
| 7. Veri ayrımı | §7 |

**Karar:** Tasarım, kabul edilebilir zarar sınırı altında **uygulanabilir**
görünüyor; ancak in-sample tek atışının istatistiksel gücü düşüktür ve
doğrulama yükü ileriye dönük paper'a düşer. Bu, protokolün
`docs/SONRAKI_YON_KARAR_NOTU.md` §3 adım 6'sı gereği **koşu başlamadan**
kayda geçti.

## 7. Veri ayrımı

| Dönem | Rol | Durum |
|---|---|---|
| 2021-01-01 → 2024-12-31 | **In-sample (keşif)** | Bu projede **görülmüş** (V1/V2/Plan B daily verisi). Tek atış. |
| 2025-01-01 → 2026-11-07 | **Hold-out (zayıf doğrulama)** | Kısmen görülmüş. **Yalnız in-sample geçerse açılır.** |
| 2026-11-07 → ileri | **Asıl doğrulama (ileri paper)** | **Hiç görülmemiş.** En güçlü kanıt. |

**Evren yanlılığı:** Aday havuzu bugün listelenen coinlerden kurulur
(`DEFAULT_POOL`, 25 sembol). Delist edilen coinler kapsam dışıdır →
**hayatta kalma yanlılığı** sonucu **iyimser** yapar. Bu, raporda açıkça
yazılır ve **düzeltilemez** (nokta-in-zaman evren 2021 için geriye dönük
sembol listesi gerektirir).

**Maliyet duyarlılığı (tanı, kapı değil):** Slippage iki katına çıkarılarak
tek bir ek koşu yapılacak ve raporda "maliyet duyarlılığı" olarak
gösterilecektir. Bu koşu **kapı değildir** ve sonucu ne olursa olsun
**hiçbir parametre değiştirilmeyecektir**. (Tanı, ilk in-sample sonucu
görüldükten **sonra** çalıştırılır; protokol gereği bir kez.)

## 8. Bağlı dosyalar

- `docs/ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md` — kurallar ve kapılar
- `trader/strategies/basket_momentum.py` — kural setinin kodu
- `trader/backtest.py` — motor (muhafazakâr varsayımlar)
- `out/reports/` — backtest raporları (koşu çıktıları)
- `out/gates.json` — kapı kayıtları (denetim izi)
