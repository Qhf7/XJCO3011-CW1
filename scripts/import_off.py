"""
Open Food Facts (OFF) data integration.

Two modes:
  1. API mode (default, recommended):
     Query OFF REST API on-demand. No large download required.
     Usage: python import_off.py --mode api

  2. Bulk CSV mode (if you have downloaded the full CSV):
     Streams the 9GB CSV in chunks, extracting only needed columns
     for English/US/UK products. Result: a ~50MB filtered subset.
     Usage: python import_off.py --mode csv --csv-path /path/to/en.openfoodfacts.org.products.csv

The script stores a local cache table 'off_product' in the same SQLite DB
so repeated queries for the same product skip the API call.
"""

import argparse
import csv
import os
import sqlite3
import time
import json
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "nutrition.db")

# Columns we care about from the OFF CSV (out of ~200 columns)
OFF_KEEP_COLS = [
    "code",                     # barcode
    "product_name",
    "brands",
    "categories_en",
    "countries_en",
    "allergens_en",
    "traces_en",
    "nutriscore_grade",         # A-E rating
    "nova_group",               # food processing level 1-4
    "energy-kcal_100g",
    "proteins_100g",
    "fat_100g",
    "saturated-fat_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fiber_100g",
    "sodium_100g",
]

# Only keep products from English-speaking countries
ENGLISH_COUNTRIES = {"united states", "united kingdom", "canada", "australia", "ireland"}

OFF_API_BASE = "https://world.openfoodfacts.org/api/v2"


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_off_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS off_product (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode             TEXT UNIQUE,
            product_name        TEXT,
            brands              TEXT,
            categories          TEXT,
            allergens           TEXT,
            traces              TEXT,
            nutriscore_grade    TEXT,
            nova_group          INTEGER,
            energy_kcal_100g    REAL,
            protein_100g        REAL,
            fat_100g            REAL,
            saturated_fat_100g  REAL,
            carbohydrate_100g   REAL,
            sugar_100g          REAL,
            fiber_100g          REAL,
            sodium_100g         REAL,
            fetched_at          TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_off_barcode ON off_product(barcode);
        CREATE INDEX IF NOT EXISTS idx_off_name ON off_product(product_name);
        CREATE INDEX IF NOT EXISTS idx_off_allergens ON off_product(allergens);
        CREATE INDEX IF NOT EXISTS idx_off_nutriscore ON off_product(nutriscore_grade);
    """)
    conn.commit()
    print("OFF product table ready.")


# ---------------------------------------------------------------------------
# Mode 1: API-based lookup (used at runtime by the FastAPI service)
# ---------------------------------------------------------------------------

def fetch_by_barcode_api(barcode: str) -> dict | None:
    """
    Fetch a single product from OFF API by barcode.
    Returns a cleaned dict or None if not found.
    Requires: pip install requests
    """
    try:
        import requests
    except ImportError:
        print("Install requests: pip install requests")
        return None

    url = f"{OFF_API_BASE}/product/{barcode}.json"
    try:
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "NutritionAPI/1.0 (coursework)"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != 1:
            return None
        return _parse_off_product(data["product"])
    except Exception as e:
        print(f"API error for barcode {barcode}: {e}")
        return None


def search_by_name_api(name: str, page_size: int = 5) -> list[dict]:
    """
    Search OFF API by product name. Returns list of cleaned product dicts.
    """
    try:
        import requests
    except ImportError:
        return []

    url = (
        f"https://world.openfoodfacts.org/cgi/search.pl"
        f"?search_terms={name}&search_simple=1&action=process"
        f"&json=1&page_size={page_size}&fields="
        + ",".join([
            "code", "product_name", "brands", "allergens_tags",
            "nutriscore_grade", "nova_group",
            "nutriments",
        ])
    )
    try:
        resp = requests.get(url, timeout=10,
                            headers={"User-Agent": "NutritionAPI/1.0 (coursework)"})
        if resp.status_code != 200:
            return []
        products = resp.json().get("products", [])
        return [_parse_off_product(p) for p in products]
    except Exception:
        return []


def _parse_off_product(p: dict) -> dict:
    """Normalise a raw OFF API product dict into our schema."""
    nutriments = p.get("nutriments", {})
    allergens_raw = p.get("allergens_tags", [])
    # Strip "en:" prefix used in tags
    allergens = [a.replace("en:", "") for a in allergens_raw]

    return {
        "barcode": p.get("code", ""),
        "product_name": p.get("product_name", ""),
        "brands": p.get("brands", ""),
        "categories": p.get("categories_tags", ""),
        "allergens": ",".join(allergens),
        "traces": p.get("traces", ""),
        "nutriscore_grade": p.get("nutriscore_grade", ""),
        "nova_group": p.get("nova_group"),
        "energy_kcal_100g": nutriments.get("energy-kcal_100g"),
        "protein_100g": nutriments.get("proteins_100g"),
        "fat_100g": nutriments.get("fat_100g"),
        "saturated_fat_100g": nutriments.get("saturated-fat_100g"),
        "carbohydrate_100g": nutriments.get("carbohydrates_100g"),
        "sugar_100g": nutriments.get("sugars_100g"),
        "fiber_100g": nutriments.get("fiber_100g"),
        "sodium_100g": nutriments.get("sodium_100g"),
    }


def cache_product(conn, product: dict):
    """Insert/update a product in the local cache table."""
    conn.execute("""
        INSERT OR REPLACE INTO off_product (
            barcode, product_name, brands, categories, allergens, traces,
            nutriscore_grade, nova_group,
            energy_kcal_100g, protein_100g, fat_100g, saturated_fat_100g,
            carbohydrate_100g, sugar_100g, fiber_100g, sodium_100g
        ) VALUES (
            :barcode, :product_name, :brands, :categories, :allergens, :traces,
            :nutriscore_grade, :nova_group,
            :energy_kcal_100g, :protein_100g, :fat_100g, :saturated_fat_100g,
            :carbohydrate_100g, :sugar_100g, :fiber_100g, :sodium_100g
        )
    """, product)
    conn.commit()


def get_cached_product(conn, barcode: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM off_product WHERE barcode=?", (barcode,)
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Mode 2: Bulk CSV streaming (for users who downloaded the full 9GB file)
# ---------------------------------------------------------------------------

def import_from_csv(conn, csv_path: str, max_rows: int = 500_000):
    """
    Stream the large OFF CSV file in chunks.
    Only keep products from English-speaking countries.
    Stops after max_rows matching rows to keep DB manageable.

    The full OFF CSV has ~200 columns and 2M+ rows (~9GB).
    We skip irrelevant columns using DictReader field filtering.
    """
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV file not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    file_size_gb = os.path.getsize(csv_path) / (1024 ** 3)
    print(f"File size: {file_size_gb:.1f} GB")
    print(f"Streaming (keeping only {len(OFF_KEEP_COLS)} of ~200 columns)...")
    print(f"Target: up to {max_rows:,} English-language products\n")

    inserted = 0
    skipped_lang = 0
    skipped_noname = 0
    t0 = time.time()

    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        # OFF CSV uses tab separator
        reader = csv.DictReader(f, delimiter="\t")

        batch = []
        for i, row in enumerate(reader):
            if inserted >= max_rows:
                break

            # Filter by country
            countries_raw = row.get("countries_en", "").lower()
            if not any(c in countries_raw for c in ENGLISH_COUNTRIES):
                skipped_lang += 1
                continue

            name = row.get("product_name", "").strip()
            if not name:
                skipped_noname += 1
                continue

            def safe_float(val: str) -> float | None:
                try:
                    return float(val) if val.strip() else None
                except ValueError:
                    return None

            product = {
                "barcode": row.get("code", ""),
                "product_name": name,
                "brands": row.get("brands", ""),
                "categories": row.get("categories_en", ""),
                "allergens": row.get("allergens_en", ""),
                "traces": row.get("traces_en", ""),
                "nutriscore_grade": row.get("nutriscore_grade", "").lower()[:1] or None,
                "nova_group": int(row["nova_group"]) if row.get("nova_group", "").strip().isdigit() else None,
                "energy_kcal_100g": safe_float(row.get("energy-kcal_100g", "")),
                "protein_100g": safe_float(row.get("proteins_100g", "")),
                "fat_100g": safe_float(row.get("fat_100g", "")),
                "saturated_fat_100g": safe_float(row.get("saturated-fat_100g", "")),
                "carbohydrate_100g": safe_float(row.get("carbohydrates_100g", "")),
                "sugar_100g": safe_float(row.get("sugars_100g", "")),
                "fiber_100g": safe_float(row.get("fiber_100g", "")),
                "sodium_100g": safe_float(row.get("sodium_100g", "")),
            }
            batch.append(product)
            inserted += 1

            if len(batch) >= 1000:
                _bulk_insert_off(conn, batch)
                batch = []
                if inserted % 50000 == 0:
                    elapsed = time.time() - t0
                    rate = inserted / elapsed
                    print(f"  {inserted:,} rows inserted | {elapsed:.0f}s elapsed | {rate:.0f} rows/s")

        if batch:
            _bulk_insert_off(conn, batch)

    elapsed = time.time() - t0
    print(f"\n=== OFF CSV Import Complete ===")
    print(f"  Inserted       : {inserted:,}")
    print(f"  Skipped (lang) : {skipped_lang:,}")
    print(f"  Skipped (name) : {skipped_noname:,}")
    print(f"  Time           : {elapsed:.1f}s")

    total = conn.execute("SELECT COUNT(*) FROM off_product").fetchone()[0]
    print(f"  Total in DB    : {total:,}")


def _bulk_insert_off(conn, batch: list[dict]):
    conn.executemany("""
        INSERT OR IGNORE INTO off_product (
            barcode, product_name, brands, categories, allergens, traces,
            nutriscore_grade, nova_group,
            energy_kcal_100g, protein_100g, fat_100g, saturated_fat_100g,
            carbohydrate_100g, sugar_100g, fiber_100g, sodium_100g
        ) VALUES (
            :barcode, :product_name, :brands, :categories, :allergens, :traces,
            :nutriscore_grade, :nova_group,
            :energy_kcal_100g, :protein_100g, :fat_100g, :saturated_fat_100g,
            :carbohydrate_100g, :sugar_100g, :fiber_100g, :sodium_100g
        )
    """, batch)
    conn.commit()


# ---------------------------------------------------------------------------
# Demo: test the API mode
# ---------------------------------------------------------------------------

def demo_api(conn):
    test_barcodes = [
        "3017620422003",  # Nutella
        "5000159484695",  # Heinz Baked Beans
        "0016000275607",  # Cheerios
    ]
    print("=== API Demo ===")
    for barcode in test_barcodes:
        cached = get_cached_product(conn, barcode)
        if cached:
            print(f"[cache] {barcode}: {cached['product_name']} | nutriscore={cached['nutriscore_grade']}")
        else:
            print(f"[api]   Fetching {barcode}...")
            product = fetch_by_barcode_api(barcode)
            if product:
                cache_product(conn, product)
                print(f"        -> {product['product_name']} | nutriscore={product['nutriscore_grade']} | "
                      f"kcal={product['energy_kcal_100g']} | allergens={product['allergens']}")
            else:
                print(f"        -> Not found")
        time.sleep(0.5)  # Be polite to the OFF API


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Open Food Facts data integration")
    parser.add_argument(
        "--mode",
        choices=["api", "csv", "demo"],
        default="demo",
        help=(
            "api  = create table only (API calls happen at runtime via services/off_service.py)\n"
            "csv  = bulk import from downloaded CSV (requires --csv-path)\n"
            "demo = run API demo with 3 sample barcodes"
        ),
    )
    parser.add_argument("--csv-path", help="Path to en.openfoodfacts.org.products.csv")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=500_000,
        help="Max rows to import from CSV (default: 500,000 ≈ 50MB in DB)",
    )
    args = parser.parse_args()

    conn = connect_db()
    try:
        create_off_table(conn)

        if args.mode == "csv":
            if not args.csv_path:
                print("ERROR: --csv-path required for csv mode", file=sys.stderr)
                sys.exit(1)
            import_from_csv(conn, args.csv_path, args.max_rows)

        elif args.mode == "demo":
            demo_api(conn)

        else:  # api mode: just ensure the table exists
            print("OFF table created. The API service will populate it on-demand.")
            print("See app/services/off_service.py for runtime usage.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
