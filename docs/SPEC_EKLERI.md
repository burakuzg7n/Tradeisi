# SPEC EKLERİ — V2 (§8) ve Plan B (§9) için Yorum Netleştirmeleri

**Tarih:** 31 Ekim 2026 · **Onaylayan:** Burak · **Hazırlayan:** Claude
**Kaynak:** ChatGPT bağımsız denetimi (#4, #5, #26–#31) bulguları.

## Statü ve kural
Bu ek, `DEVIR_NOTU.md` §8 (V2) ve §9 (Plan B) metinlerinin **yorumudur**.
- Strateji **fikrini ve eşiklerini DEĞİŞTİRMEZ**; yalnızca iki farklı okunabilen
  yerleri tek anlama bağlar.
- Yazıldığı anda **hiçbir V2 veya Plan B sonucu görülmemişti** (çalıştırıcı yoktu).
- Bu noktadan sonra **DEĞİŞTİRİLEMEZ**. Sonuç görüldükten sonra yapılacak her
  değişiklik = yeni versiyon numarası (V2.1, Plan B.1) + yeni tek atış.
- Çelişki halinde bu ek, §8/§9'un o maddesine göre önceliklidir.

## V2 Ekleri

**E1 — Giriş fiyatı (§8 "entry = kapanışta MARKET").**
Tetik barının kapanışı yalnızca **referans fiyattır**: hedef (2R), stop mesafesi
ve %0,2 min stop mesafesi bu fiyattan hesaplanır. Gerçek dolum **bir sonraki
barın açılışı + aleyhe slippage**dır (kapanışı görüp aynı fiyattan girmek
mümkün değil). Backtest motoru bunu zaten böyle uygular.

**E2 — Setup yaşam döngüsü.**
- Sweep sonrası 24 bar içinde tetik beklenir (§8).
- Beklerken HTF bias, sweep yönünün aksine dönerse setup **iptal**.
- Beklerken yeni bir sweep gelirse eskisinin yerini **almaz**; ilk sweep geçerlidir.
- İlk tetik killzone dışına denk gelirse veya min stop mesafesi şartı
  sağlanmazsa setup **biter** (sonraki tetik beklenmez).

**E3 — BTC+ETH birleşik kapı.**
- Her sembol **kendi hesabında** (10.000$ başlangıç) test edilir.
- "Tek pozisyon" **sembol başınadır**.
- **Birleşik PF** = tüm işlemlerin brüt kârı ÷ brüt zararı (USD, iki sembol toplamı).
- **Birleşik DD** = iki hesabın equity eğrilerinin **toplamı** üzerinden.
- Birleşik kapı: PF > 1,3 VE işlem sayısı ≥ 150 (iki sembol toplamı) VE DD < %15.

**E4 — Hold-out kapıları (2025-01 → bugün).**
PF > 1,15 **VE** DD < %15. İşlem sayısı raporlanır ama kapı değildir.

## Plan B Ekleri

**E5 — Kanallar.**
- Giriş kanalı: **önceki 55 günün en yüksek HIGH**'ı (bugün hariç).
- Çıkış kanalı: **önceki 20 günün en düşük LOW**'u (bugün hariç).
- Sinyal **günlük kapanışta** değerlendirilir (close > giriş kanalı;
  close < çıkış kanalı). İşlem **ertesi günün açılışında** market (taker +
  aleyhe slippage) yapılır.

**E6 — Stop.**
Stop = **giriş fiyatı − 2 × ATR(20)**. ATR: Wilder yöntemi, **sinyal gününün**
değeri. Stop **sabittir** (takip eden değil), gün içi stop-market (taker).
Kanal çıkışı (E5) stop'tan bağımsız ikinci çıkış koşuludur; hangisi önce
gerçekleşirse.

**E7 — Portföy.**
Ortak sermaye. Pozisyon başına risk %0,5. Aynı anda **en fazla 2** pozisyon.
Aynı gün ikiden fazla sinyal gelirse **sabit öncelik sırası: BTC, ETH, SOL, BNB**.
Aynı sembole ek giriş (piramitleme) **yok**. Veri geçmişi henüz başlamamış
sembol, veri başladığı günden itibaren dahil edilir.

**E8 — Funding.**
Perp uzun pozisyonlara **sabit %0,03 / gün** funding maliyeti uygulanır
(pozisyon nominali üzerinden, açık kalınan her gün). Mevcut motorda funding
yoktur; Plan B çalıştırılmadan önce eklenmelidir.

**E9 — Kapılar.**
In-sample (2020-01 → 2024-12): PF > 1,3 VE DD < %15 VE işlem sayısı ≥ 100
(günlük bar az işlem ürettiği için 150 yerine 100). Hold-out (2025-01 → bugün):
PF > 1,15 VE DD < %15.

## Bilinen sınırlama (dürüstlük notu — kural değil, gerçek)
2025+ verisi V1 analizinde **zaten görüldü** ve volume filtresinin kapatılması
kararında uzun dönem sonuçları kullanıldı. Bu yüzden 2025+ hold-out'u **tam
bağımsız değildir**; geçmesi zayıf kanıttır. Asıl bağımsız doğrulama,
**31 Ekim 2026'dan sonra gelecek veriyle** yapılacak paper/testnet dönemidir.
Backtest geçse bile paper'a geçmeden bu sınırlama akılda tutulur.
