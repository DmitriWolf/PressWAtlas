"""LangGraph agent: model routing -> LLM-driven tool loop, plus memory I/O.

All LLM calls go through LangChain's ChatAnthropic (no Anthropic SDK directly),
per the brief. The graph is a standard ReAct-style loop: the model decides when
to call tools; we never hardcode a tool sequence.

Flow per request (orchestrated from main.py):
  1. load_memory      -> read equipment + prefs from SQLite, set equipment ctx
  2. route            -> cheap classifier picks fast vs smart model
  3. agent <-> tools  -> LLM-driven loop until the model answers
  4. extract_and_save -> pull durable prefs/equipment (never health) into memory
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, TypedDict

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
def classify_turn(user_text: str) -> str:
    """One cheap call -> 'simple' or 'complex'. Defaults to smart model on error."""
    try:
        resp = _llm(config.ROUTER_MODEL).invoke(
            [SystemMessage(content=ROUTER_PROMPT), HumanMessage(content=user_text)]
        )
        verdict = (resp.content or "").strip().lower()
        return config.FAST_MODEL if verdict.startswith("simple") else config.SMART_MODEL
    except Exception:
        return config.SMART_MODEL


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

    model_choice = classify_turn(last_user) if last_user else config.SMART_MODEL
    return messages, model_choice


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
def extract_and_save(user_id: str, transcript: list[dict]) -> None:
    """Pull durable preferences/equipment from the turn and persist them.

    Health conditions are excluded by the extraction prompt. Failures here must
    never break the chat response, so everything is wrapped defensively.
    """
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
