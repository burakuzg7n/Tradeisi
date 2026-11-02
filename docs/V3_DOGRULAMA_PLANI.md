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
| R3a Emir/API davranışı | Emir türleri, reddedilen emir, asgari emir, durum senkronu | Testnet (§3c) |
| R3b Üretim piyasası maliyeti | Gerçek dolum, slippage, kuyruk maliyetler | **Yalnız gerçek piyasada** (küçük canlı, §4); testnet ve paper bunu kanıtlamaz |
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
  istatistiksel kanıt için yeterli değildir ve **kabul kriteri olarak kullanılmaz**.
  Performans izleme kuralı (erken uyarı) **yalnız küçük canlı aşamada** uygulanır (§4);
  paper/testnet sırasında performansa göre durma kararı verilmez.

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
  5. **Uygulanabilirlik engelleri** (testnet + paper, kabul sınırlı):
     - Emir gecikmesi: sinyal mumunun kapanışından emrin borsaya ulaşmasına kadar süre;
       işlemlerin **≥ %95**'inde ≤ 60 saniye.
     - Uygulanamayan sinyal oranı (asgari emir, bakiye, reddedilen emir, kaçırılan
       sinyal): **≤ %5**.
     - Stop ve hedef emirleri her pozisyon için girişten sonra ≤ 60 saniyede borsada
       doğrulanmış olmalı: **%100**.
     Biri sağlanmazsa canlıya geçilmez; kural/parametre bu sonuca göre değiştirilmez.
  6. **Testnet dolum/slippage verisi üretim maliyeti kanıtı DEĞİLDİR** (testnet likiditesi
     ve emir defteri üretimi temsil etmez); paper dolumları modelin kendisidir. Bu
     aşamada maliyet modeli doğrulanmış sayılmaz; maliyet kontrolü §4'tedir.
- 40–75 işlem/ay tasarım hedefiyle 30 işlem ≈ 2–4 hafta; 4 hafta alt sınırı bunu kapsar.

## 4. Küçük canlı (yalnız 3b ve 3c kabul edildikten sonra)
- Tutar 200–300 $, işlem başına risk Z2 = %1, kural V3 aynen. Her sinyal ve dolum
  `docs/islem_gunlugu.csv` formatında kaydedilir.
- **Sert durma:** hesap düşüşü (gerçekleşmiş + açık pozisyon değeri) Z1 = %30'a
  ulaşırsa dur. (Gap ve gecikme nedeniyle gerçekleşen kayıp %30'u aşabilir; bu bir
  garanti değildir.)
- **Üretim maliyeti kontrolü (önceden sabit):** kontrol noktaları **50., 100. ve
  sonrasında her 100.** canlı işlem. Ölçüt: işlem başına gerçekleşmiş toplam maliyet
  (ücret + slippage + funding) R cinsinden **ortalaması** — medyan değil; kuyruk
  maliyetleri ortalamaya girer. Model maliyetinin (aynı işlemler için modelin
  hesaplayacağı maliyet) ortalamasını **%50'den fazla** aşarsa dur ve değerlendir. 90. ve
  99. yüzdelik ayrıca raporlanır.
- **Performans erken uyarısı (tek tanım):**
  - Seri: canlı dönemin tüm UTC günleri için günlük net R toplamı (işlemsiz gün 0;
    gün ataması V3 §4.9).
  - Referans: hold-out dönemindeki aynı tanımlı günlük R serisinin ortalaması m_h.
  - Kontrol noktaları: canlıda **60., 120., 180. ...** gün (her 60 günde bir); ara
    bakış yok.
  - İstatistik: canlı serinin ortalaması m_c ve Newey–West HAC standart hatası SE_c
    (Bartlett, L = floor(4 × (T/100)^(2/9)), en az 1; T = canlı gün sayısı).
  - Kural: m_c < m_h − 2 × SE_c ise **dur ve değerlendir** (kural değiştirilmez; devam
    kararı yeni bir yazılı karar gerektirir). Tekrarlanan bakışlar yanlış alarm olasılığını
    artırır; bu kural bir "durup bakma" tetiğidir, istatistiksel ret testi değildir.
- Canlı sonuçlar V3'ün "doğrulandığı" anlamına gelmez; ileriye dönük gözlem olarak
  raporlanır.

## 5. Onay
Bu planın uygulanması için: (1) ChatGPT denetimi, (2) Burak'ın §1'deki sapmayı açıkça
onaylaması, (3) V3'ün in-sample ve hold-out kapılarını geçmesi gerekir.
