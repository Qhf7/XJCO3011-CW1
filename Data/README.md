# Data Sources

This directory contains the raw datasets used by the Nutrition & Recipe Analytics API.
The actual data files are excluded from version control (`.gitignore`) due to their size.
Follow the instructions below to download and set up each dataset locally.

---

## Dataset 1: USDA FoodData Central — SR Legacy (2018)

| Property     | Details |
|--------------|---------|
| **Source**   | U.S. Department of Agriculture, Agricultural Research Service |
| **URL**      | https://fdc.nal.usda.gov/download-data |
| **Format**   | CSV (multiple files) |
| **Size**     | ~50 MB (CSV directory) |
| **Licence**  | Public Domain (U.S. Government Work) |

### Why This Dataset?

The USDA SR Legacy dataset is the gold standard for ingredient-level nutritional data.
It provides precise per-100g measurements for 7,793 food items across 474 nutrient types,
including energy (kcal), macronutrients (protein, fat, carbohydrates), dietary fibre,
sugars, vitamins (A, C), and minerals (calcium, iron, sodium, potassium).

This precision is essential for the API's **Nutrient Density Score (NDS)** feature, which
grades ingredients A–E based on how much nutrition they deliver per 100 kcal — a metric that
requires accurate per-gram nutrient values rather than estimated %Daily Values.

### Key Files Used

| File | Records | Description |
|------|---------|-------------|
| `FoodData_Central_sr_legacy_food_csv_2018-04/food.csv` | 7,793 | Food items with fdc_id and description |
| `FoodData_Central_sr_legacy_food_csv_2018-04/food_nutrient.csv` | 644,458 | Per-food nutrient measurements |
| `FoodData_Central_sr_legacy_food_csv_2018-04/nutrient.csv` | 474 | Nutrient definitions and units |
| `FoodData_Central_sr_legacy_food_csv_2018-04/food_category.csv` | 25 | Food category taxonomy |

### Setup

```bash
# Download from: https://fdc.nal.usda.gov/download-data
# Select "SR Legacy" → "April 2018" → Download CSV
# Extract into: Data/FoodData_Central_sr_legacy_food_csv_2018-04/

# Import into SQLite:
python scripts/import_usda_sr.py
# Imports 7,793 ingredients + 644k nutrient records (~4 seconds)
```

---

## Dataset 2: Food.com Recipes and Interactions (Kaggle)

| Property     | Details |
|--------------|---------|
| **Source**   | Kaggle — shuyangli94/food-com-recipes-and-user-interactions |
| **URL**      | https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions |
| **Format**   | CSV |
| **File**     | `RAW_recipes.csv` (~281 MB) |
| **Licence**  | CC BY-SA 3.0 |

### Why This Dataset?

Food.com Recipes provides 231,636 real-world community recipes with structured fields:
recipe name, preparation time, tags (cuisine type, meal type, dietary preferences),
step-by-step cooking instructions, ingredient lists, and per-serving nutritional estimates
as %Daily Values.

This dataset is the backbone of the API's **recipe analytics** features:
- The ingredient lists power the **FDA Allergen Detection Engine**, which identifies
  which of the 9 major allergens (gluten, dairy, eggs, peanuts, tree nuts, soy, fish,
  shellfish, sesame) are present in each recipe.
- The step count, ingredient count, cooking time, and technique keywords (e.g. "sous vide",
  "deglaze") feed the **Multi-factor Difficulty Estimator** (1–5 stars).
- The calorie estimates enable calorie-level filtering (low / medium / high).

### Key Fields

| Field | Description |
|-------|-------------|
| `name` | Recipe title |
| `minutes` | Total preparation + cooking time |
| `tags` | Categorical labels (e.g. `['easy', 'vegetarian', 'quick-breads']`) |
| `nutrition` | `[calories, %DV fat, %DV sugar, %DV sodium, %DV protein, %DV sat_fat, %DV carbs]` |
| `n_steps` | Number of cooking steps |
| `steps` | Full step-by-step instructions |
| `ingredients` | List of ingredient names (text format) |
| `n_ingredients` | Ingredient count |

### Setup

```bash
# Download RAW_recipes.csv from Kaggle (link above)
# Place in: Data/RAW_recipes.csv

# Import into SQLite:
python scripts/import_recipes.py
# Imports 231,636 recipes with pre-computed allergen flags,
# difficulty scores, and calorie levels (~36 seconds)
```

---

## Dataset 3: Open Food Facts (Real-time API Integration)

| Property     | Details |
|--------------|---------|
| **Source**   | Open Food Facts |
| **URL**      | https://world.openfoodfacts.org/data |
| **Format**   | REST API (JSON) / CSV bulk download (9 GB) |
| **Licence**  | Open Database Licence (ODbL) |

### Why This Dataset?

Open Food Facts provides real-world packaged food product data — barcodes, brand names,
allergen declarations, Nutri-Score grades (A–E), and per-100g/per-serving nutrition.
This complements the USDA data (raw ingredients) with commercial product context,
enabling users to look up branded foods by barcode or product name.

### Integration Strategy

Rather than downloading the 9 GB bulk CSV, the API uses a **cache-first pattern**:
1. On first lookup (by barcode or product name), the OFF REST API is called.
2. The response is stored in the local `off_product` SQLite table.
3. Subsequent lookups for the same product return the cached result instantly.

This keeps the deployment database lightweight (~11.6 MB) while still providing
access to OFF's full product catalogue on demand.

### Setup

```bash
# No download required — the API integration works out of the box.
# The cache table is created automatically on first run.

# Optionally, seed the cache with a few lookups:
python scripts/import_off.py --mode api --query "oatmeal"
```

---

## Data Architecture Overview

```
Raw Data Sources               Import Scripts              SQLite Tables
────────────────               ──────────────              ─────────────
USDA SR Legacy CSV    ──►  scripts/import_usda_sr.py  ──►  food_category
                                                       ──►  ingredient
                                                       ──►  ingredient_nutrition

Food.com RAW_recipes  ──►  scripts/import_recipes.py  ──►  recipe
                                                       ──►  recipe_ingredient_link

Open Food Facts API   ──►  scripts/import_off.py      ──►  off_product
                           (cache-first, real-time)
```

---

## Citation

If you use this data or build upon this project, please cite the original sources:

```
USDA Agricultural Research Service (2018). USDA FoodData Central SR Legacy.
  Retrieved from https://fdc.nal.usda.gov/

Li, S. (2019). Food.com Recipes and Interactions [Data set].
  Kaggle. https://doi.org/10.34740/KAGGLE/DSV/783974

Open Food Facts contributors. Open Food Facts database.
  Retrieved from https://world.openfoodfacts.org/
  Licensed under ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/
```
