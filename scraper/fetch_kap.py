"""
KAP Bildirim Scraper
Her çalışmada son 72 saatin tüm KAP özel durum bildirimlerini çeker
ve data/kap_news.json dosyasına yazar.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ── Sabitler ──────────────────────────────────────────────────
BASE_URL = "https://www.kap.org.tr"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": "https://www.kap.org.tr/tr/Bildirim/Ozel",
    "Origin": "https://www.kap.org.tr",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "kap_news.json"
HOURS_BACK = 72


def fetch_disclosures() -> list[dict]:
    """KAP API'den son bildirimleri çeker."""
    items = []

    # Birden fazla endpoint dene
    endpoints = [
        f"{BASE_URL}/tr/api/disclosures?orderBy=publishDate&orderDir=desc&pageSize=100&pageIndex=0",
        f"{BASE_URL}/tr/api/disclosures?type=ozel&orderBy=publishDate&orderDir=desc&pageSize=100&pageIndex=0",
        f"{BASE_URL}/tr/api/disclosures?orderBy=publishDate&orderDir=desc&pageSize=50&pageIndex=0",
    ]

    session = requests.Session()

    # Önce ana sayfayı ziyaret et (session cookie al)
    try:
        session.get(f"{BASE_URL}/tr", headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }, timeout=20)
        time.sleep(1)
    except Exception:
        pass

    for url in endpoints:
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            print(f"  {url[-70:]} → {r.status_code}")

            if r.status_code == 200:
                data = r.json()
                raw_list = (
                    data if isinstance(data, list)
                    else data.get("data", data.get("items", data.get("disclosures", [])))
                )
                if raw_list:
                    items = raw_list
                    print(f"  ✓ {len(items)} bildiri alındı")
                    break
        except Exception as e:
            print(f"  ✗ {e}")
        time.sleep(1)

    return items


def parse_date(raw: str) -> datetime | None:
    """Çeşitli tarih formatlarını parse eder."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    # "10.07.2026 14:30" formatı
    try:
        parts = raw.split(" ")
        if len(parts) >= 2:
            dp = parts[0].split(".")
            if len(dp) == 3:
                tp = parts[1].split(":")
                return datetime(
                    int(dp[2]), int(dp[1]), int(dp[0]),
                    int(tp[0]), int(tp[1] if len(tp) > 1 else 0),
                    tzinfo=timezone.utc
                )
    except Exception:
        pass
    return None


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def filter_and_format(raw_items: list[dict]) -> list[dict]:
    """Son 72 saat içindeki bildirimleri filtreler ve formatlar."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    result = []

    for d in raw_items:
        raw_date = (
            d.get("publishDate")
            or d.get("releaseDate")
            or d.get("disclosureDate")
            or ""
        )
        dt = parse_date(str(raw_date))
        within_72h = dt is not None and dt > cutoff

        title = (
            d.get("title")
            or d.get("subject")
            or d.get("companyName")
            or "KAP Bildirimi"
        )
        subject = d.get("subject") or d.get("disclosureClass") or ""
        source = d.get("companyCode") or d.get("stockCode") or "KAP"
        disc_id = d.get("id") or d.get("disclosureIndex") or ""
        url = (
            d.get("url")
            or (f"{BASE_URL}/tr/Bildirim/{disc_id}" if disc_id else "")
        )

        result.append({
            "title": str(title),
            "summary": str(subject),
            "source": str(source),
            "time": fmt_date(dt) if dt else fmt_date(datetime.now(timezone.utc)),
            "url": str(url),
            "within72h": within_72h,
            "rawDate": str(raw_date),
        })

    # Sadece 72h içindekileri al, yoksa hepsini
    filtered = [i for i in result if i["within72h"]]
    return filtered if filtered else result[:30]


def fallback_scrape() -> list[dict]:
    """KAP API çalışmazsa HTML sayfasını parse et."""
    print("HTML scraping deneniyor...")
    result = []
    try:
        r = requests.get(
            f"{BASE_URL}/tr/Bildirim/Ozel",
            headers={**HEADERS, "Accept": "text/html,application/xhtml+xml"},
            timeout=20,
        )
        if r.status_code != 200:
            return result

        text = r.text
        # JSON data içinde bildirim ara
        # window.__data veya benzeri
        patterns = [
            r'"title":"([^"]{5,120})"[^}]*"companyCode":"([^"]{2,10})"[^}]*"publishDate":"([^"]{10,30})"',
            r'"companyCode":"([^"]{2,10})"[^}]*"title":"([^"]{5,120})"',
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            if matches:
                print(f"  HTML'den {len(matches)} eşleşme bulundu")
                for m in matches[:50]:
                    if len(m) == 3:
                        result.append({
                            "title": m[0], "summary": "",
                            "source": m[1], "time": m[2][:16],
                            "url": "", "within72h": True, "rawDate": m[2],
                        })
                    elif len(m) == 2:
                        result.append({
                            "title": m[1], "summary": "",
                            "source": m[0], "time": fmt_date(datetime.now(timezone.utc)),
                            "url": "", "within72h": True, "rawDate": "",
                        })
                break
    except Exception as e:
        print(f"  HTML scrape hatası: {e}")
    return result


def main():
    print(f"KAP Scraper başlatıldı — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Data klasörü oluştur
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Bildirimleri çek
    raw = fetch_disclosures()

    if not raw:
        print("API başarısız, HTML scraping deneniyor...")
        items = fallback_scrape()
    else:
        items = filter_and_format(raw)

    print(f"Toplam {len(items)} bildiri işlendi")

    # Mevcut dosya varsa oku, yenileri başa ekle
    existing = []
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f).get("items", [])
        except Exception:
            existing = []

    # Yeni öğeleri başa ekle, tekrarları kaldır
    existing_titles = {e["title"] + e["source"] for e in existing}
    new_items = [i for i in items if i["title"] + i["source"] not in existing_titles]
    merged = new_items + existing

    # 72 saat dışındakileri temizle
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    merged_filtered = []
    for item in merged:
        dt = parse_date(item.get("rawDate", ""))
        if dt is None or dt > cutoff:
            merged_filtered.append(item)

    # Maksimum 200 kayıt tut
    merged_filtered = merged_filtered[:200]

    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "count": len(merged_filtered),
        "items": merged_filtered,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✓ {OUTPUT_FILE} dosyasına {len(merged_filtered)} bildiri yazıldı")


if __name__ == "__main__":
    main()
