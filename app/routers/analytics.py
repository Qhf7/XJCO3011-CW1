from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ingredient import Ingredient
from app.models.recipe import Recipe, RecipeIngredientLink
from app.schemas.analytics import (
    CalorieDistributionOut,
    CompareIn,
    CompareOut,
    MacroTrendOut,
    MealPlanIn,
    MealPlanOut,
    NutritionCalculateIn,
    NutritionCalculateOut,
    TopIngredientOut,
)
from app.services.allergen import detect_allergens_from_list
from app.services.nutrition import calculate_custom_nutrition, dri_comparison

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/nutrition/calculate", response_model=NutritionCalculateOut)
def calculate_nutrition(
    payload: NutritionCalculateIn,
    db: Session = Depends(get_db),
):
    """
    Calculate total and per-serving nutrition for a custom list of ingredients.
    Provide ingredient IDs and amounts in grams.
    """
    items = [{"ingredient_id": i.ingredient_id, "amount_g": i.amount_g} for i in payload.items]
    result = calculate_custom_nutrition(db, items, payload.servings)
    return NutritionCalculateOut(**result)


@router.post("/nutrition/compare", response_model=CompareOut)
def compare_ingredients(payload: CompareIn, db: Session = Depends(get_db)):
    """
    Compare nutritional profiles of multiple ingredients side by side.
    Returns per-100g values for all provided ingredient IDs.
    """
    rows = []
    for ing_id in payload.ingredient_ids:
        ing = db.query(Ingredient).filter(Ingredient.id == ing_id).first()
        if not ing:
            raise HTTPException(status_code=404, detail=f"Ingredient {ing_id} not found")

        n = ing.nutrition
        row: dict = {
            "id": ing.id,
            "description": ing.description,
            "category": ing.category.description if ing.category else None,
        }
        if n:
            row.update({
                "energy_kcal": n.energy_kcal,
                "protein_g": n.protein_g,
                "fat_g": n.fat_g,
                "carbohydrate_g": n.carbohydrate_g,
                "fiber_g": n.fiber_g,
                "sugar_g": n.sugar_g,
                "sodium_mg": n.sodium_mg,
                "saturated_fat_g": n.saturated_fat_g,
            })
        rows.append(row)
    return CompareOut(items=rows)


@router.post("/meal-plan/analyze", response_model=MealPlanOut)
def analyze_meal_plan(payload: MealPlanIn, db: Session = Depends(get_db)):
    """
    Analyze a full meal plan (list of recipe + serving-count pairs).
    Returns aggregated nutrition, DRI percentages, and combined allergen warnings.
    """
    total_cal = 0.0
    total_prot = 0.0
    total_fat = 0.0
    total_carbs = 0.0
    all_allergens: set[str] = set()
    valid = 0

    for entry in payload.entries:
        recipe = db.query(Recipe).filter(Recipe.id == entry.recipe_id).first()
        if not recipe:
            raise HTTPException(status_code=404, detail=f"Recipe {entry.recipe_id} not found")
        s = entry.servings
        if recipe.calories:
            total_cal += recipe.calories * s
        if recipe.protein_pdv:
            total_prot += recipe.protein_pdv * s
        if recipe.total_fat_pdv:
            total_fat += recipe.total_fat_pdv * s
        if recipe.carbs_pdv:
            total_carbs += recipe.carbs_pdv * s

        from app.routers.recipes import _parse_ingredients
        ings = _parse_ingredients(recipe.raw_ingredients)
        for k in detect_allergens_from_list(ings):
            all_allergens.add(k)
        valid += 1

    dri = {
        "calories_percent_dri": round(total_cal / 2000 * 100, 1) if total_cal else None,
        "protein_percent_dv": round(total_prot, 1),
        "fat_percent_dv": round(total_fat, 1),
        "carbs_percent_dv": round(total_carbs, 1),
        "note": "%DV values are summed across all recipes and servings",
    }

    return MealPlanOut(
        total_calories=round(total_cal, 1),
        total_protein_pdv=round(total_prot, 1),
        total_carbs_pdv=round(total_carbs, 1),
        total_fat_pdv=round(total_fat, 1),
        recipes_included=valid,
        dri_summary=dri,
        allergens_combined=sorted(all_allergens),
    )


@router.get("/calorie-distribution", response_model=CalorieDistributionOut)
def calorie_distribution(db: Session = Depends(get_db)):
    """Distribution of recipes across calorie levels (low/medium/high)."""
    rows = (
        db.query(Recipe.calorie_level, func.count(Recipe.id))
        .group_by(Recipe.calorie_level)
        .all()
    )
    dist = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    for level, count in rows:
        key = level if level in dist else "unknown"
        dist[key] = count
    return CalorieDistributionOut(**dist)


@router.get("/top-ingredients", response_model=list[TopIngredientOut])
def top_ingredients(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Most frequently used ingredients across all recipes."""
    rows = (
        db.query(
            RecipeIngredientLink.ingredient_name,
            func.count(RecipeIngredientLink.id).label("cnt"),
        )
        .group_by(RecipeIngredientLink.ingredient_name)
        .order_by(func.count(RecipeIngredientLink.id).desc())
        .limit(limit)
        .all()
    )
    return [TopIngredientOut(ingredient_name=r[0], recipe_count=r[1]) for r in rows]


@router.get("/macro-trends", response_model=list[MacroTrendOut])
def macro_trends(db: Session = Depends(get_db)):
    """
    Average macronutrient breakdown grouped by calorie level.
    Useful for understanding nutritional patterns across recipe categories.
    """
    rows = (
        db.query(
            Recipe.calorie_level,
            func.avg(Recipe.calories).label("avg_cal"),
            func.avg(Recipe.total_fat_pdv).label("avg_fat"),
            func.avg(Recipe.protein_pdv).label("avg_prot"),
            func.avg(Recipe.carbs_pdv).label("avg_carbs"),
            func.count(Recipe.id).label("cnt"),
        )
        .filter(Recipe.calorie_level != None)
        .group_by(Recipe.calorie_level)
        .all()
    )
    return [
        MacroTrendOut(
            calorie_level=r[0] or "unknown",
            avg_calories=round(r[1], 1) if r[1] else None,
            avg_fat_pdv=round(r[2], 1) if r[2] else None,
            avg_protein_pdv=round(r[3], 1) if r[3] else None,
            avg_carbs_pdv=round(r[4], 1) if r[4] else None,
            count=r[5],
        )
        for r in rows
    ]


@router.get("/allergen-stats")
def allergen_statistics(db: Session = Depends(get_db)):
    """Count of recipes containing each allergen type."""
    from sqlalchemy import case

    allergens = [
        "gluten", "dairy", "eggs", "peanuts", "tree_nuts",
        "soy", "fish", "shellfish", "sesame", "sulfites",
    ]
    result = {}
    for allergen in allergens:
        count = (
            db.query(func.count(Recipe.id))
            .filter(Recipe.allergen_flags.ilike(f"%{allergen}%"))
            .scalar()
        )
        result[allergen] = count
    return result
