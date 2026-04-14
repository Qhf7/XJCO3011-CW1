"""
Recipe difficulty estimation service.

Score 1–5 computed from:
  - Number of steps
  - Number of ingredients
  - Total cooking time
  - Presence of advanced cooking techniques in tags/steps
  - Beginner-friendly tag hints
"""

ADVANCED_TECHNIQUES = {
    "julienne", "brunoise", "chiffonade", "deglaze", "emulsify", "temper",
    "braise", "sous vide", "flambé", "flambe", "poach", "blanch", "caramelise",
    "caramelize", "baste", "fold", "proof", "ferment", "cure", "smoke",
    "deep-fry", "deep fry", "pressure cook",
}

BEGINNER_HINTS = {
    "easy", "beginner", "simple", "quick", "no-cook", "5-ingredients-or-less",
    "3-steps-or-less", "for-1-or-2",
}

DIFFICULTY_LABELS = {
    1: "Very Easy",
    2: "Easy",
    3: "Moderate",
    4: "Challenging",
    5: "Expert",
}


def estimate_difficulty(
    n_steps: int,
    n_ingredients: int,
    minutes: int | None,
    tags: list[str],
    steps: list[str],
) -> tuple[int, dict]:
    """
    Returns (score, factors_dict) where score is 1–5.
    factors_dict explains each contribution for the API response.
    """
    factors: dict[str, int] = {}

    # Steps contribution (0–2)
    if n_steps <= 5:
        steps_score = 0
    elif n_steps <= 10:
        steps_score = 1
    else:
        steps_score = 2
    factors["steps_score"] = steps_score

    # Ingredients contribution (0–2)
    if n_ingredients <= 5:
        ing_score = 0
    elif n_ingredients <= 10:
        ing_score = 1
    else:
        ing_score = 2
    factors["ingredients_score"] = ing_score

    # Time contribution (0–1)
    time_score = 0
    if minutes and minutes > 90:
        time_score = 1
    factors["time_score"] = time_score

    # Advanced technique detection (0–1)
    all_text = " ".join(tags + steps).lower()
    technique_found = any(t in all_text for t in ADVANCED_TECHNIQUES)
    technique_score = 1 if technique_found else 0
    factors["technique_score"] = technique_score

    raw = steps_score + ing_score + time_score + technique_score  # 0–6

    # Beginner hint modifier (subtract 1)
    tag_text = " ".join(tags).lower()
    if any(h in tag_text for h in BEGINNER_HINTS):
        raw = max(raw - 1, 0)
        factors["beginner_hint"] = -1
    else:
        factors["beginner_hint"] = 0

    # Map 0–6 → 1–5
    score = min(max((raw // 2) + 1, 1), 5)
    return score, factors


def difficulty_label(score: int) -> str:
    return DIFFICULTY_LABELS.get(score, "Unknown")
