# DEVİR NOTU — Sonraki Asistan İçin (Opus dahil)

Yazan: Claude (Fable 5) · 8 Temmuz 2026 · Kullanıcı: Burak

## 0. GÜNCEL DURUM (3 Kasım 2026) — önce bunu oku

**V1, V2, Plan B v1 ve V3 REDDEDİLDİ.** Retler, eşikler, parametreler ve kilitler
korunur; reddedilen stratejilerin hold-out'u koşulmaz. Aktif aday yoktur.

**Yön C:** aylık yaklaşık 100 $ birikim, gerçek para bağlamadan araştırma;
henüz bulunmamış kâr bütçeye yazılmaz, aylık ikiye katlama hedef/kriter değildir.
Karar: `docs/KARAR_NOTU_C_2026-11-02.md`.
Cash-and-carry değerlendirmesi 3 Kasım'da **kullanıcı tercihiyle sonlandırıldı**;
ekonomik uygulanamazlık kanıtlanmadı, eleme testi tamamlanmadı.
Kayıt: `docs/ADAY_DEGERLENDIRME_CASH_AND_CARRY.md` §8.
C kararı PR #17 (`789aef2`), sonlandırma kaydı PR #18 (`3eaa285`) ile main'e girdi.

**Çalışma düzeni:** ChatGPT araştırma/tasarım/uygulamayı yürütür, Claude bağımsız
denetler, Burak merge ve yeni aday/gerçek veri koşusu kararını verir.
Bu devir yeni strateji, backtest, hold-out, paper, testnet veya canlı koşusu izni değildir.
Yeni aday önce kodsuz değerlendirme notuyla ele alınır; otomatik olarak V4'e geçilmez.

| Strateji | Sonuç ve dönem | Kayıt |
|---|---|---|
| V1 | **RED** — BTC/ETH 2020–2026 değerlendirmeleri; PF yaklaşık 0,78–0,82 | `reports/YILLIK_ANALIZ.md`, `reports/BACKTEST_RAPORU.md` |
| V2 | **KALDI** — in-sample 2020–2024; PF 0,796, işlem 490, DD %22,37 | `reports/V2_INSAMPLE.json/.md/.lock`; sonuç commit'i `52239d7` |
| Plan B v1 | **KALDI** — in-sample 2020–2024; PF 5,93, işlem 37, DD %20,36; E16 geçti | `reports/PLANB_INSAMPLE.json/.md/.lock`; sonuç commit'i `6c5ed47` |
| V3 | **KALDI** — in-sample 2021–2024; PF 0,91254, işlem 3.201, DD %95,39, HAC t −1,36453; sermaye tükenmedi | `reports/V3_INSAMPLE.json/.md/.lock`; sonuç commit'i `4d55f57`; üç ham CSV arşivi |

**Sonuçları okurken:**
- Plan B'nin yıl tablosu kapanan işlemlere göredir; takvim yılı equity getirisi değildir.
  122 kontenjan iptali, 122 bağımsız kaçırılmış fırsat veya iyileştirme kanıtı değildir.
- PF kapanmış işlemlerden, DD açık pozisyonları da içeren equity'den hesaplanır.
  Yüksek PF ile yüksek DD birbiriyle çelişmez.
- V3'ün maliyet ayrıştırması mevcut işlem listesi üzerindedir; komisyonsuz bir
  yeniden koşu veya “maliyetsiz kazanırdı” kanıtı değildir. Sık işlemin genel olarak
  kazandırmayacağı sonucu çıkarılamaz. Ayrıntı: `reports/V3_INSAMPLE_INCELEME.md`.
- Yeni adayda fizibilite ve örneklem planı sonuç görülmeden hazırlanır. Eski kapılar
  geriye dönük değiştirilmez; yöntem: `docs/SONRAKI_YON_KARAR_NOTU.md` §3.

**Denetimin kapsamı ve sınırları:**
Önceki PR denetimleri ve geçen testler hatasızlık veya canlı işlem güvenliği garantisi
değildir. V1/V2/Plan B için tam işlem/equity arşivlerinin yokluğu bağımsız yeniden
hesabı sınırlar. V2'nin veri kaynağı spot API'dir. V3'ün işlem, günlük seri ve 15m
equity arşivleri mevcuttur; arşivden yeniden hesap inceleme raporunda kayıtlıdır.
Arşiv hash'leri değerlendirilirken kayıtlı CRLF/LF farkı dikkate alınır; arşivler değiştirilmez.
Eski canlı katman gerçek parayla kullanılmaz; kayıtlı dört bulgu için C karar notu §4'e bak.

**Tarihsel bölümler:** aşağıdaki eski seçenekler ve örnekler yeni görev/koşu izni değildir.
§8 ve §9 bağlayıcı tarihsel strateji metinleri olarak aynen korunur; içlerindeki uygulama
talimatları tamamlanmıştır. Sonuç sonrası yeniden uygulama/koşu başlatılmaz.

## 1. Projenin özeti

Depoda dört reddedilmiş stratejinin kodu, motorlar, veri sağlık kontrolleri,
tek atış protokolleri ve sonuç arşivleri bulunur. Gerçek parayla kullanılabilirliği
doğrulanmış bir strateji yoktur. Testler yazılım davranışını sınar; kâr kanıtı değildir.
Önceki “sıradaki V2”, “altyapı eksiksiz” ve “35 test” ifadeleri güncel durum değildir.
Güncel test sonucu her PR'ın belirli commit'i için raporlanır.

## 2. ASLA YAPMA Listesi (Burak'ın kendi roadmap kuralları)

Bu liste ilk yol haritasının tarihsel kaydıdır. Sayısal kapılar ilgili stratejinin
önceden onaylı spesifikasyonundan okunur; bu devir hiçbir eşiği değiştirmez.

1. **Parametre optimizasyonu = curve fitting = YASAK.** V1'i ayar çekerek
   "kurtarmaya" çalışma. PF 0.82'lik sistem turlanarak 1.3 yapılır ve canlıda
   batar. Burak sıklık/sonuç baskısı yaparsa bile bu çizgiyi koru.
2. **Kapılar atlanamaz:** Backtest (PF>1.3, DD<%15, 300+ işlem, OOS sağlam)
   → 300 paper → 100 testnet → ancak o zaman 100-500$ canlı.
3. **"Kesin kazanç" vaat etme.** Burak bunu istiyor; dürüst cevap: kimse
   veremez. Beklenti yönetimini baştan yap, sonda değil.
4. Backtest varsayımları HEP muhafazakâr: aynı barda stop+target=stop,
   maliyetler dahil, lookahead sıfır. Motor bunu zaten yapıyor — bozma.
5. Yeni strateji testi TEK ATIŞ: kurallar veriye bakmadan yazılır,
   2020-2024'te bir kez test, 2025+ hold-out. Aynı veride deneme-yanılma
   döngüsü = arka kapıdan overfitting.

## 3. Teknik Tuzaklar (tarihsel ortam notları)

Aşağıdaki OneDrive, araç adı ve ağ kısıtları önceki çalışma ortamının kaydıdır;
her ortamda geçerli kabul edilmez. ChatGPT değişiklikleri GitHub bağlantısı üzerinden
ayrı dal/PR ile iletebilir; dosya bütünlüğü ve diff kontrol edilir. Gerçek veri
Burak'ın makinesindedir; devir sırasında veri indirilmez veya yeniden koşulmaz.

- **OneDrive mount'ta Write/Edit araçları dosya kuyruğunu KESIYOR** (sync
  race, bazen null byte/hibrit içerik). Bu projede dosya yazmak için HER
  ZAMAN `mcp__workspace__bash` heredoc kullan; sonra ast.parse / ``` sayısı
  ile bütünlük doğrula.
- **Burak'ın makinesi:** Python 3.13 + unit-koruyan pandas. to_datetime
  ms/us çözünürlük üretir → tüm DatetimeIndex'ler `.as_unit("ns")` ile
  sabitlenmeli (data.py ve structure.py'de yapıldı; yeni kod yazarken unutma).
  Bu bug bir kez tüm tarihleri 1970'e çökertti (save_csv) — testi var.
- **Sandbox ağı:** borsa API'leri, raw.githubusercontent, HF hepsi 403.
  TEK kanal: github.com (git clone çalışır) ama akış ~10MB/2dk'da kesilir —
  büyük blob çekilemez. Gerçek veri işleri Burak'ın makinesinde (.bat'lar).
- **Bybit testnet:** ccxt load_markets, API key varken private
  fetchCurrencies çağırır → hata. `exchange.has["fetchCurrencies"]=False`
  yapıldı (execution.py). recvWindow=20000 (saat kayması).
- **.bat dosyaları ASCII yazılmalı** (TR karakter cmd codepage'inde bozulur).

## 4. Denenmiş ve Sonuçlanmış (TEKRAR TEST ETME)

| Deney | Sonuç |
|---|---|
| V1 (sweep+FVG, 15M/4H) 6.5 yıl BTC+ETH | RED — PF 0.78-0.82, 2022-23 yıkıcı |
| Session filtresi (killzone) | Kayıpları azaltıyor ama kâra çeviremiyor |
| Volume filtresi (1.5×MA20) | 18 aylık BTC'de iyi görünüp uzun dönemde genellemedi — dönemsel şans |
| Taker/taker ücret modeli dar stopla | 0.4R+/işlem maliyet — maker/taker ayrımı + min %0.2 stop şart |
| V2 (sweep + CHoCH, 15M/4H) in-sample 2020–2024, tek atış | RED — PF 0.796, DD %22.37, 490 işlem (`reports/V2_INSAMPLE.md`) |
| Plan B v1 (Donchian 55/20, günlük, BTC/ETH/SOL/BNB) in-sample 2020–2024, tek atış | RED — işlem 37 < 100, DD %20.36 > %15 (PF 5.93) (`reports/PLANB_INSAMPLE.md`) |
| V3 (seans kırılımı, 15m) in-sample 2021–2024, tek atış | RED — PF 0,91254, işlem 3.201, DD %95,39, HAC t −1,36453 (`reports/V3_INSAMPLE.md`) |

Detaylar: reports/YILLIK_ANALIZ.md, reports/BACKTEST_RAPORU.md, PROGRESS.md.

## 5. Mevcut altyapı ve kullanım sınırı

`tradebot/` altında stratejiler, motorlar, protokol, veri, risk ve yürütme modülleri
bulunur. Varlıkları “sağlam, aynen kullanılabilir” olarak kabul etme; yeni kullanım
için ilgili kapsam ayrıca denetlenir.
`live.py`, `execution.py`, `server.py` ve demo çalıştırıcı gerçek parayla kullanılmaz.
C karar notu §4'teki bulguların düzeltilmesi bu devir PR'ının kapsamında değildir;
kullanılacak mimari bir aday doğrulandıktan sonra belirlenir.
Doğrulama komutu: `python -m pytest tests/`. Test sayısı/sonucu çalıştırılmadan
iddia edilmez. Gerçek veri koşucuları ve tek atış .bat dosyaları denetimde çalıştırılmaz.

## 6. Kullanıcı Profili

Burak: kod bilgisi yok, .bat + ekran görüntüsüyle çalışır. Sık işlem ve
somut sonuç ister; uzun sessizlik ve ret kararı moral bozuyor — dürüst kal
ama emeğinin ürününü görünür kıl (rapor, grafik, Telegram). Türkçe konuşur.
Referans kütüphaneler SADECE fikir için; kod sıfırdan yazılır (kendi kuralı).

## 7. Tarihsel yol haritası seçenekleri (8 Temmuz 2026)

Aşağıdaki seçenekler geçmiş kayıttır; V2 ve Plan B tamamlandı ve reddedildi.
Güncel iş listesi değildir. Aktif durum §0, yeni aday süreci C karar notu §3'tedir.

a) **V2 (SMC ailesi):** sweep sonrası CHoCH konfirmasyonu (knowledge base'in
   kendi uyarısı; V1 bunu atlıyordu). Kuralları önceden yaz, tek atış test.
b) **Farklı aile:** Günlük TF trend-following / momentum — literatürde on
   yıllarca belgelenmiş anomaliler; yine garanti değil, yine aynı kapılardan
   geçer. Hisse/emtia/FX genişlemesi ancak bu disiplinle anlamlı.
c) **Kabul:** "Her piyasada kesin kazanan sistem" diye bir hedef koymak
   projeyi sonsuz hayal kırıklığı döngüsüne sokar. Küçük edge + sıkı risk
   + uzun vade tek gerçekçi çerçevedir.

Hepsinde ölçüm altyapısı hazır. Başarısızlık verilerini SİLME — bunlar
projenin en pahalı ödenmiş dersleri.

---

## 8. V2 STRATEJİ SPESİFİKASYONU (önceden sabitlendi — 8 Tem 2026)

Bu kurallar VERİYE BAKILMADAN, knowledge base mantığından yazıldı ve artık
DEĞİŞTİRİLEMEZ. Sonraki asistan: bunu `tradebot/strategy_v2.py` olarak
implemente et, aşağıdaki protokolle TEK KEZ test et. Kural değişikliği =
yeni versiyon numarası + yeni tek atış; aynı kuralda ikinci deneme YOK.

**V2 = "Sweep + CHoCH konfirmasyonu" (V1'den fark: FVG'ye limit emir yerine
yapı dönüşü onayı beklenir — knowledge base'in 'konfirmasyonsuz girme'
uyarısının kodu):**

- Aynı kalan: 4H bias (structure.py), 15M çalışma TF'i, killzone filtresi,
  tek pozisyon, RR hedefi 2.0, stop tamponu %0.1, min stop mesafesi %0.2,
  maker/taker maliyet modeli, sweep tanımı (V1 ile aynı).
- LONG: bias=1 iken SSL sweep olur (bar s). Tetik: sonraki 24 bar içinde
  ilk close[i] > max(high[s-10 .. s]). Entry = o barın kapanışında MARKET
  (taker fee + slippage aleyhe). Stop = sweep_low × 0.999.
  Target = entry + 2 × (entry − stop). 24 barda tetik yoksa setup iptal.
- SHORT simetrik: close[i] < min(low[s-10 .. s]), stop = sweep_high × 1.001.
- Volume filtresi: KAPALI (6.5 yıllık kanıt genellemedi).

**Test protokolü (sıra kesin):**
1. Unit testler (V1 testlerinin simetriği; lookahead testi ŞART).
2. In-sample: 2020-01→2024-12, BTCUSDT+ETHUSDT. Geçme eşiği: birleşik
   PF > 1.3 VE ≥150 işlem VE DD < %15.
3. Geçerse hold-out: 2025-01→bugün. PF > 1.15 korunmalı.
4. İkisi de geçerse → paper 300 → testnet 100 → 100-500$ canlı.
5. Herhangi bir kapıda kalırsa: V2 REDDEDİLDİ yazılır, parametre kurcalanmaz.

## 9. PLAN B SPESİFİKASYONU (farklı aile — bu da önceden sabit)

Günlük TF trend-following (klasik Donchian/Turtle, literatür bazlı):
Evren: BTC, ETH, SOL, BNB (USDT perp, günlük bar). LONG: close > son 55
günün en yükseği → ertesi gün open'da market. Stop: 2×ATR(20). Çıkış:
close < son 20 günün en düşüğü VEYA stop. Risk pozisyon başına %0.5, aynı
anda en fazla 2 pozisyon. Short YOK (v1'i basit tut). Maliyet modeli aynı.
Aynı test protokolü (2020-24 in-sample, 2025+ hold-out, PF>1.3).
Not: Günlük TF = az işlem ama düşük maliyet oranı ve on yıllardır belgeli
anomali ailesi. V2 ile AYNI oturumda test edilebilir — iki bağımsız tek atış.

## 10. Tarihsel ölçek örneğinin sınırı

Önceki metindeki +0,15R/işlem, yılda yaklaşık 150 işlem ve %0,5 risk örneği
ölçülmüş getiri veya gelir tahmini değildi. Böyle bir beklenti mevcut stratejilerde
doğrulanmadı. Risk iki katına çıkarılınca DD'nin tam iki kat olacağı veya bir
durdurma eşiğinin kaybı garantiyle sınırlayacağı varsayılmaz.
Güncel ilke: bulunmamış kâr bütçeye yazılmaz; aylık ikiye katlama kriter değildir
(C karar notu §1).

## 11. Sonraki oturum için iş akışı (3 Kasım 2026)

1. `AGENTS.md`, bu belgenin §0'ı, `reports/YILLIK_ANALIZ.md`, C karar notu ve
   aday notunun §8'ini oku. GitHub'daki main/PR/commit durumunu doğrudan doğrula;
   yerel fetch veya hareketli dal adı yerine inceleme tabanını tam SHA ile kaydet.
2. ChatGPT'nin bu oturumdaki işi devir belgeleridir. Yeni aday varsa önce kodsuz
   değerlendirme notu hazırlanır; Burak'ın ayrı kararı olmadan yeni aday uygulaması
   veya gerçek veri/hold-out/paper/testnet/canlı koşusu başlatılmaz.
3. `reports/`, kilitler, §8/§9, `docs/SPEC_EKLERI.md` ve V3 spesifikasyonu korunur.
   §9 Plan B parmak izine dahildir; devirde metni birebir aynı kalmalıdır.
4. ChatGPT ayrı `chatgpt/...` dalında PR hazırlar. Claude bağımsız denetler;
   mutasyon testleri ayrı geçici kopyada yapılır. Burak, denetim ve gerekli testler
   tamamlandıktan sonra merge kararını verir.
