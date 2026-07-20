"""
KAP Bildirim Scraper v2
KAP HTML sayfasını parse ederek son bildirimleri çeker.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

OUTPUT_FILE = Path(__file__).parent.parent / "data" / "kap_news.json"
BASE_URL = "https://www.kap.org.tr"
HOURS_BACK = 72


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def visit_homepage(s: requests.Session):
    """Ana sayfayı ziyaret edip session cookie al."""
    try:
        r = s.get(f"{BASE_URL}/tr", headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }, timeout=20)
        print(f"  Ana sayfa: {r.status_code}")
        time.sleep(2)
    except Exception as e:
        print(f"  Ana sayfa hatası: {e}")


def try_json_api(s: requests.Session) -> list[dict]:
    """JSON API endpoint'lerini dene."""
    endpoints = [
        f"{BASE_URL}/tr/api/disclosures?orderBy=publishDate&orderDir=desc&pageSize=100&pageIndex=0",
        f"{BASE_URL}/tr/api/disclosures?type=ozel&orderBy=publishDate&orderDir=desc&pageSize=50",
        f"{BASE_URL}/en/api/disclosures?orderBy=publishDate&orderDir=desc&pageSize=50&pageIndex=0",
    ]
    for url in endpoints:
        try:
            r = s.get(url, headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{BASE_URL}/tr/Bildirim/Ozel",
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=20)
            print(f"  API {r.status_code}: {url[-60:]}")
            if r.status_code == 200 and r.text.strip().startswith('['):
                data = r.json()
                if isinstance(data, list) and data:
                    print(f"  ✓ JSON API: {len(data)} kayıt")
                    return data
            elif r.status_code == 200:
                try:
                    data = r.json()
                    for key in ["data", "items", "disclosures", "result"]:
                        if key in data and isinstance(data[key], list) and data[key]:
                            print(f"  ✓ JSON API ({key}): {len(data[key])} kayıt")
                            return data[key]
                except Exception:
                    pass
        except Exception as e:
            print(f"  API hata: {e}")
        time.sleep(1)
    return []


def try_html_scrape(s: requests.Session) -> list[dict]:
    """KAP HTML sayfasını parse et."""
    pages = [
        f"{BASE_URL}/tr/Bildirim/Ozel",
        f"{BASE_URL}/tr/bildirim/ozel",
        f"{BASE_URL}/tr/Ozel-Durum-Aciklamalari",
    ]
    for page_url in pages:
        try:
            r = s.get(page_url, headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{BASE_URL}/tr",
            }, timeout=25)
            print(f"  HTML {r.status_code}: {page_url}")
            if r.status_code != 200:
                continue

            text = r.text
            results = []

            # JSON data blocklarını ara
            # Pattern 1: disclosureIndex ile
            pat1 = re.findall(
                r'"disclosureIndex"\s*:\s*(\d+)[^}]*?"title"\s*:\s*"([^"]{5,150})"[^}]*?"stockCode"\s*:\s*"([^"]{2,10})"[^}]*?"publishDate"\s*:\s*"([^"]{10,30})"',
                text
            )
            if pat1:
                print(f"  HTML pattern1: {len(pat1)} kayıt")
                for m in pat1[:100]:
                    results.append({
                        "id": m[0], "title": m[1],
                        "companyCode": m[2], "publishDate": m[3],
                        "subject": ""
                    })
                return results

            # Pattern 2: title + stockCode + publishDate
            pat2 = re.findall(
                r'"title"\s*:\s*"([^"]{5,150})"[^}]{0,200}?"stockCode"\s*:\s*"([^"]{2,10})"[^}]{0,200}?"publishDate"\s*:\s*"([^"]{10,30})"',
                text
            )
            if pat2:
                print(f"  HTML pattern2: {len(pat2)} kayıt")
                for m in pat2[:100]:
                    results.append({
                        "title": m[0], "companyCode": m[1],
                        "publishDate": m[2], "subject": ""
                    })
                return results

            # Pattern 3: Geniş arama
            pat3 = re.findall(
                r'"companyCode"\s*:\s*"([A-Z]{2,6})"[^}]{0,300}?"title"\s*:\s*"([^"]{5,150})"',
                text
            )
            if pat3:
                print(f"  HTML pattern3: {len(pat3)} kayıt")
                now = datetime.now(timezone.utc).isoformat()
                for m in pat3[:50]:
                    results.append({
                        "companyCode": m[0], "title": m[1],
                        "publishDate": now, "subject": ""
                    })
                return results

        except Exception as e:
            print(f"  HTML hata: {e}")
        time.sleep(1)
    return []


def try_alternative_sources() -> list[dict]:
    """Alternatif haber kaynaklarından KAP haberleri çek."""
    results = []

    # Midas KAP haberleri — zengin içerik, gerçek bildirimler
    try:
        r = requests.get(
            "https://www.getmidas.com/kap-haberleri/",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "tr-TR,tr;q=0.9",
                "Referer": "https://www.getmidas.com/",
            },
            timeout=20,
        )
        print(f"  Midas KAP: {r.status_code}")
        if r.status_code == 200:
            text = r.text
            # Pattern: hisse kodu ve içerik bloğu
            # Yapı: [TICKER X,XX%] paragraf metni
            paragraphs = re.findall(
                r'<p[^>]*>([\s\S]*?)</p>',
                text,
                re.DOTALL
            )
            items_found = []
            for para in paragraphs:
                clean = re.sub(r'<[^>]+>', ' ', para)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if len(clean) > 30 and len(clean) < 500:
                    # Hisse kodu bul
                    ticker_match = re.search(r'\b([A-Z]{3,6})\b', clean)
                    ticker = ticker_match.group(1) if ticker_match else 'KAP'
                    items_found.append({
                        "title": clean[:200],
                        "subject": "",
                        "companyCode": ticker,
                        "publishDate": datetime.now(timezone.utc).isoformat(),
                        "url": "https://www.getmidas.com/kap-haberleri/",
                    })
            if items_found:
                print(f"  ✓ Midas KAP: {len(items_found)} haber")
                return items_found[:50]
    except Exception as e:
        print(f"  Midas KAP hata: {e}")

    # Bigpara KAP haberleri
    try:
        r = requests.get(
            "https://bigpara.hurriyet.com.tr/haberler/kap-haberleri/",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9",
                "Referer": "https://bigpara.hurriyet.com.tr/",
            },
            timeout=20,
        )
        print(f"  bigpara KAP haberleri: {r.status_code}")
        if r.status_code == 200:
            text = r.text
            # bigpara URL pattern: /haberler/kap-haberleri/BASLIK_IDXXXXX/
            pat = re.findall(
                r'href="(https://bigpara\.hurriyet\.com\.tr/haberler/kap-haberleri/[^"]+)"[^>]*>\s*([^<]{10,200})',
                text
            )
            if not pat:
                # Alternatif pattern
                pat = re.findall(
                    r'href="(/haberler/kap-haberleri/[^"]+)"[^>]*>\s*([^<]{10,200})',
                    text
                )
                pat = [("https://bigpara.hurriyet.com.tr" + u, t) for u, t in pat]
            if pat:
                print(f"  ✓ bigpara KAP haberleri: {len(pat)} haber")
                seen_urls = set()
                for url, title in pat:
                    title = title.strip()
                    if len(title) > 10 and url not in seen_urls:
                        seen_urls.add(url)
                        # Başlıktan ***SEMBOL*** formatını temizle
                        clean_title = re.sub(r'^\*+[A-Z0-9]+\*+\s*', '', title).strip()
                        results.append({
                            "title": clean_title if clean_title else title,
                            "subject": _extract_type(title),
                            "companyCode": _extract_ticker(title),
                            "publishDate": datetime.now(timezone.utc).isoformat(),
                            "url": url,
                        })
                if results:
                    return results
    except Exception as e:
        print(f"  bigpara KAP hata: {e}")

    # Son çare: RSS kaynakları
    rss_sources = [
        {"url": "https://api.rss2json.com/v1/api.json?rss_url=https://www.haberturk.com/rss/ekonomi.xml", "name": "Habertürk"},
        {"url": "https://api.rss2json.com/v1/api.json?rss_url=https://www.ntv.com.tr/ekonomi.rss", "name": "NTV Ekonomi"},
        {"url": "https://api.rss2json.com/v1/api.json?rss_url=https://feeds.bbci.co.uk/turkce/ekonomi/rss.xml", "name": "BBC Türkçe"},
    ]
    for src in rss_sources:
        try:
            r = requests.get(src["url"], timeout=12)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                if items:
                    print(f"  ✓ {src['name']}: {len(items)} haber")
                    for item in items[:20]:
                        results.append({
                            "title": item.get("title", ""),
                            "subject": _strip_html(item.get("description", ""))[:200],
                            "companyCode": _extract_ticker(item.get("title", "")),
                            "publishDate": item.get("pubDate", ""),
                            "url": item.get("link", ""),
                        })
                    if results:
                        break
        except Exception as e:
            print(f"  {src['name']} hata: {e}")

    return results


def _extract_ticker(text: str) -> str:
    """Metinden hisse kodu çıkar."""
    # ***THYAO*** formatı
    m = re.search(r'\*+([A-Z]{2,6})\*+', text)
    if m:
        return m.group(1)
    # Büyük harf kelime
    m = re.search(r'\b([A-Z]{3,6})\b', text)
    return m.group(1) if m else "KAP"


def _extract_type(text: str) -> str:
    """Parantez içindeki bildirim türünü çıkar."""
    m = re.search(r'\(([^)]{5,80})\)', text)
    return m.group(1).strip() if m else ""


def _strip_html(html: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&\w+;', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_date(raw: str):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        pass
    try:
        # RFC 2822: "Wed, 15 Jul 2026 10:30:00 +0300"
        months = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
        }
        parts = raw.replace(",", "").strip().split()
        if len(parts) >= 5:
            day = int(parts[1])
            month = months.get(parts[2], 1)
            year = int(parts[3])
            tp = parts[4].split(":")
            return datetime(year, month, day, int(tp[0]),
                            int(tp[1]) if len(tp) > 1 else 0,
                            tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def format_items(raw: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)
    result = []
    for d in raw:
        raw_date = (d.get("publishDate") or d.get("pubDate") or
                    d.get("releaseDate") or "")
        dt = parse_date(str(raw_date))
        within72h = dt is not None and dt.replace(tzinfo=None) > cutoff.replace(tzinfo=None)

        title = (d.get("title") or d.get("subject") or
                 d.get("companyName") or "KAP Bildirimi")
        subject = d.get("subject") or d.get("disclosureClass") or ""
        source = (d.get("companyCode") or d.get("stockCode") or
                  d.get("company") or "KAP")
        disc_id = d.get("id") or d.get("disclosureIndex") or ""
        url = d.get("url") or (
            f"{BASE_URL}/tr/Bildirim/{disc_id}" if disc_id else "")

        result.append({
            "title": str(title),
            "summary": str(subject),
            "source": str(source),
            "time": fmt_date(dt) if dt else fmt_date(datetime.now(timezone.utc)),
            "url": str(url),
            "within72h": within72h,
            "rawDate": str(raw_date),
        })

    filtered = [i for i in result if i["within72h"]]
    return filtered if filtered else result[:30]


def main():
    print(f"\n{'='*50}")
    print(f"KAP Scraper v2 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    s = make_session()

    # 1. Ana sayfayı ziyaret et
    visit_homepage(s)

    # 2. JSON API dene
    print("\n[1] JSON API deneniyor...")
    raw = try_json_api(s)

    # 3. HTML scrape
    if not raw:
        print("\n[2] HTML scraping deneniyor...")
        raw = try_html_scrape(s)

    # 4. Alternatif kaynaklar
    if not raw:
        print("\n[3] Alternatif kaynaklar deneniyor...")
        raw = try_alternative_sources()

    print(f"\nToplam {len(raw)} ham kayıt")

    # Format ve filtrele
    items = format_items(raw) if raw else []

    # Mevcut dosya ile birleştir
    existing = []
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f).get("items", [])
        except Exception:
            existing = []

    # Yeni öğeleri başa ekle, tekrar olmayanları
    seen = {e["title"] + e.get("source", "") for e in existing}
    new_items = [i for i in items if i["title"] + i.get("source", "") not in seen]
    merged = new_items + existing

    # 72 saat dışındakileri temizle
    cutoff_naive = (datetime.now(timezone.utc) - timedelta(hours=HOURS_BACK)).replace(tzinfo=None)
    merged = [
        i for i in merged
        if not parse_date(i.get("rawDate", ""))
        or parse_date(i.get("rawDate", "")).replace(tzinfo=None) > cutoff_naive
    ][:200]

    output = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "count": len(merged),
        "items": merged,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {len(merged)} bildiri kaydedildi → {OUTPUT_FILE}")
    print(f"  Yeni: {len(new_items)}, Mevcut: {len(existing)}")


if __name__ == "__main__":
    main()
