"""Check public xPrice charts for strict price records on a small list of URLs."""
import argparse
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
import json
import re
from urllib.parse import urljoin, urlsplit
import subprocess
from zoneinfo import ZoneInfo

ORIGIN = "https://xprice.ro"
WINDOWS = {"6": 182, "12": 365, "24": 730}


def fetch(url, fragment=False):
    headers = ["-H", "HX-Request: true"] if fragment else []
    return subprocess.check_output(
        ["curl", "-fsSL", "--max-time", "20", *headers, "--", url], text=True
    )


def record_prices(points, today):
    if today not in points or max(points) != today:
        return {}
    current = points[today]
    records = {}
    for window, days in WINDOWS.items():
        cutoff = today - timedelta(days=days)
        previous = [price for date, price in points.items() if cutoff <= date < today]
        if previous and current < min(previous):
            records[window] = {
                "previousMin": min(previous) / 100,
                "percentBelow": (min(previous) - current) * 100 / min(previous),
                "observations": len(previous),
            }
    return records


def scan(url, today):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "xprice.ro" or not parsed.path.startswith("/istoric-pret/"):
        raise ValueError("Expected a public xprice.ro product URL")
    url = ORIGIN + parsed.path + "?hist=730"
    page = fetch(url)
    fragment = re.search(r'hx-get="([^"]*\?partial=hist[^"]*)"', page)
    title = re.search(r"<h1\b[^>]*>(.*?)</h1>", page, re.S)
    if not fragment or not title:
        raise ValueError("Public product chart or title missing")
    chart_url = urljoin(url, unescape(fragment[1]))
    if urlsplit(chart_url).netloc != "xprice.ro" or urlsplit(chart_url).scheme != "https":
        raise ValueError("Unexpected chart origin")
    chart = fetch(chart_url, fragment=True)
    points = {}
    for date_text, whole, decimals in re.findall(
        r'data-date="(\d{2}\.\d{2}\.\d{4})"\s+data-price-int="([\d.]+)"\s+data-price-decimals="(\d{2})"',
        chart,
    ):
        date = datetime.strptime(date_text, "%d.%m.%Y").date()
        price = int(whole.replace(".", "")) * 100 + int(decimals)
        if price > 0:
            points[date] = min(price, points.get(date, price))
    if not points:
        raise ValueError("No dated chart points found")
    print(f"{parsed.path}: {len(points)} dates; latest {max(points)}")
    records = record_prices(points, today)
    if records:
        return {
            "name": unescape(re.sub(r"<[^>]+>", "", title[1])).strip(),
            "price": points[today] / 100,
            "observedDate": today.isoformat(),
            "url": url,
            "records": records,
        }
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--output", type=Path, default=Path("xprice-records.json"))
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("Europe/Bucharest")).date()
    results = [row for url in dict.fromkeys(args.urls) if (row := scan(url, today))]
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(results)} strict records")


if __name__ == "__main__":
    main()
