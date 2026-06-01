"""Central configuration, loaded from environment.

Everything runs locally; the only outbound calls are to Anthropic (LLM) and
Tavily (the required external web-search tool).
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Paths -----------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
# Recipes ship with the repo; allow override so Docker can point at /app/assets.
RECIPES_PATH = Path(os.getenv("RECIPES_PATH", REPO_ROOT / "assets" / "recipes.json"))
# Local SQLite store for per-user memory (equipment + food preferences).
DB_PATH = Path(os.getenv("PANTRYPAL_DB", BACKEND_DIR / "pantrypal.db"))
# Static chat UI served by FastAPI so the whole app is one local container.
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", REPO_ROOT / "frontend"))

# --- Keys ------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- Model routing ---------------------------------------------------------
# Cost-aware routing (Priya): cheap+fast model for simple turns, stronger model
# for recipe reasoning / tool-heavy turns. Quality on hard turns is not capped
# (Marcus). Both are overridable via env so the team can tune without code.
FAST_MODEL = os.getenv("PANTRYPAL_FAST_MODEL", "claude-haiku-4-5")
SMART_MODEL = os.getenv("PANTRYPAL_SMART_MODEL", "claude-sonnet-4-6")
# Router classifier is the cheapest model; one tiny call per turn.
ROUTER_MODEL = os.getenv("PANTRYPAL_ROUTER_MODEL", FAST_MODEL)

MAX_TOKENS = int(os.getenv("PANTRYPAL_MAX_TOKENS", "1024"))
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "3"))
RECIPE_SEARCH_LIMIT = int(os.getenv("RECIPE_SEARCH_LIMIT", "5"))


def require_anthropic_key() -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ANTHROPIC_API_KEY
