from pydantic import BaseModel, Field


class RecipeIngredientIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class RecipeBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=500)
    minutes: int | None = Field(None, ge=1, le=10000)
    description: str | None = Field(None, max_length=2000)
    tags: str | None = None


class RecipeCreate(RecipeBase):
    ingredients: list[str] = Field(..., min_length=1, description="List of ingredient names")
    steps: list[str] = Field(default_factory=list)
    calories: float | None = Field(None, ge=0)
    protein_pdv: float | None = Field(None, ge=0)
    carbs_pdv: float | None = Field(None, ge=0)
    fat_pdv: float | None = Field(None, ge=0)


class RecipeUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=500)
    minutes: int | None = Field(None, ge=1, le=10000)
    description: str | None = None
    tags: str | None = None
    ingredients: list[str] | None = None
    steps: list[str] | None = None
    calories: float | None = None


class RecipeOut(RecipeBase):
    id: int
    food_com_id: int | None = None
    n_steps: int | None = None
    n_ingredients: int | None = None
    calories: float | None = None
    calorie_level: str | None = None
    difficulty_score: int | None = None
    allergen_flags: str | None = None
    ingredients_list: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class RecipeListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RecipeOut]


class RecipeNutritionOut(BaseModel):
    recipe_id: int
    recipe_name: str
    servings: int = 1
    calories_per_serving: float | None = None
    total_fat_pdv: float | None = None
    sugar_pdv: float | None = None
    sodium_pdv: float | None = None
    protein_pdv: float | None = None
    sat_fat_pdv: float | None = None
    carbs_pdv: float | None = None
    calorie_level: str | None = None
    dri_comparison: dict | None = None


class AllergenWarningOut(BaseModel):
    recipe_id: int
    recipe_name: str
    allergens_detected: list[str]
    ingredient_breakdown: dict[str, list[str]]
    safe_for: list[str]


class DifficultyOut(BaseModel):
    recipe_id: int
    recipe_name: str
    difficulty_score: int = Field(..., ge=1, le=5)
    difficulty_label: str
    factors: dict
