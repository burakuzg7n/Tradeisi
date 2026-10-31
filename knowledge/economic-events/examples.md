# Economic Events — Örnekler

## Örnek 1: FOMC Günü Davranışı

```
FOMC: 21 Haziran 2026, 18:00 UTC

Sistem takvimi:
  17:30 UTC → news_window aktif ("FOMC Rate Decision")
  Gelen sinyal → reddedildi, loglandı
  
18:10 UTC: Faiz beklenti üstü artırıldı → BTC %4 düştü
  (trade açık olsaydı büyük kayıp)

18:20 UTC → news_window kapandı
18:25 UTC → yeni sinyal geldi, değerlendirildi
```

---

## Örnek 2: NFP Sabahı Senaryosu

```
NFP: İlk Cuma, 12:30 UTC

09:00-12:00 UTC: Normal trading
12:00 UTC → news_window aktif (30dk önce)

12:15: SSL sweep sinyali geldi → reddedildi (news window)
12:30: NFP açıklandı (beklentinin altında) → BTC %2 spike
12:45: news_window kapandı
12:50: Setup hâlâ geçerliyse → entry değerlendirme
```

---

## Örnek 3: Haftalık Takvim Hazırlığı

```python
# Her Pazartesi sabahı çalışır
events = await calendar.fetch_events()

print("Bu hafta yüksek etkili haberler:")
for e in events:
    istanbul_time = e.time_utc.astimezone(pytz.timezone('Europe/Istanbul'))
    print(f"  {e.title}: {istanbul_time.strftime('%a %d/%m %H:%M')} İstanbul")

# Çıktı:
# CPI Data: Sal 24/06 15:30 İstanbul
# FOMC Minutes: Çar 25/06 21:00 İstanbul
# NFP: Cum 27/06 15:30 İstanbul
```
