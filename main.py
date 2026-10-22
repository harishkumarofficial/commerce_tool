import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

PROJECT_KEY = os.environ["CT_PROJECT_KEY"]
AUTH_URL = os.environ["CT_AUTH_URL"].rstrip("/")
API_URL = os.environ["CT_API_URL"].rstrip("/")
CLIENT_ID = os.environ["CT_CLIENT_ID"]
CLIENT_SECRET = os.environ["CT_CLIENT_SECRET"]
SCOPES = os.environ["CT_SCOPES"].strip()

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

PAGE_SIZE = 100
session = requests.Session()
access_token = None
token_expiry = 0


def get_access_token(force_refresh=False):
    """Obtain a token and reuse it until it is near expiry."""
    global access_token, token_expiry

    if (
        access_token
        and not force_refresh
        and time.time() < token_expiry - 60
    ):
        return access_token

    response = requests.post(
        f"{AUTH_URL}/oauth/token",
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        data={
            "grant_type": "client_credentials",
            "scope": SCOPES,
        },
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    access_token = result["access_token"]
    token_expiry = time.time() + result.get("expires_in", 3600)

    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    })

    print("Authentication successful.")
    return access_token


def api_get(path, params=None):
    """Call an API endpoint, refreshing the token once on HTTP 401."""
    get_access_token()

    url = f"{API_URL}/{PROJECT_KEY}/{path.lstrip('/')}"

    for attempt in range(2):
        response = session.get(url, params=params, timeout=60)

        if response.status_code == 401 and attempt == 0:
            get_access_token(force_refresh=True)
            continue

        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"API request failed: {path}")


def fetch_all(resource):
    """Retrieve all pages of a resource collection."""
    records = []
    offset = 0

    while True:
        data = api_get(
            resource,
            params={"limit": PAGE_SIZE, "offset": offset},
        )

        page = data.get("results", [])
        records.extend(page)

        print(
            f"{resource}: fetched {len(page)} records "
            f"(total collected: {len(records)})"
        )

        if not page or len(page) < PAGE_SIZE:
            break

        total = data.get("total")
        offset += len(page)

        if total is not None and offset >= total:
            break

    return records


def save_json(filename, data):
    path = OUTPUT_DIR / filename
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
    print(f"Saved {path}")


def build_relationships(products, carts, orders):
    """Extract useful parent/child references without inventing links."""
    mappings = {
        "product_variants": [],
        "cart_customers": [],
        "cart_line_items": [],
        "order_customers": [],
        "order_line_items": [],
    }

    for product in products:
        parent_id = product.get("id")

        variants = [
            product.get("masterVariant", {}),
            *product.get("variants", []),
        ]

        for variant in variants:
            mappings["product_variants"].append({
                "product_id": parent_id,
                "product_key": product.get("key"),
                "variant_id": variant.get("id"),
                "sku": variant.get("sku"),
            })

    for cart in carts:
        cart_id = cart.get("id")

        mappings["cart_customers"].append({
            "cart_id": cart_id,
            "customer_id": cart.get("customerId"),
            "anonymous_id": cart.get("anonymousId"),
        })

        for item in cart.get("lineItems", []):
            mappings["cart_line_items"].append({
                "cart_id": cart_id,
                "line_item_id": item.get("id"),
                "product_id": item.get("productId"),
                "product_key": item.get("productKey"),
                "variant_id": (
                    item.get("variant", {}).get("id")
                ),
                "sku": item.get("variant", {}).get("sku"),
                "quantity": item.get("quantity"),
            })

    for order in orders:
        order_id = order.get("id")

        mappings["order_customers"].append({
            "order_id": order_id,
            "customer_id": order.get("customerId"),
            "anonymous_id": order.get("anonymousId"),
        })

        for item in order.get("lineItems", []):
            mappings["order_line_items"].append({
                "order_id": order_id,
                "line_item_id": item.get("id"),
                "product_id": item.get("productId"),
                "product_key": item.get("productKey"),
                "variant_id": (
                    item.get("variant", {}).get("id")
                ),
                "sku": item.get("variant", {}).get("sku"),
                "quantity": item.get("quantity"),
            })

    return mappings


def main():
    get_access_token()

    resources = {}
    # A permission failure is reported; it is not silently ignored.
    for resource in ("products", "customers", "carts", "orders"):
        try:
            records = fetch_all(resource)
            resources[resource] = records
            save_json(f"{resource}.json", records)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            print(f"ERROR: {resource}: HTTP {status}")
            if exc.response is not None:
                print(exc.response.text[:1000])
        except requests.RequestException as exc:
            print(f"ERROR: {resource}: {exc}")

    products = resources.get("products", [])
    carts = resources.get("carts", [])
    orders = resources.get("orders", [])

    mappings = build_relationships(products, carts, orders)
    save_json("relationships.json", mappings)

    print("\nExtraction summary:")
    for name, records in resources.items():
        print(f"{name}: {len(records)} records")

    print("Relationship mapping saved.")
    print("Review API permissions and errors before using partial data.")


if __name__ == "__main__":
    main()
