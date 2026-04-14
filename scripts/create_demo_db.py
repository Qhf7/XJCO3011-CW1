"""
Create a lightweight demo database (~15MB) suitable for cloud deployment.

Extracts:
  - All 7,793 USDA ingredients + nutrition (full set, ~5MB)
  - 5,000 representative recipes covering all calorie levels + allergen types (~10MB)

Usage:
    python scripts/create_demo_db.py
Outputs:
    nutrition_demo.db  (~15MB, safe to commit to GitHub)
"""

import os
import shutil
import sqlite3
import random

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DB = os.path.join(BASE_DIR, "nutrition.db")
DEMO_DB = os.path.join(BASE_DIR, "nutrition_demo.db")

RECIPE_LIMIT = 5000


def main():
    if not os.path.exists(SRC_DB):
        print(f"ERROR: {SRC_DB} not found. Run import scripts first.")
        return

    # Copy full DB, then delete most recipes
    print(f"Copying {SRC_DB} → {DEMO_DB} ...")
    shutil.copy2(SRC_DB, DEMO_DB)

    conn = sqlite3.connect(DEMO_DB)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA foreign_keys=ON")

    # Count originals
    total = conn.execute("SELECT COUNT(*) FROM recipe").fetchone()[0]
    print(f"  Total recipes in source: {total:,}")

    # Pick a representative sample:
    # - 1500 low calorie recipes
    # - 2000 medium calorie recipes
    # - 1500 high calorie recipes
    # Stratified by difficulty (include all 5 levels)
    keep_ids = set()
    for level, n in [("low", 1500), ("medium", 2000), ("high", 1500)]:
        rows = conn.execute(
            "SELECT id FROM recipe WHERE calorie_level=? ORDER BY RANDOM() LIMIT ?",
            (level, n),
        ).fetchall()
        keep_ids.update(r[0] for r in rows)

    print(f"  Keeping {len(keep_ids):,} representative recipes...")

    # Delete recipe_ingredient_link for removed recipes
    conn.execute(
        f"DELETE FROM recipe_ingredient_link WHERE recipe_id NOT IN ({','.join('?' * len(keep_ids))})",
        list(keep_ids),
    )
    # Delete removed recipes
    conn.execute(
        f"DELETE FROM recipe WHERE id NOT IN ({','.join('?' * len(keep_ids))})",
        list(keep_ids),
    )

    conn.commit()
    conn.execute("VACUUM")

    remaining = conn.execute("SELECT COUNT(*) FROM recipe").fetchone()[0]
    conn.close()

    size_mb = os.path.getsize(DEMO_DB) / (1024 ** 2)
    print(f"  Remaining recipes: {remaining:,}")
    print(f"  Demo DB size: {size_mb:.1f} MB")
    print(f"\nDemo DB created: {DEMO_DB}")


if __name__ == "__main__":
    main()
