"""Tests for analytics endpoints and business logic services."""

import pytest
from app.services.allergen import detect_allergens_from_list, allergens_safe_for
from app.services.difficulty import estimate_difficulty, difficulty_label
from app.services.nutrition import compute_nutrient_density_score, nutrient_density_grade


# ---------- Unit tests: Allergen service ----------

def test_allergen_detect_dairy():
    result = detect_allergens_from_list(["butter", "milk", "cheddar cheese"])
    assert "dairy" in result
    assert "butter" in result["dairy"]


def test_allergen_detect_gluten():
    result = detect_allergens_from_list(["all-purpose flour", "yeast", "salt"])
    assert "gluten" in result


def test_allergen_detect_multiple():
    result = detect_allergens_from_list(["wheat flour", "eggs", "almond milk", "peanut butter"])
    assert "gluten" in result
    assert "eggs" in result
    assert "peanuts" in result


def test_allergen_none_detected():
    result = detect_allergens_from_list(["rice", "water", "salt", "olive oil"])
    assert len(result) == 0


def test_allergen_safe_for():
    detected = {"dairy", "gluten"}
    safe = allergens_safe_for(detected)
    assert "dairy-free" not in safe
    assert "gluten-free" not in safe
    assert "egg-free" in safe
    assert "peanut-free" in safe


# ---------- Unit tests: Difficulty service ----------

def test_difficulty_easy_recipe():
    score, factors = estimate_difficulty(
        n_steps=3, n_ingredients=4, minutes=15, tags=["easy", "quick"], steps=[]
    )
    assert score <= 2
    assert factors["beginner_hint"] == -1


def test_difficulty_hard_recipe():
    score, factors = estimate_difficulty(
        n_steps=15, n_ingredients=12, minutes=120,
        tags=["advanced"], steps=["julienne the vegetables", "deglaze the pan"]
    )
    assert score >= 4


def test_difficulty_labels():
    assert difficulty_label(1) == "Very Easy"
    assert difficulty_label(3) == "Moderate"
    assert difficulty_label(5) == "Expert"


def test_difficulty_bounds():
    score, _ = estimate_difficulty(0, 0, 0, [], [])
    assert 1 <= score <= 5

    score, _ = estimate_difficulty(100, 100, 9999, ["advanced"], ["sous vide everything"])
    assert 1 <= score <= 5


# ---------- Unit tests: Nutrition service ----------

class MockNutrition:
    energy_kcal = 165.0
    protein_g = 31.0
    fat_g = 3.6
    carbohydrate_g = 0.0
    fiber_g = 0.0
    sugar_g = 0.0
    sodium_mg = 74.0
    calcium_mg = 15.0
    iron_mg = 1.04
    vitamin_c_mg = 0.0
    vitamin_a_ug = 6.0
    saturated_fat_g = 1.01


def test_nutrient_density_score_computed():
    score = compute_nutrient_density_score(MockNutrition())
    assert score is not None
    assert 0 <= score <= 100


def test_nutrient_density_zero_calories():
    class ZeroCal:
        energy_kcal = 0
    assert compute_nutrient_density_score(ZeroCal()) is None


def test_nutrient_density_grade():
    assert nutrient_density_grade(80) == "A"
    assert nutrient_density_grade(55) == "B"
    assert nutrient_density_grade(35) == "C"
    assert nutrient_density_grade(20) == "D"
    assert nutrient_density_grade(5) == "E"
    assert nutrient_density_grade(None) is None


# ---------- Integration tests: Analytics endpoints ----------

def test_calorie_distribution(client):
    resp = client.get("/analytics/calorie-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert "low" in data
    assert "medium" in data
    assert "high" in data


def test_macro_trends(client):
    resp = client.get("/analytics/macro-trends")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_top_ingredients(client, seed_recipe):
    resp = client.get("/analytics/top-ingredients?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert "ingredient_name" in item
        assert "recipe_count" in item


def test_allergen_statistics(client):
    resp = client.get("/analytics/allergen-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "dairy" in data
    assert "gluten" in data
    assert "eggs" in data


def test_nutrition_calculate(client, seed_ingredient):
    resp = client.post("/analytics/nutrition/calculate", json={
        "items": [{"ingredient_id": seed_ingredient.id, "amount_g": 200}],
        "servings": 2,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["servings"] == 2
    # 200g of chicken breast (165 kcal/100g) = 330 total, 165 per serving
    assert data["total"]["energy_kcal"] == pytest.approx(330.0, rel=0.01)
    assert data["per_serving"]["energy_kcal"] == pytest.approx(165.0, rel=0.01)


def test_nutrition_compare(client, seed_ingredient):
    resp = client.post("/analytics/nutrition/compare", json={
        "ingredient_ids": [seed_ingredient.id, seed_ingredient.id],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2


def test_meal_plan_analyze(client, seed_recipe):
    resp = client.post("/analytics/meal-plan/analyze", json={
        "entries": [
            {"recipe_id": seed_recipe.id, "servings": 1},
            {"recipe_id": seed_recipe.id, "servings": 2},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["recipes_included"] == 2
    assert data["total_calories"] == pytest.approx(320.0 * 3, rel=0.01)
    assert isinstance(data["allergens_combined"], list)
    assert "dri_summary" in data


def test_meal_plan_nonexistent_recipe(client):
    resp = client.post("/analytics/meal-plan/analyze", json={
        "entries": [{"recipe_id": 99999999, "servings": 1}]
    })
    assert resp.status_code == 404
