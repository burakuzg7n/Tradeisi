# KURULUM — TradeBot'u Sıfırdan Çalıştırma

**Bu kılavuz 8 Kasım 2026'da güncellendi** ve yeni `trader/` programını
kapsar. Adım adım, kod bilmeyenler için yazıldı.

> **En kısa yol:** Proje klasöründe **`TradeBot.bat`** dosyasına çift tıklayın.
> Menü açılır, gerisini program yapar.
>
> Ayrıntılı günlük kullanım kılavuzu: **`docs/TEADEBOT_KULLANIM.md`**

> **ÖNEMLİ:** Program şu an **paper modunda** çalışır — borsadan sadece fiyat
> okur, emirleri **simüle eder**. Gerçek para harcanmaz. Testnet/canlı modları
> protokol kapıları kapalı olduğu için program tarafından reddedilir (bu bir
> güvenlik özelliğidir, hata değildir).

---

## Adım 1 — Python kur (bir kez, 5 dk)

1. <https://www.python.org/downloads/> → "Download Python 3.11+"
2. Kurulumda **"Add python.exe to PATH" kutusunu MUTLAKA işaretle**
3. Kontrol: Başlat → "cmd" → aç → `python --version` yaz → sürüm görünmeli

> Python 3.13 ile geliştirildi ve test edildi (3.11+ çalışır).

## Adım 2 — Kütüphaneleri kur (bir kez, 2-3 dk)

Proje klasöründe **`1_kurulum.bat`** dosyasına çift tıklayın.

Ne yapar:
- `pandas`, `numpy`, `ccxt`, `fastapi`, `uvicorn`, `pytest` kurar
- Ardından `python -m trader kurulum` ile ortam kontrolü yapar ve eksikleri söyler

Bittiğinde ekranda **"KURULUM TAMAM"** yazar.

> Ekranda Türkçe karakterler bozuk görünüyorsa endişelenmeyin: `.bat`
> dosyaları ASCII kodlamayla yazılmıştır (Windows cmd uyumu için), sorun
> yalnızca konsol fontundadır. Program normal çalışır.

Manuel kurulum isterseniz:

```
python -m pip install -r requirements.txt
```

## Adım 3 — Veri indir (bir kez, ~10-20 dk)

**`2_veri_indir.bat`** dosyasına çift tıklayın.

Ne yapar:
- Binance'den 25 kripto sembolünün **günlük** mum (OHLCV) verisini indirir
  (2021-01-01 → bugün)
- Funding (vadeli faiz) oranlarını da indirir
- Verileri `data/` klasörüne kaydeder; **aynı veri tekrar indirilmez**
- Her sembol için boşluk/uyumsuzluk kontrolü yapar, sonucu
  `out/veri_sagligi.json` dosyasına yazar

Ekranda sembol başına `OK` / `UYARI` / `HATA` göreceksiniz. 25/25 `OK` ve
`bosluk=0` ise veri hazırdır.

## Adım 4 — Backtest (geçmiş testi)

**`3_backtest.bat`** dosyasına çift tıklayın.

Ne yapar:
- İndirilen veriyle stratejiyi 2021-01-01 → 2024-12-31 arasında "geçmişte"
  çalıştırır (in-sample)
- Raporu `out/reports/` klasörüne yazar (JSON + Markdown)
- Protokol kapılarını değerlendirir (PF ≥ 1,30 · DD ≤ %15 · işlem ≥ 150)

> **Not:** `sepet_momentum` stratejisi bu aşamada **reddedildi** (PF 1,140 ·
> DD %55,20). Aynı komutu tekrar çalıştırmak yeni bilgi üretmez; protokol
> "tek atış" der. Sonuçları sadece görmek için çalıştırabilirsiniz.

## Adım 5 — Paper trading (gerçek para YOK — asıl çalışma modu)

**`4_paper.bat`** dosyasına çift tıklayın.

Ne yapar:
- Borsadan güncel fiyatları çeker
- Stratejiyi **baştan** oynatır (backtest ile **aynı** motor, **aynı** kod)
- Journal'a yeni işlemleri yazar, Telegram'a bildirim gönderir (varsa)
- Web panelini arka planda başlatır

**Durdurmak için:** pencereye tıklayıp `Ctrl+C` yapın.

**Ne zaman çalıştırılır?** Bilgisayar açıkken açık olabilir. Program günlük
mum kapanışını (UTC 00:00) bekler, her yeni gün bir tur oynar.

## Adım 6 — Web paneli

**`5_panel.bat`** dosyasına çift tıklayın, 5 saniye bekleyin, tarayıcıda açın:

**<http://127.0.0.1:8765>**

Panelde göreceğiniz: mod ve strateji, kapalı işlem sayısı, kazanma oranı,
profit factor, beklenen R, equity grafiği ve son işlemlerin tablosu.

## Adım 7 — Telegram bildirimleri (isteğe bağlı)

1. Telegram'da `@BotFather`'a yazıp `/newbot` gönderin → **token** alın
2. `@userinfobot`'a mesaj atın → **chat id**'nizi öğrenin
3. `.env.example` dosyasını kopyalayıp adını `.env` yapın ve şunları doldurun:

```
TELEGRAM_BOT_TOKEN=<botfather_token>
TELEGRAM_CHAT_ID=<chat_id>
```

> `.env` dosyası **asla commit edilmez** ve kimseyle paylaşılmaz. Zaten
> `.gitignore` içindedir.

## Adım 8 — Testnet (şu an KAPALI — ileride)

Testnet, borsanın **sahte parayla** çalışan test ortamıdır. Gerçek para
riski yoktur, ama bir strateji **yalnız** protokol kapılarını geçerse
çalışabilir.

Protokol sırası:

```
Backtest kapısı GEÇTİ → Hold-out kapısı GEÇTİ → 300 paper işlem
→ 100 testnet işlem → 100-500 $ canlı para
```

`sepet_momentum` backtest kapısını geçemediği için `6_testnet.bat` şu an
"kapı kapalı" mesajı verir ve emir göndermez. **Bu doğru davranıştır.**

Yine de ileride bir strateji geçerse, testnet kurulumu şöyle:

1. **Bybit testnet hesabı:** <https://testnet.bybit.com> → üye ol (gerçek
   Bybit'ten ayrı, bedava hesap). Sahte bakiye gelmezse: Assets →
   "Request Test Coins"
2. Profil → **API** → **Create New Key** → "System-generated API Keys"
   - İzinler: **Contract - Orders & Positions** (okuma + yazma)
   - **Withdraw iznini ASLA vermeyin** (testnette bile)
   - IP kısıtlaması testnette boş bırakılabilir
3. API Key + Secret'ı kopyalayın, `.env` dosyasına yazın:

```
TRADING_MODE=testnet          # 'live' YAZMAYIN
EXCHANGE_ID=bybit
EXCHANGE_API_KEY=...
EXCHANGE_API_SECRET=...
TRADER_MODE=testnet
```

4. `6_testnet.bat` dosyasına çift tıklayın.

Binance testnet isterseniz: `EXCHANGE_ID=binanceusdm`, anahtarlar
<https://testnet.binancefuture.com> adresinden alınır.

---

## Sık Sorulanlar

**Binance testnet kullanabilir miyim?** Evet — `EXCHANGE_ID=binanceusdm`,
anahtarlar `https://testnet.binancefuture.com` adresinden.

**Bilgisayar kapalıyken çalışır mı?** Hayır. İleride küçük bir VPS'e taşınır.
Şimdilik gerekmiyor: strateji günlük mum kapanışını (00:00 UTC) bekler.

**Gerçek paraya ne zaman?** `AGENTS.md`: backtest PF > 1,3 + DD < %15 + 150+
işlem → hold-out → 300 paper → 100 testnet → 100-500 $ canlı. Sıra atlanmaz.

**Neden hiçbir strateji geçemedi?** 5 strateji denendi, 5'i de reddedildi
(`README.md`). Bu **normal ve değerli**: gerçek parayla öğrenmek yerine kâğıt
üstünde öğrenmek. Kâr garantisi yoktur.

**Parametreleri değiştirip tekrar deneyebilir miyim?** Hayır. "Başarısız
stratejiyi ayar çekerek kurtarmak" (curve fitting) protokolde yasak.

**Verileri silersem ne olur?** `data/` klasörünü silerseniz `2_veri_indir.bat`
ile yeniden indirilir. `out/reports/`, `out/gates.json` ve `reports/` klasörleri
**asla silinmez** — tek atış protokolünün kayıtlarıdır.

---

## Sorun Giderme

| Belirti | Sebep | Çözüm |
|---|---|---|
| "Python was not found" | Python kurulu değil ya da PATH'te yok | Python kurun, **"Add Python to PATH"** işaretleyin, bilgisayarı yeniden başlatın |
| "No module named 'trader'" | Yanlış klasördesiniz | Proje klasörüne geçin (içinde `trader/` klasörü olmalı) |
| "No module named 'pandas'" | Kütüphaneler kurulmamış | `1_kurulum.bat` çalıştırın |
| Panel açılmıyor | Panel çalışmıyor | `5_panel.bat` çalıştırın, 5 saniye bekleyin, <http://127.0.0.1:8765> |
| "Veri yok" hatası | Veri indirilmemiş | `2_veri_indir.bat` çalıştırın |
| "kapı kapalı" mesajı | Strateji testnet'e çıkamaz | **Normal.** Backtest kapısını geçemedi; bu koruma mekanizması. |
| "Unclosed client session" uyarısı | Borsa oturumu kapatılmamış | Program düzeltildi; eski sürümü kullanıyorsanız güncelleyin |
| Türkçe karakterler bozuk | Konsol fontu eski | Sorun değil; `.bat` dosyaları ASCII'dir, program çalışır |
| Telegram bildirimi gelmiyor | Token yok | `.env` içinde `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` dolu olmalı |
| `pip` hatası | Python PATH sorunu | `py -m pip install -r requirements.txt` deneyin |

---

## Komut satırından (isteğe bağlı)

Proje klasöründe "cmd" veya "PowerShell" açın:

| Ne yapmak | Komut |
|---|---|
| Kurulum kontrolü | `python -m trader kurulum` |
| Veri indir | `python -m trader veri` |
| Backtest | `python -m trader backtest --strategy sepet_momentum --exchange binance --start 2021-01-01 --end 2024-12-31 --stage insample --equity 10000` |
| Paper (tek tur) | `python -m trader paper --strategy sepet_momentum --once` |
| Paper (sürekli) | `python -m trader paper --strategy sepet_momentum` |
| Web paneli | `python -m trader panel` |
| Anlık durum | `python -m trader durum` |
| Protokol kapıları | `python -m trader kapilar` |
| Testler | `python -m pytest tests/ -q` |

---

## Dosya düzeni (referans)

```
TradeBot.bat          Menü (buradan başlayın)
1_kurulum.bat         Bir kez çalıştır
2_veri_indir.bat      Veriyi indir
3_backtest.bat        Geçmiş testi
4_paper.bat           Paper trading (gerçek para yok)
5_panel.bat           Web paneli
6_testnet.bat         Testnet (kapı kapalıysa açılmaz)

trader/               Program kodu (tradebot/ dokunulmadan)
data/                 İndirilen fiyat verisi
out/                  Çalışma çıktıları (reports/, gates.json, trader.db)
reports/              ARŞİV — silinmez, değiştirilmez
docs/                 Kural setleri, kararlar, koşu geçmişi
```

---

## Tarihsel not

Bu kılavuzun Temmuz 2026 sürümü, **reddedilmiş V1 stratejisi** için
`scripts/live_runner.py` (Bybit testnet demo çalıştırıcı) ve
`2_backtest.bat` / `3_demo_baslat.bat` dosyalarını anlatıyordu. Bu dosyalar
2 Kasım 2026'da kökten kaldırıldı (git geçmişinde duruyor) ve
`scripts/live_runner.py` **kullanılmamalıdır** — reddedilmiş V1 stratejisini
çalıştırır. Bugünkü program `trader/` paketindedir ve `TradeBot.bat` menüsü
ile çalışır.
