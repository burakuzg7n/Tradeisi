# V3 doğrulama planı — testten sonra (TASLAK)

**Tarih:** 2 Kasım 2026 · **Hazırlayan:** Claude · **Denetim:** ChatGPT · **Onay:** Burak
**Statü:** TASLAK; hiçbir aşaması uygulanmaz. Yalnız V3 in-sample **ve** hold-out kapılarını
geçerse gündeme gelir; o zaman da Burak onayı ve bağımsız denetimden sonra başlar.

## 1. Mevcut kural ve bu planın ondan sapması

AGENTS.md: "Backtest → OOS sağlam → **300 paper → 100 testnet** → ancak sonra 100–500 $
canlı." Bu plan, 300/100 **işlem sayısı** şartını aşağıdaki **ölçülebilir kabul
kriterleriyle** değiştirmeyi önerir. **Bu, mevcut kuraldan bir [SAPMA]'dır**; Burak onayı
ve bağımsız denetim olmadan uygulanmaz. Amaç süreyi keyfî kısaltmak değil, her aşamanın
neyi ölçtüğünü ayırmaktır. Süreyi kısaltmak için işlem sıklığı, coin sayısı veya risk
**artırılmaz**.

## 2. 300 paper + 100 testnet hangi riskleri ölçüyordu?

| Risk | Açıklama | Hangi aşama gerçekten ölçer |
|---|---|---|
| R1 İstatistiksel üstünlük yok | Backtest sonucu şans/uydurma | In-sample + hold-out kapıları (§3a); ileri veri ancak uzun sürede |
| R2 Yazılım hatası | Sinyal, boyut, emir, stop/hedef, durum kaydı yanlış | Hızlandırılmış oynatma + sentetik senaryolar (§3b) |
| R3 Yürütme farkı | Gerçek dolum, slippage, gecikme, asgari emir, reddedilen emir | Gerçek zamanlı paper/testnet (§3c) |
| R4 Operasyon | Bağlantı kopması, yeniden başlama, saat kayması, alarm kaçırma | Sentetik (§3b) + gerçek zamanlı (§3c) |
| R5 Disiplin | Kullanıcının sinyale uymaması, kuralı değiştirmesi | Gerçek zamanlı aşamalar + günlük |

300/100 işlem bu riskleri tek bir sayıyla birlikte ölçmeye çalışıyordu. Ayda 40–75
işlemde 300 + 100 ≈ 5–10 ay sürer; R2/R4 bunun çok daha azında, R1 ise 400 işlemde bile
ancak sınırlı ölçülür.

## 3. Ayrılmış doğrulama

### 3a. Strateji (istatistik) — yalnız önceden sabit kapılar
- V3 in-sample ve hold-out kapıları (`docs/V3_SPEC_TASLAK.md` §7). Ek bir backtest,
  yeniden koşu veya parametre değişikliği yok.
- Görülmüş veriden (2020–2026) **yeni bağımsız kanıt üretildiği iddia edilmez.**
- Gerçek zamanlı aşamalardaki işlemler ileriye dönük yeni veridir; ancak §3c'nin süresi
  istatistiksel kanıt için yeterli değildir ve **kabul kriteri olarak kullanılmaz**; yalnız
  önceden yazılmış bir "erken uyarı" ile izlenir (§4).

### 3b. Yazılım — hızlandırılmış oynatma ve sentetik senaryolar (piyasa işlemi DEĞİL)
Canlıda kullanılacak **aynı kod yolu** (sinyal → emir → durum) ile:
1. **Oynatma eşliği:** in-sample verisi mum mum, gerçek zamanlı akış gibi oynatılır;
   üretilen sinyal/emir/çıkış listesi backtest motoruyla **birebir aynı** olmalı
   (tarih, yön, miktar; fiyat farkı ≤ 1 tick). Kabul: %100 eşleşme.
2. **Sentetik senaryolar** (her biri beklenen sonucu yazılı test): giriş dolumu, kısmi
   dolum, reddedilen emir (asgari emir/bakiye), stop dolumu, hedef dolumu, gap stop, gap
   hedef, zaman çıkışı, funding anı geçişi, eksik mum, bağlantı kopması (emir öncesi /
   emir sonrası / pozisyon açıkken), program çökmesi ve **yeniden başlama** (açık
   pozisyon ve bekleyen emirlerin borsadan doğru geri yüklenmesi; çift emir yok), saat
   kayması, aynı sinyalin iki kez işlenmeye çalışılması. Kabul: tüm senaryolar yeşil.
3. Bu aşamadaki hiçbir işlem "yeni piyasa işlemi" veya istatistiksel gözlem sayılmaz.

### 3c. Gerçek zamanlı paper + testnet — PARALEL
- **Paralel yürütme:** aynı canlı sinyaller aynı anda (i) paper (canlı fiyattan simüle
  dolum) ve (ii) testnet (borsa API'sine gerçek emir) olarak işlenir. Biri model, biri
  borsa davranışını ölçer; ardışık yapılmaları gerekmez.
- **Aynı sinyal iki bağımsız gözlem sayılmaz** (paper ve testnet aynı olayın iki
  ölçümüdür).
- **Kabul kriterleri (hepsi):**
  1. Süre en az **4 hafta** (haftalık ve funding döngülerini kapsamak için) **ve**
  2. Emir yaşam döngüsü kapsamı: testnette en az **30 tamamlanmış işlem**, bunların içinde
     en az **5'er** adet stop, hedef ve zaman çıkışı; en az 1 gerçek funding anı geçişi;
     en az 1 planlı yeniden başlama (bakım) testi. Bir tür eksikse süre uzar.
  3. Sinyal eşliği: canlı sinyaller, aynı mumlar üzerinde offline motorla **%100** aynı.
  4. Ele alınmamış hata: **0** (her hata kayda geçer ve kök nedeni kapatılır).
  5. Yürütme farkı ölçülür ve raporlanır: medyan ve 90. yüzdelik slippage, gecikme,
     asgari emir nedeniyle uygulanamayan sinyal oranı. Ölçülen medyan slippage modelin
     (%0,03) **üstündeyse**: maliyet modeli geçersiz sayılır, canlıya geçilmez; bu durum
     yeni karar gerektirir (kural/parametre bu sonuca göre ayarlanmaz).
- 40–75 işlem/ay tasarım hedefiyle 30 işlem ≈ 2–4 hafta; 4 hafta alt sınırı bunu kapsar.

## 4. Küçük canlı (yalnız 3b ve 3c kabul edildikten sonra)
- Tutar 200–300 $, işlem başına risk Z2 = %1, kural V3 aynen.
- **Durma kuralları (önceden):** (i) hesap düşüşü Z1 = %30'a ulaşırsa dur; (ii) **erken
  uyarı:** ilk 100 canlı+testnet-sonrası işlemde gerçekleşmiş ortalama R, hold-out
  ortalamasının 2 standart hata altına düşerse dur ve değerlendir (kural değiştirilmez);
  (iii) her sinyal ve dolum `docs/islem_gunlugu.csv` formatında kaydedilir.
- Canlı sonuçlar V3'ün "doğrulandığı" anlamına gelmez; ileriye dönük gözlem olarak
  raporlanır.

## 5. Onay
Bu planın uygulanması için: (1) ChatGPT denetimi, (2) Burak'ın §1'deki sapmayı açıkça
onaylaması, (3) V3'ün in-sample ve hold-out kapılarını geçmesi gerekir.
