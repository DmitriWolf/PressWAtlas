# PantryPal v1 — Scoping Document

A conversational AI cooking assistant. Backend: FastAPI + LangGraph + LangChain (Anthropic models). Frontend: minimal chat UI. Built to run via Docker. This doc records what we commit to in the 3-hour window, what we defer, and how we resolved the stakeholders' disagreements.

---

## Scope committed

What we will actually build:

1. **LangGraph agent with LLM-driven tool use.** The model decides when to call tools — no hardcoded sequences. Tools:
   - `search_recipes` — semantic/keyword search over the 1,042-recipe local dataset (`assets/recipes.json`).
   - `web_search` — the required external tool, for general cooking questions and gaps the local dataset can't fill (substitutions, techniques).
   - `check_can_make` — given a recipe + the user's stated equipment, judge whether they can make it and, if not, **propose a workaround or a substitute recipe** (Jordan's "you can't do this, but you CAN do this" requirement).
2. **Per-user equipment inventory, user-supplied — not a fixed assumed list.** We ask the user what they have (and let them update it), persist it, and filter/adjust suggestions against it. This directly targets the #1 churn cause.
3. **Lightweight memory across sessions** for *preferences only*: cuisines they like, dislikes, and **stated dietary preferences** ("I'm vegetarian"). Keyed by a user id. This is Marcus's "feels like a relationship" bar, scoped to what Legal allows.
4. **Personality.** A house voice with opinions (Marcus's "the friend who cooks"), implemented in the system prompt — opinionated on taste, never on safety/health.
5. **Compliance layer baked into the response format from day one** (Diane's non-negotiables):
   - Allergen notice attached to **any** response suggesting a specific recipe/ingredient.
   - Health conditions → generic acknowledgment + "talk to a qualified professional," no dietary adaptation, **not stored**.
   - Food-safety / "is this safe to eat" → defer to food-safety authorities, no specific judgment.
   - Off-topic → polite redirect (generous "food-adjacent" interpretation, see Contradictions).
6. **Cost-aware model routing.** Cheap fast model (Haiku) for simple/chitchat turns, stronger model (Sonnet) for recipe reasoning / tool-heavy turns. Keeps per-query cost down (Priya) without capping quality on hard queries (Marcus).
7. **Docker + README + curl examples** so the team can clone and run.

## Scope cut

- **Voice / hands-free cooking mode.** Marcus flagged it as long-term; Jordan echoed it. Real value but a full input/output modality — out of a 3-hour build. We *avoid architectural lock-in* (the agent is transport-agnostic behind the FastAPI endpoint) so voice can be added later without a rewrite. That's the "don't paint ourselves into a corner" ask, satisfied cheaply.
- **PDF / family-cookbook ingestion.** One beta tester; Jordan explicitly said not needed for v1. Ingestion + parsing + storage is its own project.
- **Grocery-list export and meal planning.** Came up repeatedly but Jordan tagged it v2. Defer.
- **Favorites / saved recipes.** Genuinely wanted in every interview, but it needs durable user-owned storage + UI we can't do well in the window. Deferred with a clear note; the memory store we build is the natural home for it later.

## Contradictions resolved

1. **Scope breadth — Priya ("stay in its lane") vs Marcus ("food-adjacent is fair game").** We side with Marcus on breadth but keep Priya's intent (users should know what it's for): **anything food/kitchen/hosting/wine/dining-adjacent is in; clearly off-topic gets a polite redirect, not a lecture.** Priya's list is the floor; Marcus's memo is the direction. We don't make it "a narc."
2. **Latency — Priya (<2s) vs Marcus (quality over speed).** We don't treat 2s as a hard SLA. Routing keeps simple turns fast (~sub-2s), and we let genuinely hard / tool-using turns take longer for a better answer, with a streaming/"thinking" affordance in the UI so waiting feels intentional. Marcus's call wins on the hard tail; Priya's instinct wins on the common case.
3. **Personality vs Legal hedging — Marcus vs Diane.** These are separable axes: **opinionated on taste, strict on safety.** The bot has takes on pineapple-on-pizza; it is non-negotiably careful on allergens, medical, and food safety. The disclaimer is a fixed, consistent element of the response envelope (Diane's "don't retrofit inconsistently"), not a per-turn hedge that muddies the voice.
4. **Memory vs data retention — Marcus vs Diane.** We store **preferences** (cuisine likes, vegetarian/vegan) but **not health-adjacent mentions** (allergies-as-medical, conditions like diabetes/pregnancy). Allergies are handled in-session for safety but not persisted as a health record. This delivers the continuity Marcus wants while staying on the safe side of Diane's "prefer not to store health mentions at all."

## Clarifying questions (for a production build)

1. **Allergen disclaimer wording & placement** — Diane said "we can workshop the language." We need the approved copy and whether it can be a persistent UI element vs. inline per message.
2. **COPPA / under-13 stance** — Diane asked directly and it's unanswered. It affects auth, data collection, and onboarding. We need a yes/no on whether under-13 users are in scope before any real launch.
3. **Memory identity & deletion** — How are users identified (account? device?), and what's the deletion/retention SLA? Drives the storage design Diane wants before launch.

## Assumptions made

1. **Equipment is collected from the user, stored per-user, and editable** — since no stakeholder owns the "right" list and the data confirms there isn't one. We seed nothing; we ask.
2. **The recipe dataset has no equipment or allergen metadata** (confirmed by inspection), so the agent **infers required equipment from a recipe's ingredients/method at reasoning time** rather than relying on a structured field. Acceptable for v1; flagged as a risk.
3. **Single shared "PantryPal voice"** for v1 — no per-user personality tuning.
4. **Web search via a single provider** is sufficient for the external-tool requirement; results are summarized, not shown raw.

## Risks accepted

1. **Equipment inference is LLM-judgment, not ground truth.** Without an equipment field, the bot may occasionally misjudge what a recipe needs. Mitigation: conservative prompting + the workaround/substitute path so a wrong call degrades gracefully instead of dead-ending. Accepting it because building a structured equipment ontology over 1,042 recipes doesn't fit the window.
2. **Compliance is prompt-and-envelope enforced, not a hard guardrail model.** A determined adversarial user might extract a borderline medical/safety answer. Mitigation: layered system-prompt rules + a fixed disclaimer envelope. A production build would add an output-side classifier. Accepted for v1.
3. **Latency on hard, tool-using turns may exceed Priya's 2s.** We're deliberately trading this for answer quality per Marcus, mitigated by routing + streaming UX. Accepted as a documented product decision, not an oversight.
4. **Memory persistence is minimal (local/file or lightweight store), not production-grade.** Good enough to demonstrate continuity; not the privacy-reviewed system Diane will require. Accepted and flagged.
