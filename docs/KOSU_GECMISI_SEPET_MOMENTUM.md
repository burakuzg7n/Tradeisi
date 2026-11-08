# Koşu geçmişi — Sepet momentum (in-sample)

**Strateji:** `sepet_momentum` · **Aşama:** in-sample · **Evren:** Binance USDT-M perpetual, 25 sembol

Bu dosya, protokole uygun olarak **tüm koşuların** kaydını tutar. Başarısız
koşular silinmez. Kod hatası nedeniyle **geçersiz** olan koşu da burada
belgelenir; "geçersiz" burada "strateji hakkında bilgi vermeyen" anlamına
gelir, "başarılı" anlamına gelmez.

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
kapatıldı. Aşağıdaki koşu, **geçerli tek atış** olarak kabul edilir.

---

## Koşu 2 — 8 Kasım 2026 · **GEÇERLİ TEK ATIŞ (in-sample)**

Sonuç bu dosyanın altına ve `out/reports/` altındaki rapora yazılır.
