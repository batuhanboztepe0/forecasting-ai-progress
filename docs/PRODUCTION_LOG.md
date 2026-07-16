# PRODUCTION_LOG.md

The running narrative of how this project was actually built with Claude Code — the candid
engineering + science journal. It doubles as the cross-chat handoff record. **Append newest
entries at the top.** Keep it honest: what was done, what broke, what changed, and why.

## How to use

- One entry per work session (or per meaningful step). Never rewrite history; append.
- On a chat switch, the last entry MUST state: what's done, the current phase, the **exact next
  action**, and any blockers, so a fresh orchestrator can resume.
- Reference decisions in `DECISIONS.md` and runs in `EXPERIMENTS.md` rather than duplicating them.

## Entry template

```
### YYYY-MM-DD — <short title> — Phase <n>
Done: <what was completed this session>
Findings/decisions: <key results; link DECISIONS.md IDs>
Cost this session: <USD, if any LLM runs; link EXPERIMENTS.md run IDs>
Broke / changed: <what went wrong and how it was addressed>
Gate status: <which gate; pass/fail + why>
Next action: <the single next concrete step>
Blockers: <none | ...>
```

---

### 2026-07-16 — Recon v1.1: Metaculus with token + empirical pilot ρ — Phase 0
Done: Human provisioned `.env` (METACULUS_API_TOKEN, ANTHROPIC_API_KEY). data-engineer re-run:
(1) Metaculus pulled with auth via `/api/posts/` — 142 AI-progress binary questions found, but
`question.resolution` is null for ALL of them (API limitation as of 2026-07-16) → countable, not
analyzable; (2) pilot elicitation completed (30 seeded questions × 2 models, crowd prob at T from
Manifold bet history); (3) orchestrator-caught fix-ups: manifest restructured to cover all three
pulls with SHA-256 hashes, and the cutoff table corrected to TRAINING-data cutoffs (end-of-month,
conservative) instead of "reliable knowledge" cutoffs.
Findings/decisions: **Empirical ρ̂ = 0.57** pooled (haiku-4.5: 0.49 [0.16, 0.72]; sonnet-5: 0.66
[0.39, 0.82], logit-scale, n=30). Under training cutoffs the clean snapshot-feasible N: haiku-4.5
(C=2025-07-31) → 808 combined (791 Manifold), power ≈100% at ρ̂; Claude-5-family (C=2026-01-31) →
175 → a standalone shared-question encompassing test at the newest cutoff is UNDERPOWERED (~70-75%);
RQ3 confirmatory status rides on the haiku-cutoff sample. **RQ3: CONFIRMATORY** per D-008.
11/30 pilot questions have T < C for sonnet-5 (recency leak) — inflates ρ̂, i.e. conservative for
the power verdict; those questions are inadmissible in the Phase-2/3 clean sample for Jan-2026
models (documented in recon report LIMITATIONS §9). Haiku pilot calibration poor (Brier 0.214 vs
crowd 0.056) — keep but monitor. `temperature` is deprecated on newest Anthropic models (HTTP 400)
— response caching is the determinism mechanism for them.
Cost this session: USD 0.054 (run `pilot-elicitation-2026-07-16`; running total USD 0.054).
Broke / changed: v1.1 initially shipped without updating the manifest (caught at orchestrator
verification; fixed same day). Cutoff basis corrected from "reliable" to training cutoff — lowers
clean N (1,125→808; 239→175) but is the defensible reading of D-006.
Gate status: Phase-0 feasibility — ALL deliverables complete incl. empirical ρ. **PENDING human
gate decisions**; orchestrator recommends PASS (novelty incremental-but-defensible, N ample,
RQ3 confirmatory, RQ4 viable, cost negligible).
Next action: Human decides: (1) Manifold-only v1 (Metaculus → future work)?; (2) panel:
haiku-4-5 + sonnet-5 + fable-5 (Anthropic-only, two cutoffs) vs. adding OPENAI_API_KEY for an
older-cutoff model (2-3× clean N, stronger RQ2); (3) training-cutoff constants confirmation.
Then: log D-011, tick Phase 0 in SCOPE, commit, start Phase 1 thin slice.
Blockers: awaiting human gate decisions.

### 2026-07-15 — Phase-0 feasibility: novelty check + data recon complete — Phase 0
Done: (1) researcher novelty check → `docs/novelty_memo.md`, `docs/references.md`, D-010 appended.
(2) data-engineer recon → `docs/recon_report.md`, `src/recon/` (re-runnable, seeded),
`data/recon_manifest.json`, run `recon-2026-07-15` logged in EXPERIMENTS.md.
Findings/decisions: Novelty verdict **INCREMENTAL** (D-010): RQ1 is replication+extension; the
differentiating combination is AI-progress domain + encompassing framing + C ≤ T + dataset
release; closest work is AIA Forecaster (arXiv 2511.07678, forecast-combination not encompassing).
Recon: **Metaculus API now requires auth (HTTP 403)** — zero Metaculus data this phase; Manifold
alone yields 3,728 resolved binary AI-progress questions (keyword filter v1.0, precision ~85%).
Snapshot-feasible clean N: 2,886 (2022-01 cutoff) → 2,709 (2023-10) → 1,183 (2025-01) → 1,004
(2025-04). RQ4 liquidity viable: 54.7% of markets ≥20 bettors and ≥1,000 mana volume. Seeded
power sketch (seed 42): 80% power at N=200–400 for ρ ≤ 0.75, N≈1,000 at ρ = 0.9 → RQ3
provisionally **CONFIRMATORY**; D-008 exploratory fallback stays armed until empirical ρ is
measured (pilot blocked — no API keys).
Cost this session: USD 0.00 (no LLM calls; see run `recon-2026-07-15`).
Broke / changed: DATA.md's "key-less Metaculus API" assumption no longer holds (policy change);
needs `METACULUS_API_TOKEN` in `.env` or a Manifold-only v1. Pilot elicitation (DATA.md recon
item 5) blocked by missing `.env`; substituted a simulation-based power grid, clearly labeled.
Process note: data-engineer subagent committed its own work (b903b0f) — contents verified clean
(no raw data, no secrets), but per HANDOFF the orchestrator commits; future dispatches will say so
explicitly.
Gate status: Phase-0 feasibility — deliverables complete, **PENDING human sign-off**.
Orchestrator's read: pass — novelty defensible (incremental, honestly positioned), N ample,
RQ4 viable; RQ3 confirmatory label is robust to the known haircuts (precision ~85%, snapshot
heuristic −5–15%) at ρ ≤ 0.75, marginal only for the newest cutoff if ρ ≈ 0.9.
Next action: Human gate decisions: (1) accept Manifold as v1 primary source vs. provision
`METACULUS_API_TOKEN` and re-run recon; (2) lock the ~3-model panel (log as D-011); (3) provide
LLM API keys in `.env` so Phase 1 can run the pilot ρ estimate + thin slice.
Blockers: `.env` keys (LLM API required for Phase 1; Metaculus token optional) — user-provided.

### 2026-07-15 — v1 scope locked; design decisions integrated — Phase 0
Done: Full-repo read + design discussion with the human. Locked the v1 scope and the workflow;
integrated decisions into SCOPE.md, DATA.md, HANDOFF.md, README.md and recorded D-005..D-009.
Findings/decisions: v1 = RQ1–RQ3 confirmatory core + RQ4 preliminary (D-005); snapshot-aware
contamination rule C ≤ T (D-006); single 30-day horizon (D-007); RQ3 exploratory fallback + report
market–model correlation (D-008); sources/panel decided by recon (D-009). Positioning: the project
stands on methodology and honesty, not on a particular empirical outcome (SCOPE §4).
Cost this session: none (no API calls).
Broke / changed: Refined D-002's cutoff rule (R > C) into the stricter C ≤ T (D-006).
Workflow: faithful repo model — orchestrator dispatches named subagents serially; stop at each
phase gate. Not yet a git repo; `git init` is step 0 of the sprint.
Gate status: Phase 0 still open — feasibility (novelty + recon) not yet run.
Next action: Start Phase 0 — `git init` + first commit, then (1) `researcher` novelty check and
(2) `data-engineer` recon on Metaculus + Manifold (clean post-cutoff N per candidate cutoff,
market–model correlation on a small pilot, Manifold liquidity, RQ3 power sketch). Do NOT start
Phase 1 until the feasibility gate passes.
Blockers: none. Note: `docs/WRITING_STYLE.md` is still a stub (only bites at Phase 4).

### (bootstrap) — Scaffold created — Phase 0
Done: Repository scaffold authored — CLAUDE.md, HANDOFF.md, SCOPE.md, DATA.md, agents, skills,
docs. Research direction fixed: calibration + information content of AI-progress forecasts
(market vs. model), contamination-controlled, with a friction-aware backtest.
Findings/decisions: See DECISIONS.md D-001..D-004.
Cost this session: none (no API calls).
Broke / changed: n/a.
Gate status: Phase 0 not yet passed — feasibility (novelty check + data reconnaissance) pending.
Next action: Run the Phase-0 feasibility gate — (1) `researcher` novelty check; (2)
`data-engineer` reconnaissance per DATA.md (counts of resolved binary AI-progress questions and
the per-cutoff post-cutoff clean sample). Do NOT start Phase 1 until this gate passes.
Blockers: none.
