# V3 — işlem sıklığı fizibilitesi (SENTETİK veri)

Gerçek fiyat verisi kullanılmadı; PnL/PF/DD raporlanmaz. Varsayımlar:
`tradebot/synthetic_v3.py` (sonuç görülmeden sabit). Dönem uzunluğu: in-sample ile
aynı 48 ay (1.461 gün), 5 sembol, 3 tohum/senaryo.

| σ_günlük | ρ | rejim | 48 ay işlem (min / medyan / maks) | ay başına (medyan) |
|---:|---:|---|---|---:|
| 0.025 | 0.5 | trend | 1818 / 1862 / 1947 | 38.8 |
| 0.025 | 0.5 | yatay | 1802 / 1831 / 1943 | 38.1 |
| 0.025 | 0.8 | trend | 1753 / 1796 / 1861 | 37.4 |
| 0.025 | 0.8 | yatay | 1703 / 1769 / 1938 | 36.9 |
| 0.04 | 0.5 | trend | 4143 / 4203 / 4371 | 87.6 |
| 0.04 | 0.5 | yatay | 4148 / 4154 / 4342 | 86.5 |
| 0.04 | 0.8 | trend | 4100 / 4159 / 4278 | 86.6 |
| 0.04 | 0.8 | yatay | 4052 / 4103 / 4368 | 85.5 |
| 0.06 | 0.5 | trend | 4723 / 4755 / 4929 | 99.1 |
| 0.06 | 0.5 | yatay | 4721 / 4731 / 4891 | 98.6 |
| 0.06 | 0.8 | trend | 4715 / 4727 / 4872 | 98.5 |
| 0.06 | 0.8 | yatay | 4641 / 4726 / 4941 | 98.5 |

**Tüm senaryolar aralığı:** 1703 – 4941 işlem / 48 ay (35.5 – 102.9 / ay).
**İşlem kapısı:** ≥ 1300. Aralığın alt ucu kapının ÜSTÜNDE.

## Gün durumları (tüm senaryolar, sembol-gün başına pay)

| durum | pay |
|---|---:|
| intent | %49.4 |
| no_trigger | %34.3 |
| min_stop | %16.4 |

Not: bu bir model tahminidir; gerçek piyasa rejimleri, oynaklık ve korelasyon bu
aralığın dışına düşebilir. Karar kuralı (§6b): alt uç < 1.300 ise koşu başlamaz;
kural sonuç görülmeden yeni ön-kayıtla değiştirilir (coin/risk eklenmez).
