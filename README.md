# Applied AI Engineer: Take-Home Assessment

**Role:** Applied AI Engineer (Full-Stack)
**Time:** 3 hours, self-timeboxed
**Submission:** Public GitHub repo, or private repo shared with @elmdecoste and @bgreal5

---

## Before you start

Your 3-hour window starts when the assessment zip is delivered. The delivery system tracks the clock automatically, so there's no need to mark a start time yourself.

The time box is intentionally tight. Part of what we're evaluating is what you choose to build and what you choose to defer.

How to work:

1. Read the artifacts in `/brief/` and decide what to build.
2. Commit as you go so we can see your progress.
3. At the 3-hour mark, stop. If you commit past that point, note them as post-window in your writeup. We'd rather see honesty than a silent overrun.

If something goes wrong (life, illness, internet), just tell us. Rescheduling is fine; silent extensions are not.

---

## What you're building

PantryPal is an early-stage B2C startup building an AI-powered cooking assistant. They've engaged us to build the first working version of their core product: a conversational assistant that helps users figure out what to cook.

Instead of a clean spec, we've included the actual messages and artifacts we received from the PantryPal team during discovery. You'll find them in `/brief/`:

- An email from their Head of Product
- A voice-memo transcript from the CEO
- A message from their Head of Customer Experience
- A late-breaking email from their legal counsel

Your first job is to read these carefully and decide what to build.

---

## Deliverables

You will submit four things:

### 1. A scoping document (`SCOPING.md` in the repo root)

Before writing code, produce a short scoping doc with the following sections:

- **Scope committed:** what you're actually building, as a tight list
- **Scope cut:** what you heard but decided not to do, with reasoning
- **Contradictions resolved:** where stakeholders disagreed, and how you decided
- **Clarifying questions:** what you'd want answered before a production build
- **Assumptions made:** what you decided without asking
- **Risks accepted:** what could bite later and why you're accepting it

Keep this to 1-2 pages. We care about what's in each bucket. A scoping doc with three sharp, defensible entries per section beats one with fifteen generic ones.

### 2. A working system

Build against your own scope. Baseline requirements (non-negotiable):

- A Python backend using **FastAPI** and **LangGraph**
- LLM-driven tool use: the model decides when to invoke tools (no hardcoded sequences)
- At least one external tool (web search or equivalent)
- All LLM calls routed through **LangChain** (no model-specific SDKs directly)
- A chat frontend (stack of your choice; we recommend something you're fast in)
- Docker setup, so we can clone and run

Everything else is up to you. Implement what your scope says you'll implement.

### 3. A README

Setup instructions, example requests (curl is fine), and anything a teammate would need to run and understand the code.

### 4. A trade-offs writeup (`TRADEOFFS.md` in the repo root)

Short doc covering:

- What you actually built vs. what you scoped (time pressure is expected; tell us what got cut)
- Specific trade-offs you made and why
- What you'd do next with more time
- Known issues or unhandled cases

---

## Expectations and norms

- **Use AI tools.** We do, and we expect you to. We're evaluating your judgment and your output.
- **Don't optimize for feature count.** A smaller working system with defensible choices beats a larger system built on unexamined assumptions.
- **Ship something that runs.** If you have to cut, cut scope before quality.
- **Document unfinished work.** Stubs with clear TODOs are fine. Leave a clear trail of what's unfinished.
- **Expect robustness to be tested.** We'll exercise your system with inputs you didn't design for. Build accordingly.

---

## A note on the brief

The PantryPal artifacts are what you'd actually receive from a client at this stage: incomplete, sometimes contradictory, with real constraints buried in asides. Reading them carefully is part of the work. Do not assume every stated requirement belongs in your build, and do not assume every omission is unimportant.

Good luck.
