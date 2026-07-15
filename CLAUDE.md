# CLAUDE.md

Instructions for any AI agent (Claude Code or otherwise) working in this repo.
**Before acting, read `SCOPE.md`, `DATA.md`, and `HANDOFF.md`.** State lives in those files
and in `docs/`; keep them current.

## Coding principles (Karpathy-inspired)

Distilled from Andrej Karpathy's publicly expressed engineering style — treat as defaults,
not dogma.

- The best code is no code. Prefer deleting to adding; solve the problem, then stop.
- Write for the reader. Optimize for how fast a human understands it, not cleverness.
- No premature abstraction. Wait for the third repetition before generalizing. YAGNI.
- Keep functions small and flat. Fewer layers, less indirection, obvious data flow.
- Make it work, make it right, then (only if measured) make it fast.
- Fail loud and early. No silent excepts; surface the real error.
- Comments explain *why*, never *what*. If code needs a *what*-comment, rewrite the code.
- Minimize dependencies. Every import is a liability you now maintain.
- Code you can throw away beats code you must maintain. Favor easy-to-delete modules.

## Project engineering standards

- Error handling: `try/except` with specific exceptions and meaningful messages.
- Docstrings on every function and class (purpose, args, returns, raises).
- Testability: pure functions + dependency injection at boundaries (I/O, API, clock, RNG).
- No magic numbers: named constants sourced from config.
- Type hints where the module benefits (public interfaces, data schemas).
- Reproducibility: explicit seeds, config-driven runs, no hidden global state.

## Hard rules (do not violate)

1. **Public-safe.** Everything is public from the first commit. Never write secrets, API
   keys, tokens, personal data, or private strategy into any tracked file. Keys come from
   `.env` (git-ignored) only.
2. **Scientific integrity.** Hypotheses are pre-registered in `SCOPE.md`. Do not silently
   change a hypothesis to fit results; log the change in `docs/DECISIONS.md` with reasoning.
   Report null and unexpected findings.
3. **No data leakage.** Genuine-skill claims use only post-cutoff questions (see `DATA.md`).
   Never let resolution information reach a forecaster.
4. **Cost-aware.** Every LLM run records model, token, and USD cost in `docs/EXPERIMENTS.md`.
   Use batching + caching. Cap output tokens on reasoning models.
5. **Determinism.** Same config + same seed → same result. Cache raw LLM responses.

## Where things live

- Research design & hypotheses → `SCOPE.md`
- Data sources & schema → `DATA.md`
- How agents coordinate & how to resume across chats → `HANDOFF.md`
- Build journal (how production actually went) → `docs/PRODUCTION_LOG.md`
- Decisions (with rationale) → `docs/DECISIONS.md`
- Runs & costs → `docs/EXPERIMENTS.md`
- Report voice → `docs/WRITING_STYLE.md`
