# Plan B v1 — IN-SAMPLE (2020-2024): **KALDI**

Koşu: 2026-11-01T19:57:52+00:00 · Dönem: 2020-01-01 → 2024-12-31 (dahil)

## Kapılar (önceden sabit, E9 + E16)
- ✅ PF > 1.3
- ❌ işlem >= 100
- ❌ DD < %15
- ✅ sermaye tükenmedi (E16)

## Portföy sonucu (BTC/ETH/SOL/BNB ortak hesap, maliyetler + funding dahil)
- Profit factor: **5.934533994740182**
- İşlem sayısı: **37**
- Max drawdown (günlük MTM, E15): **%20.36**
- Beklenti: 3.434 R · Kazanma oranı: %35.1
- Başlangıç → bitiş: 10000 → 17140 (net 7140.45)
- Ücretler: 34.66 · Funding: 380.02
- Çıkış sebepleri: {'channel_exit': 18, 'stop': 18, 'period_end': 1}
- Sayaçlar: {'channel_exits': 18, 'channel_exit_through_stop': 0, 'deferred_channel_exits': 0, 'gap_stops': 0, 'stops': 18, 'entry_day_stops': 1, 'entries_cancelled_capacity': 122, 'entries_cancelled_missing_bar': 0, 'entries_skipped_invalid_atr': 0, 'entries_blocked_no_capital': 0, 'days_no_capital_before_open': 0, 'forced_closes': 1}
- Eksik günde değerleme (E12): {'BTCUSDT': 0, 'ETHUSDT': 0, 'SOLUSDT': 0, 'BNBUSDT': 0}
- Dönem sonu tasfiyeleri (E3b/E13): [{'symbol': 'BTCUSDT', 'day': '2024-12-31', 'price': 93539.54510999999, 'pnl': 463.4572855170825}]
- Ortak bitişten ÖNCE tasfiye (bitiş barı eksik, E13): yok

## Yıl bazında (kapanış yılı; bilgi amaçlı, kapı değil)
| Yıl | İşlem | PF | Net $ |
|---|---:|---:|---:|
| 2020 | 9 | 0.8539964337292041 | -39.59 |
| 2021 | 7 | 24.2630456262532 | 3991.54 |
| 2022 | 5 | 0.0 | -363.79 |
| 2023 | 7 | 0.6369592952459702 | -104.13 |
| 2024 | 9 | 11.338620750837052 | 3656.42 |

## Sembol bazında (bilgi amaçlı)
| Sembol | İşlem | PF | Net $ |
|---|---:|---:|---:|
| BNBUSDT | 8 | 0.056022610435240906 | -474.41 |
| BTCUSDT | 12 | 7.408561771961033 | 2361.1 |
| ETHUSDT | 12 | 5.836562060477028 | 2075.7 |
| SOLUSDT | 5 | 22.638016132844687 | 3178.05 |

## Tekrar üretilebilirlik
- Kod parmak izi: `8821c9c764cf3612…` · git: d49785a35622816d612707382f9416c8612cbd9a
- Kilit öncesi değişmiş dosyalar: []
- Veri sha256 (sağlık raporuyla aynı): BTCUSDT `d0d7c252e73a…`, ETHUSDT `81378f3a7350…`, SOLUSDT `3c03e9e9ca82…`, BNBUSDT `f57ff7b14021…`
- Python 3.13.14, pandas 3.0.3

## Notlar
- E13: dönem sonu tasfiyesi sembolün dönem içindeki son mevcut barını dönem sonu verisine bakarak belirler (onaylanmış dönem sonu varsayımı). Bu rapor genel bir 'lookahead yok' iddiası taşımaz; sinyal hesabı lookahead içermez.

> Kural: sonuç kapılarla raporlanır, süslenmez. KALDI ise Plan B v1 REDDEDİLDİ, parametre kurcalanmaz.
