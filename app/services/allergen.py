"""
Allergen detection service.

Covers the FDA's 9 major food allergens (updated 2023 to include sesame)
plus common additional allergens.
"""

ALLERGEN_KEYWORDS: dict[str, list[str]] = {
    "gluten": [
        "wheat", "flour", "bread", "pasta", "barley", "rye", "oats",
        "semolina", "spelt", "farro", "couscous", "bulgur", "cracker",
        "biscuit", "noodle", "dumpling",
    ],
    "dairy": [
        "milk", "butter", "cheese", "cream", "yogurt", "whey", "lactose",
        "casein", "ghee", "buttermilk", "parmesan", "mozzarella", "cheddar",
        "brie", "gouda", "ricotta", "sour cream", "half-and-half",
    ],
    "eggs": [
        "egg", "eggs", "mayonnaise", "meringue", "albumin", "aioli",
    ],
    "peanuts": [
        "peanut", "groundnut", "monkey nut", "arachis",
    ],
    "tree_nuts": [
        "almond", "cashew", "walnut", "pecan", "pistachio", "macadamia",
        "hazelnut", "brazil nut", "chestnut", "pine nut", "coconut",
        "praline", "marzipan",
    ],
    "soy": [
        "soy", "soya", "tofu", "tempeh", "edamame", "miso", "tamari",
        "natto", "soybean",
    ],
    "fish": [
        "salmon", "tuna", "cod", "tilapia", "halibut", "bass", "flounder",
        "sardine", "anchovy", "trout", "catfish", "haddock", "mackerel",
        "swordfish", "pollock", "snapper", "fish sauce",
    ],
    "shellfish": [
        "shrimp", "crab", "lobster", "clam", "oyster", "scallop", "mussel",
        "prawn", "crawfish", "crayfish", "abalone", "barnacle",
    ],
    "sesame": [
        "sesame", "tahini", "til", "benne",
    ],
    "sulfites": [
        "wine", "dried fruit", "vinegar", "beer",
    ],
}

ALL_ALLERGEN_NAMES = set(ALLERGEN_KEYWORDS.keys())


def detect_allergens_from_list(ingredients: list[str]) -> dict[str, list[str]]:
    """
    Scan an ingredients list for allergens.

    Returns a dict mapping each detected allergen name to the ingredient(s) that triggered it.
    Example: {"gluten": ["all-purpose flour", "bread crumbs"], "dairy": ["butter"]}
    """
    combined_lower = [(ing, ing.lower()) for ing in ingredients]
    result: dict[str, list[str]] = {}

    for allergen, keywords in ALLERGEN_KEYWORDS.items():
        matched = []
        for original, lower in combined_lower:
            if any(kw in lower for kw in keywords):
                matched.append(original)
        if matched:
            result[allergen] = matched

    return result


def allergens_safe_for(detected: set[str]) -> list[str]:
    """Return list of dietary labels the recipe is safe for."""
    all_names = ALL_ALLERGEN_NAMES
    missing = all_names - detected
    label_map = {
        "gluten": "gluten-free",
        "dairy": "dairy-free",
        "eggs": "egg-free",
        "peanuts": "peanut-free",
        "tree_nuts": "tree-nut-free",
        "soy": "soy-free",
        "fish": "fish-free",
        "shellfish": "shellfish-free",
        "sesame": "sesame-free",
        "sulfites": "sulfite-free",
    }
    return sorted([label_map[k] for k in missing if k in label_map])


def compute_allergen_response(ingredients: list[str], recipe_id: int, recipe_name: str) -> dict:
    breakdown = detect_allergens_from_list(ingredients)
    detected_set = set(breakdown.keys())
    safe_for = allergens_safe_for(detected_set)
    return {
        "recipe_id": recipe_id,
        "recipe_name": recipe_name,
        "allergens_detected": sorted(detected_set),
        "ingredient_breakdown": breakdown,
        "safe_for": safe_for,
    }
