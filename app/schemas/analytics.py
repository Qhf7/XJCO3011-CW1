from pydantic import BaseModel, Field


class NutritionCalculateIn(BaseModel):
    """Free-form nutrition calculation: list of ingredient + amount pairs."""

    class Item(BaseModel):
        ingredient_id: int
        amount_g: float = Field(..., gt=0, description="Amount in grams")

    items: list[Item] = Field(..., min_length=1)
    servings: int = Field(1, ge=1)


class NutritionCalculateOut(BaseModel):
    servings: int
    per_serving: dict
    total: dict
    allergens_detected: list[str]


class CompareIn(BaseModel):
    ingredient_ids: list[int] = Field(..., min_length=2, max_length=10)


class CompareOut(BaseModel):
    items: list[dict]


class MealPlanIn(BaseModel):
    class Entry(BaseModel):
        recipe_id: int
        servings: float = Field(1.0, gt=0)

    entries: list[Entry] = Field(..., min_length=1)


class MealPlanOut(BaseModel):
    total_calories: float | None
    total_protein_pdv: float | None
    total_carbs_pdv: float | None
    total_fat_pdv: float | None
    recipes_included: int
    dri_summary: dict
    allergens_combined: list[str]


class CalorieDistributionOut(BaseModel):
    low: int
    medium: int
    high: int
    unknown: int


class TopIngredientOut(BaseModel):
    ingredient_name: str
    recipe_count: int


class MacroTrendOut(BaseModel):
    calorie_level: str
    avg_calories: float | None
    avg_fat_pdv: float | None
    avg_protein_pdv: float | None
    avg_carbs_pdv: float | None
    count: int
