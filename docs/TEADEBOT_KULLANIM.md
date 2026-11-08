# TradeBot — Kullanım Kılavuzu (Burak için)

**Bu program gerçek parayla otomatik işlem YAPMAZ.**
Şu an sadece "paper" (kâğıt) modunda çalışıyor: borsadan sadece fiyat okur,
emirleri simüle eder. Gerçek para için ek adımlar gerekir (aşağıda §7).

---

## 0. Tek cümleyle

`TradeBot.bat` dosyasına çift tıklayın, menüden seçim yapın. Program geri
kalanını yapar.

---

## 1. Bilgisayarınızda ne olmalı?

| Gereken | Nasıl kontrol edilir |
|---|---|
| Windows 10 veya 11 | Zaten varsun ✓ |
| Python 3.11+ | `py --version` yazıp bakın. "Python was not found" derse kurun: <https://www.python.org/downloads/> → kurarken **"Add Python to PATH"** kutusunu işaretleyin |

---

## 2. İlk kurulum (sadece bir kez)

Proje klasöründe **`1_kurulum.bat`** dosyasına çift tıklayın.

Ne yapar:
- Gerekli kütüphaneleri kurar (pandas, numpy, ccxt, fastapi...).
- Sonra "kurulum kontrolu" yapar ve eksikleri söyler.

Bittiğinde ekranda **"KURULUM TAMAM"** yazar.

> Ekranda Türkçe karakterler bozuk görünüyorsa endişelenmeyin — kod çalışıyor,
> sadece konsol fontu eski. `.bat` dosyaları ASCII'dir, sorun değil.

---

## 3. Veri indirme (bir kez, ~10-20 dakika)

**`2_veri_indir.bat`** dosyasına çift tıklayın.

Ne yapar:
- Binance'den 25 kripto sembolünün **günlük** mum verisini indirir
  (2021-01-01 → bugün).
- Funding (vadeli faiz) oranlarını da indirir.
- Verileri `data/` klasörüne kaydeder. Aynı veri tekrar indirilmez.

Ekranda "25/25 sembol TAMAM" gibi bir mesaj göreceksiniz.

---

## 4. Backtest (geçmiş testi)

**`3_backtest.bat`** dosyasına çift tıklayın.

Ne yapar:
- İndirilen veriyle stratejiyi 2021-2024 arasında "geçmişte" çalıştırır.
- Sonuç raporunu `out/reports/` klasörüne yazar.
- Protokol kapılarını değerlendirir (PF, drawdown, işlem sayısı).

**Önemli:** Bu strateji **tek atış** protokolüyle test edildi ve
**reddedildi** (bkz. §8). Aynı komutu tekrar çalıştırmak yeni bilgi üretmez.
Panelden sadece sonuçları görmek için bakabilirsiniz.

---

## 5. Paper trading (gerçek para yok — asıl çalışma modu)

**`4_paper.bat`** dosyasına çift tıklayın.

Ne yapar:
- Borsadan güncel fiyatları çeker.
- Stratejiyi **baştan** oynatır (backtest ile aynı motor, aynı kod).
- Journal'a yeni işlemleri yazar, Telegram'a bildirim gönderir (varsa).
- Web panelini arka planda başlatır.

**Durdurmak için:** pencereye tıklayıp `Ctrl+C` yapın.

**Ne zaman çalıştırılır?** Bilgisayar açıkken sürekli açık olabilir. Program
günlük mum kapanışını (UTC 00:00) bekler, her yeni gün bir tur oynar.

---

## 6. Web paneli

**`5_panel.bat`** dosyasına çift tıklayın, sonra tarayıcıda açın:

**<http://127.0.0.1:8765>**

Panelde göreceğiniz:
- Üstte: mod, strateji, başlangıç sermayesi
- Kartlar: kapalı işlem sayısı, kazanma oranı, profit factor, beklenen R, equity
- Altta: equity grafiği ve son işlemlerin tablosu

Aynı paneli terminalden de açabilirsiniz:
```
python -m trader panel
```

---

## 7. Gerçek para (ileride — şu an kapalı)

**Testnet kapısı KAPALI.** `sepet_momentum` stratejisi backtest kapısını
geçemediği için testnet ve canlı modları program tarafından engellenir.
Bunu görmek için `6_testnet.bat` çalıştırın — "kapı kapalı" mesajı alırsınız.
Bu **koruma**dır, hata değil.

Gerçek paraya geçmek için gerekenler (protokol sırası):

1. Yeni bir strateji adayı seçilir.
2. Kural seti ve kapı eşiği **sonuç görülmeden** yazılır.
3. Tek atış backtest → **geçerse** hold-out.
4. **300 paper işlemi** (yaklaşık 5-6 yıl sürer, evren 25 sembol).
5. **100 testnet işlemi** (sahte para).
6. **100-500 $** canlı para.

> **Not:** 300 paper işlemi için 5-6 yıl beklemek gerekiyor. Bu yüzden
> "hızlıca testnet'e geçelim" diye kural atlanmaz.

---

## 8. Şu anki stratejinin durumu

| Strateji | Sonuç | Detay |
|---|---|---|
| `sepet_momentum` | **RED** | PF 1,140 (gereken 1,30) · Drawdown %55,20 (tavan %15) |

Program **çalışır durumda** ve paper modunda kendi halinde oynatılabilir;
ama protokol gereği bu strateji testnet'e/canlıya çıkamaz.

Sonuçların tam hikâyesi:
- `docs/KOSU_GECMISI_SEPET_MOMENTUM.md` — dört koşunun tamamı
- `docs/ADAY_DEGERLENDIRME_SEPET_MOMENTUM.md` — kural seti ve sonuç
- `out/reports/` — makine tarafından üretilen raporlar

---

## 9. Terminal kullanmak isterseniz

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

## 10. Sorun giderme

| Belirti | Sebep | Çözüm |
|---|---|---|
| "Python was not found" | Python kurulu değil ya da PATH'te yok | Python kurun, **"Add Python to PATH"** işaretleyin, bilgisayarı yeniden başlatın |
| "No module named 'trader'" | Yanlış klasördesiniz | Proje klasörüne geçin (içinde `trader/` klasörü olmalı) |
| Panel açılmıyor | Panel çalışmıyor | `5_panel.bat` çalıştırın, 5 saniye bekleyin, <http://127.0.0.1:8765> |
| "Veri yok" hatası | Veri indirilmemiş | `2_veri_indir.bat` çalıştırın |
| "kapı kapalı" mesajı | Strateji testnet'e çıkamaz | **Bu normal.** Backtest kapısını geçemedi. |
| Telegram bildirimi gelmiyor | Token yok | `.env` dosyasında `TELEGRAM_TOKEN` ve `TELEGRAM_CHAT_ID` dolu olmalı |
| `pip` hatası | Python PATH sorunu | `py -m pip install -r requirements.txt` deneyin |

---

## 11. Sık sorulanlar

**Gerçek parayla işlem yapıyor mu?**
Hayır. Paper modunda borsadan sadece fiyat okunur, emirler simüle edilir.
Gerçek emir göndermek için testnet kapısının geçilmiş olması gerekir ve
o şu an kapalı.

**Neden bir kripto "kötü" çıktı?**
Program kendi kuralını uyguluyor ve sonucu olduğu gibi gösteriyor. Dört
strateji denendi, dördü de reddedildi. **Bu normal ve değerli** — gerçek
parayla öğrenmek yerine kâğıt üstünde öğrenmek. Kâr garantisi yoktur;
`AGENTS.md` bunu baştan söyler.

**Verileri silersem ne olur?**
`data/` klasörünü silerseniz `2_veri_indir.bat` ile yeniden indirilir.
`out/reports/` ve `reports/` klasörleri **asla silinmez** — tek atış
protokolünün kayıtlarıdır.

**Parametreleri değiştirip tekrar deneyebilir miyim?**
Hayır. "Başarısız stratejiyi ayar çekerek kurtarmak" (curve fitting)
protokolde yasak. Yeni bir strateji ailesi denemek isterseniz önce kural seti
veriye bakılmadan yazılır.

---

## 12. Dosya düzeni (referans)

```
TradeBot.bat          Menü (buradan başlayın)
1_kurulum.bat         Bir kez çalıştır
2_veri_indir.bat      Veriyi indir
3_backtest.bat        Geçmiş testi
4_paper.bat           Paper trading (gerçek para yok)
5_panel.bat           Web paneli
6_testnet.bat         Testnet (kapalıysa açılmaz)

trader/               Program kodu (yeni, tradebot/ dokunulmadan)
  backtest.py         Backtest motoru (deterministik)
  paper.py            Paper motoru
  live.py             Testnet/canlı yürütücü (kapı kapalı)
  dashboard.py        Web paneli
  strategies/         Strateji kuralları
  gates.py            Protokol kapıları
  cli.py              Komut satırı arayüzü

data/                 İndirilen fiyat verisi
out/reports/          Backtest raporları
out/gates.json        Kapı defteri (geçmiş dahil)
docs/                 Kural setleri, kararlar, koşu geçmişi
```
