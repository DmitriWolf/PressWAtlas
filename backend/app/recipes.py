"""Local recipe dataset: load + lightweight keyword search.

The dataset (assets/recipes.json) is JSON-lines: one recipe object per line.
It has NO equipment or allergen fields and `ingredients` is a single
newline-delimited string. We do keyword scoring in-process (no embeddings, no
external service) to keep the app fully local and fast.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .config import RECIPES_PATH

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Words that add noise to cooking queries / ingredient lists.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "with", "for", "in", "on", "i",
    "me", "my", "some", "something", "want", "make", "cook", "recipe", "recipes",
    "dish", "dinner", "lunch", "meal", "can", "have", "got", "need", "please",
    "tablespoons", "tablespoon", "teaspoon", "teaspoons", "cup", "cups", "ounce",
    "ounces", "pound", "pounds", "whole", "sliced", "diced", "taste", "to",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1]


def _iso_duration_to_minutes(value: str | None) -> int | None:
    """Parse ISO-8601 durations like 'PT15M', 'PT1H30M'. 'PT'/'' -> None."""
    if not value or value == "PT":
        return None
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", value.strip())
    if not m:
        return None
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    total = hours * 60 + mins
    return total or None


class RecipeIndex:
    """In-memory keyword index over the local recipe set."""

    def __init__(self, recipes: list[dict[str, Any]]):
        self.recipes = recipes
        self._token_sets: list[set[str]] = []
        self._name_token_sets: list[set[str]] = []
        for r in recipes:
            name = r.get("name", "")
            ing = r.get("ingredients", "")
            desc = r.get("description", "")
            self._name_token_sets.append(set(_tokens(name)))
            self._token_sets.append(set(_tokens(f"{name} {ing} {desc}")))
            # Precompute total time for "fast" filtering.
            prep = _iso_duration_to_minutes(r.get("prepTime")) or 0
            cook = _iso_duration_to_minutes(r.get("cookTime")) or 0
            r["_total_minutes"] = (prep + cook) or None

    def search(self, query: str, limit: int = 5, max_minutes: int | None = None) -> list[dict[str, Any]]:
        q = set(_tokens(query))
        scored: list[tuple[float, int]] = []
        for i, toks in enumerate(self._token_sets):
            overlap = q & toks
            if not overlap:
                continue
            score = float(len(overlap))
            # Weight name matches heavily — a query word in the title is a strong signal.
            score += 2.0 * len(q & self._name_token_sets[i])
            if max_minutes is not None:
                tm = self.recipes[i].get("_total_minutes")
                if tm is not None and tm <= max_minutes:
                    score += 1.5  # nudge fast recipes up when speed was requested
            scored.append((score, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._public(self.recipes[i]) for _, i in scored[:limit]]

    @staticmethod
    def _public(r: dict[str, Any]) -> dict[str, Any]:
        """Trim to the fields the model/UI need."""
        return {
            "name": r.get("name"),
            "ingredients": [
                line.strip() for line in (r.get("ingredients") or "").split("\n") if line.strip()
            ],
            "url": r.get("url"),
            "image": r.get("image"),
            "total_minutes": r.get("_total_minutes"),
            "yield": r.get("recipeYield"),
            "description": (r.get("description") or "").strip(),
        }


def _load_recipes(path) -> list[dict[str, Any]]:
    """Load recipes from either a JSON array or JSON-lines file.

    The dataset has shipped in both shapes, so we accept both: try to parse the
    whole file as one JSON document first, and fall back to line-by-line.
    """
    text = open(path, encoding="utf-8").read()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):  # tolerate a {"recipes": [...]} wrapper
            inner = data.get("recipes")
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
    except json.JSONDecodeError:
        pass
    # Fall back to JSON-lines.
    recipes: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line or line in "[]":
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                recipes.append(obj)
        except json.JSONDecodeError:
            continue
    return recipes


@lru_cache(maxsize=1)
def get_index() -> RecipeIndex:
    recipes = _load_recipes(RECIPES_PATH)
    if not recipes:
        raise RuntimeError(f"No recipes loaded from {RECIPES_PATH}")
    return RecipeIndex(recipes)
