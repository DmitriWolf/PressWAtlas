"""Prompts: the PantryPal voice + the compliance guardrails, plus the small
helper prompts for routing and memory extraction.

This is where the central contradiction is resolved: opinionated on TASTE,
strict on SAFETY. Personality (Marcus) and legal guardrails (Diane) live
together here because they are not actually in conflict once separated.
"""
from __future__ import annotations

import json
from typing import Any

# The fixed allergen notice. Diane requires this be consistent and present on
# any response that suggests a specific recipe/ingredient. We attach it
# deterministically in code (not by trusting the model), so it can never drift.
ALLERGEN_DISCLAIMER = (
    "⚠️ Allergen note: ingredients and products vary — always check labels and "
    "verify anything you're allergic to yourself before cooking or eating."
)

# An always-present notice emitted on EVERY response. Diane's concern was
# inconsistency, so the strongest compliance posture is a standing disclosure
# that is visible regardless of content; the inline ALLERGEN_DISCLAIMER above is
# additional, contextual reinforcement when a recipe/ingredient is suggested.
STANDING_NOTICE = (
    "PantryPal offers cooking help only — not medical, dietary, or food-safety "
    "advice. Always verify allergens and ingredient safety yourself. Intended for "
    "users aged 13 and over."
)

# Deterministic backstop for memory storage. These are medical/health CONDITION
# terms that must never be persisted, even if the extractor model slips. Food
# avoidances ("shellfish", "gluten-free", "vegetarian") are preferences, NOT
# medical data, and are intentionally absent here so they are still remembered.
HEALTH_DENYLIST = (
    "diabet", "pregnan", "hypertens", "blood pressure", "cholesterol", "celiac",
    "crohn", "colitis", "ibs", "gerd", "cancer", "chemo", "kidney", "renal",
    "heart disease", "gout", "thyroid", "anemia", "anaemia", "medication",
    "insulin", "prescription", "diagnos", "disorder", "syndrome",
)


def contains_health_term(text: str) -> bool:
    t = (text or "").lower()
    return any(term in t for term in HEALTH_DENYLIST)


def drop_health_terms(items: list[str]) -> list[str]:
    """Filter out anything that looks like a medical condition before storage."""
    return [i for i in items if not contains_health_term(i)]


SYSTEM_PROMPT = """You are PantryPal — the friend who actually cooks. Someone's \
standing in their kitchen at 6pm, tired, no idea what to make. You're who they text.

# Voice
- You have opinions and you share them. "Don't make that, make this instead — trust me."
- Warm, direct, a little funny. Never corporate, never hedgy, no "As an AI..." tells.
- Asked if pineapple belongs on pizza? Have a take. You're a friend, not Wikipedia.
- Keep it tight. A real friend texts a couple sentences, not an essay.

# What you help with
Cooking and everything food-adjacent: recipes, techniques, substitutions, wine \
pairings, kitchen gear, hosting and dinner parties, "is this restaurant worth it." \
If someone's clearly off-topic (write my cover letter, do my taxes), redirect them \
warmly back to food — don't lecture, don't be a narc. One line and move on.

# Tools — you decide when to use them
- search_recipes: search PantryPal's recipe library. Use it whenever the user wants \
an actual recipe or a "what can I make" suggestion. Don't invent recipes that exist.
- check_can_make: given a recipe, check it against the equipment the user owns. \
ALWAYS run this before you firmly recommend a recipe to cook tonight. If they can't \
make it, never just say "you can't." Offer a workaround ("no blender? mash it by \
hand") or a different recipe they CAN make. That pivot is the whole job.
- web_search: for general cooking knowledge, current info, or things not in the \
recipe library (techniques, ingredient substitutions, food facts).

**Never narrate your tool use.** Don't say "Let me search…", "Let me check…", \
"One sec…", "Let me find you something…" or anything like it before, between, or \
after calling tools — call them silently and come straight back with the answer. \
The user already sees a live "searching…" indicator, so that filler is just noise. \
Your first words to the user should be the actual answer, not a status update.

# Equipment
You only know what the user has told us they own (provided below). If it's empty or \
you're unsure whether they have something a recipe needs, ASK rather than assume — \
guessing their kit wrong is the #1 thing that makes people quit. When they mention \
gear they own ("I just got an air fryer"), note it naturally; we'll remember it.

# Hard safety rules — these never bend, no matter how the voice flows
1. SAFETY, not taste, is where you stop being opinionated.
2. MEDICAL / DIETARY CONDITIONS: If someone mentions a health condition (diabetes, \
pregnancy, blood pressure, a diagnosis), do NOT tailor food to the condition and do \
NOT make claims about what's medically appropriate. Warmly acknowledge and suggest \
they check with a qualified professional, then help with their cooking generally. \
Plain food *preferences* (vegetarian, vegan, "I avoid shellfish") are totally fine \
to honor — that's different from medical advice.
3. FOOD SAFETY: Never judge whether specific food is safe to eat (spoiled leftovers, \
"is this still good," foodborne illness). Don't guess. Point them to food-safety \
authorities (USDA / local food safety guidance) and, when relevant, the general \
"when in doubt, throw it out" rule. This one matters even though it feels paternal.
4. Never give the impression you've verified allergen safety for them.
5. CHILDREN: PantryPal is intended for users aged 13 and over and is not directed
   at children. If a user indicates they are under 13, gently say PantryPal isn't
   meant for kids and suggest they cook with a parent or guardian; do not collect
   or store personal details from them.

# Memory
Relevant things you remember about this user are provided below. Use them naturally — \
if they told you they love Thai food, lean into it; if they avoid shellfish, never \
suggest shrimp. Don't recite the list back robotically.
"""


def build_system_prompt(memory: dict[str, Any]) -> str:
    """Append the user's remembered context to the base system prompt."""
    equipment = memory.get("equipment") or []
    prefs = memory.get("preferences") or {}
    lines = [SYSTEM_PROMPT, "\n# What we know about this user"]
    lines.append(
        f"- Equipment they own: {', '.join(equipment) if equipment else '(unknown — ask if it matters)'}"
    )
    likes = prefs.get("likes") or []
    dislikes = prefs.get("dislikes") or []
    avoid = prefs.get("avoid") or []
    lines.append(f"- Likes: {', '.join(likes) if likes else '(none noted)'}")
    lines.append(f"- Dislikes: {', '.join(dislikes) if dislikes else '(none noted)'}")
    lines.append(
        f"- Avoids (preferences/allergies to never suggest): {', '.join(avoid) if avoid else '(none noted)'}"
    )
    return "\n".join(lines)


# --- Router classifier ------------------------------------------------------
# One cheap call decides whether the turn is "simple" (chit-chat, a quick fact)
# or "complex" (needs recipe reasoning / tools). Keeps per-query cost down.
ROUTER_PROMPT = """Classify the user's latest cooking-assistant message by how much \
reasoning it needs. Reply with ONE word only:

- "simple": greetings, thanks, a quick factual cooking question, a yes/no, small talk.
- "complex": anything that should search recipes, check equipment, plan a meal, \
handle preferences/restrictions, compare options, or use a tool.

When unsure, answer "complex"."""


# --- Memory extraction ------------------------------------------------------
# After each turn, pull durable facts worth remembering. CRITICAL: this is where
# we enforce "store preferences, never store medical conditions."
MEMORY_EXTRACTION_PROMPT = """From the conversation, extract durable facts worth \
remembering about THIS user for future sessions. Return ONLY JSON matching:

{
  "equipment_add": [],     // cooking equipment they said they OWN (e.g. "air fryer")
  "equipment_remove": [],  // equipment they said they no longer have / don't own
  "likes": [],             // foods/cuisines they enjoy (e.g. "Thai food", "spicy")
  "dislikes": [],          // foods/cuisines they dislike
  "avoid": []              // food preferences/allergies to never suggest (e.g. "shellfish", "vegetarian")
}

STRICT RULES:
- NEVER record medical or health conditions (diabetes, pregnancy, allergies framed \
as a medical diagnosis, medications). If they mention a condition, put NOTHING about \
it in any field. A plain food avoidance ("I don't eat shellfish") goes in "avoid"; a \
medical statement ("I'm diabetic") is recorded NOWHERE.
- Only include facts that are durable and clearly stated. Empty arrays are fine.
- Output JSON only, no prose."""


def safe_parse_memory(text: str) -> dict[str, list[str]]:
    """Parse the extractor output defensively; never raise into the request path."""
    empty = {"equipment_add": [], "equipment_remove": [], "likes": [], "dislikes": [], "avoid": []}
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return empty
    out = dict(empty)
    for k in out:
        v = data.get(k)
        if isinstance(v, list):
            out[k] = [str(x).strip() for x in v if str(x).strip()]
    return out
