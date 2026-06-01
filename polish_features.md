# Polish & Feature Backlog

Non-legal improvements surfaced while auditing the build against the briefs.
These are **not implemented** — this is a prioritized plan. (Legal-compliance
changes were implemented separately; see [legal_requirement_updates.md](legal_requirement_updates.md).)

Priority key: **P1** = stated requirement not fully met · **P2** = meaningful
quality/cost win · **P3** = nice-to-have / future.

---

## P1 — Enforce the equipment check (Priya, non-negotiable)

**Brief:** Priya — *"It **has to** check whether the user can actually make what it
suggests."* Today `check_can_make` is model-driven: the system prompt says "ALWAYS
call it," but nothing guarantees it. A robustness test will find the turn where the
model recommends a recipe and skips the check.

**Proposed approach:**
- After the agent finishes, detect whether a concrete recipe was recommended (a
  `search_recipes` result name appears in the final answer) **without** a
  corresponding `check_can_make` call.
- If so, either (a) re-enter the graph once to force the equipment check, or
  (b) append a deterministic "Do you have [inferred gear]? Here's the swap if not"
  nudge. Option (b) is cheaper and never blocks the answer.
- Alternatively, model the loop so a recipe recommendation *must* pass through a
  `check_can_make` node before it can reach the user (structural guarantee).

**Effort:** ~M. Touches `agent.py` (graph topology or post-step) + `main.py`.
**Risk:** option (a) adds latency on the affected turns; option (b) is safe.

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

## P2 — Suppress "AI tells" in the stream (Marcus)

**Brief:** Marcus — *"no weird AI tells."* The stream sometimes surfaces the
model's pre-tool preamble ("Let me search for something good!") before the real
answer.

**Proposed approach:** only stream tokens from the **final** agent turn (the one
with no tool calls), buffering/suppressing text emitted on intermediate
tool-calling turns. Keep the separate `tool` status events for "searching…" UX so
the user still sees progress.

**Effort:** ~S, in the `main.py` streaming loop.
**Risk:** low; must ensure the final answer still streams incrementally.

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

## P3 — Structured equipment onboarding (Jordan: #1 churn driver)

**Brief:** cookware mismatch is the top churn cause. Today equipment is learned only
when incidentally mentioned, so `check_can_make` often has no ground truth.

**Proposed approach:** a lightweight first-run checklist ("tap what you've got:
oven, stovetop, microwave, air fryer, blender…") that seeds the equipment list,
editable any time. Gives the equipment check real data from turn one.

**Effort:** ~S–M (UI + existing memory store). **Risk:** low.

---

## P3 — Output-side compliance classifier (hardening)

A second, deterministic layer behind the prompt rules: a cheap check on the final
answer that flags medical/food-safety leakage before it reaches the user. Pairs
with the legal work already done; raises robustness against adversarial extraction.
**Effort:** ~M (adds a gated call). **Risk:** latency/cost on flagged turns.

---

## Suggested order

1. **P1 equipment-check enforcement** — closes the remaining stated-requirement gap.
2. **P2 cost/latency** — directly serves Priya's economics ask, low effort.
3. **P2 AI-tells** — quick, visible polish.
4. **P3** favorites → onboarding → retrieval → compliance classifier, as time allows.
