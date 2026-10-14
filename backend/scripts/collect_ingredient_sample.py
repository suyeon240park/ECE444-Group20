"""Fetch a reproducible Canada-tagged OFF sample for ingredient validation.

Opt-in network command; pages are cached and requests are at least seven seconds
apart. Selection follows the returned API page order, never parser success.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

FIELDS = ",".join(
    [
        "code",
        "product_name",
        "product_name_en",
        "product_name_fr",
        "brands",
        "countries_tags",
        "categories_tags",
        "lang",
        "ingredients_text",
        "ingredients_text_en",
        "ingredients_text_fr",
        "ingredients",
        "last_modified_t",
    ]
)


def selected_text(product):
    return next(
        (
            product[k].strip()
            for k in ("ingredients_text_en", "ingredients_text", "ingredients_text_fr")
            if isinstance(product.get(k), str) and product[k].strip()
        ),
        None,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "LabelLens-ECE444-Group20/0.1 (https://github.com/suyeon240park/ECE444-Group20)"
        }
    )
    records, seen, pages, excluded = [], set(), [], []
    for page in range(1, 101):
        cached = args.cache / f"page-{page:03}.json"
        if cached.exists():
            envelope = json.loads(cached.read_text(encoding="utf-8"))
        else:
            for attempt in range(4):
                response = session.get(
                    "https://world.openfoodfacts.org/api/v2/search",
                    params={
                        "countries_tags_en": "canada",
                        "sort_by": "code",
                        "page_size": 100,
                        "page": page,
                        "fields": FIELDS,
                    },
                    timeout=60,
                )
                if response.status_code not in {429, 502, 503, 504} or attempt == 3:
                    break
                delay = 15 * (attempt + 1)
                print(f"Page {page}: HTTP {response.status_code}; retrying in {delay}s", flush=True)
                time.sleep(delay)
            response.raise_for_status()
            envelope = {
                "url": response.url,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "response": response.json(),
            }
            cached.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(7)
        pages.append({k: envelope[k] for k in ("url", "retrieved_at")})
        products = envelope["response"].get("products", [])
        if not products:
            break
        for product in products:
            code = product.get("code", "")
            if code in seen:
                continue
            seen.add(code)
            reason = (
                "invalid_barcode"
                if not code.isascii() or not code.isdigit() or not 8 <= len(code) <= 14
                else "not_canada_tagged"
                if "en:canada" not in product.get("countries_tags", [])
                else "missing_ingredients"
                if not selected_text(product)
                else None
            )
            if reason:
                excluded.append({"code": code, "reason": reason})
                continue
            records.append({"retrieved_at": envelope["retrieved_at"], "product": product})
            if len(records) == args.count:
                break
        print(
            f"Page {page}: {len(seen)} unique records examined, {len(records)} eligible lists",
            flush=True,
        )
        if len(records) >= args.count:
            break
    if len(records) < args.count:
        raise RuntimeError(f"Only {len(records)} usable lists; target is {args.count}")
    snapshot = {
        "source": "Open Food Facts",
        "source_url": "https://world.openfoodfacts.org",
        "license": "ODbL; https://world.openfoodfacts.org/terms-of-use",
        "selection": (
            "First eligible distinct Canada-tagged products in API page order; "
            "sort_by=code was requested but returned records are not lexically ordered. "
            "Requires valid Product barcode and nonblank selected ingredient text. "
            "No filtering by parser outcome, language or ingredient complexity."
        ),
        "target": args.count,
        "examined": len(seen),
        "excluded": excluded,
        "pages": pages,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved {len(records)} real ingredient lists to {args.output}")


if __name__ == "__main__":
    main()
