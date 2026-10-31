# Backtest Raporu — 6 Temmuz 2026

**Veri: GERÇEK piyasa verisi.** Bitstamp BTC/USD, 1 dakikalık mumlardan 15M + 4H
resample (kaynak: github.com/ff137/bitstamp-btcusd-minute-data, günlük güncellenen depo).
Dönem: **7 Ocak 2025 → 6 Temmuz 2026** (18 ay, 52.326 × 15M bar, boşluksuz).
Maliyetler dahil: maker %0.02 (entry+target), taker %0.055 (stop), slippage %0.01.

## Ana Sonuçlar

| Metrik | Session filtresi AÇIK | KAPALI | Kabul eşiği |
|---|---|---|---|
| İşlem sayısı | 68 | 262 | ≥ 300 |
| Win rate | %39.7 | %35.1 | — |
| Profit Factor | **1.035** | 0.847 | > 1.3 |
| Expectancy | +0.031R | −0.115R | > 0 |
| Max Drawdown | %7.9 | %19.0 | < %15 |
| Sharpe | 0.14 | −0.96 | > 1.0 |
| Son bakiye (10k$) | 10.086$ | 8.544$ | — |

Monte Carlo (SF açık): p95 DD = 18.4R (≈ %9.2 hesap), en kötü 30R.

## Walk-Forward (70/30, SF açık)

| | In-sample (Oca 25–Oca 26) | Out-of-sample (Oca–Tem 26) |
|---|---|---|
| İşlem | 47 | 19 |
| PF | 0.81 | 1.74 |
| Expectancy | −0.15R | +0.43R |

## KARAR: PAPER TRADING'E GEÇİLMEZ ❌

Sistemin kendi kuralları (Strategy Bible §8) net: PF 1.035 < 1.3 ve 68 işlem < 300.
Bu, doğrulama sürecinin İSTENDİĞİ GİBİ çalıştığını gösterir — zayıf strateji
canlıya çıkmadan yakalandı.

## Bulgular

1. **Session filtresi kesin fayda sağlıyor:** Filtresiz sistem net kaybediyor
   (PF 0.85, off-hours expectancy −0.55R). London KZ en iyi dilim (+0.16R).
2. **Strateji maliyetten sonra ancak başabaş:** Ortalama kazanç 1.91R (hedef 2R,
   fark = maliyet), ortalama kayıp −1.21R. WR %39.7 ile denge sınırında.
3. **68 işlem istatistiksel karar için YETERSİZ.** OOS'taki PF 1.74 umut verici
   ama 19 işlemle gürültüden ayırt edilemez.
4. Dönem notu: 18 aylık dilim güçlü düşüş rejimi içeriyor (BTC 102k$ → 64k$).
   Tek rejim = tek yönlü test.

## Ek Test: Volume Konfirmasyonu (6 Tem, aynı gün)

Knowledge base'deki "sweep + hacim spike = kurumsal" kuralı yapısal filtre
olarak eklendi (sweep barı hacmi ≥ 1.5× MA20; eşik knowledge base'den,
backtest'e göre ayarlanmadı):

| Metrik | VF kapalı | VF açık |
|---|---|---|
| İşlem | 68 | 51 |
| Win rate | %39.7 | %43.1 |
| PF | 1.035 | **1.213** |
| Expectancy | +0.031R | **+0.149R** |
| Max DD | %7.9 | **%3.3** |
| MC p95 DD | 18.4R | 13.4R |

Tek ve önceden kayıtlı bir hipotez testiydi; her metriği iyileştirdi.
PF hâlâ 1.3 eşiğinin altında ve 51 işlem istatistiksel karar için az —
karar değişmedi (paper trading'e geçilmez), ama yön doğru.

## Sonraki Adımlar (önerilen sıra)

1. **Örneklemi büyüt:** Kendi makinende `python scripts/download_data.py 2020-01-01`
   ile Binance'ten 6+ yıllık BTC + ETH verisi indir (bu depo sadece BTC ve Oca 2025
   sonrasını veriyordu). 300+ işlemle tablo netleşir.
2. ~~Volume konfirmasyonu ekle~~ ✅ Eklendi ve test edildi (yukarıda).
   Genişletilmiş veride `use_volume_filter=True` ile tekrar koşulacak.
3. Kriterler geçilirse → Pine'ı TradingView'a kur → paper trading.

*Rapor `run_backtest.py` yerine bire bir aynı motorla interaktif üretildi;
ham çıktı: `reports/backtest_report.json`.*
