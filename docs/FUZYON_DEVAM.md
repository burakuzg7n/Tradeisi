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
- [ ] 2. Çekirdek: `gostergeler.py`, `veri.py`, `motor.py`, `olcum.py`
- [ ] 3. Stratejiler: kırılım, ortalamaya dönüş, rotasyon, kural, kurul, Q-ajan, füzyon oylaması
- [ ] 4. `iletim.py`, `panel.py`, `cli.py`, `Fuzyon.bat`, `pine/fuzyon_kurul.pine`
- [ ] 5. Testler (`tests/test_fusion_*.py`) + Burak'ın makinesindeki gerçek veriyle çalıştırma kontrolü
- [ ] 6. `docs/FUZYON.md`, AGENTS.md rol güncellemesi, push + PR

## Notlar
- Burak'ın makinesindeki sanal kabukta internet yok; gerçek veri kontrolü OneDrive kopyasındaki
  `data/BTCUSDT_15m.csv`, `ETHUSDT_15m.csv` ile yapılır. Windows tarafında internet var.
- Bağımlılık: yalnız `numpy` (pandas kullanılmadı — Python 3.13 uyum sorunlarından kaçınmak için).
