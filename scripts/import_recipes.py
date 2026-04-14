"""
Import Food.com RAW_recipes.csv into SQLite database.

Nutrition column format (per serving):
  [calories, total_fat_%DV, sugar_%DV, sodium_%DV, protein_%DV, sat_fat_%DV, carbs_%DV]

Allergen detection is performed via keyword matching on the ingredients list.
"""

import csv
import sqlite3
import os
import ast
import re
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "Data")
DB_PATH = os.path.join(BASE_DIR, "nutrition.db")

RAW_RECIPES_PATH = os.path.join(DATA_DIR, "RAW_recipes.csv")

# FDA 9 major allergens + common additions
ALLERGEN_KEYWORDS: dict[str, list[str]] = {
    "gluten":    ["wheat", "flour", "bread", "pasta", "barley", "rye", "oats", "semolina",
                  "spelt", "farro", "couscous", "bulgur"],
    "dairy":     ["milk", "butter", "cheese", "cream", "yogurt", "whey", "lactose",
                  "casein", "ghee", "buttermilk", "parmesan", "mozzarella", "cheddar"],
    "eggs":      ["egg", "eggs", "mayonnaise", "meringue", "albumin"],
    "peanuts":   ["peanut", "groundnut", "monkey nut"],
    "tree_nuts": ["almond", "cashew", "walnut", "pecan", "pistachio", "macadamia",
                  "hazelnut", "brazil nut", "chestnut", "pine nut"],
    "soy":       ["soy", "soya", "tofu", "tempeh", "edamame", "miso", "tamari"],
    "fish":      ["salmon", "tuna", "cod", "tilapia", "halibut", "bass", "flounder",
                  "sardine", "anchovy", "trout", "catfish", "haddock"],
    "shellfish": ["shrimp", "crab", "lobster", "clam", "oyster", "scallop", "mussel",
                  "prawn", "crawfish", "crayfish"],
    "sesame":    ["sesame", "tahini", "til"],
    "sulfites":  ["wine", "dried fruit", "vinegar", "beer"],
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
        CREATE TABLE IF NOT EXISTS recipe (
            id              INTEGER PRIMARY KEY,
            food_com_id     INTEGER UNIQUE,
            name            TEXT NOT NULL,
            minutes         INTEGER,
            submitted       TEXT,
            description     TEXT,
            n_steps         INTEGER,
            n_ingredients   INTEGER,
            tags            TEXT,
            steps           TEXT,
            raw_ingredients TEXT,

            -- Nutrition per serving (from Food.com, %DV based)
            calories        REAL,
            total_fat_pdv   REAL,
            sugar_pdv       REAL,
            sodium_pdv      REAL,
            protein_pdv     REAL,
            sat_fat_pdv     REAL,
            carbs_pdv       REAL,

            -- Computed fields
            difficulty_score    INTEGER,
            allergen_flags      TEXT,
            calorie_level       TEXT
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredient_link (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id       INTEGER NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
            ingredient_name TEXT NOT NULL,
            matched_fdc_id  INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_recipe_name ON recipe(name);
        CREATE INDEX IF NOT EXISTS idx_recipe_calories ON recipe(calories);
        CREATE INDEX IF NOT EXISTS idx_recipe_difficulty ON recipe(difficulty_score);
        CREATE INDEX IF NOT EXISTS idx_recipe_calorie_level ON recipe(calorie_level);
        CREATE INDEX IF NOT EXISTS idx_recipe_link_recipe ON recipe_ingredient_link(recipe_id);
        CREATE INDEX IF NOT EXISTS idx_recipe_link_name ON recipe_ingredient_link(ingredient_name);
    """)
    conn.commit()
    print("Recipe tables created.")


def detect_allergens(ingredients: list[str]) -> list[str]:
    """Return list of detected allergen keys from an ingredients list."""
    combined = " ".join(ingredients).lower()
    found = []
    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            found.append(allergen)
    return found


def estimate_difficulty(n_steps: int, n_ingredients: int, minutes: int, tags: list[str]) -> int:
    """
    Score 1-5 based on:
      - number of steps
      - number of ingredients
      - total time
      - tag hints ('easy', 'beginner', 'advanced', etc.)
    """
    score = 0

    # Steps contribution (0-2)
    if n_steps <= 5:
        score += 0
    elif n_steps <= 10:
        score += 1
    else:
        score += 2

    # Ingredients contribution (0-2)
    if n_ingredients <= 5:
        score += 0
    elif n_ingredients <= 10:
        score += 1
    else:
        score += 2

    # Time contribution (0-1)
    if minutes and minutes > 60:
        score += 1

    # Tag hints
    tag_str = " ".join(tags).lower()
    if "easy" in tag_str or "beginner" in tag_str or "simple" in tag_str:
        score = max(score - 1, 0)
    if "advanced" in tag_str or "professional" in tag_str:
        score += 1

    return min(max(score + 1, 1), 5)


def calorie_level(calories: float | None) -> str:
    if calories is None:
        return "unknown"
    if calories < 200:
        return "low"
    elif calories < 500:
        return "medium"
    else:
        return "high"


def safe_parse_list(s: str) -> list[str]:
    """Safely parse a Python-list-like string from the CSV."""
    try:
        result = ast.literal_eval(s)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def safe_parse_nutrition(s: str) -> list[float | None]:
    """Parse nutrition column: [cal, fat%DV, sugar%DV, sodium%DV, protein%DV, satfat%DV, carbs%DV]"""
    try:
        result = ast.literal_eval(s)
        if isinstance(result, list) and len(result) == 7:
            return [float(x) if x is not None else None for x in result]
    except Exception:
        pass
    return [None] * 7


def main():
    print(f"Database: {DB_PATH}")
    print(f"Recipes file: {RAW_RECIPES_PATH}\n")

    conn = connect_db()
    try:
        print("[1/2] Creating recipe tables...")
        create_tables(conn)

        print("[2/2] Importing recipes...")
        t0 = time.time()
        recipe_batch = []
        link_batch = []
        total = 0
        skipped = 0

        with open(RAW_RECIPES_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    food_com_id = int(row["id"])
                    name = row["name"].strip()
                    if not name:
                        skipped += 1
                        continue

                    minutes = int(row["minutes"]) if row["minutes"].isdigit() else None
                    # Cap unrealistic times (e.g. 1 million minutes)
                    if minutes and minutes > 10000:
                        minutes = None

                    n_steps = int(row["n_steps"]) if row["n_steps"].isdigit() else 0
                    n_ingredients = int(row["n_ingredients"]) if row["n_ingredients"].isdigit() else 0

                    tags = safe_parse_list(row["tags"])
                    steps = safe_parse_list(row["steps"])
                    ingredients = safe_parse_list(row["ingredients"])

                    nutrition = safe_parse_nutrition(row["nutrition"])
                    cal, fat_pdv, sugar_pdv, sodium_pdv, prot_pdv, satfat_pdv, carbs_pdv = nutrition

                    allergens = detect_allergens(ingredients)
                    difficulty = estimate_difficulty(n_steps, n_ingredients, minutes or 0, tags)
                    cal_level = calorie_level(cal)

                    recipe_batch.append((
                        food_com_id,
                        name,
                        minutes,
                        row["submitted"],
                        row.get("description", "")[:1000],
                        n_steps,
                        n_ingredients,
                        ",".join(tags),
                        " | ".join(steps),
                        ",".join(ingredients),
                        cal, fat_pdv, sugar_pdv, sodium_pdv, prot_pdv, satfat_pdv, carbs_pdv,
                        difficulty,
                        ",".join(allergens),
                        cal_level,
                    ))

                    for ing_name in ingredients:
                        link_batch.append((food_com_id, ing_name.strip().lower()))

                    total += 1

                    if len(recipe_batch) >= 1000:
                        _flush_recipes(conn, recipe_batch)
                        recipe_batch = []
                        _flush_links(conn, link_batch)
                        link_batch = []
                        if total % 50000 == 0:
                            elapsed = time.time() - t0
                            print(f"    {total:,} recipes processed ({elapsed:.0f}s)...")

                except Exception as e:
                    skipped += 1
                    continue

        # Final flush
        if recipe_batch:
            _flush_recipes(conn, recipe_batch)
        if link_batch:
            _flush_links(conn, link_batch)

        elapsed = time.time() - t0
        print(f"\n  Done in {elapsed:.1f}s")
        print(f"  Recipes imported : {total:,}")
        print(f"  Skipped          : {skipped:,}")

        _print_summary(conn)

    finally:
        conn.close()


def _flush_recipes(conn, batch):
    conn.executemany("""
        INSERT OR IGNORE INTO recipe (
            food_com_id, name, minutes, submitted, description,
            n_steps, n_ingredients, tags, steps, raw_ingredients,
            calories, total_fat_pdv, sugar_pdv, sodium_pdv, protein_pdv,
            sat_fat_pdv, carbs_pdv,
            difficulty_score, allergen_flags, calorie_level
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, batch)
    conn.commit()


def _flush_links(conn, link_batch):
    """We need recipe internal IDs for the link table, so resolve them."""
    if not link_batch:
        return
    food_com_ids = list({row[0] for row in link_batch})
    placeholders = ",".join(["?"] * len(food_com_ids))
    cursor = conn.execute(
        f"SELECT id, food_com_id FROM recipe WHERE food_com_id IN ({placeholders})",
        food_com_ids,
    )
    id_map = {r["food_com_id"]: r["id"] for r in cursor}
    resolved = [
        (id_map[fid], iname)
        for fid, iname in link_batch
        if fid in id_map
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO recipe_ingredient_link (recipe_id, ingredient_name) VALUES (?,?)",
        resolved,
    )
    conn.commit()


def _print_summary(conn):
    recipes = conn.execute("SELECT COUNT(*) FROM recipe").fetchone()[0]
    links = conn.execute("SELECT COUNT(*) FROM recipe_ingredient_link").fetchone()[0]
    allergen_counts = conn.execute("""
        SELECT allergen_flags, COUNT(*) as cnt FROM recipe
        WHERE allergen_flags != ''
        GROUP BY allergen_flags
        ORDER BY cnt DESC
        LIMIT 5
    """).fetchall()
    calorie_dist = conn.execute("""
        SELECT calorie_level, COUNT(*) as cnt FROM recipe
        GROUP BY calorie_level ORDER BY cnt DESC
    """).fetchall()

    print(f"\n=== Recipe Import Summary ===")
    print(f"  recipe rows              : {recipes:,}")
    print(f"  recipe_ingredient_link   : {links:,}")
    print(f"\n  Calorie distribution:")
    for r in calorie_dist:
        print(f"    {r[0]:<10}: {r[1]:,}")
    print(f"\n  Top allergen combos:")
    for r in allergen_counts[:5]:
        flags = r[0][:60] if r[0] else "(none)"
        print(f"    {flags:<60}: {r[1]:,} recipes")


if __name__ == "__main__":
    main()
