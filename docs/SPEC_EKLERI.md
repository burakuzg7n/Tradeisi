# SPEC EKLERİ — V2 (§8) ve Plan B (§9)

**Tarih:** 31 Ekim 2026 · **Onaylayan:** Burak · **Hazırlayan:** Claude
**Kaynak:** ChatGPT bağımsız denetimi (#4, #5, #26–#31 ve PR #3 incelemesi).
**Önemli:** Bu belge yazıldığında hiçbir V2 veya Plan B sonucu görülmemişti.

## Statü ve etiketler
Bu belgedeki her madde iki etiketten birini taşır. Etiket dürüstçe seçilir:

- **[YORUM]** — `DEVIR_NOTU.md` §8/§9 metninin iki farklı okunabilen yerini tek
  anlama bağlar. Fikri ya da eşiği değiştirmez.
- **[KARAR]** — §8/§9'da yazılı olmayan YENİ bir sayı ya da kural, ya da yazılı bir
  ifadeden bilinçli sapma. Burak'ın onayıyla, **veri görülmeden** verilmiştir ve
  ilgili §8/§9 ifadesini o noktada değiştirir. Eski ifade ve değişiklik gerekçesi
  yanında yazılıdır.

Bu belge sonuç görüldükten sonra **DEĞİŞTİRİLEMEZ**. Her değişiklik = yeni versiyon
numarası (V2.1, Plan B.1) + yeni tek atış.
(Bu belgede "ek önceliklidir" türü genel bir üstünlük hükmü yoktur; çelişki
olursa etiket belirleyicidir: [KARAR] ilgili noktada §8/§9'u değiştirmiştir,
[YORUM] değiştirmemiştir.)

---

## V2

**E1 — Giriş zamanı [KARAR].**
§8: "Entry = o barın kapanışında MARKET". **Değişiklik:** giriş, tetik barının
**bir sonraki barının açılışında**, aleyhe slippage ile yapılır.
*Gerekçe:* kapanış fiyatını gözlemleyip aynı fiyattan emir vermek mümkün değil.
Tetik barının kapanışı yalnızca **referans fiyattır**: hedef (2R), stop mesafesi ve
%0,2 minimum stop mesafesi bu fiyattan hesaplanır. Gerçek dolum fiyatı farklı
olacağından gerçekleşen R, 2R'den sapabilir; **2R garantisi verilmez**, gerçekleşen
R raporlanır.

**E2 — Setup yaşam döngüsü [YORUM].**
- Tetik penceresi: sweep barı `s` için `s+1 … s+24` (dahil).
- Bekleme sırasında HTF bias, sweep yönüne **eşit olmaktan çıkarsa** (ters yön
  **veya nötr**) setup iptal.
- Beklerken yeni sweep eskisinin yerini **almaz**; ilk sweep geçerlidir.
- İlk tetik killzone dışına denk gelirse veya minimum stop mesafesi sağlanmazsa
  setup **biter** (sonraki tetik beklenmez).
- Killzone kontrolü, tetik barının **açılış** saati ile yapılır (V1'den miras;
  bar indeksi açılış zamanıdır).

**E3 — BTC+ETH birleşik kapı [YORUM].**
- Her sembol **kendi hesabında** (10.000 $) test edilir; "tek pozisyon" **sembol
  başınadır** (portföy genelinde değil).
- **Birleşik PF** = iki sembolün **maliyetler (ücret + slippage) SONRASI** net işlem
  sonuçları üzerinden: kazançların toplamı ÷ kayıpların mutlak toplamı (USD).
- **Birleşik DD:** iki equity eğrisi ortak 15 dakikalık zaman ekseninde birleştirilir
  (eksik barda son değer taşınır); açık pozisyonlar mark-to-market; toplam equity
  üzerinden maksimum drawdown.
- **Birleşik kapı:** PF > 1,3 VE işlem sayısı ≥ 150 (iki sembol toplamı) VE DD < %15.

**E3b — Dönem sonu tasfiyesi (V2 ve Plan B) [KARAR].**
§8/§9'da tanımlı değildi. **Karar:** her dönemin (in-sample ve hold-out ayrı ayrı)
SON barının kapanışında açık kalan pozisyonlar, o kapanış fiyatından, **aleyhe
slippage ve taker ücretle** zorla kapatılır ve işlem sayısına dahil edilir. Dönem
sonunda bekleyen (henüz tetiklenmemiş) V2 setup'ları iptal edilir.
*Gerekçe:* dönem sonunda açık kalan işlemin gerçekleşmemiş PnL'sini PF/DD dışında
bırakmak sonucu çarpıtır.

**E3c — Dönem başlangıç durumu (V2 ve Plan B) [KARAR].**
§8/§9'da tanımlı değildi. **Karar:** in-sample ve hold-out ayrı ayrı çalıştırılır;
her biri **yeni başlangıç sermayesi** (V2: sembol başına 10.000 $; Plan B: ortak
10.000 $), **boş pozisyon** ve **bekleyen setup olmadan** başlar. Göstergeler
(HTF yapı/bias, kanallar, ATR) önceki dönemin verisiyle **ısınmış** olarak başlar
(hold-out'un ilk gününde 2024 verisi kullanılabilir). Veri dosyası dönemin
başlangıcından önce yoksa (ör. in-sample başı) E5'teki yeterli geçmiş şartı geçerli.
Plan B'nin DD'si **ortak hesabın günlük kapanış mark-to-market equity**'si üzerinden
hesaplanır (V2'deki iki-eğri toplamı yöntemi yalnız V2 içindir).

**E4 — Hold-out kapısı [KARAR].**
§8: hold-out'ta "PF > 1,15 korunmalı". **Ekleme:** ayrıca DD < %15 şartı.
İşlem sayısı raporlanır ama kapı değildir. *Gerekçe:* PF tek başına yeterli
risk güvencesi vermez. **Dönem:** 2025-01-01 → verideki **son tam günün** sonu.
Çalıştırma raporuna veri dosyasının son tarihi ve hash'i yazılır (tekrar üretilebilirlik).

---

## Plan B

**E5 — Kanallar ve veri [YORUM].**
- Giriş kanalı: **önceki 55 günün en yüksek HIGH**'ı (bugün hariç).
- Çıkış kanalı: **önceki 20 günün en düşük LOW**'u (bugün hariç).
- "Gün" = UTC günü (00:00 UTC açılışlı günlük bar). "55 gün" = **55 mevcut günlük
  bar**.
- Sinyal günlük **kapanışta** (close > giriş kanalı; close < çıkış kanalı),
  işlem **ertesi günün açılışında** market (taker + aleyhe slippage).
- Yeterli geçmiş (55 bar) oluşmadan sembol için **işlem yapılmaz**; başlangıçta
  kısa pencere kullanılmaz.

**E5b — Eksik veri günü [KARAR].**
Bir sembolün o günkü barı eksikse o sembol o gün için **sinyal üretmez ve işlem
yapmaz**. Eksik bar sayısı çalıştırma raporunda sembol başına belirtilir.

**E6 — Stop ve ATR [YORUM].**
- Stop = **gerçek dolum fiyatı − 2 × ATR(20)**; ATR: Wilder, **sinyal gününün** değeri.
- ATR başlangıcı: ilk değer, ilk 20 true range'in basit ortalaması; sonrası
  Wilder düzgünleştirmesi. ATR hazır olmadan işlem yok (E5 şartı zaten daha uzun).
- Stop **sabittir** (takip eden değil), gün içi stop-market (taker). Gap kuralları
  motordakiyle aynıdır (açılış stopun ötesindeyse açılıştan çıkış).
- Kanal çıkışı (E5), stop'tan bağımsız ikinci çıkış koşuludur; hangisi önce olursa.
  Kanal çıkışı sinyal gününün kapanışında verilir, ertesi açılışta market (taker +
  slippage) yapılır.

**E7 — Portföy: yorum kısmı [YORUM].**
- Tek **ortak hesap**; pozisyon başına risk %0,5, boyut = açılış öncesi
  **gerçekleşmiş bakiye** × %0,5 ÷ risk mesafesi (equity değil; motorla aynı).
  Giriş ücreti PnL'ye pozisyon **kapanışında** işlenir; bakiye yalnız kapanışlarda
  değişir. Aynı açılışta iki giriş yapılırsa ikisi de **aynı** (açılış öncesi)
  bakiyeden boyutlandırılır.
- Aynı anda **en fazla 2** pozisyon. Aynı sembole ek giriş (piramitleme) yok.

**E7b — Portföy: yeni yürütme kuralları [KARAR].**
§9'da tanımlı değildi. **Karar:**
- Başlangıç sermayesi **10.000 $**.
- Eşzamanlı sinyallerde **sabit öncelik sırası: BTC, ETH, SOL, BNB**; boş kontenjana
  sığmayan sinyal o gün için **iptal** olur (ertelenmez).
- Açılış sırası: (1) **kanal çıkışları** (önceki kapanışta kararlaştırılmış), (2) yeni
  girişler. Kanal çıkışıyla o açılışta boşalan kontenjan **aynı açılışta** kullanılabilir.
- **Stop ile kapanan** her pozisyonun (gün içi stop **veya açılışta gap stop**)
  kontenjanı **ertesi güne** kalır. Gerekçe: stop o gün keşfedilir, önceden
  verilebilecek bir karar değildir; bar içi sıra bilinmez (motor kuralıyla tutarlı).
- Veri geçmişi başlamamış sembol, E5'teki yeterli geçmiş şartı sağlandığı günden
  itibaren dahildir.

**E8 — Funding [KARAR].**
§9'da funding tanımlı değildi. **Ekleme:** uzun pozisyonlara sabit **%0,03 / UTC günü**
funding maliyeti. Hesap: nominal = giriş fiyatı × miktar (sabit); pozisyonun açık
olduğu **her UTC günü** için, açılış ve kapanış günleri dahil, **tam gün** sayılır
(aynı gün açılıp kapanan 1 gün öder — muhafazakâr); toplam maliyet pozisyon
**kapanışında** işlem PnL'sinden düşülür.
*Gerekçe ve sınır:* %0,03/gün, BTC/ETH perp funding'inin tarihsel ortalamasına
(yaklaşık %0,01 / 8 saat) yakın bir sabit varsayımdır. Gerçek funding değişkendir
(yüksek boğa dönemlerinde bunun üstüne çıkar, bazen negatiftir); **sabit oranın
gerçeğin muhafazakâr üst sınırı olduğu iddia edilmez.** Plan B short içermediği için
işaret sorunu yoktur.

**E9 — Plan B kapıları [KARAR].**
§9: "Aynı test protokolü" (işlem sayısı eşiği belirsizdi). **Karar:**
in-sample (2020-01 → 2024-12): PF > 1,3 VE DD < %15 VE işlem sayısı **≥ 100**
(günlük bar az işlem ürettiği için V2'nin 150'si yerine 100). Hold-out
(2025-01-01 → verideki son tam gün): PF > 1,15 VE DD < %15.
*Not:* 100 sayısı hiçbir önceki metinden çıkmaz, bu bilinçli yeni bir karardır.

---

## Bilinen sınırlama (dürüstlük notu)
2025+ verisi V1 analizinde **zaten görüldü** ve volume filtresinin kapatılması
kararında uzun dönem sonuçları kullanıldı. Bu yüzden 2025+ hold-out'u **tam
bağımsız değildir**; geçmesi zayıf kanıttır. Asıl bağımsız doğrulama,
**31 Ekim 2026'dan sonra gelecek veriyle** yapılacak paper/testnet dönemidir.

## Altyapı notu (kural değil, iş listesi)
Plan B çalıştırılmadan önce motora eklenmesi gerekenler: funding (E8), günlük bar
akışı, ortak sermayeli çoklu sembol portföyü (E7), dönem sonu zorla kapanış (E3).
