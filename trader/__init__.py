"""TradeBot — calisir durumdaki trading programi (V2 motoru).

Bu paket `tradebot/` (V1 donemi arsivi) ve `reports/` (muhurlu sonuc
arsivi) dosyalarina DOKUNMAZ. Arşiv degistirilemez; yeni program burada
ayri bir yerde yasar.

Moduller:
    config      ayarlar (.env)
    market      borsa verisi (OHLCV + funding) indirme/dogrulama
    store       SQLite kalici kayit (sinyal, emir, islem, equity, olay)
    strategy    strateji arayuzu
    strategies  hazir stratejiler
    backtest    portfoy backtest motoru (muhafazakar varsayimlar)
    metrics     performans olcumu
    report      rapor uretimi
    paper       paper trading (canli piyasa verisi + simulasyon)
    live        testnet/canli yurutucu (idempotent + uzlastirma)
    exchange    borsa adaptoru (ccxt)
    dashboard   web paneli
    cli         komut satir arayuzu
"""

__version__ = "2.0.0"
