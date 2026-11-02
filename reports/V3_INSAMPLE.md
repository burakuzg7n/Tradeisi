# V3 — IN-SAMPLE (2021-2024): **KALDI**

Koşu: 2026-11-02T12:26:34+00:00 · Dönem: 2021-01-01 → 2024-12-31 (dahil)

## Kapılar (önceden sabit, spec §7)
- ❌ PF > 1.3
- ✅ işlem >= 1300
- ❌ günlük ortalama > 0.0
- ❌ HAC t > 2.0 (nan → KALDI)
- ❌ DD < %30
- ✅ sermaye tükenmedi

## Portföy (XRP/DOGE/ADA/AVAX/LINK, ortak hesap, %1 risk, maliyetler dahil)
- Profit factor: **0.9125402587086651**
- İşlem: **3201** (long 1614 / short 1587)
- Max DD (15m MTM): **%95.39**
- Günlük seri: 1461 gün, ortalama -0.000624, HAC SE 0.000457 (L=7), **t = -1.3645264045169292**
- Beklenti -0.061 R · kazanma %38.0 · günlük ortalama R (bilgi) -0.1346
- 10000 → 883 (net -9117.43) · ücret 7959.01 · funding 695.99
- Çıkışlar: {'target': 657, 'stop': 1532, 'time_exit': 1012}
- Sayaçlar: {'orders': 3201, 'orders_cancelled_missing_fill_bar': 0, 'orders_skipped_busy': 0, 'orders_blocked_no_capital': 0, 'gap_through_stop': 0, 'gap_stop': 0, 'gap_target': 0, 'stop': 1532, 'target': 657, 'time_exit': 1012, 'time_exit_deferred': 0, 'mtm_carried_marks': 0, 'orders_pending_at_end': 0}
- Sermaye tükendi: False

## Yıl (muhasebe günü yılı; bilgi, kapı değil)
| Yıl | İşlem | PF | Net $ |
|---|---:|---:|---:|
| 2021 | 922 | 1.0048262248852435 | 293.27 |
| 2022 | 831 | 0.7556176603107839 | -7051.03 |
| 2023 | 652 | 0.82068712353992 | -1498.85 |
| 2024 | 796 | 0.8626963003051287 | -860.82 |

## Sembol (bilgi)
| Sembol | İşlem | PF | Net $ |
|---|---:|---:|---:|
| ADAUSDT | 661 | 0.8904792534659579 | -2320.0 |
| AVAXUSDT | 702 | 0.9129430795748636 | -1957.51 |
| DOGEUSDT | 599 | 0.899932353708287 | -1963.3 |
| LINKUSDT | 692 | 0.9461229027609523 | -1223.83 |
| XRPUSDT | 547 | 0.9094046800168651 | -1652.79 |

## Tekrar üretilebilirlik
- Parmak izi `9abf96b1db7183bf…` · git 54fdfba039cfa6328c647c31d901e38200621a6e
- Kilit öncesi değişmiş dosyalar: []
- Veri sha256: XRPUSDT `84501b971273…`, DOGEUSDT `685be21bc499…`, ADAUSDT `73470c7d5993…`, AVAXUSDT `ed74df70c982…`, LINKUSDT `2a219b01dc43…`
- Python 3.13.14, pandas 3.0.3
- Ham sonuç arşivi (sha256 mühürlü raporda): `V3_INSAMPLE_islemler.csv`, `V3_INSAMPLE_gunluk.csv`, `V3_INSAMPLE_equity.csv`

## Notlar
- Sunuş (§2): yeni sembollerde önceden kaydedilmiş test; tam bağımsız piyasa kanıtı değildir.
- DD 15 dakikalık kapanış MTM equity'sinden ölçülür; mum içi en kötü an görünmez. %30 DD sınırı gerçek işlemde bir durma garantisi değildir.
- İstatistik ölçütü günlük seri r_d (tüm günler) üzerinde Newey–West HAC t'dir; %80 gücü garanti etmez. 1.300 işlem bir kapsam kararıdır.
- Maliyet modeli (slippage %0,03, funding %0,01/an) sabit varsayımdır; üst sınır değildir.

> Kural: sonuç kapılarla raporlanır, süslenmez. KALDI ise V3 REDDEDİLDİ, parametre kurcalanmaz. GEÇTİ tek başına canlıya geçiş hakkı vermez (docs/V3_DOGRULAMA_PLANI.md).
