# Trade-offs & Decisions

A short, honest account of what got built, what got cut, and why. Pairs with [SCOPING.md](SCOPING.md).

## Built vs. scoped

Everything in the committed scope shipped and is verified working end-to-end against the live Anthropic + Tavily APIs:

- ✅ LangGraph agent with **model-driven** tool use (ReAct loop; no hardcoded sequences)
- ✅ Three tools: `search_recipes` (local 1,042-recipe library), `check_can_make` (equipment-aware), `web_search` (Tavily — the external tool)
- ✅ **User-supplied, persisted equipment** (no fixed assumed kit) + "you can't do X, but you CAN do Y" pivots
- ✅ Cross-session memory of food preferences/avoidances, with medical conditions excluded by design
- ✅ Cost-aware **model routing** (Haiku for simple turns, Sonnet for recipe reasoning)
- ✅ Compliance layer: deterministic allergen disclaimer, food-safety deferral, no medical advice, warm off-topic redirect
- ✅ Personality ("the friend who cooks")
- ✅ Streaming chat UI + Docker one-command run + memory delete endpoint

## Specific trade-offs

- **Keyword recipe search, not embeddings.** I used in-process keyword scoring (name-weighted) over the recipe set instead of a vector store. It keeps the app fully local with zero extra infra and is plenty good for the dataset size. Trade-off: it misses semantic matches ("comfort food" won't find a stew unless the words overlap). A vector index is the obvious upgrade.

- **Equipment fit is LLM-inferred, tool-checked.** The dataset has no equipment field, so the model infers what a recipe needs and passes it to `check_can_make`, which does the deterministic set-comparison against the user's stored kit. This puts judgment where the LLM is strong and the check where determinism matters — but the inference can still be wrong, which is why the prompt forces a graceful pivot rather than a hard refusal.

- **Allergen disclaimer is attached in code, not left to the model.** Diane (legal) required consistency. Rather than trust the LLM to always remember, the backend deterministically appends the notice whenever a recipe tool was used in the turn. Trade-off: it triggers on *recipe-tool use* as a proxy for "a recipe was suggested," so a turn that searches but then suggests nothing could still show it. I judged over-disclosure to be the safe failure direction.

- **Routing uses one extra cheap classifier call.** A ~1-token Haiku call decides fast-vs-smart per turn. It adds a small latency/cost overhead on every turn but makes routing transparent and tunable. A heuristic (length/keywords) would be free but less reliable; defaulting everything to Sonnet would be simpler but pricier. I optimized for a clear, defensible cost story.

- **Conversation history is client-managed; only preferences are server-persisted.** The frontend sends the full message array each turn, so the server stays stateless about conversations and only the durable prefs/equipment live in SQLite. Simple and robust for v1; a real build would move threads server-side with a checkpointer.

- **Latency vs. quality:** per the CEO, I did *not* treat 2s as a hard SLA. Simple turns route to Haiku and are fast; recipe turns use Sonnet + tools and can take a few seconds. Streaming + a live "thinking/searching" status makes the wait feel intentional rather than broken.

## What I'd do next with more time

1. **Vector/hybrid recipe search** for semantic queries, plus filtering on cuisine/diet tags (would require enriching the dataset).
2. **Favorites/saved recipes** — wanted in every CX interview; the memory store is the natural home, just needs a table + UI.
3. **Structured equipment onboarding** (a quick checklist on first use) so `check_can_make` has ground truth instead of relying on incidental mentions.
4. **Output-side compliance classifier** as a second layer behind the prompt rules, to harden against adversarial extraction of medical/safety answers.
5. **Eval harness** — a fixed set of prompts (compliance, equipment, memory, off-topic) run against the agent in CI to catch regressions.
6. **Grocery-list export & meal planning** (flagged v2 by CX).
7. **Voice / hands-free** — the agent is already transport-agnostic behind the API, so this is additive.

## Known issues & unhandled cases

- **Disclaimer over-triggering** (described above) — fires on recipe-tool use, occasionally when no concrete recipe is ultimately named.
- **Memory extraction is best-effort.** It runs after each turn via a cheap model and can occasionally miss a stated preference or store a slightly noisy one. It fails silently by design so it can never break a chat response.
- **No authentication.** `user_id` comes from the browser (localStorage) and is trusted as-is. Fine for a local demo; not for production. COPPA/under-13 (Diane's open question) is explicitly unresolved.
- **Equipment matching is substring-based** ("pot" matches "large pot"), which is forgiving but can mis-match in edge cases (e.g. "pan" vs "saucepan" nuances).
- **No rate limiting / cost ceiling** on the endpoint.
- **Tavily/Anthropic outages** degrade gracefully (web_search returns a fallback message; agent errors surface as a friendly error event) but there's no retry/backoff.
- **Single-process SQLite** — fine locally; would need a real DB for concurrent multi-instance deployment.

## Time / honesty note

Built within the 3-hour window. All four artifacts in `/brief/` were read and reconciled before any code (see SCOPING.md). The work was verified live against both APIs (routing, tool use, equipment pivots, memory, and all compliance paths). Any commits after the window are marked as post-window.
