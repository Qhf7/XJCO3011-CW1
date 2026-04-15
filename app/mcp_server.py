"""
MCP (Model Context Protocol) Server for the Nutrition & Recipe Analytics API.

Exposes key analytics functions as MCP tools, allowing AI assistants (e.g. Claude)
to directly query nutritional data, search recipes, and compute allergen warnings
without going through the HTTP layer.

Run standalone:
    python -m app.mcp_server

Or via FastMCP CLI:
    fastmcp run app/mcp_server.py
"""

import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from app.database import SessionLocal
from app.models.ingredient import Ingredient, IngredientNutrition
from app.models.recipe import Recipe, RecipeIngredientLink
from app.services.allergen import compute_allergen_response, detect_allergens_from_list
from app.services.difficulty import difficulty_label, estimate_difficulty
from app.services.nutrition import (
    compute_nutrient_density_score,
    nutrient_density_grade,
    recipe_dri_comparison,
)
from sqlalchemy import func, or_

mcp = FastMCP(
    name="NutritionRecipeAPI",
    instructions=(
        "A nutrition and recipe analytics assistant. "
        "Use these tools to look up ingredient nutrition data, search recipes, "
        "detect allergens, compute nutrient density scores, and analyse meal plans. "
        "All nutritional values use USDA FoodData Central SR Legacy data (per 100g). "
        "Recipe data comes from Food.com (231,636 recipes)."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: Search ingredients
# ---------------------------------------------------------------------------
@mcp.tool()
def search_ingredients(query: str, limit: int = 5) -> list[dict]:
    """
    Search USDA food ingredients by name.
    Returns ingredient id, description, food category, and key nutrition (per 100g).

    Args:
        query: Ingredient name to search (e.g. 'chicken breast', 'spinach')
        limit: Max number of results (1-20, default 5)
    """
    limit = max(1, min(limit, 20))
    db = SessionLocal()
    try:
        rows = (
            db.query(Ingredient)
            .filter(Ingredient.description.ilike(f"%{query}%"))
            .limit(limit)
            .all()
        )
        result = []
        for ing in rows:
            item: dict = {
                "id": ing.id,
                "description": ing.description,
                "category": ing.category.description if ing.category else None,
            }
            if ing.nutrition:
                n = ing.nutrition
                item["nutrition_per_100g"] = {
                    "energy_kcal": n.energy_kcal,
                    "protein_g": n.protein_g,
                    "fat_g": n.fat_g,
                    "carbohydrate_g": n.carbohydrate_g,
                    "fiber_g": n.fiber_g,
                    "sodium_mg": n.sodium_mg,
                }
            result.append(item)
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 2: Get ingredient nutrition + NDS grade
# ---------------------------------------------------------------------------
@mcp.tool()
def get_ingredient_nutrition(ingredient_id: int) -> dict:
    """
    Get full nutritional profile and Nutrient Density Score (NDS) for an ingredient.
    NDS measures how much nutrition a food provides per 100 kcal (A=best, E=lowest).

    Args:
        ingredient_id: The ingredient's database ID (from search_ingredients)
    """
    db = SessionLocal()
    try:
        ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if not ing:
            return {"error": f"Ingredient {ingredient_id} not found"}
        if not ing.nutrition:
            return {"error": "No nutrition data available"}
        n = ing.nutrition
        score = compute_nutrient_density_score(n)
        return {
            "id": ing.id,
            "description": ing.description,
            "category": ing.category.description if ing.category else None,
            "nutrition_per_100g": {
                "energy_kcal": n.energy_kcal,
                "protein_g": n.protein_g,
                "fat_g": n.fat_g,
                "saturated_fat_g": n.saturated_fat_g,
                "carbohydrate_g": n.carbohydrate_g,
                "fiber_g": n.fiber_g,
                "sugar_g": n.sugar_g,
                "sodium_mg": n.sodium_mg,
                "calcium_mg": n.calcium_mg,
                "iron_mg": n.iron_mg,
                "vitamin_c_mg": n.vitamin_c_mg,
                "vitamin_a_ug": n.vitamin_a_ug,
            },
            "nutrient_density_score": score,
            "nutrient_density_grade": nutrient_density_grade(score),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 3: Search recipes
# ---------------------------------------------------------------------------
@mcp.tool()
def search_recipes(
    query: str = "",
    calorie_level: str = "",
    max_calories: float = 0,
    allergen_free: str = "",
    max_minutes: int = 0,
    difficulty: int = 0,
    limit: int = 5,
) -> dict:
    """
    Search recipes with optional filters.

    Args:
        query: Search recipe name or description
        calorie_level: 'low' (<200 kcal), 'medium' (200-500), or 'high' (>500)
        max_calories: Maximum calories per serving (0 = no limit)
        allergen_free: Comma-separated allergens to exclude (e.g. 'gluten,dairy,eggs')
        max_minutes: Maximum cooking time in minutes (0 = no limit)
        difficulty: Difficulty score 1-5 (0 = any)
        limit: Max results (1-20)
    """
    limit = max(1, min(limit, 20))
    db = SessionLocal()
    try:
        q = db.query(Recipe)
        if query:
            q = q.filter(
                or_(Recipe.name.ilike(f"%{query}%"), Recipe.description.ilike(f"%{query}%"))
            )
        if calorie_level in ("low", "medium", "high"):
            q = q.filter(Recipe.calorie_level == calorie_level)
        if max_calories > 0:
            q = q.filter(Recipe.calories <= max_calories)
        if max_minutes > 0:
            q = q.filter(Recipe.minutes <= max_minutes)
        if 1 <= difficulty <= 5:
            q = q.filter(Recipe.difficulty_score == difficulty)
        if allergen_free:
            for allergen in [a.strip() for a in allergen_free.split(",") if a.strip()]:
                q = q.filter(
                    or_(
                        Recipe.allergen_flags == None,
                        Recipe.allergen_flags == "",
                        ~Recipe.allergen_flags.ilike(f"%{allergen}%"),
                    )
                )
        total = q.count()
        recipes = q.limit(limit).all()
        return {
            "total_matching": total,
            "results": [
                {
                    "id": r.id,
                    "name": r.name,
                    "minutes": r.minutes,
                    "calories": r.calories,
                    "calorie_level": r.calorie_level,
                    "difficulty_score": r.difficulty_score,
                    "n_ingredients": r.n_ingredients,
                    "allergen_flags": r.allergen_flags,
                }
                for r in recipes
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 4: Get recipe allergen warnings
# ---------------------------------------------------------------------------
@mcp.tool()
def get_recipe_allergens(recipe_id: int) -> dict:
    """
    Get detailed allergen warnings for a recipe.
    Detects FDA's 9 major allergens and shows which ingredients trigger each.

    Args:
        recipe_id: Recipe database ID
    """
    import ast
    db = SessionLocal()
    try:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            return {"error": f"Recipe {recipe_id} not found"}
        try:
            ingredients = ast.literal_eval(recipe.raw_ingredients or "[]")
        except Exception:
            ingredients = [s.strip() for s in (recipe.raw_ingredients or "").split(",")]
        return compute_allergen_response(ingredients, recipe.id, recipe.name)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 5: Get recipe nutrition
# ---------------------------------------------------------------------------
@mcp.tool()
def get_recipe_nutrition(recipe_id: int, servings: int = 1) -> dict:
    """
    Get nutrition summary for a recipe, optionally scaled by number of servings.
    Includes comparison against Daily Reference Intake (DRI/RDA).

    Args:
        recipe_id: Recipe database ID
        servings: Number of servings to scale values by (default 1)
    """
    servings = max(1, servings)
    db = SessionLocal()
    try:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            return {"error": f"Recipe {recipe_id} not found"}

        def scale(v):
            return round(v / servings, 2) if v else None

        dri = recipe_dri_comparison(
            recipe.calories, recipe.protein_pdv,
            recipe.total_fat_pdv, recipe.carbs_pdv, recipe.sodium_pdv,
        )
        return {
            "recipe_id": recipe.id,
            "recipe_name": recipe.name,
            "servings": servings,
            "calories_per_serving": scale(recipe.calories),
            "calorie_level": recipe.calorie_level,
            "macros_%DV": {
                "protein": scale(recipe.protein_pdv),
                "total_fat": scale(recipe.total_fat_pdv),
                "carbohydrates": scale(recipe.carbs_pdv),
                "saturated_fat": scale(recipe.sat_fat_pdv),
                "sodium": scale(recipe.sodium_pdv),
                "sugar": scale(recipe.sugar_pdv),
            },
            "dri_comparison": dri,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 6: Get recipe difficulty
# ---------------------------------------------------------------------------
@mcp.tool()
def get_recipe_difficulty(recipe_id: int) -> dict:
    """
    Get difficulty estimate (1=Very Easy to 5=Expert) for a recipe,
    with a breakdown of contributing factors.

    Args:
        recipe_id: Recipe database ID
    """
    db = SessionLocal()
    try:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if not recipe:
            return {"error": f"Recipe {recipe_id} not found"}
        tags = [t.strip() for t in (recipe.tags or "").split(",") if t.strip()]
        steps = [s.strip() for s in (recipe.steps or "").split(" | ") if s.strip()]
        score, factors = estimate_difficulty(
            recipe.n_steps or 0, recipe.n_ingredients or 0, recipe.minutes, tags, steps
        )
        return {
            "recipe_id": recipe.id,
            "recipe_name": recipe.name,
            "difficulty_score": score,
            "difficulty_label": difficulty_label(score),
            "factors": {**factors, "n_steps": recipe.n_steps, "n_ingredients": recipe.n_ingredients, "minutes": recipe.minutes},
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 7: Analyse allergens from custom ingredient list
# ---------------------------------------------------------------------------
@mcp.tool()
def check_allergens(ingredients: list[str]) -> dict:
    """
    Check a custom list of ingredient names for allergens.
    Useful for meal planning or checking a recipe before cooking.

    Args:
        ingredients: List of ingredient names (e.g. ['wheat flour', 'butter', 'eggs'])
    """
    breakdown = detect_allergens_from_list(ingredients)
    from app.services.allergen import allergens_safe_for
    safe = allergens_safe_for(set(breakdown.keys()))
    return {
        "allergens_detected": sorted(breakdown.keys()),
        "ingredient_breakdown": breakdown,
        "safe_for": safe,
        "ingredients_checked": len(ingredients),
    }


# ---------------------------------------------------------------------------
# Tool 8: Global analytics summary
# ---------------------------------------------------------------------------
@mcp.tool()
def get_analytics_summary() -> dict:
    """
    Get a high-level summary of the entire recipe and ingredient database:
    calorie distribution, top ingredients, macro averages, and allergen counts.
    """
    db = SessionLocal()
    try:
        recipe_count = db.query(func.count(Recipe.id)).scalar()
        ingredient_count = db.query(func.count(Ingredient.id)).scalar()

        calorie_dist_rows = (
            db.query(Recipe.calorie_level, func.count(Recipe.id))
            .group_by(Recipe.calorie_level)
            .all()
        )
        calorie_dist = {r[0] or "unknown": r[1] for r in calorie_dist_rows}

        top_ings = (
            db.query(RecipeIngredientLink.ingredient_name, func.count().label("cnt"))
            .group_by(RecipeIngredientLink.ingredient_name)
            .order_by(func.count().desc())
            .limit(10)
            .all()
        )

        allergens = ["gluten", "dairy", "eggs", "peanuts", "tree_nuts", "soy", "fish", "shellfish", "sesame"]
        allergen_counts = {}
        for a in allergens:
            allergen_counts[a] = (
                db.query(func.count(Recipe.id))
                .filter(Recipe.allergen_flags.ilike(f"%{a}%"))
                .scalar()
            )

        return {
            "database": {"total_recipes": recipe_count, "total_ingredients": ingredient_count},
            "calorie_distribution": calorie_dist,
            "top_10_ingredients": [{"name": r[0], "recipe_count": r[1]} for r in top_ings],
            "allergen_recipe_counts": allergen_counts,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 9: Find recipes by available ingredients
# ---------------------------------------------------------------------------
@mcp.tool()
def find_recipes_by_ingredients(ingredients: list[str], limit: int = 5) -> dict:
    """
    Find recipes that use the given ingredients (any match).
    Great for "what can I cook with what I have?" queries.

    Args:
        ingredients: List of ingredient names you have available
        limit: Max results (1-20)
    """
    limit = max(1, min(limit, 20))
    if not ingredients:
        return {"error": "Provide at least one ingredient"}
    db = SessionLocal()
    try:
        q = db.query(Recipe).filter(
            or_(*[Recipe.raw_ingredients.ilike(f"%{i.strip()}%") for i in ingredients])
        )
        total = q.count()
        recipes = q.limit(limit).all()
        return {
            "total_matching": total,
            "results": [
                {
                    "id": r.id,
                    "name": r.name,
                    "minutes": r.minutes,
                    "calories": r.calories,
                    "difficulty_score": r.difficulty_score,
                    "allergen_flags": r.allergen_flags,
                }
                for r in recipes
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool 10: Compare two ingredients nutritionally
# ---------------------------------------------------------------------------
@mcp.tool()
def compare_ingredients(ingredient_id_1: int, ingredient_id_2: int) -> dict:
    """
    Compare two ingredients side-by-side on all nutritional metrics (per 100g).
    Also shows which one has a better Nutrient Density Score.

    Args:
        ingredient_id_1: First ingredient ID
        ingredient_id_2: Second ingredient ID
    """
    db = SessionLocal()
    try:
        results = []
        for iid in [ingredient_id_1, ingredient_id_2]:
            ing = db.query(Ingredient).filter(Ingredient.id == iid).first()
            if not ing:
                return {"error": f"Ingredient {iid} not found"}
            n = ing.nutrition
            score = compute_nutrient_density_score(n) if n else None
            results.append({
                "id": ing.id,
                "description": ing.description,
                "energy_kcal": n.energy_kcal if n else None,
                "protein_g": n.protein_g if n else None,
                "fat_g": n.fat_g if n else None,
                "carbohydrate_g": n.carbohydrate_g if n else None,
                "fiber_g": n.fiber_g if n else None,
                "sodium_mg": n.sodium_mg if n else None,
                "nutrient_density_score": score,
                "nutrient_density_grade": nutrient_density_grade(score),
            })
        winner = None
        if results[0]["nutrient_density_score"] and results[1]["nutrient_density_score"]:
            winner = results[0]["description"] if results[0]["nutrient_density_score"] >= results[1]["nutrient_density_score"] else results[1]["description"]
        return {"comparison": results, "higher_nutrient_density": winner}
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
