# Yıllık Rejim Analizi — NİHAİ KARAR (8 Tem 2026)

Veri: Binance BTCUSDT + ETHUSDT, 2020-2026 (6.5 yıl), gerçek, maliyetler dahil.
Toplam örneklem: 394 + 423 işlem (filtresiz) — istatistiksel olarak YETERLİ.

## Sonuç Tablosu (PF, session filtresi açık)

| Yıl | BTC | BTC+VF | ETH | ETH+VF |
|-----|-----|--------|-----|--------|
| 2020 | 1.01 | 1.06 | 0.94 | 0.64 |
| 2021 | 0.94 | 1.27 | 1.08 | 0.74 |
| 2022 | 0.63 | 0.57 | 0.85 | 0.54 |
| 2023 | 0.44 | 0.49 | 0.56 | 0.45 |
| 2024 | 1.28 | 1.37 | 0.71 | 0.55 |
| 2025 | 0.73 | 0.91 | 0.62 | 0.83 |
| 2026 | 0.92 | 0.60 | 0.63 | 1.37* |

*26 işlem — gürültü.

## KARAR: STRATEJİ V1 REDDEDİLDİ ❌

1. **Tutarlı edge yok.** Pozitif yıllar dağınık ve zayıf; 2022-2023 her
   konfigürasyonda yıkıcı (PF 0.44-0.63). Kayıp, maliyet sürtünmesi + gürültü
   profiline uyuyor.
2. **Volume filtresi genellemedi.** 18 aylık BTC'de iyileştiren filtre, ETH'de
   ve uzun dönemde işe yaramadı → o iyileşme dönemsel şanstı. (Bu, filtre
   eklerken neden tek atışlık test yaptığımızın kanıtı — iyi ki kural koyduk.)
3. **Ban kriteri tetiklendi:** PF < 1.0. Roadmap'e göre bu sistemle canlıya
   çıkılMAZ, paper trading'den sonuç beklenMEZ.

## Bu Bir Başarısızlık Değil

Sistemin amacı buydu: zayıf stratejiyi GERÇEK PARA YANMADAN yakalamak.
90 günlük planın ilk 45 günü "strateji doğrula" diyordu — doğrulama çalıştı,
cevap "hayır" çıktı. Altyapı (motor, risk engine, testnet runner, journal)
sağlam ve strateji-bağımsız: V2 aynı iskelete takılır.

## V2 İçin Kurallar (kritik — overfitting tuzağına düşmemek için)

1. Yeni strateji hipotezi VERİYE BAKMADAN, mantıktan yazılır
   (örn. knowledge base'in kendi uyarısı: sweep sonrası CHoCH konfirmasyonu
   beklemek — V1 bunu atlayıp direkt FVG'ye giriyordu).
2. Kurallar önceden sabitlenir → 2020-2024 ile TEK test → geçerse 2025-2026
   hold-out ile doğrulama. Aynı veri üzerinde deneme-yanılma döngüsü YASAK.
3. V1'in parametreleriyle oynamak yasak — 0.82 PF'li sistemi parametre
   turlayarak 1.3 yapmak matematiksel olarak mümkün ve pratikte değersizdir
   (curve fitting).

## Testnet Runner Durumu

Çalışmaya devam edebilir — altyapı testi olarak değerli (emir yaşam döngüsü,
Telegram, journal). Ama beklenti net: sinyaller DOĞRULANMAMIŞ stratejiden.
