# Derin Analiz — VF + SF Açık (51 işlem, gerçek veri)

Konfigürasyon: volume filtresi (≥1.5×MA20) + session filtresi (London/NY KZ),
BTC/USD 15M, Oca 2025 – Tem 2026. Grafik: `equity_curve.png`

## Yön Simetrisi (sağlıklı işaret)

| Yön | İşlem | Ort. R | Toplam R |
|---|---|---|---|
| Long | 25 | +0.163 | +4.08 |
| Short | 26 | +0.136 | +3.54 |

Edge tek yöne bağımlı değil — düşüş rejiminde long'ların da artıda olması
sweep mekaniğinin yön-bağımsız çalıştığını gösteriyor.

## Çıkış Dağılımı

| Çıkış | Adet | Ort. R |
|---|---|---|
| Target | 22 (%43.1) | +1.91 |
| Stop | 29 (%56.9) | −1.19 |

Ort. kazanç 1.91R (hedef 2R − maliyet), ort. kayıp −1.19R (1R + slippage +
taker + aynı-bar muhafazakârlığı). Kayıp tarafı teorik −1R'den %19 ağır:
bunun ~%9'u maliyet, kalanı fill-barında-stop senaryolarının cezası.

## Aylık Dağılım (net R)

18 ayın 11'i pozitif/nötr. En kötü ay −2.47R (Mar 2026), en iyi +3.00R
(Haz 2025). Tek ayda hesap riski maksimum ~%1.5 (R=%0.5 ile) — sakin seyir.
Ayda ortalama ~3 işlem: sinyal SEYREK. Sabır gerektirir; 300 işlem hedefi
tek sembolle ~8 yıl demek → çok sembol (BTC+ETH+…) şart.

## Pozisyon Süresi

Ortalama 6.2 saat (15M barda ~25 bar). Funding etkisi küçük ama canlıda
journal'a kaydedilecek.

## Yorum

Sistem şu an "az ama isabetli" profilinde: PF 1.21, DD %3.3. Zayıf nokta
işlem sıklığı ve PF'nin eşik altında kalması. Doğru yol: (1) çok sembol,
(2) uzun tarih, (3) eşik geçilirse paper trading. Parametre oynamak YOK.
