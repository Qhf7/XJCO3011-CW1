from pydantic import BaseModel, Field


class NutritionOut(BaseModel):
    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    vitamin_c_mg: float | None = None
    vitamin_a_ug: float | None = None
    saturated_fat_g: float | None = None

    model_config = {"from_attributes": True}


class IngredientBase(BaseModel):
    description: str = Field(..., min_length=2, max_length=500)
    category_id: int | None = None


class IngredientCreate(IngredientBase):
    """Used when a user manually creates a custom ingredient."""
    nutrition: NutritionOut | None = None


class IngredientUpdate(BaseModel):
    description: str | None = Field(None, min_length=2, max_length=500)
    category_id: int | None = None
    nutrition: NutritionOut | None = None


class IngredientOut(IngredientBase):
    id: int
    fdc_id: int
    data_source: str
    category_name: str | None = None
    nutrition: NutritionOut | None = None

    model_config = {"from_attributes": True}


class IngredientListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[IngredientOut]


class NutrientDensityOut(BaseModel):
    """Nutrient Density Score: nutrition value per calorie."""
    ingredient_id: int
    description: str
    energy_kcal: float | None
    nutrient_density_score: float | None = Field(
        None,
        description="Combined score of protein+fiber+vitamins per 100kcal. Higher = more nutritious per calorie.",
    )
    grade: str | None = Field(None, description="A/B/C/D/E rating like Nutri-Score")
