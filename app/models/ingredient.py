from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FoodCategory(Base):
    __tablename__ = "food_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(128), nullable=False)

    ingredients: Mapped[list["Ingredient"]] = relationship(back_populates="category")


class Ingredient(Base):
    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fdc_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("food_category.id"), index=True)
    data_source: Mapped[str] = mapped_column(String(32), default="usda_sr_legacy")

    category: Mapped["FoodCategory | None"] = relationship(back_populates="ingredients")
    nutrition: Mapped["IngredientNutrition | None"] = relationship(
        back_populates="ingredient", uselist=False
    )
    recipe_links: Mapped[list["RecipeIngredientLink"]] = relationship(  # type: ignore[name-defined]
        back_populates="matched_ingredient",
        foreign_keys="RecipeIngredientLink.matched_fdc_id",
        primaryjoin="Ingredient.fdc_id == RecipeIngredientLink.matched_fdc_id",
    )


class IngredientNutrition(Base):
    """Nutritional values per 100g for a given ingredient (USDA SR Legacy data)."""

    __tablename__ = "ingredient_nutrition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    energy_kcal: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    carbohydrate_g: Mapped[float | None] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    calcium_mg: Mapped[float | None] = mapped_column(Float)
    iron_mg: Mapped[float | None] = mapped_column(Float)
    vitamin_c_mg: Mapped[float | None] = mapped_column(Float)
    vitamin_a_ug: Mapped[float | None] = mapped_column(Float)
    saturated_fat_g: Mapped[float | None] = mapped_column(Float)
    per_100g: Mapped[int] = mapped_column(Integer, default=1)

    ingredient: Mapped["Ingredient"] = relationship(back_populates="nutrition")
