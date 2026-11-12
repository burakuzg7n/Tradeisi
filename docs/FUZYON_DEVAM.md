# Füzyon — devam notu (kontrol noktası)

Yeni oturum ÖNCE bu dosyayı okur, "Adımlar" listesinde ilk işaretsiz maddeden devam eder.

- **Dal:** `claude/fuzyon` · **Paket:** `fusion/` · **Başlangıç:** 12 Kasım 2026
- **İstek (Burak, 12 Kas):** 10 GitHub projesini harmanlayan tek çalışan sistem; ne/nasıl Claude'a ait;
  kâr/zarar analizi Burak'ta; ChatGPT süreçten çıktı.
- **Karar:** Sıfırdan yazılmış (kod kopyası yok, AGENTS kural 7) çok stratejili kripto **kâğıt-işlem arenası**
  + web paneli + TradingView göstergesi. Gerçek emir yok; sinyal iletimi (Telegram/webhook) var.

## Hangi projeden ne alındı
| Proje | Alınan fikir | Modül |
|---|---|---|
| nautilus_trader | Backtest ve canlıda aynı olay motoru (deterministik yeniden oynatma) | `motor.py` |
| freqtrade | Strateji arayüzü, dry-run, korumalar (bekleme, DD kilidi), Telegram | `strateji.py`, `motor.py`, `iletim.py` |
| timercrack/trader | Kaplumbağa tipi Donchian kırılımı + ATR stop | `stratejiler/kirilim.py` |
| binance-trade-bot | Coinler arası oran rotasyonu | `stratejiler/rotasyon.py` |
| TradingAgents | Analist kurulu → boğa/ayı tezi → trader → risk yöneticisi | `stratejiler/kurul.py` |
| TradeMaster | Pekiştirmeli öğrenme ajanı (Q-öğrenme) + değerlendirme metrikleri | `stratejiler/qajan.py`, `olcum.py` |
| Superalgos | Düğüm/kural tabanlı strateji tanımı (JSON), görsel panel | `kural.py`, `kurallar/*.json`, `panel.py` |
| Vibe-Trading | Tek satır metinden strateji üretme (`kural` komutu) | `kural.py`, `cli.py` |
| AI-Trader | Stratejilerin eşit sermayeyle yarıştığı arena + liderlik tablosu | `motor.py`, `panel.py` |
| StrategyEase-SDK | Sinyali dış yürütücüye REST ile iletme, lideri takip | `iletim.py` |

## Adımlar
- [x] 1. Repolar incelendi, tasarım ve bu not yazıldı
- [x] 2. Çekirdek: `gostergeler.py`, `veri.py`, `motor.py`, `olcum.py`
- [x] 3. Stratejiler: kırılım, ortalamaya dönüş, rotasyon, kural, kurul, Q-ajan, füzyon oylaması
- [x] 4. `iletim.py`, `panel.py`, `cli.py`, `Fuzyon.bat`, `pine/fuzyon_kurul.pine`
- [x] 5. Testler (`tests/test_fusion_*.py`) + Burak'ın makinesindeki gerçek veriyle çalıştırma kontrolü
- [x] 6. `docs/FUZYON.md`, AGENTS.md rol güncellemesi, push + PR

## Notlar
- Burak'ın makinesindeki sanal kabukta internet yok; gerçek veri kontrolü OneDrive kopyasındaki
  `data/BTCUSDT_15m.csv`, `ETHUSDT_15m.csv` ile yapılır. Windows tarafında internet var.
- Bağımlılık: yalnız `numpy` (pandas kullanılmadı — Python 3.13 uyum sorunlarından kaçınmak için).
- 12 Kas: 6 adımın hepsi tamam. 331 test yeşil (17'si `tests/test_fusion.py`). Paket ayrıca Burak'ın
  OneDrive `Tradeİşi` klasörüne kopyalandı (sha256 eşleşti) ve oradaki BTC/ETH 15m verisiyle
  Python 3.10'da backtest komutu uçtan uca çalıştı (35.041 bar, ~8 sn).
- Denenmeyenler: Windows'ta `Fuzyon.bat`, Binance'ten canlı indirme (sanal kabukta internet yok),
  Pine göstergesinin TradingView'da derlenmesi, Telegram/webhook iletimi.

## 2. denetim turu (12 Kasım 2026, Burak: "son kez analizle, gerekirse kod kopyala")
- [x] 7. Asıl kaynak kodlarla karşılaştırma: `oran_rotasyon` (binance-trade-bot `auto_trader.py`) ve
  `kirilim` (timercrack/trader `strategy/brother2.py`) asıllarıyla aynı kurallara getirildi.
  Kod kopyalanmadı (gerek kalmadı; ikisi de yeniden yazıldı, binance-trade-bot ve freqtrade GPL-3.0).
- [x] 8. Gerçek kullanım hataları: kapanmış mum kontrolü Binance saatine göre; CSV sona eklenir
  (15 dakikada bir tüm dosya yeniden yazılmıyor); Windows/OneDrive'da güvenli dosya değişimi;
  672 barlık medyanın 1,2 GB bellek istemesi (bloklu hesap); yıllarca geçmişin her turda
  hesaplanması (kırpma); toplam kaldıraç tavanı; dolmayacak/yinelenen sinyallerin yayımlanması;
  rotasyonun füzyon oylamasında sürekli "long" oy sayılması; Pine'da yerel blokta işlev tanımı.
- [x] 9. Demo verisi yönsüz rastgele yürüyüş yapıldı (eski sürüm trend içeriyordu ve stratejileri
  olduğundan iyi gösteriyordu). Tarafsızlık ölçümü: yönsüz yürüyüş + sıfır maliyetle 150 tohumda
  ortalama K/Z istatistiksel olarak sıfır (t ≈ 0,5) → motorun dolum mantığında iyimser sapma yok.
- [x] 10. Varsayılan aralık 15m → 4h (gerekçe: maliyet/stop oranı, `docs/FUZYON.md`).
- [x] 11. 345 test yeşil (31'u `tests/test_fusion.py`); Binance indirme + canlı döngü sahte API ile uçtan uca sınandı (40 mumluk canlı döngü, çift sinyal yok, tek seferde oynatmayla aynı sonuç).

### Ölçümler (Burak'ın makinesi, yalnız BTCUSDT + ETHUSDT, maliyetler dahil, 1.000 USDT/strateji)
Bunlar kapı kararı değildir; tek geçmiş yolun ölçümüdür.

**15m, son 365 gün (Tem 2025 → Tem 2026):** 8 stratejinin 8'i ekside (−%3,7 … −%89,6).
Maliyet öncesi toplamlar sıfır civarı (−349 … +285 USDT), maliyet 650–1.040 USDT (yüksek frekanslılarda).

**4h, son 730 gün (Tem 2024 → Tem 2026):** kirilim +%24,4 · fuzyon +%20,9 · kural_hacim_patlamasi +%14,5 ·
kural_ema_kesisim +%11,6 · ortalamaya_donus +%2,5 · ajan_kurulu +%0,5 · oran_rotasyon +%0,4 · q_ajan −%26,2.

**4h, 2021-01 → 2026-07 (5,5 yıl):**
| Strateji | Getiri | Maks. düşüş | İşlem | Sharpe | Yıllar (2021…2026 H1) |
|---|---|---|---|---|---|
| oran_rotasyon | +%177 | %67 | 24 | 0,61 | +35, −49, +148, +77, +11, −18 |
| fuzyon | +%136 | %19 | 466 | 0,88 | +20, +5, +39, +12, +17, +3 |
| kural_hacim_patlamasi | +%97 | %15 | 396 | 1,04 | −7, +33, +19, +19, +13, −2 |
| ajan_kurulu | +%82 | %20 | 1.009 | 0,69 | +37, +8, +7, −1, +14, 0 |
| kirilim | +%47 | %20 | 473 | 0,57 | +1, −11, +18, +17, +10, +8 |
| kural_ema_kesisim | +%27 | %29 | 219 | 0,35 | +12, +17, −4, −9, +1, +11 |
| ortalamaya_donus | +%6 | %5 | 45 | 0,40 | 0, +1, 0, +1, +3, +1 |
| q_ajan | −%28 | %36 | 3.225 | −0,54 | +9, −14, +4, −5, −4, −19 |

Aynı dönemde al-tut: BTC +%63, ETH +%45 (yıllar BTC: +60, −64, +156, +121, −6, −27).
Uyarılar: yalnız 2 coin; fonlama modellenmedi; 15m görüldükten sonra 4h'ye geçildi; 8 strateji ×
2 aralık denendi; en iyi Sharpe ≈ 1 (5,5 yılda t ≈ 2) — zayıf-orta kanıt. Hold-out kalmadı.

- Denenmeyenler (değişmedi): Windows'ta `Fuzyon.bat`, Binance'ten gerçek indirme (sanal kabukta
  internet yok), Pine'ın TradingView'da derlenmesi, Telegram/webhook.
- Teknik not: `device_commit_files` kopyalamadan hemen sonra çağrılırsa ESKİ içeriği yazabiliyor;
  her eşitlemeden sonra cihazda sha256 karşılaştır.

## Sonraki olası işler (istek gelirse)
- Burak'ın ilk Windows çalıştırmasından gelen hata/çıktıya göre düzeltme
- Pine derleme hatası çıkarsa düzeltme
- Yeni kural stratejileri (`python -m fusion kural …`)
