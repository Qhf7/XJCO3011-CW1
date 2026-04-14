import ast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.database import get_db
from app.models.recipe import Recipe, RecipeIngredientLink
from app.models.user import User
from app.schemas.recipe import (
    AllergenWarningOut,
    DifficultyOut,
    RecipeCreate,
    RecipeListOut,
    RecipeNutritionOut,
    RecipeOut,
    RecipeUpdate,
)
from app.services.allergen import compute_allergen_response
from app.services.difficulty import difficulty_label, estimate_difficulty
from app.services.nutrition import recipe_dri_comparison

router = APIRouter(prefix="/recipes", tags=["Recipes"])


def _parse_ingredients(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        result = ast.literal_eval(raw)
        return result if isinstance(result, list) else raw.split(",")
    except Exception:
        return [s.strip() for s in raw.split(",") if s.strip()]


def _to_out(recipe: Recipe) -> RecipeOut:
    return RecipeOut(
        id=recipe.id,
        food_com_id=recipe.food_com_id,
        name=recipe.name,
        minutes=recipe.minutes,
        description=recipe.description,
        tags=recipe.tags,
        n_steps=recipe.n_steps,
        n_ingredients=recipe.n_ingredients,
        calories=recipe.calories,
        calorie_level=recipe.calorie_level,
        difficulty_score=recipe.difficulty_score,
        allergen_flags=recipe.allergen_flags,
        ingredients_list=_parse_ingredients(recipe.raw_ingredients),
    )


@router.get("", response_model=RecipeListOut)
def list_recipes(
    q: str | None = Query(None, description="Search recipe name or description"),
    calorie_level: str | None = Query(None, enum=["low", "medium", "high"]),
    max_calories: float | None = Query(None, ge=0),
    difficulty: int | None = Query(None, ge=1, le=5),
    allergen_free: str | None = Query(None, description="Comma-separated allergens to exclude, e.g. 'gluten,dairy'"),
    ingredient: str | None = Query(None, description="Filter recipes containing this ingredient"),
    max_minutes: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    List and filter recipes.
    Supports full-text search, calorie/difficulty/allergen/ingredient/time filters.
    """
    query = db.query(Recipe)

    if q:
        query = query.filter(
            or_(
                Recipe.name.ilike(f"%{q}%"),
                Recipe.description.ilike(f"%{q}%"),
            )
        )
    if calorie_level:
        query = query.filter(Recipe.calorie_level == calorie_level)
    if max_calories is not None:
        query = query.filter(Recipe.calories <= max_calories)
    if difficulty:
        query = query.filter(Recipe.difficulty_score == difficulty)
    if max_minutes:
        query = query.filter(Recipe.minutes <= max_minutes)
    if allergen_free:
        allergens_to_exclude = [a.strip() for a in allergen_free.split(",")]
        for allergen in allergens_to_exclude:
            query = query.filter(
                or_(
                    Recipe.allergen_flags == None,
                    Recipe.allergen_flags == "",
                    ~Recipe.allergen_flags.ilike(f"%{allergen}%"),
                )
            )
    if ingredient:
        query = query.join(RecipeIngredientLink).filter(
            RecipeIngredientLink.ingredient_name.ilike(f"%{ingredient}%")
        )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return RecipeListOut(
        total=total, page=page, page_size=page_size, items=[_to_out(r) for r in items]
    )


@router.get("/by-ingredients", response_model=RecipeListOut)
def find_by_ingredients(
    ingredients: str = Query(..., description="Comma-separated ingredient names you have on hand"),
    match_all: bool = Query(False, description="Require ALL ingredients to match (stricter)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Find recipes you can make with the ingredients you have.
    Set match_all=true to only return recipes using exclusively those ingredients.
    """
    ing_list = [i.strip().lower() for i in ingredients.split(",") if i.strip()]
    if not ing_list:
        raise HTTPException(status_code=400, detail="Provide at least one ingredient")

    if match_all:
        # Recipes where ALL provided ingredients appear
        query = db.query(Recipe)
        for ing in ing_list:
            query = query.filter(Recipe.raw_ingredients.ilike(f"%{ing}%"))
    else:
        query = db.query(Recipe).filter(
            or_(*[Recipe.raw_ingredients.ilike(f"%{ing}%") for ing in ing_list])
        )

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return RecipeListOut(
        total=total, page=page, page_size=page_size, items=[_to_out(r) for r in items]
    )


@router.get("/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Get a single recipe by ID."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return _to_out(recipe)


@router.get("/{recipe_id}/nutrition", response_model=RecipeNutritionOut)
def get_recipe_nutrition(
    recipe_id: int,
    servings: int = Query(1, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Get nutrition summary for a recipe.
    Optionally specify servings to scale values.
    Includes comparison against Daily Reference Intake (DRI).
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    def scale(val: float | None) -> float | None:
        if val is None:
            return None
        return round(val / servings, 2)

    dri = recipe_dri_comparison(
        recipe.calories,
        recipe.protein_pdv,
        recipe.total_fat_pdv,
        recipe.carbs_pdv,
        recipe.sodium_pdv,
    )

    return RecipeNutritionOut(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        servings=servings,
        calories_per_serving=scale(recipe.calories),
        total_fat_pdv=scale(recipe.total_fat_pdv),
        sugar_pdv=scale(recipe.sugar_pdv),
        sodium_pdv=scale(recipe.sodium_pdv),
        protein_pdv=scale(recipe.protein_pdv),
        sat_fat_pdv=scale(recipe.sat_fat_pdv),
        carbs_pdv=scale(recipe.carbs_pdv),
        calorie_level=recipe.calorie_level,
        dri_comparison=dri,
    )


@router.get("/{recipe_id}/allergens", response_model=AllergenWarningOut)
def get_recipe_allergens(recipe_id: int, db: Session = Depends(get_db)):
    """
    Get detailed allergen warnings for a recipe.
    Lists which ingredients trigger each allergen,
    and which dietary restrictions the recipe is safe for.
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = _parse_ingredients(recipe.raw_ingredients)
    result = compute_allergen_response(ingredients, recipe.id, recipe.name)
    return AllergenWarningOut(**result)


@router.get("/{recipe_id}/difficulty", response_model=DifficultyOut)
def get_recipe_difficulty(recipe_id: int, db: Session = Depends(get_db)):
    """
    Get difficulty estimate for a recipe with detailed factor breakdown.
    Score 1 (Very Easy) to 5 (Expert).
    """
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    tags = [t.strip() for t in (recipe.tags or "").split(",") if t.strip()]
    steps = [s.strip() for s in (recipe.steps or "").split(" | ") if s.strip()]

    score, factors = estimate_difficulty(
        n_steps=recipe.n_steps or 0,
        n_ingredients=recipe.n_ingredients or 0,
        minutes=recipe.minutes,
        tags=tags,
        steps=steps,
    )

    return DifficultyOut(
        recipe_id=recipe.id,
        recipe_name=recipe.name,
        difficulty_score=score,
        difficulty_label=difficulty_label(score),
        factors={
            **factors,
            "n_steps": recipe.n_steps,
            "n_ingredients": recipe.n_ingredients,
            "minutes": recipe.minutes,
        },
    )


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
def create_recipe(
    payload: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new recipe (requires authentication)."""
    from app.services.allergen import detect_allergens_from_list

    allergens = detect_allergens_from_list(payload.ingredients)
    allergen_str = ",".join(sorted(allergens.keys()))

    tags_list = [t.strip() for t in (payload.tags or "").split(",") if t.strip()]
    score, _ = estimate_difficulty(
        n_steps=len(payload.steps),
        n_ingredients=len(payload.ingredients),
        minutes=payload.minutes or 0,
        tags=tags_list,
        steps=payload.steps,
    )

    cal = payload.calories
    calorie_level = (
        "low" if cal and cal < 200
        else "medium" if cal and cal < 500
        else "high" if cal
        else None
    )

    recipe = Recipe(
        name=payload.name,
        minutes=payload.minutes,
        description=payload.description,
        tags=payload.tags,
        n_steps=len(payload.steps),
        n_ingredients=len(payload.ingredients),
        steps=" | ".join(payload.steps),
        raw_ingredients=str(payload.ingredients),
        calories=payload.calories,
        protein_pdv=payload.protein_pdv,
        carbs_pdv=payload.carbs_pdv,
        total_fat_pdv=payload.fat_pdv,
        allergen_flags=allergen_str,
        difficulty_score=score,
        calorie_level=calorie_level,
    )
    db.add(recipe)
    db.flush()

    for ing_name in payload.ingredients:
        db.add(RecipeIngredientLink(recipe_id=recipe.id, ingredient_name=ing_name.lower()))

    db.commit()
    db.refresh(recipe)
    return _to_out(recipe)


@router.put("/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an existing recipe (requires authentication)."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if payload.name is not None:
        recipe.name = payload.name
    if payload.minutes is not None:
        recipe.minutes = payload.minutes
    if payload.description is not None:
        recipe.description = payload.description
    if payload.tags is not None:
        recipe.tags = payload.tags
    if payload.calories is not None:
        recipe.calories = payload.calories

    if payload.ingredients is not None:
        from app.services.allergen import detect_allergens_from_list
        db.query(RecipeIngredientLink).filter(
            RecipeIngredientLink.recipe_id == recipe_id
        ).delete()
        for ing_name in payload.ingredients:
            db.add(RecipeIngredientLink(recipe_id=recipe.id, ingredient_name=ing_name.lower()))
        recipe.raw_ingredients = str(payload.ingredients)
        recipe.n_ingredients = len(payload.ingredients)
        allergens = detect_allergens_from_list(payload.ingredients)
        recipe.allergen_flags = ",".join(sorted(allergens.keys()))

    if payload.steps is not None:
        recipe.steps = " | ".join(payload.steps)
        recipe.n_steps = len(payload.steps)

    db.commit()
    db.refresh(recipe)
    return _to_out(recipe)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a recipe (requires authentication)."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(recipe)
    db.commit()
