# Polish & Feature Backlog

Non-legal improvements surfaced while auditing the build against the briefs.
These are **not implemented** — this is a prioritized plan. (Legal-compliance
changes were implemented separately; see [legal_requirement_updates.md](legal_requirement_updates.md).)

Priority key: **P1** = stated requirement not fully met · **P2** = meaningful
quality/cost win · **P3** = nice-to-have / future.

---

## P1 — Enforce the equipment check (Priya, non-negotiable) — ✅ IMPLEMENTED

**Brief:** Priya — *"It **has to** check whether the user can actually make what it
suggests."* `check_can_make` is model-driven: the system prompt says "ALWAYS call
it," but nothing guaranteed it, so a robustness test could find the turn where the
model recommends a recipe and skips the check.

**Implemented (option (b), keyword-heuristic variant):**
- After the agent finishes, the stream detects whether a searched recipe was
  actually recommended (token-overlap match of a `search_recipes` result name in
  the final answer) **without** a `check_can_make` call.
- If so, it deterministically appends a "Quick gear check" prompt:
  `infer_equipment()` (in `recipes.py`) guesses the likely gear from the recipe's
  name/description/ingredients via keywords; `unmet_equipment()` filters it against
  the user's stored kit so we only ask about gear we're unsure of; if nothing is
  inferable it falls back to a generic ask. Framed as a question, never an
  assertion, and it never blocks the streamed answer.
- Guards: skipped entirely when `check_can_make` ran (happy path) or when the model
  already asked about gear itself (`_ALREADY_ASKED`), so it never double-asks.

**Files:** `recipes.py` (`infer_equipment`, `unmet_equipment`), `agent.py`
(`build_equipment_nudge`, `_named_recipe`), `main.py` (capture search results +
`check_called`, append nudge before the disclaimer).

**Verified:** unit-tested all branches (shortened-name match, owned/unowned/unknown
equipment, no false positives) and exercised against live search results. In live
runs the model almost always calls the check or asks itself, so the backstop stays
silent — exactly the intended safety-net behavior.

> Not done (deferred): the stronger *structural* guarantee (a graph topology where a
> recommendation must pass through a `check_can_make` node). The post-step backstop
> covers the requirement at much lower cost/latency.

---

## P2 — Cut per-turn cost & latency (Priya: <2s + unit economics)

**Brief:** Priya wants <2s and low per-query cost; Marcus accepts slower for better.
Today **every turn makes 3 LLM calls**: a router classifier (before the answer), the
answer, and a memory extractor (after). The router sits in front of the response on
*every* turn, and the extractor runs even on "thanks."

**Proposed approach:**
- **Gate the extractor:** skip it unless the user's message plausibly contains a
  durable preference/equipment mention (cheap keyword/heuristic pre-check, or only
  run every N turns). Removes a call from most turns.
- **Heuristic-first routing:** classify obvious cases (very short message, greeting,
  no question mark) with a zero-cost heuristic and only fall back to the Haiku
  classifier when ambiguous. Removes the pre-answer call from most simple turns.
- **Measure:** add per-turn token/cost logging so the economics are observable
  (supports Priya's "keep an eye on per-query cost").

**Effort:** ~S–M, localized to `agent.py`/`main.py`.
**Risk:** heuristics can mis-route; keep the LLM fallback for ambiguity.

---

## P2 — Suppress "AI tells" in the stream (Marcus) — ✅ IMPLEMENTED

**Brief:** Marcus — *"no weird AI tells."* The stream surfaced the model's pre-tool
preamble ("Let me search for something good!") before the real answer.

**Implemented (source-level, not buffering):** rather than buffer/suppress at the
stream layer — which would have killed live token streaming for the final answer
(the one constraint this item flagged: *"must ensure the final answer still streams
incrementally"*) — a firm system-prompt rule stops the model from generating the
narration at all: *"Never narrate your tool use… your first words should be the
actual answer."* The live "🔎 searching…" `tool` status events already provide
progress feedback, so the narration was pure filler.

**Why not buffering:** preamble text and the tool call live in the *same* agent
message, and the text streams before the tool call is known — so suppressing it at
the stream layer requires buffering the whole message, which also defers the final
answer (no incremental streaming). The prompt approach removes the preamble *and*
keeps the answer streaming token-by-token. The earlier segment-separator fix in
`main.py` remains as a safety net for any residual multi-segment output.

**Files:** `backend/app/prompts.py` (SYSTEM_PROMPT tools section).

**Verified:** across recipe-search, hosting, and web-search (substitution) turns,
answers now open directly with content (no "Let me…" preamble) and still arrive as
multiple streamed token events (7–12 per turn) — streaming preserved.

**Effort:** ~S. **Risk:** low; relies on instruction-following (highly reliable for
this formatting rule), with the separator fix as backup.

---

## P3 — Favorites / saved recipes (Jordan: "every single interview")

**Brief:** the single most-requested feature in CX interviews; cut from v1 for time.

**Proposed approach:** a `favorites` list per user in the existing SQLite memory
store, a `save_recipe`/`list_favorites` tool or REST endpoints, and a UI affordance
(a ★ on recipe suggestions + a favorites view). The memory layer is already the
natural home.

**Effort:** ~M (backend + UI). **Risk:** low.

---

## P3 — Smarter recipe retrieval (Priya features 2 & 3)

**Brief:** "suggest recipes based on what the user wants" and "what can I make with
what I have." Today retrieval is in-process keyword scoring — it misses semantic
queries ("comfort food," "something cozy") and doesn't scale yield ("dinner for
four").

**Proposed approach:**
- **Hybrid search:** add embeddings (local model or a vector store) and blend with
  the existing keyword score for semantic recall.
- **Structured filters:** parse intent for diet/cuisine/time/servings and filter on
  recipe fields (`recipeYield`, parsed times). Handle "for four" by surfacing yield
  and offering to scale ingredients.
- **Ingredient-aware ranking** for "what can I make with X": score by ingredient
  overlap and flag the few missing items.

**Effort:** ~L (embeddings/infra). **Risk:** adds a dependency; keep it local to
preserve the "runs locally" guarantee.

---

## P3 — Structured equipment onboarding (Jordan: #1 churn driver) — ✅ IMPLEMENTED

**Brief:** cookware mismatch is the top churn cause. Equipment used to be learned
only when incidentally mentioned, so `check_can_make` often had no ground truth on
turn one.

**Implemented:** a first-run checklist modal ("What's in your kitchen?") of ~26
common items (oven, stovetop, air fryer, Instant Pot, sous vide, hot plate…) as
toggle chips, plus a free-text add for anything unusual. It auto-opens on first
visit when no equipment is stored, and a "🍳 My Kitchen" button in the header
reopens it to edit anytime (pre-checked from stored state). Saving seeds the
equipment list, so `check_can_make` and the P1 backstop have real data immediately.

- **Backend:** `GET/PUT /api/equipment/{user_id}` and `memory.set_equipment()`,
  which replaces the equipment list **without** touching food preferences (verified:
  likes/avoidances survive an equipment update).
- **Frontend:** modal + chips in `index.html`/`styles.css`/`app.js`; first-run
  detection via a stored equipment check + `localStorage` flag; "Reset memory" also
  re-triggers onboarding.

**Verified:** endpoints round-trip; onboarded equipment is immediately visible to
the agent (tested: stored a blender → "you've got a blender, you're good to go").

**Effort:** ~S–M (UI + existing memory store). **Risk:** low.

---

## P3 — Output-side compliance classifier (hardening)

A second, deterministic layer behind the prompt rules: a cheap check on the final
answer that flags medical/food-safety leakage before it reaches the user. Pairs
with the legal work already done; raises robustness against adversarial extraction.
**Effort:** ~M (adds a gated call). **Risk:** latency/cost on flagged turns.

---

## Suggested order

1. ~~**P1 equipment-check enforcement**~~ — ✅ done (closed the stated-requirement gap).
2. ~~**P2 AI-tells**~~ — ✅ done (source-level suppression, streaming preserved).
3. ~~**P3 equipment onboarding**~~ — ✅ done (seeds the equipment check on turn one).
4. **P2 cost/latency** — directly serves Priya's economics ask, low effort. (remaining)
5. **P3** favorites → retrieval → compliance classifier, as time allows. (remaining)
