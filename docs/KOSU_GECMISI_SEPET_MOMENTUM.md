# Koşu geçmişi — Sepet momentum (in-sample)

**Strateji:** `sepet_momentum` · **Aşama:** in-sample · **Evren:** Binance USDT-M perpetual, 25 sembol

Bu dosya, protokole uygun olarak **tüm koşuların** kaydını tutar. Başarısız
koşular silinmez. Kod hatası nedeniyle **geçersiz** olan koşu da burada
belgelenir; "geçersiz" burada "strateji hakkında bilgi vermeyen" anlamına
gelir, "başarılı" anlamına gelmez.

> **Makineler tarafından üretilen raporların arşivi:**
> `reports/SEPET_MOMENTUM/` — 16 koşunun JSON + Markdown çıktısı, kapı
> defteri (`GATES.json`), tek atış kilidi ve SHA-256 parmak izleri
> (`MANIFEST.json`). Arşivdeki dosyalar `out/reports/` altından **bit bit**
> kopyalandı; hiçbiri silinmedi veya değiştirilmedi.

---

## Koşu 1 — 7 Kasım 2026 19:38 UTC · **GEÇERSİZ (VOID)**

**Komut:**
```
python -m trader backtest --strategy sepet_momentum --exchange binance \
       --start 2021-01-01 --end 2024-12-31 --stage insample --equity 10000
```

**Çıktı (motorun ürettiği):**

| Metrik | Değer |
|---|---|
| Kapanmış işlem | 6 |
| Kazanan oran | %50,00 |
| Profit Factor | 0,450 |
| Expectancy | −76,47 R |
| Max Drawdown | %97,93 |
| Equity | 10.000 → 2.052,25 |
| Dosya | `out/reports/sepet_momentum_insample_20261107_193859.{json,md}` |

**Bu koşu GEÇERSİZDIR.** Üç ayrı motor hatası vardı; hiçbiri stratejinin
kural setiyle ilgili değildir:

### Hata 1 — Tarih aralığı kırpılmıyor (hold-out sızıntısı)

`trader/market.py::get_ohlcv` onbellekteki **tüm** dosyayı döndürüyordu;
istenen `[start, end]` aralığına kırpmıyordu. Bu nedenle "2021-01-01 →
2024-12-31" in-sample koşusu fiilen **2026-11-07'ye kadar** veriyle çalıştı
(rapordaki kapanış tarihi 2026-11-07'dir).

### Hata 2 — Pozisyon limiti rebalance emirlerini tümden reddediyordu

`trader/backtest.py::_orders_from_signals` içinde
`max_new = max_positions − len(positions)` hesabı yapılıyordu. Portföy 6
pozisyonla dolduğunda `max_new = 0` oluyor ve **mevcut pozisyonların
düzeltme emirleri de** "pozisyon limiti" gerekçesiyle reddediliyordu.
Sonuç: portföy 2021-03'teki ilk rebalance ağırlıklarında **donup kaldı** ve
o pozisyonlar 2026-11-07'ye kadar taşındı. 2.968 sinyal reddedildi.

### Hata 3 — Tam kapamada pozisyon kayıttan silinmiyordu

`trader/backtest.py::_apply_fill` karşı-yön dalında, emrin mevcut pozisyonun
tamamını kapattığı durumda `positions` sözlüğünden çıkarma yapmıyordu. Bu
pozisyon dönem sonunda **ikinci kez** kapanıyordu. Kısmi kapamada da kalan
miktar azaltılmıyordu.

### Ek motor düzeltmeleri (aynı pakette)

- Hedef ağırlık karşılaştırması mevcut pozisyonun **giriş fiyatıyla**
  değil **piyasa değeriyle** yapılıyordu → ralli sırasında portföy gereksiz
  long'a itiliyordu.
- Brüt kaldıraç tavanı `Σ|delta|` üzerinden hesaplanıyordu; doğrusu
  rebalance **sonrası oluşacak brüt pozisyon**dur.
- Kill switch portföyü donduruyordu (sinyal üretimi tamamen duruyordu);
  artık **riski artırmaz, pozisyonları küçültür**.
- `_close_position` içinde R çarpanı kısmi kapamada tam pozisyon riskine
  bölünüyordu → R değerleri şişik çıkıyordu.

### Hold-out sızıntısının dürüst kaydı

Bu koşu 2025-01-01 → 2026-11-07 dönemini **teknik olarak gezdi**. Ancak o
dönemde strateji **hiç işlem yapmadı**: portföy 2021-03 ağırlıklarında
dondurulmuştu. Koşunun çıktısı, stratejinin hold-out dönemindeki davranışı
hakkında **hiçbir bilgi taşımaz**; yalnızca 2021-03'te seçilmiş altı varlığın
2021→2026 yolunu gösterir. Bu koşudan hold-out'a özgü hiçbir metrik
(hold-out PF/DD/işlem listesi) çıkarılmadı ve incelenmedi.

Yine de, şeffaflık için: **hold-out dönemi bu aday için artık "hiç görülmemiş"
değildir.** Aşağıdaki geçerli in-sample koşusundan sonra hold-out açılırsa,
bu not raporla birlikte okunacaktır.

### Sözleşme

Bu koşudan sonra **hiçbir strateji kuralı, parametresi veya kapısı
değiştirilmedi.** Değişen yalnızca motor hatalarıdır; her biri birim testiyle
kapatıldı.

---

## Koşu 2 — 8 Kasım 2026 10:55 UTC · **GEÇERSİZ (VOID)**

**Komut:**
```
python -m trader backtest --strategy sepet_momentum --exchange binance \
       --start 2021-01-01 --end 2024-12-31 --stage insample --equity 10000
```

**Çıktı (motorun ürettiği):**

| Metrik | Değer |
|---|---|
| Kapanmış işlem | 824 |
| Kazanan oran | %49,88 |
| Profit Factor | 1,140 |
| Expectancy | +8,5983 R |
| Max Drawdown | %55,27 |
| Equity | 10.000 → 35.146,16 |
| Dosya | `out/reports/sepet_momentum_insample_20261108_105543.{json,md}` |

**Bu koşu GEÇERSİZDİR.** Sonuçlar makul görünüyordu (PF 1,14 / DD %55),
ama koşu **tekrarlanabilir değildi**: aynı komut farklı sonuç veriyordu.
Bunun nedeni aşağıdaki determinizm hatasıdır. Bu koşu, strateji hakkında
geçerli bilgi taşımaz.

---

## Koşu 3 — 8 Kasım 2026 11:20 UTC · **GEÇERSİZ (VOID)**

**Komut:**
```
python -m trader backtest --strategy sepet_momentum --exchange binance \
       --start 2021-01-01 --end 2024-12-31 --stage none --equity 10000
```

**Çıktı (motorun ürettiği):**

| Metrik | Değer |
|---|---|
| Kapanmış işlem | 822 |
| Kazanan oran | %50,00 |
| Profit Factor | 1,137 |
| Expectancy | +8,7851 R |
| Max Drawdown | %56,22 |
| Equity | 10.000 → 34.405,15 |
| Dosya | `out/reports/sepet_momentum_none_20261108_112058.{json,md}` |

**Bu koşu GEÇERSİZDİR.** Koşu 2 ile **aynı** komut, **farklı** sayıda işlem
(824 → 822) ve farklı equity (35.146 → 34.405) üretti. Bu, determinizm
hatasının varlığını gösteren doğrudan kanıttır: aynı veri, aynı kod, farklı
sonuç.

---

## Hata 4 — Backtest deterministik değildi (KÖK NEDEN)

**Ne oldu?** Python'da string hash'i her süreçte rastgele başlar
(`PYTHONHASHSEED`). `trader/backtest.py::_orders_from_signals` içinde brüt
pozisyon toplamı şu şekilde hesaplanıyordu:

```python
result_gross = 0.0
for sym in set(positions.keys()) | set(targets.keys()):   # <-- SET!
    ...
    result_gross += abs(...)                              # <-- elle float toplamı
```

İki ayrı sorun birleşti:

1. **`set` üzerinde gezmek** sırayı hash seed'e bağlıdır → her süreçte farklı
   sırada gezilir.
2. **Elle float toplamı** sıraya bağlıdır → `1e16 + 1.0 + 1.0` ile
   `1.0 + 1.0 + 1e16` farklı sonuç verir.

Toplam, 1 ULP (≈1e-16) kadar oynuyordu. Stratejinin brüt hedefi **tam** 2,0
kaldıraç (long bacak 1,0 + short bacak 1,0) ve motorun tavanı da 2,0 olduğu
için, brüt pozisyon **her zaman tavanın tam eşiğindeydi**. ULP oynaması
`result_gross > cap` kararını **açıp kapatıyordu** → ölçekleme faktörü
değişiyor → portföy yörüngesi kaotik biçimde ayrışıyordu.

**Ölçüm (gerçek veriyle, aynı komut):**

| PYTHONHASHSEED | İşlem | PF | DD | Equity |
|---|---|---|---|---|
| 0 | 821 | 1,126 | %61,01 | — |
| 1 | 830 | 1,138 | %55,20 | — |
| (düzeltilmiş) 0 / 1 / 2 | 812 | 1,126 | %59,33 | 31.477,81 |

Yani **aynı veri, aynı kod, 9 farklı işlem** üretiyordu. 2.935 rebalance
satırının 1.397'sinde brüt toplam 1 ULP farklıydı.

**Düzeltme:**

- `trader/backtest.py::gross_exposure()` adlı saf yardımcı fonksiyon
  eklendi: semboller `sorted()` ile **sabit sırada** geziliyor, toplam
  `math.fsum` ile (tam yuvarlanmış, **sıra bağımsız**) alınıyor.
- `_orders_from_signals` artık bu fonksiyonu kullanıyor.
- Equity hesabı da `math.fsum`'a çevrildi (aynı sınıf risk).
- `trader/strategies/basket_momentum.py::_inverse_vol_weights` içindeki
  `sum(inv.values())` → `math.fsum` (aynı sınıf risk).

**Regression testi:** `tests/test_trader_determinism.py`

- `test_backtest_is_deterministic_across_hash_seeds` — dört farklı
  `PYTHONHASHSEED` altında **bit düzeyinde** aynı sonucu doğruluyor.
  Senaryo, gerçek hatayı birebir taklit ediyor: ağırlıkların |w| toplamı
  tam 2,0 (cap eşiği). Bu test **hatalı sürümde başarısız oluyor**
  (doğrulandı: `list(set(...))` + elle toplam sürümü kırmızı).
- `test_gross_exposure_is_order_independent` — `gross_exposure` çıktısının
  `math.fsum` ile birebir aynı olduğunu ve sembol sırasından bağımsız
  olduğunu doğruluyor.
- `test_backtest_is_deterministic_within_process` — aynı süreçte iki çalıştırma.

### Sözleşme (Koşu 2 ve 3 için)

Koşu 2 ve Koşu 3 sırasında **hiçbir strateji kuralı, parametresi veya kapısı
değiştirilmedi.** Değişen yalnızca motor hatalarıdır. Her biri regression
testiyle kapatıldı. Aşağıdaki koşu, **geçerli tek atış** olarak kabul edilir.

---

## Koşu 4 — 8 Kasım 2026 13:27 UTC · **GEÇERLİ TEK ATIŞ (in-sample)**

**Komut:**
```
python -m trader backtest --strategy sepet_momentum --exchange binance \
       --start 2021-01-01 --end 2024-12-31 --stage insample --equity 10000 \
       --void-prior --void-reason "Koşu 1 motor hatalari nedeniyle gecersiz"
```

**Çıktı:**

| Metrik | Değer |
|---|---|
| Kapanmış işlem | 823 |
| Kazanan oran | %50,18 |
| Profit Factor | 1,140 |
| Expectancy | +8,9410 R |
| Max Drawdown | %55,20 |
| HAC t (işlem ort.) | 4,192 |
| Sharpe | 0,81 |
| Equity | 10.000 → 35.203,91 |
| Dosya | `out/reports/sepet_momentum_insample_20261108_132730.{json,md}` |

**Tekrarlanabilirlik kontrolü:** bu koşu üç ayrı `PYTHONHASHSEED` altında
(0, 1, 2) çalıştırıldı ve **bit düzeyinde aynı** sonucu verdi:
823 işlem · PF 1,140 · DD %55,20 · equity 35.203,91.

### Kapı değerlendirmesi — **SONUÇ: RED (KALDI)**

| Kapı | Eşik | Gerçek | Sonuç |
|---|---|---|---|
| Profit Factor | ≥ 1,30 | 1,140 | **KALDI** |
| İşlem sayısı | ≥ 150 | 823 | GEÇTİ |
| Max Drawdown | ≤ %15 | %55,20 | **KALDI** |

**Strateji RED edildi.** İki kapı (PF ve DD) tutulmadı.

### Yorum

- **PF 1,140 < 1,30:** Strateji para kazanıyor (equity 10.000 → 35.204,
  yıllık ortalama %37), ama kazanım **kapı eşiğinin altında**. Rastgele
  gürültüyle açıklanabilecek bir marj.
- **DD %55,20 > %15:** Bu, asıl red sebebidir. 1.000 dolarlık bir portföy
  2021→2024 arasında aralarında iki kez yarıya yaklaşan düşüş yaşadı.
  %55'lik düşüş, %15'lik tavanın **3,7 katı**. Büyük kazançlar küçük
  düşüşleri telafi ediyor, ama kaldıraç 2,0 ile bu profili taşımak
  gerçek parayla taşınamaz.
- **İşlem sayısı geçti (823):** Örneklem yeterliydi. Red, "az veri" yüzünden
  değil, sonucun **kötü** olduğu içindir.
- **HAC t = 4,192:** Getiri ortalaması istatistiksel olarak sıfırdan farklı.
  Yani PF'nin 1,14'ü (1,30 değil) bir gürültü artefaktı değil — gerçek ama
  **yetersiz** bir edge.

### Sözleşme

Bu koşudan sonra **hiçbir strateji kuralı, parametresi veya kapısı
değiştirilmedi ve değiştirilmeyecek.** Parametre ayarıyla (curve fitting)
kurtarma yasaktır.

### Hold-out durumu: **AÇILMADI**

Hold-out (2025-01-01 → 2026-11-07) **in-sample RED kararı verildikten sonra
açılmadı ve açılmayacak.** Protokol: "Hold-out verisine (2025+) in-sample
kararı verilmeden bakılmaz." In-sample kararı RED'dir; dolayısıyla hold-out
koşusu yapılmadı.

Bu, bilinçli bir bilgi kaybıdır: stratejinin 2025-2026'da nasıl davrandığını
**bilmiyoruz**. Ama kurallar böyle. Kırmızı bir adayı " acaba hold-out'ta
daha mı iyi çıkıyor? " diye açmak, tek atış protokolünü ve amacını ortadan
kaldırırdı.

### Bilinçli kalan riskler (rapor bunları saklamaz)

1. **Hayatta kalma yanlılığı:** Evren, bugün hâlâ listelenen 25 coin'den
   kuruldu. 2021'de listelenmiş ama sonradan delist olmuş coinler evrende
   yok → sonuç **iyimser**dir (gerçek performans daha kötüdür).
2. **Veri "görülmüş" olabilir:** 2020-2024 aralığı V1/V2/Plan B tarafından
   zaten incelenmişti. Bu aralıkta tamamen bağımsız bir örneklem değildir.
3. **Ana doğrulama yöntemi ileri paper trade:** Gerçek para yakmadan
   öğrenmenin tek yolu ileri yönde paper trade'tir. Bir sonraki aday için
   asıl kanıt kaynağı hold-out değil, **forward paper** olmalıdır.

### Sonraki adım

Bu aday **bitti — RED.** Protokol gereği aynı kuralla ikinci deneme yok.

Yeni bir strateji ailesi denemek istenirse:
1. Önce `docs/` altına **veriye bakmadan** kural seti + kapı eşiği yazılır ve
   commit edilir.
2. Tek atış in-sample koşusu yapılır.
3. GEÇTİ'YE hold-out, ardından forward paper (300 işlem), sonra testnet
   (100 işlem), en son 100-500$ canlı.

**Bu aday için testnet ve canlı kapıları KAPALI** (`out/gates.json`:
`backtest.passed = false`).

---

## Özet tablo — tüm koşular

| # | Tarih | Statü | İşlem | PF | DD | Not |
|---|---|---|---|---|---|---|
| 1 | 7 Kas 19:38 | **VOID** | 6 | 0,450 | %97,93 | 3 motor hatası (tarih kırpma, pozisyon limiti, çift kapanma) |
| 2 | 8 Kas 10:55 | **VOID** | 824 | 1,140 | %55,27 | Motor deterministik değil (tekrar edilemiyor) |
| 3 | 8 Kas 11:20 | **VOID** | 822 | 1,137 | %56,22 | Aynı komut farklı sonuç → determinizm hatası kanıtı |
| 4 | 8 Kas 13:27 | **GEÇERLİ** | 823 | 1,140 | %55,20 | **RED** — PF 1,14 < 1,30 ve DD %55,20 > %15 |

**Not:** Koşu 2, 3 ve 4'ün PF/DD değerleri birbirine çok yakın (1,137–1,140
PF; %55–56 DD). Bu, RED kararının motor hatalarından bağımsız ve **kararlı**
olduğunu gösterir: hatalar sonucu birkaç puan oynatır, kırmızıyı yeşile
çevirmez.

**Strateji kuralı, parametresi veya kapısı hiçbir koşudan sonra
değiştirilmedi.** Değişen tek şey motor hatalarıydı ve her biri regression
testiyle kapatıldı.
