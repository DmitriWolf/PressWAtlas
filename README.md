# PantryPal 🍳

> The friend who actually cooks. A conversational AI cooking assistant for that 6pm "what do I even make" moment.

PantryPal answers cooking questions, suggests recipes from a 1,000+ recipe library, figures out what you can make with the gear you actually own, and remembers your tastes across sessions — with personality, and with safety guardrails baked in.

**Stack:** FastAPI · LangGraph · LangChain · Anthropic (Claude) · Tavily (web search) · vanilla-JS chat UI · Docker.

See [SCOPING.md](SCOPING.md) for what we committed to and why, and [TRADEOFFS.md](TRADEOFFS.md) for what got cut.

---

https://github.com/user-attachments/assets/157cccce-5037-41d6-b70b-74e7aff28701

---

## Quick start (Docker — recommended)

```bash
# 1. Add your keys
cp .env.example .env        # then paste your ANTHROPIC_API_KEY and TAVILY_API_KEY

# 2. Build + run
docker compose up --build

# 3. Open the chat
open http://localhost:8000
```

That's it — one container serves both the API and the chat UI. Per-user memory persists in a Docker volume (`pantrypal_data`).

## Quick start (local Python, no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# keys are read from ../.env automatically
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

Requires Python 3.12+.

---

## Configuration

All config is environment-driven (see [.env.example](.env.example)):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | — | LLM calls (via LangChain) |
| `TAVILY_API_KEY` | for web search | — | external web-search tool; app still runs without it |
| `PANTRYPAL_FAST_MODEL` | | `claude-haiku-4-5` | cheap/fast model for simple turns |
| `PANTRYPAL_SMART_MODEL` | | `claude-sonnet-4-6` | stronger model for recipe reasoning |
| `PANTRYPAL_MAX_TOKENS` | | `1024` | max response tokens |

---

## How it works

```
user ─▶ /api/chat (SSE stream)
          │
          ├─ load_memory   read equipment + food prefs from SQLite
          ├─ route         a cheap classifier picks fast vs smart model  ← cost control
          ├─ agent ⇄ tools LLM decides which tools to call (no hardcoded sequence)
          │                 • search_recipes  (local 1,042-recipe library)
          │                 • check_can_make  (your equipment vs. what a recipe needs)
          │                 • web_search      (Tavily — the external tool)
          └─ extract_memory pull durable food prefs (never health data) → SQLite
```

- **All LLM calls go through LangChain** (`ChatAnthropic`) — no Anthropic SDK used directly.
- **Tool use is model-driven** — the LangGraph ReAct loop lets Claude decide when to search, when to check equipment, and when to hit the web.
- **Equipment-aware:** `check_can_make` compares a recipe's needs against the user's *stored* kit (not a guessed default list). If something's missing, the assistant is prompted to offer a workaround or an alternative, never a flat "you can't."
- **Compliance is structural, not vibes:** the allergen disclaimer is attached **deterministically in code** whenever a recipe/ingredient is suggested; medical-condition and food-safety questions are deflected by hard rules in the system prompt.

---

## API

### `POST /api/chat` — streaming chat (Server-Sent Events)

```bash
curl -N http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "demo",
    "messages": [{"role": "user", "content": "something spicy and fast for dinner"}]
  }'
```

Streams `data:` events of type `model`, `notice`, `tool`, `token`, `disclaimer`, `done`, `error`.
Send the full `messages` array each turn to preserve conversation context; cross-session
preferences are recalled automatically from `user_id`.

### `GET /api/equipment/{user_id}` — list a user's stored kitchen equipment
### `PUT /api/equipment/{user_id}` — set equipment (used by the onboarding checklist); body `{"equipment": ["Oven", "Air fryer"]}`
### `GET /api/memory/{user_id}` — inspect stored memory
### `DELETE /api/memory/{user_id}` — right-to-delete (wipe everything for a user)
### `GET /api/health` — status + which keys/models are configured

---

## Try these (they exercise the interesting paths)

| Ask | What it shows |
|---|---|
| `something spicy and fast for dinner` | recipe search + speed filter + opinionated pick |
| `I only have a hot plate and one pan. What can I make?` | equipment-aware filtering + workaround pivot |
| `what can I substitute for buttermilk?` | Tavily web search |
| `I'm vegetarian and I love Thai food` then later `what's for dinner?` | cross-session memory |
| `I left chicken out overnight, is it safe?` | food-safety deferral (won't judge) |
| `I'm diabetic, what should I eat?` | acknowledges generically, no medical advice, not stored |
| `write my cover letter` | warm off-topic redirect |

---

## Project layout

```
backend/
  app/
    main.py      FastAPI app: /api/chat (SSE) + memory endpoints + static UI
    agent.py     LangGraph graph, model routing, memory extraction
    tools.py     search_recipes, check_can_make, web_search (Tavily)
    recipes.py   loads recipes.json (JSON or JSON-lines) + keyword search
    memory.py    SQLite store for equipment + food preferences
    prompts.py   PantryPal voice + compliance rules + helper prompts
    config.py    env-driven configuration
  requirements.txt
  Dockerfile
frontend/        index.html + styles.css + app.js (vanilla, streaming)
assets/recipes.json   the recipe library (ships with the repo)
docker-compose.yml
```
