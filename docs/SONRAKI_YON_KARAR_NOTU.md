# Sonraki yön — karar notu (1 Kasım 2026)

**Statü:** Yalnız seçeneklerin değerlendirmesi. Bu not hiçbir araştırmayı başlatmaz.
Karar Burak'ındır; karar verilene kadar yeni strateji, parametre değişikliği, backtest,
hold-out, paper veya testnet koşusu **yapılmaz**.

## 1. Mevcut durum (değişmez kararlar)

| Strateji | Test | Sonuç | Kayıt |
|---|---|---|---|
| V1 (sweep + FVG, 15m/4h) | 6,5 yıl BTC+ETH | **REDDEDİLDİ** (PF 0,78–0,82) | `reports/YILLIK_ANALIZ.md` |
| V2 (sweep + CHoCH, 15m/4h) | In-sample 2020–2024, tek atış | **REDDEDİLDİ** (KALDI: PF 0,796; DD %22,37; 490 işlem) | `reports/V2_INSAMPLE.*`, commit `52239d7` |
| Plan B v1 (Donchian 55/20, günlük, 4 sembol) | In-sample 2020–2024, tek atış | **REDDEDİLDİ** (KALDI: işlem 37 < 100; DD %20,36 > %15; PF 5,93) | `reports/PLANB_INSAMPLE.*`, commit `6c5ed47` |

Bu ret kararları korunur. Hiçbirinin hold-out'u koşulmamıştır ve koşulmayacaktır. Eşikler
geriye dönük değiştirilmez. 2020–2024 dönemi bu üç strateji ailesi için **görülmüş**
veridir.

## 2. Seçenekler

### A) Projeyi durdurmak / arşivlemek
- Kod, testler, raporlar, kilitler ve bu belgeler olduğu gibi kalır; `reports/` silinmez.
- Artısı: ek zaman ve dikkat maliyeti yok; mevcut sonuçlar dürüstçe kapanır.
- Eksisi: gelecekteki veriden bilgi toplanmaz.
- Geçerli ve meşru bir sonuçtur; "başarısızlık" değil, bilinçli bir durma kararıdır.

### B) Plan B v1'i değiştirmeden gelecekteki veride yalnız araştırma amacıyla izlemek
- Kurallar, parametreler ve kod **aynen** kalır; yalnız 2026-10-31 sonrasındaki,
  hiç görülmemiş veride gerçek parasız kayıt tutulur.
- **Bu seçenek ret kararını KALDIRMAZ.** Mevcut protokolde paper (300) / testnet (100)
  aşamaları, kapıları GEÇEN bir stratejinin sonraki aşamasıdır; bu izleme o kabul
  aşamasının yerine geçmez ve canlıya geçiş hakkı vermez.
- Başlatılmadan önce ayrı ve önceden yazılmış bir izleme planı gerekir (süre, ölçülecek
  metrikler, ne zaman ne sonuç çıkarılacağı). Günlük sistem yılda az işlem ürettiği için
  anlamlı bir sonuç uzun süre (yıllar) gerektirebilir; bu süre izleme planında önceden
  yazılmalıdır.

### C) Farklı bir hipotezi ayrı bir araştırma olarak değerlendirmek
- Yeni hipotez, veriye bakılmadan yazılır ve yeni bir tek atış protokolüyle test edilir.
- 2020–2024 (ve kısmen 2025+) verisi bu projede **görülmüştür**. Bu dönemde yapılacak
  yeni bir test "keşif" olarak raporlanabilir ama **bağımsız doğrulama diye sunulamaz**.
  Bağımsız doğrulama yalnız hiç görülmemiş veriyle (gelecekteki veri ya da önceden
  ayrılmış ve hiç bakılmamış bir veri kümesi) yapılabilir.
- Plan B v1'in sonucunu gördükten sonra ona benzeyen bir "Plan B.1" (ör. daha fazla
  sembol, farklı kontenjan, farklı eşik) bu dönemde test edilirse sonuç, gördüğümüz
  sonuçtan etkilenmiş olur; bu seçenek bu nedenle özellikle dikkat ister.

## 3. Gelecekteki araştırmalar için: test süresi ve işlem sayısı sonuçlara bakmadan nasıl planlanır?

Plan B v1'de 100 işlem eşiği (E9), tasarımın (4 sembol, günlük bar, en fazla 2 pozisyon)
o dönemde üretebileceği işlem sayısı önceden tahmin edilmeden konmuştu. Aşağıdaki adımlar
bu hatanın tekrarlanmaması içindir. **Mevcut 100 işlem ve %15 DD eşikleri bu notla
tartışmaya açılmaz ve değiştirilmez.**

1. **Önce soru, sonra eşik.** Ne ölçülmek istendiği yazılır (ör. "işlem başına net
   beklenti > 0 mı?"). Eşikler bu soruya göre seçilir.
2. **İşlem sıklığını gerçek sonuçlardan bağımsız tahmin et.** Kural mekaniğinden ve
   sentetik veriden (gerçekçi oynaklıkta rastgele yürüyüş) sinyal ve işlem sayısı tahmin
   edilir. Gerçek fiyat verisinde PnL'ye bakılarak işlem sayısı "denenmez".
3. **Yeterli örneklem için süre hesabı.** Hedeflenen istatistiksel güven için gereken işlem
   sayısı (örnek: beklentinin işaretini anlamlı ayırmak için) ve 2. adımdaki sıklıktan
   gereken süre hesaplanır. Mevcut veri bu süreyi karşılamıyorsa ya tasarım değiştirilir
   (sonuç görülmeden), ya daha uzun bir ileri test planlanır, ya da araştırma yapılmaz.
4. **DD eşiğini riskle birlikte tasarla.** İşlem başına risk, eşzamanlı pozisyon sayısı ve
   beklenen kazanma oranından, sıfır-beklentili (şanslı/şanssız olmayan) bir sistemin
   sentetik veride göreceği DD dağılımı önceden çıkarılır; DD kapısı bu dağılıma göre
   anlamlı bir yere konur.
5. **Fizibilite kontrolünü kayda geçir.** 2–4. adımların sonuçları, kurallar ve kapılarla
   birlikte, gerçek veride hiçbir koşu yapılmadan commit edilir ve bağımsız denetimden
   geçer. Kapılar bu tahminle uyumsuzsa koşu başlamaz.
6. **Veri ayrımı.** Hangi dönemin keşif, hangisinin doğrulama olduğu ve doğrulama
   döneminin hiç görülmediği önceden yazılır.

## 4. Denetimin kapsamı ve sınırları (sonuçlar okunurken)

- **İncelenen:** V2 ve Plan B v1 kodu (motor, sinyaller, veri, koşucular) ve testleri,
  PR #1–#9 boyunca ChatGPT tarafından bağımsız incelendi; bulunan hatalar düzeltildi ve
  regresyon testleriyle (çoğu mutasyon denemesiyle) kapatıldı. Sonuç raporlarının mühürü,
  kapıların yeniden hesabı, parmak izi ve iç aritmetik tutarlılığı ayrıca doğrulandı.
- **Bu bir hatasızlık garantisi değildir.** Testler sentetik senaryolarla sınırlıdır;
  incelenmeyen durumlar ve bilinmeyen hatalar olabilir.
- **Ham sonuçlardan bağımsız yeniden hesap sınırlı:** raporlar tam işlem listesini ve
  günlük equity serisini arşivlemiyor; CSV verileri depoda değil (yalnız sha256). Bu
  nedenle PF/DD'nin ham veriden bağımsız olarak yeniden hesaplanması bugüne kadar
  yapılamadı; doğrulanan şey raporların iç tutarlılığı ve kayıt bütünlüğüdür.
- **Bilinen sınırlamalar:** V2 verisi spot API'den (`api.binance.com`) indirilmiştir (perp
  değil); arşiv dosyalarının kökeni ayrıca doğrulanmadı. V2 raporundaki `dirty=True`
  nedeninin koşu anındaki kaydı yoktur. Plan B'de E13 dönem sonu tasfiyesi, dönem sonu
  verisine bakan onaylı bir varsayımdır. V2 (Python 3.10/pandas 2.3, Linux) ve Plan B
  (Python 3.13/pandas 3.0, Windows) farklı ortamlarda koşulmuştur.
