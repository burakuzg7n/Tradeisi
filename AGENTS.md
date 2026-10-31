# AGENTS.md — Bu repoda çalışan tüm yapay zekâlar için kurallar

Bu dosya Claude, ChatGPT ve diğer tüm asistanlar için TEK ortak kural
setidir. Çalışmaya başlamadan önce bu dosyayı, `DEVIR_NOTU.md`'yi ve
`reports/YILLIK_ANALIZ.md`'yi oku.

## Hakem kim?
Yapay zekâların görüşü değil: **testler ve önceden sabitlenmiş kapı
kriterleri.** Üç asistan aynı fikirde olsa bile hold-out sonucu ne diyorsa o
geçerlidir.

## Değişmez kurallar
1. **Kâr garantisi yoktur.** RED sonucu geçerli ve değerlidir; gerçek para
   yanmadan öğrenmek demektir. Kimse "kesin kazandıran sistem" vaat etmez.
2. **Parametre optimizasyonu / turlama = curve fitting = YASAK.** Başarısız
   bir stratejiyi ayar çekerek kurtarmaya çalışma.
3. **Kapı kriterleri sabittir:** Backtest PF > 1.3, DD < %15, 150+ işlem
   (V2 için), OOS sağlam → 300 paper → 100 testnet → ancak sonra 100-500$ canlı.
4. **Tek atış protokolü:** Kurallar veriye bakılmadan yazılır ve commit edilir.
   2020-2024 in-sample'da BİR kez test, sonra 2025+ hold-out. Kural değişirse
   yeni versiyon numarası + yeni tek atış. Aynı kuralda ikinci deneme yok.
5. **Hold-out verisine (2025+) in-sample kararı verilmeden bakılmaz.**
6. **Backtest varsayımları muhafazakâr kalır:** aynı barda stop+target=stop,
   maliyetler dahil, lookahead sıfır. `tradebot/backtest.py`'ı bozma.
7. **Kod sıfırdan yazılır.** Referans kütüphaneler (smart-money-concepts vb.)
   yalnızca fikir içindir; kod kopyalanmaz.
8. **Başarısızlık verileri/raporları silinmez.** `reports/` arşivdir.
9. **Sırlar:** `.env`, API anahtarı, token hiçbir yere yapıştırılmaz, commit
   edilmez.
10. **Merge şartı:** `python -m pytest tests/` yeşil olmadan `main`'e birleştirme yok.

## Bağlayıcı spesifikasyon belgeleri
- `DEVIR_NOTU.md` §8 (V2) ve §9 (Plan B): strateji kuralları.
- `docs/SPEC_EKLERI.md`: bu kuralların tek anlama bağlanmış yorumu (31 Ekim 2026,
  veriye bakılmadan). Sonuç görüldükten sonra değiştirilemez; değişiklik = yeni versiyon.

## Rol dağılımı (öneri)
- **Claude:** kod yazma, backtest, test koşma.
- **ChatGPT:** bağımsız kod/mantık incelemesi (lookahead, hatalı varsayım avı),
  rapor ve doküman kontrolü, sonuçları kapı kriterlerine karşı doğrulama.
- Gemini şu an projede YOK (pasif). Gerekirse sonra eklenir.

## Dal (branch) düzeni
- `main`: yalnız onaylı ve testten geçmiş kod.
- Her asistan kendi dalında çalışır: `claude/...`, `chatgpt/...`.
- Değişiklik Pull Request ile girer; Burak karar verir.

## Teknik notlar
- Strateji SADECE `tradebot/strategy*.py` içinde; altyapıya (backtest, risk,
  journal, execution) strateji değişikliği için dokunma.
- DatetimeIndex'ler `.as_unit("ns")` ile sabitlenmeli (pandas/Python 3.13).
- `.bat` dosyaları ASCII yazılmalı.
- Kullanıcı (Burak) kod bilmez; açıklamalar Türkçe, sade ve adım adım olmalı.
