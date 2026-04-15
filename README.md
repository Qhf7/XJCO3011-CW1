# Nutrition & Recipe Analytics API

A data-driven RESTful API for nutrition analysis and recipe management, built with **FastAPI** and **SQLite**. Backed by the **USDA FoodData Central SR Legacy** dataset (7,793 ingredients) and **Food.com** (231,636 recipes), with real-time product enrichment via the **Open Food Facts** API.

> **XJCO3011 Coursework 1** — Web Services and Web Data  
> Module lead: Dr Ammar Alsalka, University of Leeds (SWJTU)

---

## Features

| Category | Capability |
|---|---|
| **Ingredient CRUD** | Search 7,793 USDA-sourced ingredients; create/update/delete custom ones |
| **Recipe CRUD** | Manage 231,636+ Food.com recipes with full filtering |
| **Nutrition Calculator** | Per-100g USDA data; custom ingredient-amount combos; DRI comparison |
| **Allergen Engine** | Detects FDA's 9 major allergens per recipe with ingredient-level breakdown |
| **Difficulty Estimator** | Multi-factor 1–5 star scoring (steps, ingredients, time, techniques) |
| **Nutrient Density Score** | Proprietary A–E grading: nutrition value per 100 kcal |
| **Meal Plan Analyser** | Aggregate nutrition across a full day's recipes |
| **Open Food Facts** | Barcode/name lookup with local caching |
| **Smart Search** | Filter by calorie level, allergen exclusion, ingredient, difficulty, time |
| **Analytics** | Calorie distribution, macro trends, top ingredients, allergen statistics |
| **JWT Auth** | Bearer token authentication for all write operations |

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- The pre-built `nutrition_demo.db` database (11.6 MB, included in the repository — contains all 7,793 USDA ingredients and a 5,000-recipe sample)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the API server

```bash
uvicorn app.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

### 4. (Optional) Rebuild the database from raw data

If you have the raw datasets in `Data/`, run the import scripts in order:

```bash
# Step 1: Import USDA SR Legacy nutrition data (~4 seconds)
python scripts/import_usda_sr.py

# Step 2: Import Food.com recipes (~36 seconds)
python scripts/import_recipes.py

# Step 3: Set up Open Food Facts cache table (no download required)
python scripts/import_off.py --mode api
```

---

## API Endpoints

### Authentication
| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Login, receive JWT token |

### Ingredients
| Method | Path | Description |
|---|---|---|
| `GET` | `/ingredients` | List/search ingredients (supports `?q=`, `?category_id=`) |
| `GET` | `/ingredients/categories` | List all food categories |
| `GET` | `/ingredients/{id}` | Get ingredient details |
| `GET` | `/ingredients/{id}/nutrition` | Nutrition per 100g |
| `GET` | `/ingredients/{id}/nutrient-density` | Nutrient Density Score (A–E grade) |
| `POST` | `/ingredients` | Create custom ingredient 🔒 |
| `PUT` | `/ingredients/{id}` | Update ingredient 🔒 |
| `DELETE` | `/ingredients/{id}` | Delete ingredient 🔒 |

### Recipes
| Method | Path | Description |
|---|---|---|
| `GET` | `/recipes` | List/search recipes (many filter options) |
| `GET` | `/recipes/by-ingredients` | Find recipes by available ingredients |
| `GET` | `/recipes/{id}` | Get recipe details |
| `GET` | `/recipes/{id}/nutrition` | Nutrition summary + DRI comparison |
| `GET` | `/recipes/{id}/allergens` | Allergen warnings with breakdown |
| `GET` | `/recipes/{id}/difficulty` | Difficulty score + factor breakdown |
| `POST` | `/recipes` | Create recipe 🔒 |
| `PUT` | `/recipes/{id}` | Update recipe 🔒 |
| `DELETE` | `/recipes/{id}` | Delete recipe 🔒 |

### Analytics
| Method | Path | Description |
|---|---|---|
| `POST` | `/analytics/nutrition/calculate` | Custom ingredient-amount nutrition calculator |
| `POST` | `/analytics/nutrition/compare` | Side-by-side ingredient comparison |
| `POST` | `/analytics/meal-plan/analyze` | Full meal plan nutrition + DRI summary |
| `GET` | `/analytics/calorie-distribution` | Recipe distribution across calorie levels |
| `GET` | `/analytics/top-ingredients` | Most-used ingredients across all recipes |
| `GET` | `/analytics/macro-trends` | Average macros grouped by calorie level |
| `GET` | `/analytics/allergen-stats` | Recipe count per allergen type |

### Open Food Facts
| Method | Path | Description |
|---|---|---|
| `GET` | `/products/barcode/{barcode}` | Look up product by barcode |
| `GET` | `/products/search?name=` | Search products by name |

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/stats` | Database record counts |

> 🔒 = Requires `Authorization: Bearer <token>` header

---

## Architecture

```
nutrition_api/
├── app/
│   ├── main.py               # FastAPI app, CORS, router registration
│   ├── config.py             # Settings via pydantic-settings
│   ├── database.py           # SQLAlchemy engine + session factory
│   ├── auth/
│   │   ├── security.py       # bcrypt hashing, JWT encode/decode
│   │   └── dependencies.py   # OAuth2 bearer token dependency
│   ├── models/               # SQLAlchemy ORM table definitions
│   │   ├── user.py
│   │   ├── ingredient.py     # FoodCategory, Ingredient, IngredientNutrition
│   │   ├── recipe.py         # Recipe, RecipeIngredientLink
│   │   └── off.py            # OffProduct (OFF cache)
│   ├── schemas/              # Pydantic request/response models
│   │   ├── user.py
│   │   ├── ingredient.py
│   │   ├── recipe.py
│   │   └── analytics.py
│   ├── routers/              # HTTP route handlers
│   │   ├── auth.py
│   │   ├── ingredients.py
│   │   ├── recipes.py
│   │   ├── analytics.py
│   │   └── off.py
│   └── services/             # Business logic (pure Python, testable)
│       ├── allergen.py       # Allergen keyword detection engine
│       ├── difficulty.py     # Multi-factor difficulty estimator
│       ├── nutrition.py      # NDS calculator, DRI comparison
│       └── off_service.py    # OFF API cache-first integration
├── scripts/
│   ├── import_usda_sr.py     # USDA SR Legacy → SQLite
│   ├── import_recipes.py     # Food.com RAW_recipes.csv → SQLite
│   └── import_off.py        # Open Food Facts (API or CSV mode)
├── tests/
│   ├── conftest.py           # Shared fixtures, in-memory test DB
│   ├── test_auth.py          # Authentication tests (8 tests)
│   ├── test_ingredients.py   # Ingredient CRUD + nutrition (12 tests)
│   ├── test_recipes.py       # Recipe CRUD + analysis (17 tests)
│   └── test_analytics.py     # Analytics + service unit tests (19 tests)
├── nutrition_demo.db         # Pre-built SQLite database (11.6 MB, committed to repo)
├── nutrition.db              # Full SQLite database (456 MB, not committed — rebuild locally)
├── requirements.txt
└── README.md
```

---

## Data Sources

| Dataset | Records | Source | Licence |
|---|---|---|---|
| USDA FoodData Central SR Legacy | 7,793 foods, 644k nutrient measurements | [USDA FDC](https://fdc.nal.usda.gov/) | Public Domain |
| Food.com Recipes | 231,636 recipes | [Kaggle](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions) | CC BY-SA 3.0 |
| Open Food Facts | On-demand via REST API | [OFF](https://world.openfoodfacts.org/) | ODbL |

---

## Running Tests

```bash
pytest tests/ -v
```

All **56 tests** pass against an isolated in-memory SQLite database — the production `nutrition.db` is never touched during testing.

```
56 passed in ~4 seconds
```

---

## Key Innovation: Nutrient Density Score (NDS)

The NDS is a proprietary metric that rates an ingredient's nutritional value **per calorie** rather than per weight. It computes a 0–100 score based on how much protein, fibre, vitamin C, calcium, and iron the food provides relative to the US Dietary Reference Intake for a 100-kcal portion.

```
NDS = mean(protein_score, fiber_score, vitamin_c_score, calcium_score, iron_score)

where each score = min(actual_per_100kcal / DRI_100kcal_portion × 100, 100)
```

| Grade | NDS Range | Example |
|---|---|---|
| A | 70–100 | Spinach, Salmon |
| B | 50–69 | Chicken breast, Lentils |
| C | 30–49 | Pasta, White rice |
| D | 15–29 | Potato chips |
| E | 0–14 | Sugar, Soda |

---

## Documentation

### API Documentation

Full interactive documentation is auto-generated by FastAPI and available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

A static PDF export of the API documentation is available in [`docs/api_documentation.pdf`](docs/api_documentation.pdf).

### Technical Report

The technical report (design decisions, stack justification, testing approach, limitations, and GenAI declaration) is available in [`docs/technical_report.pdf`](docs/technical_report.pdf).

### Appendix A — GenAI Conversation Log

Selected excerpts from the AI-assisted development session (Cursor IDE / Claude) are available in [`docs/genai_appendix.pdf`](docs/genai_appendix.pdf). Full session ID: `38778eed-e850-434d-b8f6-e013ee468440`.

### GitHub Repository

[https://github.com/Qhf7/XJCO3011-CW1](https://github.com/Qhf7/XJCO3011-CW1)

---

## Environment Variables

Create a `.env` file to override defaults:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./nutrition.db
DEBUG=false
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```
