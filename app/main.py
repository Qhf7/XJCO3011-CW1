from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.routers import analytics, auth, ingredients, off, recipes

# Create any tables not yet in the DB (User table, OffProduct table)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## Nutrition & Recipe Analytics API

A data-driven REST API backed by the **USDA FoodData Central SR Legacy** dataset
(7,793 ingredients) and **Food.com** (231,636 recipes).

### Features
- **Ingredient CRUD** — search, create, update, delete ingredients with full nutritional data
- **Recipe CRUD** — full recipe management with automatic allergen detection and difficulty scoring
- **Nutrition Calculator** — compute nutrition for custom ingredient combinations
- **Allergen Engine** — detects FDA's 9 major allergens per recipe
- **Difficulty Estimator** — multi-factor scoring (1–5 stars)
- **Nutrient Density Score** — proprietary A–E grading per ingredient
- **Meal Plan Analyser** — aggregate nutrition across a full day's recipes
- **Open Food Facts Integration** — real-time product lookup by barcode or name
- **Analytics** — macro trends, calorie distribution, top ingredients, allergen stats

### Authentication
Protected endpoints use **JWT Bearer** tokens.
Register via `POST /auth/register`, then login via `POST /auth/login`.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(analytics.router)
app.include_router(off.router)


@app.get("/", tags=["Health"])
def health_check():
    """API health check and version info."""
    return {
        "status": "ok",
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/stats", tags=["Health"])
def database_stats(db=None):
    """Quick overview of database record counts."""
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    from app.models.ingredient import Ingredient
    from app.models.recipe import Recipe
    from app.models.off import OffProduct
    from app.models.user import User

    db = SessionLocal()
    try:
        return {
            "ingredients": db.query(Ingredient).count(),
            "recipes": db.query(Recipe).count(),
            "off_products_cached": db.query(OffProduct).count(),
            "users": db.query(User).count(),
        }
    finally:
        db.close()
