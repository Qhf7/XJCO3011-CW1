"""
Nutrition calculation and analysis service.

Provides:
  - Per-ingredient nutrition lookup
  - Custom ingredient-amount combination calculator
  - DRI (Dietary Reference Intake) comparison for adults
  - Nutrient Density Score (NDS) — proprietary innovation
  - Nutri-Score grade derivation
"""

from sqlalchemy.orm import Session

from app.models.ingredient import Ingredient, IngredientNutrition

# Approximate adult DRI (US/EU reference values)
DRI = {
    "energy_kcal": 2000,
    "protein_g": 50,
    "fat_g": 65,
    "carbohydrate_g": 300,
    "fiber_g": 28,
    "sugar_g": 50,
    "sodium_mg": 2300,
    "calcium_mg": 1000,
    "iron_mg": 18,
    "vitamin_c_mg": 90,
    "vitamin_a_ug": 900,
    "saturated_fat_g": 20,
}

NUTRIENT_FIELDS = list(DRI.keys())


def _nutrition_to_dict(n: IngredientNutrition) -> dict:
    return {field: getattr(n, field) for field in NUTRIENT_FIELDS}


def compute_nutrient_density_score(n: IngredientNutrition) -> float | None:
    """
    Nutrient Density Score (NDS): measures how much beneficial nutrition
    a food provides per 100 kcal.

    Formula:
      NDS = (protein_score + fiber_score + vitamin_c_score + calcium_score + iron_score) / 5
      where each score = min(actual / DRI_100kcal_portion * 100, 100)

    Range: 0–100. Higher = more nutrient-dense per calorie.
    """
    if not n or not n.energy_kcal or n.energy_kcal <= 0:
        return None

    kcal_ratio = n.energy_kcal / 100  # scale to per-100-kcal portion

    def score(actual: float | None, dri: float) -> float:
        if actual is None:
            return 0.0
        # expected DRI amount in a 100-kcal portion
        expected = dri * (100 / DRI["energy_kcal"])
        return min((actual / kcal_ratio) / expected * 100, 100)

    components = [
        score(n.protein_g, DRI["protein_g"]),
        score(n.fiber_g, DRI["fiber_g"]),
        score(n.vitamin_c_mg, DRI["vitamin_c_mg"]),
        score(n.calcium_mg, DRI["calcium_mg"]),
        score(n.iron_mg, DRI["iron_mg"]),
    ]
    return round(sum(components) / len(components), 2)


def nutrient_density_grade(score: float | None) -> str | None:
    """Map NDS score to A–E grade (similar to Nutri-Score logic)."""
    if score is None:
        return None
    if score >= 70:
        return "A"
    elif score >= 50:
        return "B"
    elif score >= 30:
        return "C"
    elif score >= 15:
        return "D"
    return "E"


def calculate_custom_nutrition(
    db: Session,
    items: list[dict],  # [{"ingredient_id": int, "amount_g": float}]
    servings: int = 1,
) -> dict:
    """
    Compute total nutrition for an arbitrary combination of ingredients.
    Returns per_serving and total dicts.
    """
    totals: dict[str, float] = {f: 0.0 for f in NUTRIENT_FIELDS}
    allergens: set[str] = set()

    for item in items:
        ing = db.query(Ingredient).filter(Ingredient.id == item["ingredient_id"]).first()
        if not ing or not ing.nutrition:
            continue

        ratio = item["amount_g"] / 100.0
        for field in NUTRIENT_FIELDS:
            val = getattr(ing.nutrition, field)
            if val is not None:
                totals[field] += val * ratio

        # Import here to avoid circular dependency
        from app.services.allergen import detect_allergens_from_list
        allergens.update(detect_allergens_from_list([ing.description]).keys())

    per_serving = {k: round(v / servings, 2) for k, v in totals.items()}
    total = {k: round(v, 2) for k, v in totals.items()}

    return {
        "servings": servings,
        "per_serving": per_serving,
        "total": total,
        "allergens_detected": sorted(allergens),
    }


def dri_comparison(nutrition: dict) -> dict:
    """
    Compare a nutrition dict against DRI values.
    Returns percentage of DRI covered for each nutrient.
    """
    result = {}
    for field, dri_val in DRI.items():
        actual = nutrition.get(field)
        if actual is not None and dri_val > 0:
            pct = round(actual / dri_val * 100, 1)
            result[field] = {"value": actual, "dri": dri_val, "percent_dri": pct}
        else:
            result[field] = {"value": actual, "dri": dri_val, "percent_dri": None}
    return result


def recipe_dri_comparison(
    calories: float | None,
    protein_pdv: float | None,
    fat_pdv: float | None,
    carbs_pdv: float | None,
    sodium_pdv: float | None,
) -> dict:
    """
    Build a simplified DRI comparison from Food.com %DV fields.
    %DV is already the percentage of daily value, so we surface it directly.
    """
    return {
        "calories": {
            "value": calories,
            "percent_dri": round(calories / DRI["energy_kcal"] * 100, 1) if calories else None,
        },
        "protein": {"percent_dv": protein_pdv},
        "fat": {"percent_dv": fat_pdv},
        "carbohydrates": {"percent_dv": carbs_pdv},
        "sodium": {"percent_dv": sodium_pdv},
    }
