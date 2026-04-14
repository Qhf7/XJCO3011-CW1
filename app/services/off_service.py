"""
Open Food Facts integration service.

Implements a cache-first strategy:
  1. Check local off_product table in SQLite
  2. On cache miss, call OFF REST API and persist the result
"""

from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models.off import OffProduct

_HEADERS = {"User-Agent": "NutritionRecipeAPI/1.0 (XJCO3011 coursework; academic use)"}


def _call_off_api(url: str, params: dict | None = None) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=_HEADERS, timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


def _parse_product(raw: dict) -> dict:
    nutriments = raw.get("nutriments", {})
    tags = raw.get("allergens_tags", [])
    allergens = ",".join(t.replace("en:", "") for t in tags)
    return {
        "barcode": raw.get("code", ""),
        "product_name": raw.get("product_name", "") or "",
        "brands": raw.get("brands", "") or "",
        "categories": str(raw.get("categories_tags", ""))[:500],
        "allergens": allergens,
        "traces": (raw.get("traces", "") or "")[:300],
        "nutriscore_grade": (raw.get("nutriscore_grade", "") or "").lower()[:1] or None,
        "nova_group": raw.get("nova_group"),
        "energy_kcal_100g": nutriments.get("energy-kcal_100g"),
        "protein_100g": nutriments.get("proteins_100g"),
        "fat_100g": nutriments.get("fat_100g"),
        "saturated_fat_100g": nutriments.get("saturated-fat_100g"),
        "carbohydrate_100g": nutriments.get("carbohydrates_100g"),
        "sugar_100g": nutriments.get("sugars_100g"),
        "fiber_100g": nutriments.get("fiber_100g"),
        "sodium_100g": nutriments.get("sodium_100g"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _upsert(db: Session, data: dict) -> OffProduct:
    existing = db.query(OffProduct).filter(OffProduct.barcode == data["barcode"]).first()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
    else:
        existing = OffProduct(**data)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_by_barcode(db: Session, barcode: str) -> OffProduct | None:
    """Cache-first lookup by barcode."""
    cached = db.query(OffProduct).filter(OffProduct.barcode == barcode).first()
    if cached:
        return cached

    url = f"{settings.off_api_base}/product/{barcode}.json"
    data = _call_off_api(url)
    if not data or data.get("status") != 1:
        return None

    parsed = _parse_product(data["product"])
    return _upsert(db, parsed)


def search_products(db: Session, name: str, page_size: int = 5) -> list[OffProduct]:
    """Search OFF by name. Returns cached results where possible."""
    local = (
        db.query(OffProduct)
        .filter(OffProduct.product_name.ilike(f"%{name}%"))
        .limit(page_size)
        .all()
    )
    if local:
        return local

    params = {
        "search_terms": name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "fields": "code,product_name,brands,allergens_tags,nutriscore_grade,nova_group,nutriments",
    }
    data = _call_off_api(settings.off_search_url, params)
    if not data:
        return []

    results = []
    for raw in data.get("products", []):
        parsed = _parse_product(raw)
        if parsed["barcode"]:
            product = _upsert(db, parsed)
            results.append(product)
    return results
