"""Tests for ingredient CRUD and nutrition endpoints."""

import pytest


def test_list_ingredients_empty(client):
    resp = client.get("/ingredients?page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_ingredient_not_found(client):
    resp = client.get("/ingredients/99999999")
    assert resp.status_code == 404


def test_get_ingredient_success(client, seed_ingredient):
    resp = client.get(f"/ingredients/{seed_ingredient.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Test Chicken Breast"
    assert data["data_source"] == "user_created"
    assert data["nutrition"]["energy_kcal"] == 165.0
    assert data["nutrition"]["protein_g"] == 31.0


def test_get_ingredient_nutrition(client, seed_ingredient):
    resp = client.get(f"/ingredients/{seed_ingredient.id}/nutrition")
    assert resp.status_code == 200
    data = resp.json()
    assert data["energy_kcal"] == 165.0
    assert data["protein_g"] == 31.0
    assert data["fat_g"] == 3.6


def test_nutrient_density_score(client, seed_ingredient):
    resp = client.get(f"/ingredients/{seed_ingredient.id}/nutrient-density")
    assert resp.status_code == 200
    data = resp.json()
    assert "nutrient_density_score" in data
    assert "grade" in data
    assert data["grade"] in ["A", "B", "C", "D", "E"]
    # Chicken breast is high-protein, should score reasonably well
    assert data["nutrient_density_score"] is not None
    assert data["nutrient_density_score"] > 0


def test_create_ingredient(client, auth_headers):
    resp = client.post("/ingredients", json={
        "description": "Custom Almond Flour",
        "nutrition": {
            "energy_kcal": 571,
            "protein_g": 21.4,
            "fat_g": 50.0,
            "carbohydrate_g": 21.6,
            "fiber_g": 12.5,
        },
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Custom Almond Flour"
    assert data["data_source"] == "user_created"
    assert data["nutrition"]["energy_kcal"] == 571


def test_create_ingredient_requires_auth(client):
    resp = client.post("/ingredients", json={"description": "No auth ingredient"})
    assert resp.status_code == 401


def test_update_ingredient(client, auth_headers):
    create = client.post("/ingredients", json={"description": "To Update"}, headers=auth_headers)
    ing_id = create.json()["id"]

    resp = client.put(f"/ingredients/{ing_id}", json={"description": "Updated Name"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated Name"


def test_update_usda_ingredient_forbidden(client, seed_ingredient, auth_headers, db_session):
    from app.models.ingredient import Ingredient
    ing = db_session.query(Ingredient).filter(Ingredient.id == seed_ingredient.id).first()
    ing.data_source = "usda_sr_legacy"
    db_session.commit()

    resp = client.put(f"/ingredients/{seed_ingredient.id}", json={"description": "Hacked"}, headers=auth_headers)
    assert resp.status_code == 403


def test_delete_ingredient(client, auth_headers):
    create = client.post("/ingredients", json={"description": "To Delete"}, headers=auth_headers)
    ing_id = create.json()["id"]

    resp = client.delete(f"/ingredients/{ing_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp2 = client.get(f"/ingredients/{ing_id}")
    assert resp2.status_code == 404


def test_search_ingredients(client, seed_ingredient):
    resp = client.get("/ingredients?q=Chicken")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("chicken" in item["description"].lower() for item in data["items"])


def test_list_categories(client, seed_category):
    resp = client.get("/ingredients/categories")
    assert resp.status_code == 200
    cats = resp.json()
    assert isinstance(cats, list)
    ids = [c["id"] for c in cats]
    assert seed_category.id in ids
