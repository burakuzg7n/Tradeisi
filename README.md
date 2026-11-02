# Tradeİşi — kural bazlı kripto strateji araştırması

Sıfırdan yazılmış, test protokolüyle çalışan bir strateji araştırma projesi.
Kâr garantisi yoktur; kararları önceden sabitlenmiş kapılar verir (`AGENTS.md`).

## Durum (2 Kasım 2026)

Dört strateji önceden yazılmış kurallarla, tek atış protokolüyle test edildi;
**hepsi reddedildi.** Hiçbiri canlıya veya paper/testnet aşamasına geçmedi.

| Strateji | Fikir | Sonuç | Rapor |
|---|---|---|---|
| V1 | 15m sweep + FVG (BTC/ETH) | Reddedildi (PF 0,78–0,82) | `reports/YILLIK_ANALIZ.md` |
| V2 | 15m sweep + CHoCH (BTC/ETH) | Reddedildi (PF 0,80, DD %22) | `reports/V2_INSAMPLE.md` |
| Plan B v1 | Günlük Donchian 55/20 (4 coin) | Reddedildi (37 işlem, DD %20) | `reports/PLANB_INSAMPLE.md` |
| V3 | 15m Asya seansı kırılımı (5 altcoin) | Reddedildi (PF 0,91, DD %95) | `reports/V3_INSAMPLE.md`, `reports/V3_INSAMPLE_INCELEME.md` |

Sonraki yön henüz kararlaştırılmadı: `docs/SONRAKI_YON_KARAR_NOTU.md`.
Ayrıntılı geçmiş: `DEVIR_NOTU.md` (§0 güncel durum) ve `PROGRESS.md`.

## Klasörler

```
AGENTS.md        Tüm asistanlar için kurallar (önce bunu oku)
DEVIR_NOTU.md    Devir notu; §8 (V2) ve §9 (Plan B) bağlayıcı spesifikasyonlar
PROGRESS.md      Zaman çizelgesi
KURULUM.md       Python kurulumu (demo bölümü tarihsel)
1_kurulum.bat    Kütüphaneleri kurar
docs/            Spesifikasyonlar ve kararlar
  SPEC_EKLERI.md          V2 + Plan B ekleri (E1–E17)
  V3_SPEC_TASLAK.md       V3 kuralları
  V3_DOGRULAMA_PLANI.md   V3 test sonrası doğrulama planı (uygulanmadı)
  SONRAKI_YON_KARAR_NOTU.md  Seçenekler ve araştırma planlama yöntemi
  STRATEGY_BIBLE.md       V1 strateji belgesi (tarihsel)
  roadmap/                İlk yol haritası belgeleri
tradebot/        Python paketi
  backtest.py, strategy.py, strategy_v2.py, protocol_v2.py   V1/V2
  daily_data.py, strategy_b.py, portfolio_b.py, protocol_planb.py   Plan B
  v3_data.py, strategy_v3.py, engine_v3.py, protocol_v3.py, synthetic_v3.py   V3
  risk.py, journal.py, server.py, execution.py, live.py, notify.py   V1 dönemi altyapı
scripts/         Veri indirme, tek atış koşucuları, inceleme scriptleri
tests/           pytest testleri (`python -m pytest tests/`)
reports/         ARŞİV — sonuç raporları, kilitler, mühürler. Silinmez, değiştirilmez.
knowledge/       ICT/SMC eğitim notları
pine/            V1 TradingView göstergesi (tarihsel)
data/            Fiyat verisi (git'te yok; sha256'ları raporlarda)
```

## Önemli

- `reports/` ve `*.lock` dosyaları tek atış kayıtlarıdır; silinmez, elle değiştirilmez.
- `data/` içindeki CSV'ler raporlardaki parmak izlerine bağlıdır; yeniden indirilmez
  (indirme scriptleri dosya varsa durur).
- Tek atış koşucularını çalıştıran `.bat` dosyaları kullanıldıktan sonra kökten
  kaldırıldı (git geçmişinde duruyor); koşucular zaten ikinci çalıştırmayı reddeder.
- `.env` gizli anahtarlar içerir; asla paylaşılmaz veya commit edilmez.
