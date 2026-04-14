from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    food_com_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    minutes: Mapped[int | None] = mapped_column(Integer)
    submitted: Mapped[str | None] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)
    n_steps: Mapped[int | None] = mapped_column(Integer)
    n_ingredients: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[str | None] = mapped_column(Text)
    raw_ingredients: Mapped[str | None] = mapped_column(Text)

    # Nutrition per serving (Food.com %DV values)
    calories: Mapped[float | None] = mapped_column(Float, index=True)
    total_fat_pdv: Mapped[float | None] = mapped_column(Float)
    sugar_pdv: Mapped[float | None] = mapped_column(Float)
    sodium_pdv: Mapped[float | None] = mapped_column(Float)
    protein_pdv: Mapped[float | None] = mapped_column(Float)
    sat_fat_pdv: Mapped[float | None] = mapped_column(Float)
    carbs_pdv: Mapped[float | None] = mapped_column(Float)

    # Computed / derived fields
    difficulty_score: Mapped[int | None] = mapped_column(Integer, index=True)
    allergen_flags: Mapped[str | None] = mapped_column(Text)
    calorie_level: Mapped[str | None] = mapped_column(String(16), index=True)

    ingredient_links: Mapped[list["RecipeIngredientLink"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeIngredientLink(Base):
    __tablename__ = "recipe_ingredient_link"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ingredient_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    matched_fdc_id: Mapped[int | None] = mapped_column(Integer)

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredient_links")
    matched_ingredient: Mapped["Ingredient | None"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[matched_fdc_id],
        primaryjoin="RecipeIngredientLink.matched_fdc_id == Ingredient.fdc_id",
        back_populates="recipe_links",
    )
