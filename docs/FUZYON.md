# Füzyon Arena — kullanım kılavuzu

**Ne:** 10 açık kaynak projenin fikirlerini tek programda birleştiren, sıfırdan yazılmış kripto
**kâğıt-işlem arenası**. 8 strateji aynı sermayeyle yan yana çalışır, web panelinde yarışır;
"füzyon" hesabı diğerlerinin çoğunluk oyuyla işlem açar. Yanında aynı kurul mantığını
TradingView'da gösteren bir gösterge vardır.

**Ne değil:** Gerçek emir göndermez. Kâr garantisi vermez. Buradaki stratejiler projenin tek atış
protokolünden (AGENTS.md) geçmemiştir; sonuçların değerlendirmesi Burak'a aittir.

## Başlangıç (Windows)
1. `Fuzyon.bat` dosyasına çift tıkla.
2. **1** → kurulum (yalnız `numpy`).
3. **2** → veri indir (Binance, anahtar gerekmez; ilk seferde birkaç dakika).
4. **3** → backtest + panel (tarayıcıda `http://127.0.0.1:8777` açılır).
5. **4** → canlı kâğıt işlem + panel. Pencere açık kaldıkça her 15 dakikada yeni mumu işler.
   Kapatıp açarsan kaldığı yerden devam eder (aynı sonucu yeniden üretir).

İnternetsiz denemek için **7** (demo, uydurma veri).

## Hangi projeden ne alındı
| Proje | Alınan fikir | Dosya |
|---|---|---|
| nautechsystems/nautilus_trader | Backtest ve canlıda aynı olay motoru; deterministik yeniden oynatma | `fusion/motor.py`, `fusion/canli.py` |
| freqtrade/freqtrade | "Gösterge → giriş/çıkış" strateji arayüzü, dry-run, korumalar (stop sonrası bekleme, DD kilidi), Telegram | `fusion/strateji.py`, `motor.py`, `iletim.py`, `stratejiler/donus.py` |
| timercrack/trader | Kaplumbağa tipi Donchian kırılımı + ATR stop | `stratejiler/kirilim.py` |
| ccxt/binance-trade-bot | Coinler arası oran rotasyonu | `stratejiler/rotasyon.py` |
| TauricResearch/TradingAgents | Analistler → boğa/ayı tezi → trader → risk yöneticisi | `stratejiler/kurul.py` |
| TradeMaster-NTU/TradeMaster | Pekiştirmeli öğrenme ajanı + çok boyutlu değerlendirme metrikleri | `stratejiler/qajan.py`, `olcum.py` |
| Superalgos/Superalgos | Koşul düğümleriyle strateji tanımı, görsel panel | `fusion/kural.py`, `fusion/kurallar/*.json`, `panel.py` |
| HKUDS/Vibe-Trading | Tek satır yazıyla strateji ekleme | `python -m fusion kural …` |
| HKUDS/AI-Trader | Ajanların eşit sermayeyle yarıştığı arena + liderlik tablosu | `motor.py`, `stratejiler/oylama.py`, `panel.py` |
| sinall/StrategyEase-Python-SDK | Sinyali dış yürütücüye REST ile iletme, "lideri takip et" | `fusion/iletim.py` |

Hiçbir projeden kod kopyalanmadı (AGENTS.md kural 7); LLM/API anahtarı gerektiren kısımlar
kural tabanlı karşılıklarıyla yazıldı. Tek bağımlılık `numpy`.

## Stratejiler
| Ad | Mantık |
|---|---|
| `kirilim` | 20 barlık kanal kırılımı, 10 barlık ters kanalda çıkış, 2 ATR stop |
| `ortalamaya_donus` | RSI < 30 + Bollinger alt bandı dışı + EMA 200 üstü → long (short tersi), 2,5 ATR stop |
| `oran_rotasyon` | Tek coin tutar; elindeki coin diğerine karşı komisyon + %0,8 değerlenince ona geçer |
| `ajan_kurulu` | Trend %35 + momentum %25 + hacim %15 + BTC rejimi %25; net > 0,40 AL, < −0,40 SAT; oynaklık aşırıysa veto |
| `q_ajan` | Q-öğrenme; yalnız değerlendirme başlangıcından önceki barlarla eğitilir |
| `kural_ema_kesisim`, `kural_hacim_patlamasi` | `fusion/kurallar/` içindeki JSON kurallar |
| `fuzyon` | Diğer stratejilerin o anki yönlerini sayar; net ≥ 2 oyla girer, çoğunluk bozulunca çıkar |

## Kendi stratejini yazıyla ekle
```
python -m fusion kural rsi_dip "rsi(14) < 30 and close > ema(200)" "rsi(14) > 55"
```
Sıra: ad, long giriş, long çıkış, short giriş, short çıkış (son üçü isteğe bağlı);
`--stop-atr 2 --kar-atr 4`. Kullanılabilenler: `open high low close volume`,
`ema sma rsi atr highest lowest roc zscore std cross_up cross_down abs max min`, `x[1]` (önceki bar).
Dosya `fusion/kurallar/` altına yazılır; silmek için dosyayı sil ya da içine `"kapali": true` ekle.

## Motorun varsayımları
- Emir, sinyal barının kapanışında verilir; **bir sonraki barın açılışında** dolar.
- Her dolumda komisyon 5 bps + aleyhe kayma 2 bps. Aynı barda stop ve hedef değdiyse **stop** sayılır;
  boşluklu açılışta stop açılış fiyatından dolar.
- Stoplu işlemlerde boyut: özsermayenin %1'i / stop mesafesi; tek pozisyon nominali ≤ özsermaye.
- Short açıktır ve vadeli gibi kâğıt üzerinde yürür; **fonlama ücreti modellenmez**.
- Hesap %25 düşerse 672 bar (15m'de 1 hafta) yeni giriş almaz.
- Canlı kâğıt mod ilk açılışta son 7 günü oynatarak başlar; sinyaller yalnız yeni mumlar için iletilir.

## Ayarlar
`Fuzyon.bat → 8` kökte `fuzyon_ayar.json` oluşturur (semboller, aralık, sermaye, risk, komisyon,
short, DD sınırı, `takip`, `webhook_url`, port). Telegram için kökteki `.env` dosyasına
`TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` yaz. `takip`: `"hepsi"`, `"lider"` ya da bir strateji adı.

## Çıktılar (`out/fusion/`)
`durum_canli.json`, `durum_backtest.json` (panel bunları okur) · `islemler_backtest.csv`,
`ozsermaye_backtest.csv` (Excel'de açılır; kendi kâr/zarar analizin için) · `sinyaller.jsonl`.

## TradingView göstergesi
`pine/fuzyon_kurul.pine` → TradingView'da Pine Editor'e yapıştır → "Add to chart". Kurul AL/SAT/çıkış
etiketleri, kırılım okları, stop/hedef çizgileri, puan tablosu ve 5 alarm koşulu içerir.
Gösterge TradingView'da derlenerek denenmedi; hata verirse mesajı Claude'a ilet.

## Bilinen sınırlar
- Kâğıt dolumlar gerçek emir defterini, kısmi dolumu ve fonlamayı yansıtmaz.
- Pine göstergesi ile Python kurulu arasında EMA/ATR başlangıç farkından küçük sapma olabilir.
- Binance verisine ulaşılamazsa canlı mod eldeki veriyle bekler ve 15 dakikada bir yeniden dener.
