# Füzyon Arena — kullanım kılavuzu

**Ne:** 10 açık kaynak projenin fikirlerini tek programda birleştiren, sıfırdan yazılmış kripto
**kâğıt-işlem arenası**. 8 strateji aynı sermayeyle yan yana çalışır, web panelinde yarışır;
"füzyon" hesabı diğerlerinin çoğunluk oyuyla işlem açar. Yanında aynı kurul mantığını
TradingView'da gösteren bir gösterge vardır.

**Ne değil:** Gerçek emir göndermez. Kâr garantisi vermez. Buradaki stratejiler projenin tek atış
protokolünden (AGENTS.md) geçmemiştir; sonuçların değerlendirmesi Burak'a aittir.

## Başlangıç (Windows) — penceresiz, her şey panelden
1. İlk kez: `Fuzyon.bat` → **1** (kurulum, yalnız `numpy`). Bir kere yeter.
2. **`Fuzyon.vbs`** dosyasına çift tıkla. Pencere açılmaz; tarayıcıda `http://127.0.0.1:8777` açılır.
3. Panelde üstteki düğmelerden zaman dilimini seç: `1m 3m 5m 10m 15m 30m 1h 2h 4h 1d`.
   Hepsi arka planda **aynı anda** çalışır; ilk açılışta veriler sırayla indirilir
   (düğmedeki nokta sarı = hazırlanıyor, yeşil = çalışıyor, gri = kapalı).
4. **Ayarlar** düğmesi: aralıkları aç/kapat, Telegram bildirimini aralık bazında aç/kapat, backtest
   çalıştır, Telegram'ı bağla, "Windows açılınca kendiliğinden başlasın", servisi durdur.

- Servis çalışırken `Fuzyon.vbs`'e yeniden tıklamak yalnız paneli açar (ikinci kopya başlamaz).
- Durdurmak: panel → Ayarlar → **Servisi durdur**. Günlük: `out/fusion/servis.log`.
- Eski menü (`Fuzyon.bat`) duruyor; **S** seçeneği aynı servisi başlatır. Servis çalışırken menüdeki
  **4**'ü (tek aralıklı canlı mod) ayrıca çalıştırma: aynı dosyalara iki süreç yazar.
- Bilgisayar uyursa servis de durur; uyanınca kaçan mumları işler (8 saatten/2 mumdan eski
  sinyalleri iletmez).

## Telegram
Panel → Ayarlar → Telegram:
1. Telegram'da **@BotFather**'a yaz → `/newbot` → bir ad ver → sana bir **token** verir.
2. Token'ı panele yapıştır → **Kaydet**.
3. Kendi botuna herhangi bir mesaj yaz → panelde adın görünür → **Evet, bağla**.

Sonrası: sinyaller telefonuna gelir (varsayılan yalnız 4h; diğer aralıkları Ayarlar'dan açarsın).
Bota `/durum`, `/durum 15m`, `/araliklar` yazarak tabloyu telefondan isteyebilirsin; yalnız bağladığın
sohbet yanıt alır. Token bu bilgisayardaki `.env` dosyasında durur (GitHub'a gitmez).

## Bulutta çalıştırma (bilgisayar kapalıyken)
Bot bir yerde sürekli çalışmak zorunda; telefon bunu yapamaz. Ücretsiz seçenek: GitHub'ın kendi
sunucuları (`.github/workflows/fuzyon-bulut.yml`). Saatte iki kez uyanır, **4h ve 1h** için tek tur
atar, yeni sinyali Telegram'a yollar, `/durum` komutlarını yanıtlar. Gerçek emir göndermez.

Kurulum (bir kerelik):
1. PR #24'ü `main`'e birleştir (zamanlanmış işler yalnız ana dalda çalışır).
2. GitHub'da repo → **Settings → Secrets and variables → Actions → New repository secret**:
   `TELEGRAM_BOT_TOKEN` (BotFather'ın verdiği) ve `TELEGRAM_CHAT_ID` (panelde Ayarlar → Telegram'da
   "sohbet kimliği" olarak görünür).
3. **Actions** sekmesi → `fuzyon-bulut` → **Run workflow** ile ilk turu elle başlat.

Sınırlar:
- Panel bulutta yoktur; telefondan izleme Telegram üzerindendir.
- GitHub'ın zamanlaması birkaç dakika (yoğun saatlerde daha fazla) gecikebilir; bu yüzden yalnız
  1h ve 4h. Kısa aralıklar için bilgisayar ya da kiralık bir sunucu gerekir.
- `/durum` yanıtı bir sonraki uyanışta gelir (en çok ~30 dk).
- Bulut ile bilgisayardaki servis **ayrı** kâğıt hesaplar tutar. İkisinde de 4h bildirimi açıksa aynı
  sinyal iki kez gelebilir: birinde kapat.
- Repo 60 gün hiç güncellenmezse GitHub zamanlanmış işi durdurur; Actions sekmesinden yeniden açılır.
- Her şeyi (panel dahil) 7/24 çalıştırmak istersen aynı komut Linux sunucuda da çalışır:
  `python -m fusion servis --sessiz`. Sunucu kiralama ve kurulum ayrı bir iştir.

## Komut satırı (isteğe bağlı)
`Fuzyon.bat` menüsü ve `python -m fusion --help` eski tek aralıklı kullanım içindir:
**2** veri indir, **3** backtest + panel, **4** tek aralıkta canlı mod, **7** demo (uydurma veri),
**9** menü komutlarının kullandığı aralığı seç.

## Mum aralığı seçimi (scalp dahil)
Serviste (önerilen) seçim panelin üstündeki düğmelerdedir; her aralığın kâğıt hesapları ayrıdır ve
birbirini etkilemez. Eski menüde **9** aynı işi tek aralık için yapar.

| Aralık | İndirilen geçmiş | Backtest dönemi | Canlı mod başlangıcı |
|---|---|---|---|
| 1m | 30 gün | son 10 gün | son 1 gün |
| 3m | 75 gün | son 25 gün | son 2 gün |
| 5m | 150 gün | son 60 gün | son 3 gün |
| 10m | 300 gün | son 120 gün | son 5 gün |
| 15m | 500 gün | son 240 gün | son 7 gün |
| 30m | 800 gün | son 365 gün | son 14 gün |
| 1h | 1500 gün | son 600 gün | son 21 gün |
| 2h, 4h | 1500 gün | son 730 gün | son 30 gün |
| 1d | 3000 gün | son 1500 gün | son 120 gün |

- 10 dakikalık mum Binance'te yoktur; 5 dakikalık mumlardan toplanarak üretilir.
- Canlı mod açılışta geçmişi bir kez oynatır, sonra her yeni mumda yalnız o mumu işler
  (1 dakikalıkta 5 coinle tur başına yaklaşık 1 saniye + indirme süresi).
- Canlı oturum 60.000 mumu aşınca (1m'de ~42 gün) "yeni sezon" başlar: son tablo
  `out/fusion/sezon_NNN.json` olarak arşivlenir, kâğıt hesaplar baştan başlar.
- Panelin üstündeki **maliyet ≈ işlem başına … R** rozeti ve backtest tablosunun altındaki satır,
  seçtiğin aralıkta gidiş-dönüş maliyetinin 2 ATR'lik stopa oranını gösterir. 0,15 R üstü kırmızıdır.

**Scalp için bilinmesi gerekenler:**
- Ölçülen: 15 dakikada maliyet işlem başına 0,16–0,24 R; 8 stratejinin 8'i son 1 yılda ekside.
  Daha kısa aralıkta stop mesafesi küçüldüğü için oran daha da büyür (5m ve 1m için henüz veri
  indirilmedi; rozet indirdikten sonra gerçek değeri gösterir).
- Bot emir göndermez. 1–5 dakikalık sinyal mum kapanışından birkaç saniye sonra gelir; bunu elle
  yakalamak pratikte mümkün değildir. Kısa aralık bu haliyle kâğıt üstünde izleme içindir.
- Tek seferlik deneme için dosyayı değiştirmeden: `python -m fusion backtest --aralik 5m`.

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
- Hesap %25 düşerse aralığa göre 1–14 gün (4h'de 7 gün) yeni giriş almaz.
- Canlı kâğıt mod ilk açılışta yakın geçmişi (4h'de son 30 gün) oynatarak başlar; sinyaller yalnız
  yeni mumlar için iletilir.
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
Başka aralık için menüde **9** (bkz. "Mum aralığı seçimi"). Gösterge periyotları bar sayısıdır;
aralık değişince süre karşılıkları da değişir.

## Ayarlar
`Fuzyon.bat → 8` kökte `fuzyon_ayar.json` oluşturur (semboller, aralık, sermaye, risk, komisyon,
short, DD sınırı, `takip`, `webhook_url`, port). Telegram için kökteki `.env` dosyasına
`TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` yaz. `takip`: `"hepsi"`, `"lider"` ya da bir strateji adı.

## Çıktılar (`out/fusion/<aralık>/`)
Her aralığın kendi klasörü vardır: `durum_canli.json`, `durum_backtest.json` (panel bunları okur) ·
`islemler_backtest.csv`, `ozsermaye_backtest.csv` (Excel'de açılır; kendi kâr/zarar analizin için) ·
`sinyaller.jsonl` · `canli.json` (canlı oturumun başlangıcı). Ortak: `out/fusion/servis.json`
(hangi aralık açık), `servis.log`.
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
