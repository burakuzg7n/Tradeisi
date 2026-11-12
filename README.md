# Tradeİşi — kural bazlı kripto strateji araştırması

Sıfırdan yazılmış, test protokolüyle çalışan bir strateji araştırma projesi.
Kâr garantisi yoktur; kararları önceden sabitlenmiş kapılar verir (`AGENTS.md`).

## Hızlı başlangıç

**`TradeBot.bat`** dosyasına çift tıklayın — menü açılır.
Ayrıntılı adım adım kılavuz: **`docs/TEADEBOT_KULLANIM.md`**.

## Füzyon Arena (12 Kasım 2026)

**`Fuzyon.bat`** → 8 stratejinin kâğıt üzerinde yarıştığı arena + web paneli + TradingView
göstergesi. Gerçek emir göndermez; stratejiler protokol kapılarından geçmemiştir.
Kılavuz: **`docs/FUZYON.md`**.

## Durum (8 Kasım 2026)

**5 strateji** önceden yazılmış kurallarla, tek atış protokolüyle test edildi;
**hepsi reddedildi.** Hiçbiri testnet veya canlıya geçemedi.

| Strateji | Fikir | Sonuç | Rapor |
|---|---|---|---|
| V1 | 15m sweep + FVG (BTC/ETH) | Reddedildi (PF 0,78–0,82) | `reports/YILLIK_ANALIZ.md` |
| V2 | 15m sweep + CHoCH (BTC/ETH) | Reddedildi (PF 0,80, DD %22) | `reports/V2_INSAMPLE.md` |
| Plan B v1 | Günlük Donchian 55/20 (4 coin) | Reddedildi (37 işlem, DD %20) | `reports/PLANB_INSAMPLE.md` |
| V3 | 15m Asya seansı kırılımı (5 altcoin) | Reddedildi (PF 0,91, DD %95) | `reports/V3_INSAMPLE.md`, `reports/V3_INSAMPLE_INCELEME.md` |
| **Sepet momentum** | **Çapraz kesit momentum, 25 sembol, long/short** | **Reddedildi (PF 1,140, DD %55,20)** | `docs/KOSU_GECMISI_SEPET_MOMENTUM.md` |

### Sepet momentum — 5. aday (ayrıntı)

Cross-sectional momentum: 25 sembol, en hacimli 10, en güçlü 3 long +
en zayıf 3 short, ters oynaklık ağırlıkları, brüt 2,0 kaldıraç, haftalık
rebalance.

| Koşu | Statü | İşlem | PF | DD |
|---|---|---|---|---|
| 1 | VOID (motor hatası) | 6 | 0,450 | %97,93 |
| 2 | VOID (motor deterministik değil) | 824 | 1,140 | %55,27 |
| 3 | VOID (determinizm hatası kanıtı) | 822 | 1,137 | %56,22 |
| **4** | **GEÇERLİ TEK ATIŞ → RED** | **823** | **1,140** | **%55,20** |

Hold-out (2025+) **açılmadı** — in-sample RED olduğu için.
Parametreler ayarlanmadı; "Plan B.1" yazılmadı.

Ayrıntı: `docs/ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md` ·
`docs/ORNEKLEM_PLANI_SEPET_MOMENTUM.md` · `docs/KOSU_GECMISI_SEPET_MOMENTUM.md`

Makine çıktılarının arşivi (16 koşu + kapı defteri + parmak izleri):
`reports/SEPET_MOMENTUM/`

## Klasörler

```
AGENTS.md        Tüm asistanlar için kurallar (önce bunu oku)
DEVIR_NOTU.md    Devir notu; §8 (V2) ve §9 (Plan B) bağlayıcı spesifikasyonlar
PROGRESS.md      Zaman çizelgesi
KURULUM.md       Python kurulumu
README.md        Bu dosya

TradeBot.bat     MENÜ — buradan başlayın
1_kurulum.bat    Kütüphaneleri kurar + kurulum kontrolü
2_veri_indir.bat Binance'den 25 sembolün günlük verisini indirir
3_backtest.bat   Geçmiş testi (tek atış)
4_paper.bat      Paper trading (GERÇEK PARA YOK)
5_panel.bat      Web paneli (http://127.0.0.1:8765)
6_testnet.bat    Testnet (kapı kapalıysa açılmaz)

docs/            Spesifikasyonlar, kararlar, koşu geçmişi
  TEADEBOT_KULLANIM.md            ← Başlangıç rehberi (Burak için)
  ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md   5. adayın kural seti + sonucu
  ORNEKLEM_PLANI_SEPET_MOMENTUM.md       Örnekleme planı
  KOSU_GECMISI_SEPET_MOMENTUM.md         4 koşunun tam geçmişi
  SPEC_EKLERI.md, V3_SPEC_TASLAK.md, V3_DOGRULAMA_PLANI.md   (tarihsel)
  SONRAKI_YON_KARAR_NOTU.md, STRATEGY_BIBLE.md                (tarihsel)
  roadmap/        İlk yol haritası belgeleri

trader/          YENİ çalışan program paketi (tradebot/ dokunulmadan)
  backtest.py     Deterministik backtest motoru (çoklu sembol, funding, maliyet)
  paper.py        Paper motoru (backtest'in deterministik oynatımı)
  live.py         Testnet/canlı yürütücü (kapı kontrolüyle)
  exchange.py     ccxt adaptörü (Binance + Bybit)
  dashboard.py    Web paneli (FastAPI)
  strategies/     basket_momentum.py (5. aday), system_test.py (altyapı testi)
  gates.py        Protokol kapıları + geçersiz koşu arşivi
  cli.py          Komut satırı arayüzü
  risk.py, store.py, notify.py, metrics.py, indicators.py, config.py, market.py

tradebot/        ESKİ paket (V1/V2/Plan B/V3) — arşiv, dokunulmuyor
scripts/         Veri indirme, tek atış koşucuları, inceleme scriptleri
tests/           pytest testleri (`python -m pytest tests/`) — 308 test
out/             Çalışma çıktıları (git'te yok)
  reports/         Makine tarafından üretilen backtest raporları
  gates.json       Kapı defteri (geçersiz koşular dahil, silinmez)
reports/         ARŞİV — sonuç raporları, kilitler, mühürler. Silinmez, değiştirilmez.
  SEPET_MOMENTUM/ 5. adayın 16 koşusunun raporları + kapı defteri + parmak izleri
knowledge/       ICT/SMC eğitim notları
pine/            V1 TradingView göstergesi (tarihsel)
data/            Fiyat verisi (git'te yok)
```

## Önemli

- `reports/` **arsivdir**: hiçbir dosya silinmez, yeniden adlandırılmaz veya
  değiştirilmez. Geçersiz koşular da arşivlenir. `reports/SEPET_MOMENTUM/`
  klasörü 5. adayın 16 koşusunun makine çıktılarını, kapı defterini, tek
  atış kilidini ve SHA-256 parmak izlerini içerir.
- `out/` (çalışma klasörü) git'e girmez; kalıcı kayıt `reports/` arşividir.
- Arşiv bütünlüğü tek komutla denetlenir: `python scripts/verify_archive.py`
  (`ARSIV BUTUN` + çıkış kodu 0 = bozulma yok).
- `data/` içindeki CSV'ler raporlardaki parmak izlerine bağlıdır; yeniden indirilmez.
- `.bat` dosyaları **ASCII** kodlamayla yazılmıştır (Windows cmd uyumu).
- `.env` gizli anahtarlar içerir; asla paylaşılmaz veya commit edilmez.
- **Tek atış protokolü:** bir strateji ailesi için ikinci deneme yapılmaz.
  Parametre ayarıyla (curve fitting) kurtarma yasaktır.

