"""FastAPI app: streaming chat endpoint + memory endpoints + static UI.

The whole product runs as one local process: this serves the JSON/SSE API and
the static chat frontend, so `docker compose up` (or uvicorn) is all you need.
"""
from __future__ import annotations

import asyncio
import json

from dotenv import load_dotenv

load_dotenv()  # pull .env before app modules read config

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import config, memory  # noqa: E402
from .agent import (  # noqa: E402
    SUGGESTION_TOOLS,
    build_equipment_nudge,
    build_graph,
    extract_and_save,
    prepare,
)
from .prompts import ALLERGEN_DISCLAIMER, STANDING_NOTICE  # noqa: E402

app = FastAPI(title="PantryPal", version="1.0")


@app.on_event("startup")
def _enforce_retention() -> None:
    """Apply the data-retention policy on boot (Diane's retention requirement)."""
    try:
        memory.purge_stale(config.RETENTION_DAYS)
    except Exception:
        pass

TOOL_LABELS = {
    "search_recipes": "🔎 searching the recipe library…",
    "check_can_make": "🧰 checking your equipment…",
    "web_search": "🌐 searching the web…",
}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    user_id: str = Field(default="anon", description="Stable id for cross-session memory")
    messages: list[Message] = Field(default_factory=list)


def _sse(event: str, **data) -> str:
    return f"data: {json.dumps({'type': event, **data})}\n\n"


def _parse_tool_recipes(content) -> list[dict]:
    """Extract recipe dicts from a search_recipes ToolMessage (content may be
    a list or a JSON string depending on the LangGraph version)."""
    if isinstance(content, list):
        return [r for r in content if isinstance(r, dict)]
    if isinstance(content, str):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
        except (ValueError, json.JSONDecodeError):
            pass
    return []


def _chunk_text(content) -> str:
    """Anthropic chunks may be str or a list of content blocks; extract text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


@app.post("/api/chat")
async def chat(req: ChatRequest):
    history = [m.model_dump() for m in req.messages]
    messages, model_choice = prepare(req.user_id, history)
    graph = build_graph()

    async def stream():
        suggested_food = False
        check_called = False
        search_results: list[dict] = []
        final_text_parts: list[str] = []
        announced: set[str] = set()
        last_msg_id = None  # to separate consecutive agent messages (pre/post tool)
        yield _sse("model", model=model_choice)
        # Always-visible standing disclosure (consistency = compliance).
        yield _sse("notice", text=STANDING_NOTICE)
        try:
            async for mode, payload in graph.astream(
                {"messages": messages, "model_choice": model_choice},
                stream_mode=["updates", "messages"],
            ):
                if mode == "messages":
                    msg, meta = payload
                    if meta.get("langgraph_node") == "agent":
                        text = _chunk_text(msg.content)
                        if text:
                            msg_id = getattr(msg, "id", None)
                            # New agent message after a tool call: separate it from
                            # the prior segment so they don't run together ("…!Here's").
                            if final_text_parts and msg_id != last_msg_id:
                                final_text_parts.append("\n\n")
                                yield _sse("token", text="\n\n")
                            last_msg_id = msg_id
                            final_text_parts.append(text)
                            yield _sse("token", text=text)
                elif mode == "updates":
                    for node, update in payload.items():
                        for m in update.get("messages", []):
                            # tool *calls* the model decided to make
                            for tc in getattr(m, "tool_calls", None) or []:
                                name = tc.get("name")
                                if name in SUGGESTION_TOOLS:
                                    suggested_food = True
                                if name == "check_can_make":
                                    check_called = True
                                if name and name not in announced:
                                    announced.add(name)
                                    yield _sse("tool", label=TOOL_LABELS.get(name, f"using {name}…"))
                            # tool *results* — capture recipes the search returned
                            if getattr(m, "name", None) == "search_recipes":
                                search_results.extend(_parse_tool_recipes(m.content))
        except Exception as e:  # never leave the client hanging
            yield _sse("error", message=f"Something went wrong: {e}")
            return

        answer = "".join(final_text_parts)

        # Polish P1: if a recipe was recommended but the model skipped the equipment
        # check, deterministically append a "do you have the gear?" prompt so the
        # check Priya requires happens even when the model forgets.
        if not check_called and search_results:
            owned = memory.get_memory(req.user_id).get("equipment") or []
            nudge = build_equipment_nudge(search_results, answer, owned, check_called)
            if nudge:
                final_text_parts.append(nudge)
                answer += nudge
                yield _sse("token", text=nudge)

        # Contextual allergen notice when a recipe/ingredient was suggested
        # (reinforces the always-on standing notice above). Diane's non-negotiable.
        if suggested_food:
            yield _sse("disclaimer", text=ALLERGEN_DISCLAIMER)
        yield _sse("done")

        # Persist durable preferences/equipment off the response path.
        transcript = history + ([{"role": "assistant", "content": answer}] if answer else [])
        await asyncio.to_thread(extract_and_save, req.user_id, transcript)

    return StreamingResponse(stream(), media_type="text/event-stream")


class EquipmentBody(BaseModel):
    equipment: list[str] = Field(default_factory=list)


@app.get("/api/equipment/{user_id}")
def get_equipment(user_id: str):
    """Equipment we have stored for a user (drives the onboarding checklist)."""
    return {"equipment": memory.get_memory(user_id).get("equipment") or []}


@app.put("/api/equipment/{user_id}")
def put_equipment(user_id: str, body: EquipmentBody):
    """Replace the user's equipment list (from the onboarding/edit checklist)."""
    mem = memory.set_equipment(user_id, body.equipment)
    return {"equipment": mem["equipment"]}


@app.get("/api/memory/{user_id}")
def get_memory(user_id: str):
    return memory.get_memory(user_id)


@app.delete("/api/memory/{user_id}")
def delete_memory(user_id: str):
    """Right-to-delete: wipe everything stored for a user."""
    memory.clear_user(user_id)
    return {"ok": True, "user_id": user_id}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "anthropic_key": bool(config.ANTHROPIC_API_KEY),
        "tavily_key": bool(config.TAVILY_API_KEY),
        "fast_model": config.FAST_MODEL,
        "smart_model": config.SMART_MODEL,
    }


# --- Static chat UI (mounted last so /api/* wins) --------------------------
if config.FRONTEND_DIR.exists():
    @app.get("/")
    def index():
        return FileResponse(config.FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR), name="static")
