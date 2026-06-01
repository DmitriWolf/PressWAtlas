"""LangGraph agent: model routing -> LLM-driven tool loop, plus memory I/O.

All LLM calls go through LangChain's ChatAnthropic (no Anthropic SDK directly),
per the brief. The graph is a standard ReAct-style loop: the model decides when
to call tools; we never hardcode a tool sequence.

Flow per request (orchestrated from main.py):
  1. load_memory      -> read equipment + prefs from SQLite, set equipment ctx
  2. route            -> heuristic picks fast/smart model; classifier only if ambiguous
  3. agent <-> tools  -> LLM-driven loop until the model answers
  4. extract_and_save -> pull durable prefs/equipment (never health), gated by signal
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Annotated, TypedDict

logger = logging.getLogger("pantrypal")

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from . import config, memory
from .prompts import (
    MEMORY_EXTRACTION_PROMPT,
    ROUTER_PROMPT,
    build_system_prompt,
    drop_health_terms,
    safe_parse_memory,
)
from .recipes import infer_equipment, unmet_equipment
from .tools import ALL_TOOLS, current_equipment

RECIPE_TOOLS = {"search_recipes", "check_can_make"}
# Diane requires the allergen notice on any response suggesting a recipe OR an
# ingredient. Substitution/"what can I use instead" answers go through web_search,
# so it must trigger the notice too — not just the recipe tools.
SUGGESTION_TOOLS = {"search_recipes", "check_can_make", "web_search"}


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    model_choice: str


@lru_cache(maxsize=8)
def _llm(model: str, with_tools: bool = False) -> ChatAnthropic:
    llm = ChatAnthropic(
        model=model,
        max_tokens=config.MAX_TOKENS,
        temperature=0.7,  # a friend has personality, not zero variance
        api_key=config.require_anthropic_key(),
    )
    return llm.bind_tools(ALL_TOOLS) if with_tools else llm


# --- Graph nodes -----------------------------------------------------------
def _agent_node(state: State) -> dict:
    llm = _llm(state["model_choice"], with_tools=True)
    return {"messages": [llm.invoke(state["messages"])]}


def _should_continue(state: State) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(State)
    g.add_node("agent", _agent_node)
    g.add_node("tools", ToolNode(ALL_TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


# --- Routing ---------------------------------------------------------------
# Cost/latency optimization (polish P2): a zero-cost heuristic resolves the
# OBVIOUS cases so we skip the classifier LLM call on most turns. Anything that
# isn't obviously trivial or obviously cooking-related still falls back to the
# classifier — so this can never route a genuinely hard turn to the weak model.

# Trivial turns (greetings / acknowledgements) -> fast model, no classifier call.
_TRIVIAL_RE = re.compile(
    r"^(hi|hey|hello|yo|sup|hiya|thanks( so much| a lot)?|thank you|thx|ty|ok(ay)?|k|"
    r"cool|nice|great|awesome|sure|yes|yep|yeah|yup|no|nope|got it|cheers|"
    r"good (morning|afternoon|evening|night)|how are you|what'?s up|whats up)[\s!.?]*$",
    re.I,
)
# Clear cooking/recipe intent -> smart model, no classifier call. (Erring toward
# the smart model is safe: worst case is slightly higher cost, never worse quality.)
_COMPLEX_RE = re.compile(
    r"\b(recipe|recipes|cook|cooking|make|made|meal|dinner|lunch|breakfast|brunch|snack|"
    r"dish|eat|ingredient|ingredients|substitut|instead of|suggest|recommend|idea|ideas|"
    r"whip up|fast|quick|easy|spicy|sweet|savou?ry|dessert|bake|baking|roast|grill|fry|"
    r"saute|sauté|simmer|boil|vegetarian|vegan|keto|paleo|gluten|dairy|allerg|pair|wine|"
    r"host|hosting|serve|servings|feed|hungry|leftover|marinade|sauce|appetizer|entree|"
    r"for (two|three|four|five|six|\d))\b",
    re.I,
)


def classify_turn(user_text: str) -> str:
    """One cheap LLM call -> 'simple' or 'complex'. Defaults to smart on error."""
    try:
        resp = _llm(config.ROUTER_MODEL).invoke(
            [SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=user_text)]
        )
        verdict = (resp.content or "").strip().lower()
        return config.FAST_MODEL if verdict.startswith("simple") else config.SMART_MODEL
    except Exception:
        return config.SMART_MODEL


def route_model(user_text: str) -> str:
    """Pick the model: heuristic for obvious cases, classifier for the rest.

    Cooking signal is checked BEFORE the trivial-greeting check on purpose: it's the
    quality-preserving branch, so even if `_TRIVIAL_RE` is later broadened to match
    compound messages, anything with a cooking keyword still routes to the smart
    model rather than being short-circuited to fast.
    """
    t = (user_text or "").strip()
    if not t:
        return config.SMART_MODEL
    if _COMPLEX_RE.search(t):
        logger.debug("route: heuristic cooking -> smart (no classifier call)")
        return config.SMART_MODEL
    if _TRIVIAL_RE.match(t):
        logger.debug("route: heuristic trivial -> fast (no classifier call)")
        return config.FAST_MODEL
    logger.debug("route: ambiguous -> classifier")
    return classify_turn(t)


# --- Request preparation ---------------------------------------------------
def prepare(user_id: str, history: list[dict]) -> tuple[list[BaseMessage], str]:
    """Load memory, set equipment context, build the message list + model choice."""
    mem = memory.get_memory(user_id)
    current_equipment.set(mem.get("equipment") or [])

    messages: list[BaseMessage] = [SystemMessage(content=build_system_prompt(mem))]
    last_user = ""
    for m in history:
        role, content = m.get("role"), m.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
            last_user = content
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    model_choice = route_model(last_user) if last_user else config.SMART_MODEL
    return messages, model_choice


_NAME_STOP = {"with", "and", "the", "of", "or", "for", "aka", "style", "easy", "best"}


def _named_recipe(results: list[dict], answer_low: str) -> dict | None:
    """Find which searched recipe the answer actually recommends.

    The model often shortens names ("...Pork Tenderloin" for "...Pork Tenderloin
    with Preserves"), so we match on token overlap rather than exact substring.
    """
    best, best_score = None, 0.0
    for r in results:
        name = (r.get("name") or "")
        toks = {w for w in re.findall(r"[a-z]+", name.lower()) if len(w) > 2 and w not in _NAME_STOP}
        if len(toks) < 2:  # too short to score reliably -> require exact mention
            if name and name.lower() in answer_low:
                return r
            continue
        score = sum(1 for w in toks if w in answer_low) / len(toks)
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= 0.6 else None


def _humanize(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


# Phrases that indicate the model already asked about gear itself — don't double up.
_ALREADY_ASKED = ("do you have", "what do you have", "what are you working with",
                  "got a ", "got an ", "equipment", "what's in your kitchen")


def build_equipment_nudge(
    search_results: list[dict], answer: str, owned: list[str], check_called: bool
) -> str | None:
    """Deterministic backstop (polish P1): if the model recommended a recipe but
    skipped `check_can_make`, append a 'do you have the gear?' prompt so Priya's
    "it HAS to check" holds even when the model forgets. Returns None when no
    nudge is warranted (check ran, no recipe named, or model already asked).
    """
    if check_called or not search_results:
        return None
    low = answer.lower()
    if any(p in low for p in _ALREADY_ASKED):
        return None
    matched = _named_recipe(search_results, low)
    if not matched:
        return None
    name = matched["name"]
    needs = infer_equipment(matched)
    if not needs:  # nothing inferable -> graceful generic ask
        return (
            f"\n\n— **Quick gear check:** before you commit to {name}, do you have the "
            f"equipment it needs? Tell me what's in your kitchen and I'll confirm or suggest a swap."
        )
    unmet = unmet_equipment(needs, owned)
    if owned and not unmet:
        return (
            f"\n\n— **Quick gear check:** {name} usually needs {_humanize(needs)} — "
            f"looks like you're set, but give it a glance before you start."
        )
    gear = unmet or needs
    pronoun = "that" if len(gear) == 1 else "those"
    return (
        f"\n\n— **Quick gear check:** {name} usually needs {_humanize(gear)}. "
        f"Do you have {pronoun}? If not, tell me your setup and I'll find something that fits."
    )


def turn_suggested_food(messages: list[BaseMessage]) -> bool:
    """Deterministic disclaimer trigger: did this turn surface a recipe/ingredient?"""
    for m in messages:
        if isinstance(m, ToolMessage) and getattr(m, "name", None) in SUGGESTION_TOOLS:
            return True
        if isinstance(m, AIMessage) and m.tool_calls:
            if any(tc.get("name") in SUGGESTION_TOOLS for tc in m.tool_calls):
                return True
    return False


# --- Memory extraction (post-turn) -----------------------------------------
# Cost optimization (polish P2): only run the extractor LLM call when the user's
# latest message actually contains a durable-preference signal. The pattern is
# intentionally generous (likes/dislikes, diet, allergies, possession/identity,
# equipment, taste words) so we never silently drop a stated preference; turns
# with no signal at all (greetings, recipe mechanics, acknowledgements) skip it.
_PREF_SIGNAL_RE = re.compile(
    r"\b(i (like|love|hate|prefer|enjoy|avoid|usually|always|never|own|have|got|bought|"
    r"don'?t|do not|can'?t|cannot|am|'?m)|i'?m|my |we (have|own|love|prefer)|"
    r"vegetarian|vegan|pescatarian|pescetarian|keto|paleo|gluten|dairy|lactose|kosher|"
    r"halal|allerg|intoleran|favou?rite|obsessed|not a fan|"
    r"oven|stove|stovetop|microwave|air ?fryer|blender|food processor|mixer|slow cooker|"
    r"crock\s?pot|instant pot|pressure cooker|toaster oven|griddle|skillet|cast iron|wok|"
    r"rice cooker|sous vide|hot plate|saucepan|"
    r"spicy|sweet|savou?ry|mild|bland|salty|sour)\b",
    re.I,
)


def should_extract(transcript: list[dict]) -> bool:
    """True if the latest user message plausibly states something worth remembering."""
    last_user = next(
        (m.get("content", "") for m in reversed(transcript) if m.get("role") == "user"), ""
    )
    return bool(_PREF_SIGNAL_RE.search(last_user or ""))


def extract_and_save(user_id: str, transcript: list[dict]) -> None:
    """Pull durable preferences/equipment from the turn and persist them.

    Health conditions are excluded by the extraction prompt. Failures here must
    never break the chat response, so everything is wrapped defensively.
    """
    if not should_extract(transcript):
        logger.debug("extract: no preference signal -> skipping extractor call")
        return
    try:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in transcript if m.get("content"))
        resp = _llm(config.FAST_MODEL).invoke(
            [SystemMessage(content=MEMORY_EXTRACTION_PROMPT), HumanMessage(content=convo)]
        )
        facts = safe_parse_memory(resp.content or "")
        # Deterministic backstop: strip anything resembling a medical condition
        # before it can be persisted, regardless of what the extractor returned.
        for key in ("equipment_add", "likes", "dislikes", "avoid"):
            facts[key] = drop_health_terms(facts[key])
        if any(facts.values()):
            memory.update_memory(
                user_id,
                equipment_add=facts["equipment_add"],
                equipment_remove=facts["equipment_remove"],
                likes=facts["likes"],
                dislikes=facts["dislikes"],
                avoid=facts["avoid"],
            )
    except Exception:
        pass
