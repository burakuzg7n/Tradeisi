# DEVİR NOTU — Sonraki Asistan İçin (Opus dahil)

Yazan: Claude (Fable 5) · 8 Temmuz 2026 · Kullanıcı: Burak

## 1. Tek Paragraf Özet

BTC/ETH için kural bazlı trade botu inşa edildi (SMC: HTF bias + liquidity
sweep + FVG retest). Altyapı EKSİKSİZ ve test edilmiş (35 unit test):
backtest motoru, risk engine, journal, Telegram, Bybit testnet canlı
çalıştırıcı. Strateji V1, 6.5 yıl gerçek veri + 800 işlemle test edildi ve
**REDDEDİLDİ** (PF 0.78-0.82). Bu, sürecin başarısı: zayıf strateji gerçek
para yanmadan yakalandı. Sıradaki iş V2 stratejisi — altyapıya dokunma.

## 2. ASLA YAPMA Listesi (Burak'ın kendi roadmap kuralları)

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

## 3. Teknik Tuzaklar (saatlerimi yedi, senin yemesin)

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

Detaylar: reports/YILLIK_ANALIZ.md, reports/BACKTEST_RAPORU.md, PROGRESS.md.

## 5. Yeniden Kullanılabilir Varlıklar (sağlam, dokunma)

`tradebot/` paketi: backtest.py (motor), risk.py, journal.py, notify.py,
execution.py, live.py (testnet runner), data.py, structure.py, fvg.py,
sessions.py. Strateji SADECE strategy.py'de — V2 yeni bir strategy modülü
olarak yazılır, gerisi aynen çalışır. 35 test: `python -m pytest tests/`.
Kurulum: KURULUM.md + 1/2/2b/3 numaralı .bat'lar. Burak'ta Bybit testnet
API + Telegram bot kurulu ve çalışıyor.

## 6. Kullanıcı Profili

Burak: kod bilgisi yok, .bat + ekran görüntüsüyle çalışır. Sık işlem ve
somut sonuç ister; uzun sessizlik ve ret kararı moral bozuyor — dürüst kal
ama emeğinin ürününü görünür kıl (rapor, grafik, Telegram). Türkçe konuşur.
Referans kütüphaneler SADECE fikir için; kod sıfırdan yazılır (kendi kuralı).

## 7. Gerçekçi Yol Haritası Seçenekleri

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

## 10. "Para ile Para Kazanmak" — Dürüst Matematik (Burak'la paylaşıldı)

GERÇEKÇİ iyi senaryo bile şudur: +0.15R/işlem ortalama, çok sembolle yılda
~150 işlem → ~+22R/yıl → %0.5 riskle **yılda ~%11**. 10.000$ ile ~1.100$/yıl,
500$ ile ~55$/yıl. Bot zenginlik makinesi değil, SERMAYE ÇARPANIdır — küçük
sermayede asıl kaldıraç sermayeyi büyütmektir, riski artırmak değil (risk
2×'lenirse drawdown da 2×'lenir, %10 kill switch'e çarpar). Bu beklentiyi
kabul etmeyen her plan, ya aşırı kaldıraca ya curve fitting'e sürükler —
ikisinin de sonu aynı. Ayrıca: asistan yatırım danışmanı değildir; sistem
kriterleri Burak'ın roadmap'inden gelir, kâr garantisi kimse veremez.

## 11. Sonraki Oturum İçin İlk Komutlar

1. Bu dosyayı ve reports/YILLIK_ANALIZ.md'yi oku.
2. §8'i implemente et (bash heredoc ile yaz — §3'teki OneDrive tuzağı!).
3. Testler → Burak'a `2b_backtest_hizli.bat` benzeri tek tık ver
   (veri data/'da hazır, 2020+ BTC+ETH indirilmiş durumda).
4. Sonucu kapı kriterleriyle raporla — GEÇTİ ya da KALDI, süsleme yok.
