"""Tests for recipe CRUD and analysis endpoints."""

import pytest


def test_list_recipes(client, seed_recipe):
    resp = client.get("/recipes?page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_get_recipe_success(client, seed_recipe):
    resp = client.get(f"/recipes/{seed_recipe.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Chicken Salad"
    assert data["calories"] == 320.0
    assert "chicken breast" in data["ingredients_list"]


def test_get_recipe_not_found(client):
    resp = client.get("/recipes/99999999")
    assert resp.status_code == 404


def test_get_recipe_nutrition(client, seed_recipe):
    resp = client.get(f"/recipes/{seed_recipe.id}/nutrition")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calories_per_serving"] == 320.0
    assert data["calorie_level"] == "medium"
    assert "dri_comparison" in data
    assert "calories" in data["dri_comparison"]


def test_get_recipe_nutrition_scaled(client, seed_recipe):
    resp = client.get(f"/recipes/{seed_recipe.id}/nutrition?servings=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["calories_per_serving"] == 160.0  # 320 / 2


def test_get_recipe_allergens(client, seed_recipe):
    resp = client.get(f"/recipes/{seed_recipe.id}/allergens")
    assert resp.status_code == 200
    data = resp.json()
    assert "allergens_detected" in data
    assert "ingredient_breakdown" in data
    assert "safe_for" in data
    assert isinstance(data["safe_for"], list)


def test_allergen_dairy_detected(client, auth_headers):
    resp = client.post("/recipes", json={
        "name": "Cheesy Pasta",
        "ingredients": ["pasta", "cheddar cheese", "butter", "milk"],
        "steps": ["boil pasta", "melt cheese", "mix together"],
    }, headers=auth_headers)
    recipe_id = resp.json()["id"]

    allergen_resp = client.get(f"/recipes/{recipe_id}/allergens")
    data = allergen_resp.json()
    assert "dairy" in data["allergens_detected"]
    assert "gluten" in data["allergens_detected"]
    assert "dairy-free" not in data["safe_for"]


def test_get_recipe_difficulty(client, seed_recipe):
    resp = client.get(f"/recipes/{seed_recipe.id}/difficulty")
    assert resp.status_code == 200
    data = resp.json()
    assert 1 <= data["difficulty_score"] <= 5
    assert data["difficulty_label"] in ["Very Easy", "Easy", "Moderate", "Challenging", "Expert"]
    assert "factors" in data
    assert "n_steps" in data["factors"]


def test_create_recipe(client, auth_headers):
    resp = client.post("/recipes", json={
        "name": "Simple Omelette",
        "minutes": 10,
        "description": "Quick breakfast",
        "ingredients": ["eggs", "butter", "salt"],
        "steps": ["crack eggs", "heat pan", "cook omelette"],
        "calories": 250.0,
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Simple Omelette"
    assert data["n_ingredients"] == 3
    assert data["n_steps"] == 3


def test_create_recipe_requires_auth(client):
    resp = client.post("/recipes", json={
        "name": "No Auth Recipe",
        "ingredients": ["ingredient"],
        "steps": ["step"],
    })
    assert resp.status_code == 401


def test_update_recipe(client, auth_headers):
    create = client.post("/recipes", json={
        "name": "Old Name",
        "ingredients": ["salt"],
        "steps": ["add salt"],
    }, headers=auth_headers)
    recipe_id = create.json()["id"]

    resp = client.put(f"/recipes/{recipe_id}", json={"name": "New Name"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_delete_recipe(client, auth_headers):
    create = client.post("/recipes", json={
        "name": "To Delete",
        "ingredients": ["x"],
        "steps": ["step"],
    }, headers=auth_headers)
    recipe_id = create.json()["id"]

    resp = client.delete(f"/recipes/{recipe_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp2 = client.get(f"/recipes/{recipe_id}")
    assert resp2.status_code == 404


def test_filter_by_calorie_level(client, seed_recipe):
    resp = client.get("/recipes?calorie_level=medium")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["calorie_level"] == "medium" for item in data["items"])


def test_filter_by_max_calories(client, seed_recipe):
    resp = client.get("/recipes?max_calories=400")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        if item["calories"] is not None:
            assert item["calories"] <= 400


def test_filter_allergen_free(client, auth_headers):
    client.post("/recipes", json={
        "name": "Vegan Bowl",
        "ingredients": ["rice", "vegetables", "olive oil"],
        "steps": ["cook rice", "add vegetables"],
    }, headers=auth_headers)

    resp = client.get("/recipes?allergen_free=gluten,dairy,eggs&q=Vegan Bowl")
    assert resp.status_code == 200


def test_find_by_ingredients(client, seed_recipe):
    resp = client.get("/recipes/by-ingredients?ingredients=chicken breast,lettuce")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
