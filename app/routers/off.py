from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import off_service

router = APIRouter(prefix="/products", tags=["Open Food Facts"])


@router.get("/barcode/{barcode}")
def lookup_barcode(barcode: str, db: Session = Depends(get_db)):
    """
    Look up a food product by barcode using Open Food Facts.
    Results are cached locally after the first lookup.
    """
    product = off_service.get_by_barcode(db, barcode)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in Open Food Facts")
    return {
        "barcode": product.barcode,
        "product_name": product.product_name,
        "brands": product.brands,
        "nutriscore_grade": product.nutriscore_grade,
        "nova_group": product.nova_group,
        "allergens": product.allergens,
        "nutrition_per_100g": {
            "energy_kcal": product.energy_kcal_100g,
            "protein_g": product.protein_100g,
            "fat_g": product.fat_100g,
            "saturated_fat_g": product.saturated_fat_100g,
            "carbohydrate_g": product.carbohydrate_100g,
            "sugar_g": product.sugar_100g,
            "fiber_g": product.fiber_100g,
            "sodium_g": product.sodium_100g,
        },
        "cached": True if product.fetched_at else False,
    }


@router.get("/search")
def search_products(
    name: str = Query(..., min_length=2, description="Product name to search"),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Search food products by name from Open Food Facts.
    Returns allergen info, Nutri-Score grade, and nutrition per 100g.
    """
    products = off_service.search_products(db, name, page_size=limit)
    if not products:
        return {"results": [], "message": "No products found"}

    return {
        "results": [
            {
                "barcode": p.barcode,
                "product_name": p.product_name,
                "brands": p.brands,
                "nutriscore_grade": p.nutriscore_grade,
                "allergens": p.allergens,
                "energy_kcal_100g": p.energy_kcal_100g,
            }
            for p in products
        ]
    }
