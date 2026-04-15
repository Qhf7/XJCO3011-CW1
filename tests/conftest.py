"""
Shared pytest fixtures.
Uses a separate in-memory SQLite database for tests so real data is untouched.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.ingredient import FoodCategory, Ingredient, IngredientNutrition
from app.models.recipe import Recipe, RecipeIngredientLink

TEST_DATABASE_URL = "sqlite:///:memory:"

# StaticPool ensures all sessions share the same in-memory connection,
# so tables created in setup_db are visible to all subsequent sessions.
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def seed_category(setup_db):
    db = TestingSessionLocal()
    try:
        existing = db.query(FoodCategory).filter(FoodCategory.id == 99).first()
        if existing:
            return existing
        cat = FoodCategory(id=99, code="TEST", description="Test Category")
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat
    finally:
        db.close()


@pytest.fixture(scope="session")
def seed_ingredient(setup_db, seed_category):
    db = TestingSessionLocal()
    try:
        existing = db.query(Ingredient).filter(Ingredient.fdc_id == 999999).first()
        if existing:
            return existing
        ing = Ingredient(
            fdc_id=999999,
            description="Test Chicken Breast",
            category_id=seed_category.id,
            data_source="user_created",
        )
        db.add(ing)
        db.flush()
        nut = IngredientNutrition(
            ingredient_id=ing.id,
            energy_kcal=165.0,
            protein_g=31.0,
            fat_g=3.6,
            carbohydrate_g=0.0,
            fiber_g=0.0,
            sugar_g=0.0,
            sodium_mg=74.0,
            calcium_mg=15.0,
            iron_mg=1.04,
            vitamin_c_mg=0.0,
            vitamin_a_ug=6.0,
            saturated_fat_g=1.01,
        )
        db.add(nut)
        db.commit()
        db.refresh(ing)
        return ing
    finally:
        db.close()


@pytest.fixture(scope="session")
def seed_recipe(setup_db):
    db = TestingSessionLocal()
    try:
        existing = db.query(Recipe).filter(Recipe.food_com_id == 888888).first()
        if existing:
            return existing
        recipe = Recipe(
            food_com_id=888888,
            name="Test Chicken Salad",
            minutes=20,
            description="A simple test recipe",
            n_steps=3,
            n_ingredients=3,
            tags="easy,salad,healthy",
            steps="chop vegetables | mix ingredients | serve",
            raw_ingredients="['chicken breast', 'lettuce', 'olive oil']",
            calories=320.0,
            total_fat_pdv=18.0,
            sugar_pdv=2.0,
            sodium_pdv=10.0,
            protein_pdv=45.0,
            sat_fat_pdv=5.0,
            carbs_pdv=8.0,
            difficulty_score=2,
            allergen_flags="",
            calorie_level="medium",
        )
        db.add(recipe)
        db.flush()
        for name in ["chicken breast", "lettuce", "olive oil"]:
            db.add(RecipeIngredientLink(recipe_id=recipe.id, ingredient_name=name))
        db.commit()
        db.refresh(recipe)
        return recipe
    finally:
        db.close()


@pytest.fixture
def auth_token(client):
    client.post("/auth/register", json={
        "username": "pytest_user",
        "email": "pytest@test.com",
        "password": "testpass123",
    })
    resp = client.post("/auth/login", data={
        "username": "pytest_user",
        "password": "testpass123",
    })
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
