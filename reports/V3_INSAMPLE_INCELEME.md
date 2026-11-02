# V3 in-sample — sonuç incelemesi (yalnız arşivden)

**Kapsam:** Bu inceleme yeni backtest yapmaz; yalnız mühürlü rapor ve üç ham arşiv
CSV'si okunur. Amaç teşhistir; stratejiyi kurtarma, parametre önerme veya yeni strateji
önerme içermez. Neden ilanı bağımsız denetimden sonra yapılır.

## 1. Mühür, hash ve yeniden hesap

- Rapor mührü (kanonik JSON sha256): **geçerli**
- `V3_INSAMPLE_islemler.csv`: mühürlü sha256 ile eşleşen biçim: **as_is, crlf** (dosyalar Windows'ta CRLF yazıldı; git deposunda LF saklanır)
- `V3_INSAMPLE_gunluk.csv`: mühürlü sha256 ile eşleşen biçim: **as_is, crlf** (dosyalar Windows'ta CRLF yazıldı; git deposunda LF saklanır)
- `V3_INSAMPLE_equity.csv`: mühürlü sha256 ile eşleşen biçim: **as_is, crlf** (dosyalar Windows'ta CRLF yazıldı; git deposunda LF saklanır)

| Ölçü | Arşivden yeniden hesap | Raporda | Eşleşme |
|---|---:|---:|---|
| PF | 0.91254 | 0.91254 | ✓ |
| Max DD | 0.953904 | 0.953904 | ✓ |
| Günlük ortalama | -0.000624054 | -0.000624054 | ✓ |
| HAC SE | 0.000457341 | 0.000457341 | ✓ |
| HAC t | -1.36453 | -1.36453 | ✓ |
| İşlem sayısı | 3201 | 3201 | ✓ |
| Net PnL (işlemler) | -9117.43 | -9117.43 | ✓ |
| Σ r_d × 10.000 | -9117.43 | -9117.43 | ✓ |

HAC: Bartlett, L = 7, T = 1461 gün (işlemsiz günler 0 dahil).

## 2. Equity ve en büyük düşüş

- Başlangıç equity: 10,000.00 $ · son equity: 882.57 $ · en yüksek: 17,034.24 $ (2021-06-26 08:00)
- En büyük düşüş: **%95.39** — zirve 17,034.24 $ (2021-06-26 08:00 UTC) → dip 785.21 $ (2024-12-18 18:30 UTC)
- Bu aralıkta açılıp kapanan işlem: **2739** (tam liste: `V3_INSAMPLE_INCELEME_dd_islemleri.csv`), net -15,291.47 $, kazanma %36.8, ortalama R -0.096
- Çıkış sebepleri (aralık): {'stop': 1332, 'time_exit': 873, 'target': 534}

| Yıl | equity başı | sonu | min | max |
|---|---:|---:|---:|---:|
| 2021 | 10,000 | 10,293 | 8,482 | 17,034 |
| 2022 | 10,293 | 3,242 | 3,025 | 11,045 |
| 2023 | 3,242 | 1,743 | 1,607 | 3,286 |
| 2024 | 1,743 | 883 | 785 | 2,002 |

## 3. Brüt sonuç ve maliyetlerin ayrıştırılması

| Kalem | USD | İşlem başına R (ortalama) |
|---|---:|---:|
| Brüt (slippage öncesi, model) | 3,683.82 | 0.0191 |
| − Model slippage (motorun uyguladığı %0,03) | -4,146.25 | -0.0261 |
| − Ücretler (taker/maker) | -7,959.01 | -0.0501 |
| − Funding | -695.99 | -0.0044 |
| = Net | -9,117.43 | -0.0614 |

Kontrol: brüt − slippage − ücret − funding = -9,117.43 $ (net -9,117.43 $).
**Sınırlama:** slippage, arşivdeki dolum fiyatlarından **modelin sabit formülü** tersine
çevrilerek bulundu; bu, motorun uyguladığı model slippage'ıdır, gerçek piyasa
slippage'ı değildir. Arşivde ham açılış/kapanış fiyatları ayrıca yok.
**Not:** USD toplamları bakiyeye bağlı değişen işlem boyutundan etkilenir (bakiye
düştükçe aynı R daha küçük USD'dir); R sütunu boyuttan bağımsız karşılaştırma içindir.

Brüt R (maliyet öncesi) dağılımı: ortalama 0.0191, medyan -0.5921, std 1.2170; kazanma oranı (brüt) %39.8, (net) %38.0.

## 4. Dağılım (yalnız teşhis; kötü grupları çıkararak strateji kurtarılmaz)

### Yön

| Grup | İşlem | Brüt R ort. | Maliyet R ort. | Net R ort. | Net $ |
|---|---:|---:|---:|---:|---:|
| long | 1614 | -0.0364 | 0.0762 | -0.1125 | -4,891.48 |
| short | 1587 | 0.0755 | 0.0849 | -0.0094 | -4,225.95 |

### Sembol

| Grup | İşlem | Brüt R ort. | Maliyet R ort. | Net R ort. | Net $ |
|---|---:|---:|---:|---:|---:|
| ADAUSDT | 661 | 0.0291 | 0.0852 | -0.0561 | -2,320.00 |
| AVAXUSDT | 702 | 0.0066 | 0.0731 | -0.0664 | -1,957.51 |
| DOGEUSDT | 599 | -0.0008 | 0.0788 | -0.0796 | -1,963.30 |
| LINKUSDT | 692 | 0.0176 | 0.0811 | -0.0636 | -1,223.83 |
| XRPUSDT | 547 | 0.0466 | 0.0854 | -0.0388 | -1,652.79 |

### Çıkış sebebi

| Grup | İşlem | Brüt R ort. | Maliyet R ort. | Net R ort. | Net $ |
|---|---:|---:|---:|---:|---:|
| stop | 1532 | -1.0001 | 0.0901 | -1.0902 | -94,916.99 |
| target | 657 | 2.0499 | 0.0620 | 1.9879 | 74,597.54 |
| time_exit | 1012 | 0.2435 | 0.0780 | 0.1655 | 11,202.01 |

## 5. Önceki reddedilen stratejilerle karşılaştırma (kanıt düzeyi belirtilerek)

| Strateji | TF | İşlem | PF (net) | Beklenti R (net) | DD | Maliyet ayrıştırması |
|---|---|---:|---:|---:|---:|---|
| V1 | 15m/4h | ~800 | 0,78–0,82 | — | — | Yok (YILLIK_ANALIZ: "maliyet sürtünmesi + gürültü profiline uyuyor" — yorum, ölçüm değil) |
| V2 | 15m/4h | 490 | 0.796 | -0.143 | %22.4 | Yok (arşiv tutulmadı) |
| Plan B v1 | 1g | 37 | 5.935 | 3.434 | %20.4 | Ücret 35 $, funding 380 $ (toplamlar; işlem bazında arşiv yok) |
| V3 | 15m | 3201 | 0.913 | -0.061 | %95.4 | Var (bu belge §3) |

**Kanıtlanabilir ortaklıklar:**
- Gün içi (15m) üç stratejinin (V1, V2, V3) üçü de maliyetler dahil PF < 1 verdi (ölçüm).
- Maliyetin brüt sonuca oranı yalnız V3 için ölçülebiliyor (§3); V1/V2 için işlem bazında
  arşiv olmadığından aynı ayrıştırma **yapılamaz**. "Ortak sebep maliyet" iddiası bu
  nedenle V3 dışına genellenemez.
- Plan B v1 (günlük) farklı biçimde kaldı: net PF > 1 ama işlem sayısı ve DD kapıları.

**Bu belgede yapılmayanlar:** neden ilanı, yeni strateji/parametre önerisi, hold-out,
yeniden backtest. Sonraki adım bağımsız denetimdir.
