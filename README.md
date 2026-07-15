# Teknik Bakış — KAP Bildirim Toplayıcı

Bu repo, KAP (Kamuoyu Aydınlatma Platformu) bildirimlerini her 10 dakikada bir
otomatik olarak çekip `data/kap_news.json` dosyasına kaydeder.

## Flutter Entegrasyonu

Flutter uygulaması şu URL'den JSON'u okur:

```
https://raw.githubusercontent.com/KULLANICI_ADI/teknik-bakis-kap/main/data/kap_news.json
```

## JSON Formatı

```json
{
  "lastUpdated": "2026-07-15T10:30:00+00:00",
  "count": 45,
  "items": [
    {
      "title": "THYAO — Özel Durum Açıklaması",
      "summary": "Özel Durum",
      "source": "THYAO",
      "time": "15.07.2026 10:25",
      "url": "https://www.kap.org.tr/tr/Bildirim/12345",
      "within72h": true,
      "rawDate": "2026-07-15T10:25:00"
    }
  ]
}
```

## Kurulum

1. Bu repoyu GitHub'a push et
2. GitHub Actions otomatik olarak her 10 dakikada çalışır
3. `data/kap_news.json` her seferinde güncellenir
