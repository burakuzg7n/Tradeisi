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
5. **4** → canlı kâğıt işlem + panel. Pencere açık kaldıkça her yeni mumu (varsayılan: 4 saatte bir)
   işler. Kapatıp açarsan kaldığı yerden devam eder (aynı sonucu yeniden üretir); bilgisayar
   kapalıyken kaçan mumlar açılışta oynatılır, yalnız son 2 mumun sinyalleri iletilir.

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

Hiçbir projeden kod kopyalanmadı; LLM/API anahtarı gerektiren kısımlar kural tabanlı
karşılıklarıyla yazıldı. Tek bağımlılık `numpy`. `kirilim` ve `oran_rotasyon`, asıl projelerin
kaynak kodu okunarak aynı kurallarla yeniden yazıldı (12 Kasım 2. denetim). Kopyalamaya gerek
kalmadı; ayrıca freqtrade ve binance-trade-bot GPL-3.0 lisanslıdır, kodları kopyalanırsa bu
reponun da GPL ile yayımlanması gerekir.

## Stratejiler
| Ad | Mantık |
|---|---|
| `kirilim` | Kısa/uzun yumuşatılmış ortalama (20/60) trend filtresi + kapanışların 20 barlık kanalı; çıkış: girişten beri en yüksek/düşükten 3 ATR izleyen stop (kapanışla) |
| `ortalamaya_donus` | RSI < 30 + Bollinger alt bandı dışı + EMA 200 üstü → long (short tersi), 2,5 ATR stop |
| `oran_rotasyon` | Tek coin tutar; A/B oranı kayıtlı eşiği ücret + %0,8 marjla aşınca B'ye geçer; B alınınca B'ye giden tüm çiftlerin eşiği güncellenir. Oylamaya katılmaz |
| `ajan_kurulu` | Trend %35 + momentum %25 + hacim %15 + BTC rejimi %25; net > 0,40 AL, < −0,40 SAT; oynaklık aşırıysa veto |
| `q_ajan` | Q-öğrenme; yalnız değerlendirme başlangıcından önceki barlarla eğitilir |
| `kural_ema_kesisim`, `kural_hacim_patlamasi` | `fusion/kurallar/` içindeki JSON kurallar |
| `fuzyon` | Yön görüşü olan stratejilerin (rotasyon hariç) o anki yönlerini sayar; net ≥ 2 oyla girer, çoğunluk bozulunca çıkar |

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
- Stoplu işlemlerde boyut: özsermayenin %1'i / stop mesafesi; tek pozisyon nominali ≤ özsermaye;
  tüm açık pozisyonların toplam nominali ≤ 3 × özsermaye (`max_kaldirac`).
- Short açıktır ve vadeli gibi kâğıt üzerinde yürür; **fonlama ücreti modellenmez**.
- Hesap %25 düşerse 7 gün yeni giriş almaz.
- Canlı kâğıt mod ilk açılışta son 30 günü oynatarak başlar; sinyaller yalnız yeni mumlar için iletilir.
- Mumun kapanıp kapanmadığı Binance saatine göre belirlenir (bilgisayar saati kayık olsa da).
- Dolmayacağı belli olan (bekleme, kilit, kapasite) ya da yinelenen emirler sinyal olarak yayımlanmaz.

## Neden 4 saatlik mum (varsayılan)
Gidiş-dönüş maliyeti ≈ 14 bps'tir (2 × 5 bps komisyon + 2 × 2 bps kayma). Burak'ın verisinde
son 2 yılın medyanıyla 2 ATR'lik stop mesafesine oranı:

| Mum | BTC | ETH |
|---|---|---|
| 15 dakika | işlem başına 0,24 R | 0,16 R |
| 4 saat | 0,05 R | 0,04 R |

15 dakikada her işlem daha başlamadan riskin beşte birini–dörtte birini maliyete verir; yılda
1.000+ işlemde bu, sermayenin büyük kısmıdır. Varsayılan bu aritmetikle 4 saate alındı.
Başka aralık denemek için: `python -m fusion veri --aralik 1h` ve `python -m fusion backtest --aralik 1h`
(ya da `fuzyon_ayar.json` içinde `"aralik"`). Gösterge periyotları bar sayısıdır; aralık değişince
süre karşılıkları da değişir.

## Ayarlar
`Fuzyon.bat → 8` kökte `fuzyon_ayar.json` oluşturur (semboller, aralık, sermaye, risk, komisyon,
short, DD sınırı, `takip`, `webhook_url`, port). Telegram için kökteki `.env` dosyasına
`TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` yaz. `takip`: `"hepsi"`, `"lider"` ya da bir strateji adı.

## Çıktılar (`out/fusion/`)
`durum_canli.json`, `durum_backtest.json` (panel bunları okur) · `islemler_backtest.csv`,
`ozsermaye_backtest.csv` (Excel'de açılır; kendi kâr/zarar analizin için) · `sinyaller.jsonl`.
Tabloda **Maliyet** = kapanan işlemlerin komisyon + kayması; **Maliyet öncesi K/Z** = sinyallerin
maliyetsiz sonucu. İkisinin farkı net sonuçtur.

## TradingView göstergesi
`pine/fuzyon_kurul.pine` → TradingView'da Pine Editor'e yapıştır → "Add to chart". Kurul AL/SAT/çıkış
etiketleri, kırılım giriş okları, stop/hedef çizgileri, puan tablosu ve 5 alarm koşulu içerir.
Grafiği botla aynı aralıkta (varsayılan 4 saat) aç. Gösterge TradingView'da derlenerek
denenmedi; hata verirse mesajı Claude'a ilet.

## Bilinen sınırlar
- Geçmiş sonuçlar ölçümdür, gelecek için kanıt değildir. Bu stratejilerle 2025–2026 verisine
  bakıldı; projenin tek atış protokolündeki "hold-out" bu stratejiler için artık kullanılmış
  veridir. Geriye kalan tek temiz doğrulama ileriye dönük canlı kâğıt işlemdir.
- 15 dakikalık sonuç görüldükten sonra varsayılan 4 saate alındı. Gerekçe maliyet aritmetiğidir,
  ama iki aralık denenmiş olması sonuçları olduğundan iyi gösterebilir.
- Kâğıt dolumlar gerçek emir defterini, kısmi dolumu ve fonlamayı yansıtmaz.
- Pine göstergesi ile Python kurulu arasında EMA/ATR başlangıç farkından küçük sapma olabilir.
- Binance verisine ulaşılamazsa canlı mod eldeki veriyle bekler ve bir sonraki mumda yeniden dener.
