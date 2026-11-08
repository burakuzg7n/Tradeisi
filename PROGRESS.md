# TradeBot — İlerleme Takibi

Başlangıç: 24 Haziran 2026 · Son güncelleme: 8 Kasım 2026

## Güncel durum (8 Kasım 2026)

**5 strateji REDDEDİLDİ** (V1, V2, Plan B v1, V3, Sepet momentum). Hiçbiri
testnet veya canlıya geçemedi. **Çalışan program teslim edildi:** `trader/`
paketi + `TradeBot.bat` menüsü + web paneli. Paper modu çalışıyor.

| Tarih | Olay | Kayıt |
|---|---|---|
| 31 Eki 2026 | Proje GitHub'a taşındı; ChatGPT bağımsız denetim akışı; motor düzeltmeleri, SPEC_EKLERI (PR #1–#3) | PR #1–#3 |
| 31 Eki 2026 | V2 tek atış koşucusu (PR #4) ve in-sample koşusu: **KALDI** (PF 0,796; DD %22,37; 490 işlem) | `reports/V2_INSAMPLE.*`, `52239d7` |
| 1 Kas 2026 | Plan B v1 ekleri E11–E17, günlük perp verisi + sağlık raporu (VERİ UYGUN), portföy motoru, sinyaller, koşucu (PR #5–#9) | `reports/PLANB_VERI_SAGLIK.*`, `b340ae5` |
| 1 Kas 2026 | Plan B v1 in-sample koşusu: **KALDI** (işlem 37 < 100; DD %20,36 > %15; PF 5,93) | `reports/PLANB_INSAMPLE.*`, `6c5ed47` |
| 2 Kas 2026 | V3 kuralları + in-sample koşusu: **KALDI** (PF 0,91; DD %95) | `reports/V3_INSAMPLE.*` |
| 7 Kas 2026 | **Yeni strateji ailesi: sepet momentum** (çapraz kesit). Kural seti ve kapılar **veriye bakılmadan** yazılıp commit edildi | `docs/ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md`, `c5358a6` |
| 7-8 Kas 2026 | `trader/` paketi kuruldu: backtest motoru, paper motoru, ccxt (Binance+Bybit), web paneli, kapı defteri, CLI, `.bat` menüsü | `c5358a6` |
| 8 Kas 2026 | Koşu 1: **VOID** — 3 motor hatası (tarih kırpma, pozisyon limiti, çift kapanma) | `docs/KOSU_GECMISI_SEPET_MOMENTUM.md`, `cb87126` |
| 8 Kas 2026 | Koşu 2–3: **VOID** — backtest **deterministik değil** (kök neden bulundu) | `docs/KOSU_GECMISI_SEPET_MOMENTUM.md` |
| 8 Kas 2026 | Determinizm düzeltmesi: `gross_exposure()` (sorted + `math.fsum`), 308 test yeşil | `tests/test_trader_determinism.py` |
| 8 Kas 2026 | **Koşu 4: GEÇERLİ TEK ATIŞ → RED** (PF 1,140 < 1,30; DD %55,20 > %15; 823 işlem). Hold-out açılmadı | `out/reports/sepet_momentum_insample_20261108_132730.*` |
| 8 Kas 2026 | Teslim: `docs/TEADEBOT_KULLANIM.md` (Başlangıç rehberi), README/PROGRESS/KURULUM güncel | `docs/TEADEBOT_KULLANIM.md` |

Okuma notları (yıllık tablo kapanış yılına göre; kontenjan iptalleri bağımsız fırsat
sayısı değil) ve denetimin kapsamı/sınırları: `DEVIR_NOTU.md` §0 ve karar notu §4.

## 8 Kasım 2026 — Çalışan program teslimi

Burak'ın istediği "çalışır halde bir trade programı" teslim edildi:

| Bileşen | Durum |
|---|---|
| `TradeBot.bat` menüsü (8 seçenek) | ✅ |
| `1_kurulum.bat` → `6_testnet.bat` | ✅ Hepsi ASCII, tek tıkla |
| Veri indirme (25 sembol, günlük + funding) | ✅ 25/25 tamam, 0 boşluk |
| Backtest motoru (çoklu sembol, gerçekçi dolum, funding, slippage) | ✅ **Deterministik** (hash seed'den bağımsız) |
| Paper motoru (backtest'in deterministik oynatımı) | ✅ `--once` ve sürekli mod |
| Web paneli (FastAPI + HTML) | ✅ `/api/state` 200, HTML 200 |
| ccxt adaptörü (Binance + Bybit, testnet dahil) | ✅ |
| Protokol kapıları + geçersiz koşu arşivi | ✅ `out/gates.json` |
| Kullanım kılavuzu (Türkçe, adım adım) | ✅ `docs/TEADEBOT_KULLANIM.md` |
| Testler | ✅ **308 passed** |

**Kapı durumu:** `sepet_momentum` → `backtest.passed = false` → testnet ve
canlı **kapalı**. Bu koruma amaçlıdır.

## 90 Günlük Plan

| Gün | Hedef | Durum |
|-----|-------|-------|
| 1-14  | Eğitim ve Knowledge Base | ✅ Tamamlandı (+ 6 Tem: 9 dosyada hata düzeltildi) |
| 15-30 | Strateji ve Pine Script | ✅ Tamamlandı (6 Tem) |
| 31-45 | Backtest | ✅ TAMAMLANDI (8 Tem): 6.5 yıl, 800+ işlem → **STRATEJİ V1 REDDEDİLDİ** (PF 0.78-0.82, ban kriteri). reports/YILLIK_ANALIZ.md |
| 46-60 | Paper Trading | 🔶 **Program hazır** (8 Kas): paper motoru + panel çalışıyor. ⛔ Strateji eşik geçmediği için strateji bazlı paper koşusu başlatılmadı |
| 61-75 | Risk Engine ve Journal | ✅ Kod tamamlandı (6 Tem) |
| 76-90 | FastAPI, CCXT, Testnet | 🔶 Kod mevcut ve çalışır; kapıları geçen strateji olmadığı için testnet koşusu yok |

## 6 Temmuz 2026 — Yapılanlar

**Knowledge base denetimi — bulunan ve düzeltilen hatalar:**
1. `market-structure/implementation.md` Pine: CHoCH hiç tetiklenmiyordu (trend, kırılımdan ÖNCE güncelleniyordu) + `lastSwingHigh[3]` yanlış offset
2. `market-structure/implementation.md` Python: tüm geçmiş SON swing seviyesiyle karşılaştırılıyordu → future data leak
3. `liquidity/implementation.md` Python: kesinleşmemiş swingler kullanılıyordu (rolling center=True lookahead) → sweep tespiti sahte
4. `liquidity/implementation.md` Pine: `pl[lookback]` na-serisi hatası → sweep neredeyse hiç yakalanmazdı
5. `fvg/implementation.md`: OTE zone ters hesaplanıyordu (%21-50 doluluk, %50-79 değil) + mitigasyon eşiği entry zone'la çelişiyordu
6. `sessions/implementation.md`: 07-09 UTC "asian" dönüyordu (öncelik sırası yoktu); Pine session'da "UTC" parametresi eksikti
7. `economic-events/implementation.md`: ForexFactory saatleri UTC sanılıyordu (US Eastern gelir) → haber penceresi 4-5 saat kayardı; `.seconds` → `.total_seconds()`
8. `backtesting/implementation.md`: short işlemlerde slippage LEHTE uygulanıyordu
9. `risk-management/implementation.md`: 1R kapanış bakiyesinden türetiliyordu (açılışta sabitlenmeli)

**Yeni üretilen:**
- `tradebot/` paketi: strateji + backtest motoru + risk engine + journal + FastAPI + CCXT (tamamı sıfırdan)
- `docs/STRATEGY_BIBLE.md`, `pine/htf_sweep_fvg.pine`, `scripts/`, 29 unit test (hepsi geçiyor)
- `reports/engine_validation.json`: 52.608 barlık sentetik koşu (motor doğrulaması — strateji performansı DEĞİL)
- Kritik bulgu: dar SMC stoplarında taker komisyonu 0.4R+/işlem → maker/taker ayrımı + min %0.2 stop mesafesi kuralı eklendi (Strategy Bible §7)

## Gerçek Veri Backtest Sonucu (6 Tem 2026)

18 ay gerçek Bitstamp BTC/USD verisi (Oca 2025 → Tem 2026):
**PF 1.035, 68 işlem, DD %7.9, expectancy +0.03R → kriterler GEÇİLEMEDİ**
(eşik: PF>1.3, 300+ işlem). Session filtresi olmadan PF 0.85'e düşüyor →
filtre çalışıyor. Detay: `reports/BACKTEST_RAPORU.md`. Paper trading'e GEÇİLMEZ.

## Bir Sonraki Adım (Burak)

```bash
pip install -r requirements.txt
python scripts/download_data.py 2020-01-01   # 6+ yıl BTC+ETH, ~10 dk
python scripts/run_backtest.py               # 300+ işlemle net tablo
```
Volume konfirmasyonu EKLENDİ ve test edildi (PF 1.04→1.21, DD %7.9→%3.3,
51 işlem) — genişletilmiş veride `use_volume_filter=True` ile koşulacak.
Not: 90MB'lık 2012-2025 arşivi ve ETH verileri bu ortamın ağ limitinden
(~10MB/akış) çekilemedi; uzun veri Burak'ın makinesinde indirilecek.

Ek (7 Tem): Demo/testnet canlı çalıştırıcı eklendi — tradebot/live.py +
scripts/live_runner.py: TradingView'sız, backtest'le BİREBİR aynı strateji
kodu her 15M kapanışta ccxt ile koşar, Bybit testnet'e emir atar (KURULUM.md +
1/2/3 numaralı .bat dosyaları). 34/34 test.

Ek (aynı gün, devam turu): Telegram bildirimleri eklendi (tradebot/notify.py,
server entegre, 32/32 test). Derin analiz + equity grafiği: reports/ANALIZ.md,
reports/equity_curve.png. Bulgu: edge yön-simetrik (long +0.16R / short +0.14R),
ayda ~3 sinyal → 300 işlem için çok sembol şart.

## Başarı / Ban Kriterleri (değişmedi)

| Metrik | Canlıya geçiş | Sistemi kapat |
|--------|--------------|----------------|
| Profit Factor | > 1.3 | < 1.0 |
| Expectancy | > 0 | — |
| Max Drawdown | < 15% | > 20% |
| Paper / Testnet | > 300 / > 100 işlem | — |
| Negatif performans | — | 3 ay üst üste |
