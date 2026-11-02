# KURULUM — Sıfırdan Demo Bakiyeyle Çalıştırma

> **TARİHSEL BELGE (Temmuz 2026, V1 dönemi).** Bu kılavuz V1 stratejisi için yazıldı;
> V1 sonradan **reddedildi** (V2, Plan B v1 ve V3 de reddedildi — `README.md`).
> Demo çalıştırıcı (`scripts/live_runner.py`) reddedilmiş V1 stratejisini çalıştırır;
> **kullanılmamalı.** Bahsi geçen `2_backtest.bat` / `3_demo_baslat.bat` 2 Kasım 2026'da
> kökten kaldırıldı (git geçmişinde duruyor). Yalnız Adım 1–2 (Python ve
> `1_kurulum.bat`) hâlâ geçerlidir.

Hedef: Bot, Bybit **testnet**'te (sahte para, sıfır risk) kendi kendine
sinyal üretip emir göndersin, Telegram'dan sana haber versin.
TradingView'a GEREK YOK — strateji doğrudan makinende çalışır.

---

## Adım 1 — Python kur (bir kere, 5 dk)

1. https://www.python.org/downloads/ → "Download Python 3.12" indir
2. Kurulumda **"Add python.exe to PATH" kutusunu MUTLAKA işaretle**
3. Kontrol: Başlat → "cmd" → aç → `python --version` yaz → sürüm görünmeli

## Adım 2 — Kütüphaneleri kur (bir kere, 2 dk)

Proje klasöründe `1_kurulum.bat` dosyasına çift tıkla.
(Ya da cmd'de: `pip install -r requirements.txt`)

## Adım 3 — Bybit testnet hesabı + API anahtarı (bir kere, 10 dk)

1. https://testnet.bybit.com → üye ol (gerçek Bybit'ten AYRI, bedava hesap)
2. Hesap otomatik sahte bakiyeyle gelir (gelmezse: Assets → "Request Test Coins")
3. Sağ üst profil → **API** → **Create New Key** → "System-generated API Keys"
   - İzinler: **Contract - Orders & Positions** (okuma+yazma)
   - **Withdraw iznini ASLA verme** (testnette bile alışkanlık olsun)
   - IP kısıtlaması: boş bırakabilirsin (testnet)
4. API Key + Secret'ı kopyala

## Adım 4 — .env dosyası (bir kere, 2 dk)

`.env.example` dosyasını kopyala, adını `.env` yap, doldur:

```
EXCHANGE_ID=bybit
TRADING_MODE=testnet          # DOKUNMA — canlı için Strategy Bible §8 şart
EXCHANGE_API_KEY=buraya_key
EXCHANGE_API_SECRET=buraya_secret
ACCOUNT_BALANCE=10000         # testnet bakiyenle aynı yap
JOURNAL_DB=journal.db

# Opsiyonel ama tavsiye: Telegram bildirimleri
# @BotFather'a "/newbot" yaz → token al
# @userinfobot'a mesaj at → chat id'ni al
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## Adım 5 — Çalıştır

`3_demo_baslat.bat`'a çift tıkla (ya da `python scripts/live_runner.py`).

Göreceklerin:
- Açılışta: `LiveRunner başladı — TESTNET (demo bakiye)` (+Telegram mesajı)
- Her 15 dakikada bir bar kapanışını bekler, taramayı yapar
- Setup oluşursa: limit emir + SL + TP Bybit testnet'e gider,
  Telegram'a "SİNYAL KABUL" düşer, journal.db'ye kaydedilir
- Sinyaller SEYREKTİR (ayda ~3-6 adet/sembol) — saatlerce sessizlik NORMAL
- Durdurmak: pencereyi kapat veya Ctrl+C

Kontrol noktaları:
- Bybit testnet → Derivatives → Orders/Positions'da emirleri gör
- `journal.db` → her sinyal ve işlem kayıtlı (DB Browser for SQLite ile açılır)

## Adım 6 — Paralelde: uzun backtest (kriter kapısı için)

```
2_backtest.bat        (ya da: python scripts/download_data.py 2020-01-01
                              python scripts/run_backtest.py)
```
6+ yıl BTC+ETH gerçek verisi iner (~10 dk), 300+ işlemli sonuç üretir.
Sonucu Claude'a getir → kriter değerlendirmesi birlikte.

---

## Sık Sorulanlar

**Binance testnet kullanabilir miyim?** Evet: `EXCHANGE_ID=binanceusdm`,
anahtarları https://testnet.binancefuture.com adresinden al.

**Bilgisayar kapalıyken çalışır mı?** Hayır. 7/24 için ileride küçük bir
VPS'e taşınır (roadmap Aşama 8'de Docker planı hazır). Şimdilik gerekli değil:
sinyaller killzone saatlerinde (10:00-13:00 ve 16:00-19:00 İstanbul) —
o saatlerde açık kalması yeterli.

**Gerçek paraya ne zaman?** Strategy Bible §8: backtest PF>1.3 + 300 paper +
100 testnet işlem + DD<%15. Şu an backtest kapısındayız. Sıra atlanmaz.

---

## Sorun Giderme (7 Tem güncellemesi)

**"tarama hatası ... asset/coin/query-info"** → Düzeltildi (execution.py:
private fetchCurrencies kapatıldı + recvWindow genişletildi). OneDrive
senkronunu bekleyip botu yeniden başlat. Hâlâ hata varsa artık TAM mesaj
yazacak — onu Claude'a gönder.

**Backtest "MergeError: incompatible merge keys (ms/us)"** → Düzeltildi
(pandas sürüm farkı; tüm zaman indexleri ns'e sabitlendi). `2_backtest.bat`'ı
yeniden çalıştır.

**Daha fazla sembol izlemek** → `.env`'e ekle:
```
LIVE_SYMBOLS=BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT,BNB/USDT:USDT
```
Sinyal sıklığını artırmanın DOĞRU yolu budur (filtre gevşetmek değil).
