# Legal Requirement Updates

Changes implemented to close compliance gaps against Diane Kobayashi's email
(`brief/04_legal_email.md`). Each item maps to a numbered point in that email.
All changes are implemented and verified live; see **Verification** at the end.

---

## 1. Allergen disclosure — now consistent and complete (Diane #1)

**Requirement:** *"Any response that suggests a specific recipe **or ingredient**
must include a visible allergen notice… whether or not the user mentioned allergies…
companies get in trouble for inconsistency."*

**Gap found:** the disclaimer only fired when a *recipe* tool ran
(`search_recipes`/`check_can_make`). Ingredient suggestions that come from
`web_search` or the model's own knowledge — e.g. *"what can I substitute for
buttermilk?"* → "use milk + lemon juice" — produced **no notice**. That is both a
literal miss on "recipe **or ingredient**" and a miss on a core product feature.

**Implemented (two layers, so consistency is structural, not best-effort):**

1. **Always-on standing notice.** Every chat response now emits a `notice` event
   carrying `STANDING_NOTICE`, and the chat UI shows a permanent allergen/scope
   disclosure in the composer footer. Because it is present on *every* turn, it
   cannot be inconsistent — the strongest posture against Diane's stated concern.
2. **Broadened contextual notice.** The point-of-suggestion `disclaimer` now fires
   for `web_search` as well as the recipe tools (`SUGGESTION_TOOLS`), so ingredient
   and substitution answers are covered, reinforcing the notice exactly where a
   recipe/ingredient is named.

**Files:** `backend/app/prompts.py` (`STANDING_NOTICE`), `backend/app/agent.py`
(`SUGGESTION_TOOLS`, `turn_suggested_food`), `backend/app/main.py` (emits `notice`
every turn; `disclaimer` on `suggested_food`), `frontend/index.html` (footer notice).

---

## 2. No medical / dietary / therapeutic advice (Diane #2)

**Requirement:** no medical or dietary advice; accommodate preferences
("I'm vegetarian") but do not adapt to medical conditions; if a condition is
mentioned, acknowledge generically and refer to a professional.

**Status:** already enforced by hard rules in the system prompt (rule 2/3) and
verified previously (diabetes prompt → generic acknowledgment + "see a
professional", no tailoring). **No change required**; retained and re-verified.
The new health-data backstop (item 4) further guarantees a mentioned condition is
never *stored*.

---

## 3. Data retention & deletion story (Diane #3)

**Requirement:** *"If the product captures user-stated dietary restrictions,
preferences, or health mentions, we need a retention and deletion story before
launch."*

**Decision recap:** we persist **food preferences and avoidances** (cuisines,
"vegetarian", "no shellfish") — required for Marcus's cross-session memory — but
never medical conditions (see item 4). Diane preferred not storing health-adjacent
data at all; we treat a food avoidance as a *preference, not a diagnosis*, and back
that with a concrete retention + deletion story:

**Implemented:**
- **Retention TTL.** `RETENTION_DAYS` (default 180) drives `memory.purge_stale()`,
  which deletes any user record not updated within the window. It runs on app
  startup; rows carry an `updated_at` timestamp.
- **Deletion / right-to-delete.** `DELETE /api/memory/{user_id}` wipes a user's
  record; the UI "Reset memory" button calls it. (Pre-existing, now documented as
  part of the formal story.)
- **Transparency.** Users can inspect exactly what is stored via
  `GET /api/memory/{user_id}`.

**Files:** `backend/app/config.py` (`RETENTION_DAYS`), `backend/app/memory.py`
(`purge_stale`), `backend/app/main.py` (startup purge).

---

## 4. Health-condition storage backstop (supports Diane #2 & #3)

**Gap found:** "never store medical conditions" lived only in the extractor
*prompt* — probabilistic. Under adversarial or unusual input, a condition could
slip into storage.

**Implemented:** a deterministic denylist (`HEALTH_DENYLIST`) of medical-condition
terms (diabetes, pregnancy, hypertension, celiac, medication, diagnosis, …).
`drop_health_terms()` filters every extracted field **before** it can be written to
SQLite. Food avoidances are intentionally **not** on the denylist, so "shellfish",
"peanuts", and "gluten-free" are still remembered while "diabetes" or
"diabetic-friendly" are dropped. This makes the guarantee code-enforced, not
prompt-dependent.

**Files:** `backend/app/prompts.py` (`HEALTH_DENYLIST`, `drop_health_terms`),
`backend/app/agent.py` (`extract_and_save` filters before `update_memory`).

---

## 5. Food safety (Diane #4)

**Status:** already enforced (system-prompt rule 3): the assistant refuses to judge
whether specific food is safe to eat and defers to food-safety authorities
(verified previously with the "chicken left out overnight" prompt). **No change
required**; retained.

---

## 6. Children / COPPA (Diane #5)

**Requirement:** *"tell me your stance."* Previously unanswered in the product.

**Stance adopted:** PantryPal is **intended for users aged 13+ and is not directed
at children**; we do not knowingly collect or store personal information from users
under 13.

**Implemented:**
- System-prompt rule 5: if a user indicates they are under 13, the assistant gently
  declines direct help, suggests cooking with a parent/guardian, and collects no
  personal details.
- Always-visible "Intended for users aged 13+" notice in the UI and in
  `STANDING_NOTICE`.
- `MIN_AGE` config (default 13) to make the threshold explicit/tunable.

**Files:** `backend/app/prompts.py` (rule 5, `STANDING_NOTICE`),
`backend/app/config.py` (`MIN_AGE`), `frontend/index.html` (notice).

> This is a product stance, not a legal opinion. It still warrants Diane's sign-off,
> and a true COPPA program (age gating/verification) is out of scope for v1.

---

## Verification

Tested live against the Anthropic + Tavily APIs after the changes:

| Scenario | Expected | Result |
|---|---|---|
| "substitute for buttermilk?" | allergen notice now present (ingredient) | ✅ `disclaimer` + `notice` emitted |
| Greeting ("hey there") | standing notice, no allergen disclaimer | ✅ `notice` only |
| "I'm 9, want to make cookies" | decline directly, refer to guardian, store nothing | ✅ COPPA response |
| extract `['shellfish','diabetes','gluten-free']` | medical dropped, food kept | ✅ → `['shellfish','gluten-free']` |
| `purge_stale(180)` | runs without error | ✅ |

## Residual risk / for legal to ratify

- **Storing food avoidances at all.** We persist allergen avoidances as
  preferences; Diane preferred zero health-adjacent storage. Retention + deletion +
  denylist mitigate this, but the policy choice needs explicit sign-off.
- **Model-knowledge ingredient answers with no tool call** still rely on the
  always-on standing notice rather than the contextual one. The standing notice
  guarantees a visible disclosure; the contextual reinforcement may be absent in
  that narrow case.
- **COPPA** relies on self-disclosure of age; there is no age gate.
- Compliance guardrails (medical/food-safety refusals) are prompt-enforced; an
  output-side classifier (see polish doc) would harden them further.
