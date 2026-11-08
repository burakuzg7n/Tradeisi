# ARSİV — Sepet momentum (5. aday) · tüm koşu geçmişi

**Bu klasor `AGENTS.md` kural 8 uyarınca arşivdir: hiçbir dosya silinmez,
değiştirilmez veya yeniden adlandırılmaz.** Koşu 1–4'ün **geçersiz (VOID)**
koşuları da dahildir — geçersizlik "başarılı" anlamına gelmez ama
"strateji hakkında bilgi vermez" anlamına gelir ve kayıt tutulur.

Aynı koşu geçmişi okunabilir biçimde: `docs/KOSU_GECMISI_SEPET_MOMENTUM.md`.

## Tek atış kaydı

**Geçerli tek atış:** `sepet_momentum_insample_20261108_132730.{json,md}`
**Kilit:** `SEPET_MOMENTUM_INSAMPLE.lock`

| Kapı | Eşik | Gerçek | Sonuç |
|---|---|---|---|
| Profit Factor | ≥ 1,30 | 1,140 | ❌ KALDI |
| Max Drawdown | ≤ %15 | %55,20 | ❌ KALDI |
| İşlem sayısı | ≥ 150 | 823 | ✅ GEÇTİ |

**Karar: RED.** Hold-out (2025+) **açılmadı**. Parametre ayarlanmadı.

## Koşu 4'ün geçerliliği — determinizm kontrolü

Koşu 4, `trader/backtest.py::gross_exposure()` düzeltmesinden **sonra**
yapıldı ve üç ayrı `PYTHONHASHSEED` (0, 1, 2) altında **bit düzeyinde aynı**
sonucu verdi. Aynı düzeltilmiş motorla yapılan doğrulama koşuları:
`sepet_momentum_none_20261108_131729`, `..._131753`, `..._131818`
(üçü de 823 işlem · PF 1,1405 · DD %55,20 · equity 35.203,91).

## Dosya haritası

| Dosya | Statü | Not |
|---|---|---|
| `sepet_momentum_insample_20261107_193859.*` | **VOID — Koşu 1** | 3 motor hatası (tarih kırpma, pozisyon limiti, çift kapanma) |
| `sepet_momentum_insample_20261108_105543.*` | **VOID — Koşu 2** | Sonuçlar makul ama koşu tekrarlanabilir değildi |
| `sepet_momentum_none_20261108_112058.*` | **VOID — Koşu 3** | Koşu 2 ile aynı komut, farklı sonuç → determinizm hatası kanıtı |
| `sepet_momentum_insample_20261108_132730.*` | **GEÇERLİ TEK ATIŞ — Koşu 4** | **RED** |
| `sepet_momentum_none_20261108_112658.*` | tanılama koşusu | determinizm hatası aranırken (VOID) |
| `sepet_momentum_none_20261108_112709.*` | tanılama koşusu | determinizm hatası aranırken (VOID) |
| `sepet_momentum_none_20261108_112909.*` | tanılama koşusu | seed=1 sonucu (VOID) |
| `sepet_momentum_none_20261108_112930.*` | tanılama koşusu | seed=2 sonucu (VOID) |
| `sepet_momentum_none_20261108_113113.*` | tanılama koşusu | seed=1 tekrar (VOID) |
| `sepet_momentum_none_20261108_113134.*` | tanılama koşusu | seed=2 tekrar (VOID) |
| `sepet_momentum_none_20261108_121909.*` | tanılama koşusu | ara düzeltme denemesi (VOID) |
| `sepet_momentum_none_20261108_121931.*` | tanılama koşusu | ara düzeltme denemesi (VOID) |
| `sepet_momentum_none_20261108_121954.*` | tanılama koşusu | ara düzeltme denemesi (VOID) |
| `sepet_momentum_none_20261108_131729.*` | doğrulama (VOID) | düzeltme sonrası, seed=0 |
| `sepet_momentum_none_20261108_131753.*` | doğrulama (VOID) | düzeltme sonrası, seed=1 |
| `sepet_momentum_none_20261108_131818.*` | doğrulama (VOID) | düzeltme sonrası, seed=2 |
| `GATES.json` | kapı defteri | Geçerli koşunun RED kaydı + Koşu 1'in VOID geçmişi |
| `MANIFEST.json` | parmak izleri | Her dosyanın SHA-256 özeti |
| `SEPET_MOMENTUM_INSAMPLE.lock` | tek atış kilidi | Koşu 4'ün üretim zaman damgası |

## Koşuların metrik özeti

| # | Zaman (UTC) | Statü | İşlem | PF | DD | Equity |
|---|---|---|---|---|---|---|
| 1 | 07 Kas 19:38 | **VOID** | 6 | 0,450 | %97,93 | 2.052,25 |
| 2 | 08 Kas 10:55 | **VOID** | 824 | 1,140 | %55,27 | 35.146,16 |
| 3 | 08 Kas 11:20 | **VOID** | 822 | 1,137 | %56,22 | 34.405,15 |
| 4 | 08 Kas 13:27 | **GEÇERLİ** | 823 | 1,140 | %55,20 | 35.203,91 |

## Bütünlük

`MANIFEST.json` içindeki SHA-256 özetleri, arşivlenen dosyaların özetleridir.
Dosyalar `out/reports/` altından **bit bit** kopyalandı; içerik değiştirilmedi.

## Bilinçli kalan riskler (rapor bunları saklamaz)

1. **Hayatta kalma yanlılığı:** Evren, bugün hâlâ listelenen 25 coin'den
   kuruldu. 2021'de listelenmiş ama sonradan delist olmuş coinler evrende yok
   → sonuç **iyimserdir**.
2. **Veri "görülmüş" olabilir:** 2020-2024 aralığı V1/V2/Plan B tarafından
   zaten incelenmişti → tamamen bağımsız bir örneklem değildir.
3. **Ana doğrulama yöntemi ileri paper trade:** Gerçek para yakmadan
   öğrenmenin tek yolu ileri yönde paper trade'tir.
