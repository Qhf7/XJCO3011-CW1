from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.database import get_db
from app.models.ingredient import FoodCategory, Ingredient, IngredientNutrition
from app.models.user import User
from app.schemas.ingredient import (
    IngredientCreate,
    IngredientListOut,
    IngredientOut,
    IngredientUpdate,
    NutrientDensityOut,
    NutritionOut,
)
from app.services.nutrition import (
    compute_nutrient_density_score,
    nutrient_density_grade,
)

router = APIRouter(prefix="/ingredients", tags=["Ingredients"])

# next available fdc_id for user-created ingredients (above USDA range)
_USER_FDC_BASE = 9_000_000


def _to_out(ing: Ingredient) -> IngredientOut:
    nutrition = None
    if ing.nutrition:
        nutrition = NutritionOut.model_validate(ing.nutrition)
    return IngredientOut(
        id=ing.id,
        fdc_id=ing.fdc_id,
        description=ing.description,
        category_id=ing.category_id,
        data_source=ing.data_source,
        category_name=ing.category.description if ing.category else None,
        nutrition=nutrition,
    )


@router.get("", response_model=IngredientListOut)
def list_ingredients(
    q: str | None = Query(None, description="Search by name"),
    category_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List and search ingredients from the USDA database."""
    query = db.query(Ingredient)
    if q:
        query = query.filter(Ingredient.description.ilike(f"%{q}%"))
    if category_id:
        query = query.filter(Ingredient.category_id == category_id)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return IngredientListOut(
        total=total, page=page, page_size=page_size, items=[_to_out(i) for i in items]
    )


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """List all food categories."""
    cats = db.query(FoodCategory).order_by(FoodCategory.description).all()
    return [{"id": c.id, "code": c.code, "description": c.description} for c in cats]


@router.get("/{ingredient_id}", response_model=IngredientOut)
def get_ingredient(ingredient_id: int, db: Session = Depends(get_db)):
    """Get a single ingredient by ID."""
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    return _to_out(ing)


@router.get("/{ingredient_id}/nutrition", response_model=NutritionOut)
def get_ingredient_nutrition(ingredient_id: int, db: Session = Depends(get_db)):
    """Get full nutritional profile for an ingredient (per 100g)."""
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if not ing.nutrition:
        raise HTTPException(status_code=404, detail="No nutrition data available for this ingredient")
    return NutritionOut.model_validate(ing.nutrition)


@router.get("/{ingredient_id}/nutrient-density", response_model=NutrientDensityOut)
def get_nutrient_density(ingredient_id: int, db: Session = Depends(get_db)):
    """
    Compute the Nutrient Density Score (NDS) for an ingredient.

    NDS measures how much beneficial nutrition (protein, fibre, vitamins, minerals)
    a food delivers per 100 kcal. Range 0–100; graded A (best) to E (lowest).
    """
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if not ing.nutrition:
        raise HTTPException(status_code=404, detail="No nutrition data available")

    score = compute_nutrient_density_score(ing.nutrition)
    grade = nutrient_density_grade(score)
    return NutrientDensityOut(
        ingredient_id=ing.id,
        description=ing.description,
        energy_kcal=ing.nutrition.energy_kcal,
        nutrient_density_score=score,
        grade=grade,
    )


@router.post("", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    payload: IngredientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a custom ingredient (requires authentication)."""
    # Assign a synthetic fdc_id in the user-reserved range
    max_fdc = db.query(Ingredient).filter(
        Ingredient.fdc_id >= _USER_FDC_BASE
    ).order_by(Ingredient.fdc_id.desc()).first()
    new_fdc = (max_fdc.fdc_id + 1) if max_fdc else _USER_FDC_BASE

    # treat category_id=0 as null (Swagger UI defaults integers to 0)
    category_id = payload.category_id if payload.category_id else None

    ing = Ingredient(
        fdc_id=new_fdc,
        description=payload.description,
        category_id=category_id,
        data_source="user_created",
    )
    db.add(ing)
    db.flush()

    if payload.nutrition:
        nut = IngredientNutrition(ingredient_id=ing.id, **payload.nutrition.model_dump())
        db.add(nut)

    db.commit()
    db.refresh(ing)
    return _to_out(ing)


@router.put("/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a custom ingredient (requires authentication)."""
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if ing.data_source != "user_created":
        raise HTTPException(status_code=403, detail="USDA ingredients are read-only")

    if payload.description is not None:
        ing.description = payload.description
    if payload.category_id is not None:
        # treat 0 as null
        ing.category_id = payload.category_id if payload.category_id else None

    if payload.nutrition is not None:
        if ing.nutrition:
            for k, v in payload.nutrition.model_dump(exclude_none=True).items():
                setattr(ing.nutrition, k, v)
        else:
            nut = IngredientNutrition(ingredient_id=ing.id, **payload.nutrition.model_dump())
            db.add(nut)

    db.commit()
    db.refresh(ing)
    return _to_out(ing)


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(
    ingredient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete a custom ingredient (requires authentication)."""
    ing = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingredient not found")
    if ing.data_source != "user_created":
        raise HTTPException(status_code=403, detail="USDA ingredients are read-only")
    db.delete(ing)
    db.commit()
