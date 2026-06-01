"""LangChain tools the agent can choose to call.

Three tools:
- search_recipes : keyword search over the local recipe library
- check_can_make : deterministic equipment check (LLM infers what's needed,
                   tool checks it against what the user actually owns)
- web_search     : Tavily (the required external tool)

Per-user equipment is injected via a contextvar so the model never has to (and
never can) fabricate the user's kit — it's read from stored memory per request.
"""
from __future__ import annotations

import contextvars
from typing import Any

from langchain_core.tools import tool

from . import config
from .recipes import get_index

# Set per request by the agent before invoking the graph.
current_equipment: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "current_equipment", default=[]
)


@tool
def search_recipes(query: str, max_minutes: int | None = None) -> list[dict[str, Any]]:
    """Search PantryPal's recipe library for recipes matching a query.

    Use this whenever the user wants an actual recipe or a "what can I make with X"
    suggestion. `query` should capture the dish, cuisine, or key ingredients
    (e.g. "spicy chicken", "vegetarian pasta", "chocolate dessert"). Pass
    `max_minutes` when the user wants something fast (e.g. 30). Returns recipe
    names, ingredients, total time, and source URL.
    """
    return get_index().search(
        query, limit=config.RECIPE_SEARCH_LIMIT, max_minutes=max_minutes
    )


@tool
def check_can_make(recipe_name: str, required_equipment: list[str]) -> dict[str, Any]:
    """Check whether the user can actually make a recipe with the equipment they own.

    ALWAYS call this before firmly recommending a recipe to cook. You infer what
    equipment the recipe needs and pass it as `required_equipment` (e.g.
    ["oven", "blender", "large pot"]). The tool compares that against the user's
    stored equipment and tells you what they have and what they're missing.

    If `missing` is non-empty, do NOT just refuse — suggest a workaround or a
    different recipe they can make. If the user's equipment is unknown, ask them
    what they have rather than guessing.
    """
    owned = current_equipment.get()
    if not owned:
        return {
            "recipe": recipe_name,
            "equipment_known": False,
            "note": "We don't know what equipment this user owns yet. Ask them what "
            "they have before assuming, instead of guessing.",
        }
    owned_lower = {e.lower() for e in owned}

    def _has(item: str) -> bool:
        il = item.lower()
        # loose match: "large pot" satisfied by "pot", "stand mixer" by "mixer"
        return any(il in o or o in il for o in owned_lower)

    missing = [item for item in required_equipment if not _has(item)]
    have = [item for item in required_equipment if _has(item)]
    return {
        "recipe": recipe_name,
        "equipment_known": True,
        "owned": owned,
        "needs": required_equipment,
        "have": have,
        "missing": missing,
        "can_make": len(missing) == 0,
        "note": "All equipment available."
        if not missing
        else f"User is missing: {', '.join(missing)}. Offer a workaround or an alternative recipe.",
    }


def _build_web_search():
    """Build the Tavily web-search tool, wrapped so a missing key degrades gracefully."""
    if not config.TAVILY_API_KEY:
        @tool
        def web_search(query: str) -> str:
            """Search the web for cooking knowledge, substitutions, or current info."""
            return (
                "Web search is unavailable (TAVILY_API_KEY not configured). "
                "Answer from your own cooking knowledge instead, and say you couldn't look it up."
            )
        return web_search

    try:
        from langchain_tavily import TavilySearch

        _tavily = TavilySearch(max_results=config.TAVILY_MAX_RESULTS, api_key=config.TAVILY_API_KEY)
    except Exception:  # pragma: no cover - fall back to community package
        from langchain_community.tools.tavily_search import TavilySearchResults

        _tavily = TavilySearchResults(max_results=config.TAVILY_MAX_RESULTS)

    @tool
    def web_search(query: str) -> Any:
        """Search the web for general cooking knowledge, ingredient substitutions,
        techniques, food facts, or current information not in the recipe library.
        Use for "how do I", "what can I substitute for", and similar questions."""
        try:
            return _tavily.invoke({"query": query})
        except Exception as e:
            return f"Web search failed ({e}). Answer from your own knowledge and note you couldn't look it up."

    return web_search


web_search = _build_web_search()

ALL_TOOLS = [search_recipes, check_can_make, web_search]
