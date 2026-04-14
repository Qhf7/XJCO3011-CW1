"""
Import USDA FoodData Central SR Legacy data into SQLite database.

Data path: Data/FoodData_Central_sr_legacy_food_csv_2018-04/
Key nutrient IDs extracted:
  1008 -> Energy (KCAL)
  1003 -> Protein (G)
  1004 -> Total fat (G)
  1005 -> Carbohydrate (G)
  1079 -> Fiber, total dietary (G)
  1063 -> Sugars, Total (G)
  1093 -> Sodium (MG)
  1087 -> Calcium (MG)
  1089 -> Iron (MG)
  1162 -> Vitamin C (MG)
  1106 -> Vitamin A, RAE (UG)
  1258 -> Fatty acids, total saturated (G)
"""

import csv
import sqlite3
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "Data", "FoodData_Central_sr_legacy_food_csv_2018-04")
DB_PATH = os.path.join(BASE_DIR, "nutrition.db")

# Only import these nutrient IDs (keeps the database lean)
TARGET_NUTRIENTS = {
    "1008": "energy_kcal",
    "1003": "protein_g",
    "1004": "fat_g",
    "1005": "carbohydrate_g",
    "1079": "fiber_g",
    "1063": "sugar_g",
    "1093": "sodium_mg",
    "1087": "calcium_mg",
    "1089": "iron_mg",
    "1162": "vitamin_c_mg",
    "1106": "vitamin_a_ug",
    "1258": "saturated_fat_g",
}


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS food_category (
            id          INTEGER PRIMARY KEY,
            code        TEXT,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingredient (
            id              INTEGER PRIMARY KEY,
            fdc_id          INTEGER UNIQUE NOT NULL,
            description     TEXT NOT NULL,
            category_id     INTEGER REFERENCES food_category(id),
            data_source     TEXT DEFAULT 'usda_sr_legacy'
        );

        CREATE TABLE IF NOT EXISTS ingredient_nutrition (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ingredient_id   INTEGER NOT NULL REFERENCES ingredient(id) ON DELETE CASCADE,
            energy_kcal     REAL,
            protein_g       REAL,
            fat_g           REAL,
            carbohydrate_g  REAL,
            fiber_g         REAL,
            sugar_g         REAL,
            sodium_mg       REAL,
            calcium_mg      REAL,
            iron_mg         REAL,
            vitamin_c_mg    REAL,
            vitamin_a_ug    REAL,
            saturated_fat_g REAL,
            per_100g        INTEGER DEFAULT 1,
            UNIQUE(ingredient_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ingredient_fdc ON ingredient(fdc_id);
        CREATE INDEX IF NOT EXISTS idx_ingredient_desc ON ingredient(description);
        CREATE INDEX IF NOT EXISTS idx_ingredient_cat ON ingredient(category_id);
    """)
    conn.commit()
    print("Tables created.")


def load_food_categories(conn):
    path = os.path.join(DATA_DIR, "food_category.csv")
    inserted = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [(r["id"], r["code"], r["description"]) for r in reader if r["id"] != "id"]
    conn.executemany(
        "INSERT OR IGNORE INTO food_category (id, code, description) VALUES (?,?,?)", rows
    )
    conn.commit()
    inserted = len(rows)
    print(f"  Food categories loaded: {inserted}")


def load_foods(conn):
    path = os.path.join(DATA_DIR, "food.csv")
    inserted = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            if row["data_type"] != "sr_legacy_food":
                continue
            cat_id = row["food_category_id"] if row["food_category_id"] else None
            batch.append((row["fdc_id"], row["description"], cat_id))
            if len(batch) >= 500:
                conn.executemany(
                    "INSERT OR IGNORE INTO ingredient (fdc_id, description, category_id) VALUES (?,?,?)",
                    batch,
                )
                inserted += len(batch)
                batch = []
        if batch:
            conn.executemany(
                "INSERT OR IGNORE INTO ingredient (fdc_id, description, category_id) VALUES (?,?,?)",
                batch,
            )
            inserted += len(batch)
    conn.commit()
    print(f"  Foods (ingredients) loaded: {inserted}")


def load_nutrition(conn):
    """
    Build a per-ingredient nutrition dict from food_nutrient.csv,
    then bulk-insert into ingredient_nutrition.
    Only processes TARGET_NUTRIENTS to stay efficient.
    """
    nutrient_path = os.path.join(DATA_DIR, "food_nutrient.csv")

    # Map fdc_id -> nutrient_field -> value
    nutrition_map: dict[str, dict[str, float]] = {}

    print("  Reading food_nutrient.csv (644k rows)...", end=" ", flush=True)
    t0 = time.time()
    with open(nutrient_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nid = row["nutrient_id"]
            if nid not in TARGET_NUTRIENTS:
                continue
            fdc_id = row["fdc_id"]
            field = TARGET_NUTRIENTS[nid]
            try:
                val = float(row["amount"]) if row["amount"] else None
            except ValueError:
                val = None
            if fdc_id not in nutrition_map:
                nutrition_map[fdc_id] = {}
            nutrition_map[fdc_id][field] = val
    print(f"done in {time.time()-t0:.1f}s, {len(nutrition_map)} foods have nutrients.")

    # Fetch all ingredient ids
    cursor = conn.execute("SELECT id, fdc_id FROM ingredient")
    fdc_to_id = {str(r["fdc_id"]): r["id"] for r in cursor}

    fields = list(TARGET_NUTRIENTS.values())
    placeholders = ",".join(["?"] * (len(fields) + 1))
    col_names = "ingredient_id," + ",".join(fields)

    batch = []
    skipped = 0
    for fdc_id, nutrient_vals in nutrition_map.items():
        ing_id = fdc_to_id.get(fdc_id)
        if ing_id is None:
            skipped += 1
            continue
        row = [ing_id] + [nutrient_vals.get(f) for f in fields]
        batch.append(row)

    conn.executemany(
        f"INSERT OR REPLACE INTO ingredient_nutrition ({col_names}) VALUES ({placeholders})",
        batch,
    )
    conn.commit()
    print(f"  Nutrition records inserted: {len(batch)} (skipped {skipped} unmatched)")


def print_summary(conn):
    cats = conn.execute("SELECT COUNT(*) FROM food_category").fetchone()[0]
    ings = conn.execute("SELECT COUNT(*) FROM ingredient").fetchone()[0]
    nuts = conn.execute("SELECT COUNT(*) FROM ingredient_nutrition").fetchone()[0]
    print(f"\n=== Import Summary ===")
    print(f"  food_category rows : {cats}")
    print(f"  ingredient rows    : {ings}")
    print(f"  nutrition rows     : {nuts}")
    sample = conn.execute("""
        SELECT i.description, n.energy_kcal, n.protein_g, n.fat_g, n.carbohydrate_g
        FROM ingredient i JOIN ingredient_nutrition n ON i.id=n.ingredient_id
        WHERE n.energy_kcal IS NOT NULL
        LIMIT 5
    """).fetchall()
    print("\n  Sample records:")
    for r in sample:
        print(f"    {r[0][:50]:<50} | kcal={r[1]} | prot={r[2]}g | fat={r[3]}g | carb={r[4]}g")


def main():
    print(f"Database: {DB_PATH}")
    print(f"Data dir: {DATA_DIR}\n")
    if not os.path.isdir(DATA_DIR):
        print("ERROR: Data directory not found. Check DATA_DIR path.", file=sys.stderr)
        sys.exit(1)

    conn = connect_db()
    try:
        print("[1/4] Creating tables...")
        create_tables(conn)

        print("[2/4] Loading food categories...")
        load_food_categories(conn)

        print("[3/4] Loading foods...")
        load_foods(conn)

        print("[4/4] Loading nutrition data...")
        load_nutrition(conn)

        print_summary(conn)
        print("\nUSDA SR Legacy import complete!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
