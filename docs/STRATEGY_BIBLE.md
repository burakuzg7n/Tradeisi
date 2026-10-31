# Strategy Bible — HTF Bias + Liquidity Sweep + FVG Retest (v1)

Durum: TANIMLANDI → kod: `tradebot/strategy.py` → doğrulama: backtest bekliyor
Piyasa: BTCUSDT, ETHUSDT (USDT perpetual) · TF: 4H bias / 15M entry · Saat: her şey UTC

---

## 1. Teori

Fiyat, stop emirlerinin biriktiği belirgin swing seviyelerini (likidite) süpürüp
gerçek yönüne döner. Süpürme sonrası oluşan momentum boşluğu (FVG), kurumsal
girişin izidir; fiyatın bu boşluğa dönüşü (retest) düşük riskli giriş sunar.
HTF bias filtresi bu mekaniği yalnızca ana trend yönünde oynatır.

Bilinçli olarak DIŞARIDA bırakılanlar (subjektif ICT): AMD, PO3, inducement
yorumları. Sadece mekanik, kodlanabilir tanımlar kullanılır.

## 2. Tanımlar (mekanik, tartışmasız)

| Kavram | Tanım |
|---|---|
| Swing High/Low | `ta.pivothigh/low(sol=N, sağ=N)`. Pivot ancak N bar SONRA kesinleşir; kesinleşmeden kullanılamaz (lookahead yasağı) |
| HTF Bias | 4H yapıda son kırılımın yönü: son kesinleşmiş swing high close ile kırıldıysa 1 (bull), swing low kırıldıysa -1 (bear), henüz kırılım yoksa 0 |
| SSL Sweep | Bar low < kesinleşmiş son 15M swing low VE close > o seviye (wick deldi, gövde geri döndü) |
| BSL Sweep | Simetrik: high > swing high VE close < seviye |
| Bullish FVG | 3 ardışık mum: `mum3.low > mum1.high`; boşluk ≥ fiyatın %0.05'i. Mum3 kapanışında kesinleşir |
| FVG %X doluluk | Bullish FVG üstten dolar: %50 = midpoint, %79 = bottom + 0.21×boyut |

## 3. Setup Koşulları (5/5 zorunlu)

1. **Bias:** 4H trend ≠ 0; yalnızca bias yönünde işlem (bias, son KAPANMIŞ 4H mumundan)
2. **Sweep:** Bias bull → SSL sweep; bias bear → BSL sweep
3. **FVG:** Sweep sonrası ≤ 24 bar (6 saat) içinde bias yönünde FVG oluşumu
4. **Session:** FVG'nin oluştuğu bar London KZ (07-10) veya NY KZ (13-16 UTC) içinde
5. **Ekonomi:** Stop mesafesi ≥ fiyatın %0.2'si (aksi hâlde komisyon 0.5R'yi aşar → setup ekonomik değil)

## 4. Giriş / Çıkış

- **Entry:** FVG %50 doluluk seviyesine LIMIT emir. 32 bar (8 saat) içinde dolmazsa iptal
- **Stop:** min(sweep dibi, FVG dibi) × (1 − %0.1 tampon) — long için; short simetrik. Stop HER ZAMAN borsada (stop-market)
- **Target:** entry + 2 × risk (limit emir). Trade sırasında target/stop DEĞİŞTİRİLMEZ
- **İptal:** fill olmadan fiyat FVG'yi tamamen doldurup kapatırsa setup geçersiz

## 5. Yasak Durumlar

- Bias 0 (nötr) → işlem yok · Bias'a karşı işlem YOK (kural, istisnasız)
- Killzone dışı FVG → setup yanar (beklemeye alınmaz)
- High-impact haber penceresi (öncesi 30 dk, sonrası 15 dk): FOMC, NFP, CPI, PCE, GDP → yeni giriş yok
- Kill switch aktifken (gün -3R / hafta -8R / DD %10) → sistem kapalı, manuel inceleme
- Aynı anda 1'den fazla pozisyon yok; sweep başına tek setup

## 6. Risk

İşlem başına %0.5 (1R açılışta SABİTLENİR). Min RR 1:2.
Günlük -3R, haftalık -8R, max DD %10 kill switch (`tradebot/risk.py`).

## 7. Maliyet Gerçeği (kritik bulgu)

Dar SMC stoplarında komisyonun R cinsinden maliyeti patlar:
`maliyet_R ≈ (entry_fee% + exit_fee%) / stop_mesafesi%`.
Örn. %0.25 stop + çift taker (%0.11 toplam) → **0.44R her işlemde**.
Bu yüzden: entry ve target LIMIT (maker %0.02), sadece stop taker (%0.055);
%0.2 altı stop mesafesi reddedilir. Motor bu modeli aynen simüle eder.

## 7b. Volume Konfirmasyonu (opsiyonel yapısal filtre)

Sweep barının hacmi ≥ 1.5 × son 20 barın ortalaması (kendi barı hariç) —
knowledge/volume'daki "sweep + hacim spike = kurumsal katılım" kuralının kodu.
`use_volume_filter=True` ile açılır. 18 aylık gerçek veri testinde her metriği
iyileştirdi (PF 1.04→1.21, DD %7.9→%3.3); eşik backtest'e göre AYARLANMAZ.
Pine karşılığı: `useVolFilter` input'u.

## 8. Doğrulama Kapıları (sıra atlanamaz)

| Kapı | Kriter |
|---|---|
| Backtest (18+ ay, komisyon+slippage dahil) | PF > 1.3 · DD < %15 · Expectancy > 0 · ≥ 300 işlem · OOS'ta çökmemeli (70/30 walk-forward) |
| Paper (Telegram + journal) | ≥ 300 işlem, kriterler korunuyor |
| Testnet | ≥ 100 işlem, execution hatasız |
| Canlı | 100-500$ ile başla; PF < 1.0 veya DD > %20 veya 3 ay negatif → sistem KAPANIR |

## 9. Webhook JSON Standardı

```json
{
  "symbol": "BTCUSDT", "direction": "long",
  "entry": 49850.0, "stop_loss": 49480.0, "take_profit": 50590.0,
  "setup": "ssl_sweep_fvg", "timeframe": "15", "htf_bias": "bullish",
  "session": "london", "fvg_top": 50000.0, "fvg_bottom": 49700.0,
  "timestamp": "2026-07-06T08:45:00Z"
}
```

## 10. Anti-Repaint Checklist (Pine)

- [x] Tüm sinyaller `barstate.isconfirmed` ile
- [x] HTF veri: `request.security(..., ifade[1], lookahead=barmerge.lookahead_off)` — yalnızca kapanmış 4H
- [x] Pivotlar doğal gecikmesiyle (sağ N bar) kullanılıyor, `[N]` hileleri yok
- [x] Session string'leri `"UTC"` parametresiyle
- [x] Alert'ler yalnızca mum kapanışında

## 11. Bilinen Sınırlar

15M OHLC ile intra-bar sıra bilinemez → aynı barda stop+target = STOP sayılır
(muhafazakâr). Limit fill'de queue pozisyonu simüle edilmez; fiyat dokunuşu =
fill varsayımı iyimserdir, buna karşılık maker yerine dokunma anı fiyatı ve
muhafazakâr stop önceliği ile dengelenir. Funding rate simüle edilmez
(pozisyonlar saatler mertebesinde, etki küçük; canlıda journal'da izlenir).
