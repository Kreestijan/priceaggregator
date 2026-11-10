import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

key = os.environ.get("APISH_KEY")
if not key:
    raise SystemExit("Set APISH_KEY in the environment before running the import.")

# Limit each manual import to 24 requests.
categories = (
    "telefoane-mobile", "televizoare", "aspiratoare",
    "masini-de-spalat-rufe", "monitoare-led", "laptopuri",
    "ssd", "casti-audio",
)
checked_at = datetime.now(timezone.utc).isoformat()
offers = {}
for category in categories:
    page = 1
    for _ in range(3):
        query = urlencode({"site": "ro", "path": f"/{category}/c", "page": page})
        request = Request(
            f"https://api.api.sh/emag/v1/search?{query}",
            headers={"x-api-key": key, "Accept": "application/json"},
        )
        with urlopen(request, timeout=40) as response:
            data = json.load(response)
        for item in data["items"]:
            offer = item.get("offer") or {}
            price_data = offer.get("price") or {}
            price = price_data.get("current")
            url = item.get("url") or ""
            name = item.get("name")
            pnk = item.get("pnk")
            if (
                offer.get("availability_code") != "in_stock"
                or offer.get("is_used") is True
                or price_data.get("currency") != "RON"
                or type(price) not in (int, float) or not 0 < price < float("inf")
                or not name or not pnk
                or urlsplit(url).scheme != "https"
                or urlsplit(url).netloc != "www.emag.ro"
            ):
                continue
            offers[pnk] = {
                "name": name, "price": price, "url": url,
                "category": item.get("category") or category,
                "seller": (offer.get("vendor") or {}).get("name"),
                "inStock": True, "checkedAt": checked_at,
            }
        next_page = data.get("next_page")
        if type(next_page) is not int or next_page <= page:
            break
        page = next_page
if not offers:
    raise SystemExit("No eligible offers returned. Existing snapshot preserved.")
Path("offers.json").write_text(
    json.dumps(list(offers.values()), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Imported {len(offers)} in-stock products.")
