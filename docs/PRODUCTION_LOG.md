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

### 2026-07-16 — Cross-chat handoff; MVP gate + protocol decision pending — Phase 1
Done: Human requested a fresh orchestrator chat. Repo left in resumable state per HANDOFF.
Clarification recorded so the next orchestrator does not re-litigate it: **haiku-4-5 remains in
the panel under BOTH protocol options** — the pending A/B decision changes only the elicitation
prompt, identically for all three models (A = protocol v1, bare JSON ask, haiku reported as-is;
B = protocol v2, 1–2 sentences of reasoning before the JSON, to be logged as D-012 and re-run on
the 50-question slice ~$0.15 before any Phase-2 scale-up). Dropping haiku was considered and
recommended AGAINST: the RQ3-confirmatory clean sample (N≈791) is defined by haiku's training
cutoff and requires haiku's forecasts — without haiku, RQ3 falls back to exploratory (N=175,
per D-008), and the weak-forecaster contrast that powers RQ2 is lost.
Findings/decisions: none new; MVP results and the haiku root-cause are in the previous entry.
Cost this session: no new LLM runs. Running total USD 0.1572.
Broke / changed: n/a.
Gate status: Phase-1 MVP — deliverables complete and committed (ac2a8c2); **PENDING human
sign-off + protocol v1-vs-v2 decision**.
Next action (fresh orchestrator): read the six state files per HANDOFF §Core principle, restate
current state, collect the human's MVP sign-off and A/B decision. If B: log D-012, data-engineer
re-runs the 50-question slice under protocol v2, quant-analyst re-scores, compare, then Phase 2.
If A: straight to Phase 2 — full collection, LLM classifier (haiku, ~5,700 candidates), batched
elicitation (~1,600 q × 3 models, est. $6–11), scoring core with known-input unit tests (day-3
schedule). Workflow unchanged: orchestrator dispatches named subagents serially; agents never
commit; stop at every phase gate.
Blockers: human decision (MVP sign-off + A/B).

### 2026-07-16 — Phase-1 MVP thin slice complete; gate pending sign-off — Phase 1
Done: Full end-to-end thin slice. data-engineer: 50 seeded questions (25 post-/25 pre-cutoff,
15 clean for all three models) × 3 panel models → 150/150 elicitations (0 parse errors, 0
refusals), crowd_prob_at_T for all 50, protocol v1 frozen in `src/mvp/mvp_config.py`, offline
re-run bit-identical from cache, provenance in `data/mvp_manifest.json`. quant-analyst:
`src/analysis/score_mvp.py` (known-input self-test PASS; SHA-256-identical outputs across runs)
→ `data/interim/mvp_scores.csv`, `docs/figures/mvp_calibration.png`, `docs/mvp_results.md`.
Findings/decisions: Crowd Brier 0.086 (BSS +0.62); sonnet-5 0.121 (+0.46); opus-4-8 0.115
(+0.49); haiku 0.257 (BSS −0.15, i.e. worse than base rate). Orchestrator audited the haiku
anomaly against raw cached responses: NOT a parse artifact — haiku genuinely emits a small set
of canonical probabilities (0.15×16, 0.72×16, 0.92×8 out of 50). Elicitation-design/model
limitation; informative for RQ2 but degrades haiku's calibration measurements. All descriptive,
n=50, no claims (per docs/mvp_results.md).
Cost this session: mvp-thin-slice $0.1032; scoring $0.00. Running total USD 0.1572.
Broke / changed: `python3` on this machine is 3.14 without matplotlib; scoring runs under
python3.11 (Homebrew) — documented in the script; clean-checkout repro must note the matplotlib
dependency. No other breakage.
Gate status: Phase-1 MVP — reproducible ✓, cost logged ✓, numbers sane ✓ (one flagged,
root-caused anomaly). **PENDING human sign-off**, with one pre-Phase-2 decision attached:
elicitation protocol v1 (bare JSON ask) vs v2 (brief reasoning before the JSON, applied to ALL
models identically, decided now — before full-scale data — to avoid post-hoc tuning; would be
logged as D-012 and re-run on the 50-question slice first).
Next action: Human sign-off on MVP gate + protocol v1-vs-v2 decision → Phase 2 (full collection,
LLM classifier, batched elicitation at target N, scoring core with unit tests).
Blockers: none.

### 2026-07-16 — Phase-0 gate PASSED (human sign-off); D-011 locked; Phase 1 started — Phase 0→1
Done: Human signed off on the feasibility gate and delegated the budget-driven panel decision.
Logged D-011 (source = Manifold-only; TRAINING cutoffs 2025-07-31 / 2026-01-31; panel =
haiku-4-5 + sonnet-5 + opus-4-8; fable-5 excluded from core on cost — always-on billed thinking
at $10/$50 per MTok — optional post-MVP frontier probe; elicitation set ≈791 clean + ≈800
pre-cutoff probe, 1 repeat + 3× variance probe; budget envelope ~$8–15 core). Ticked Phase 0 in
SCOPE and updated §8 recon-dependent items to reference D-011. Added the planned-budget table to
EXPERIMENTS.md. Verified current model pricing from the claude-api reference (not memory).
Findings/decisions: D-011. Polymarket raised by the human — assessed as a genuine future-work
upgrade for a real-money RQ4, not v1 (unrecon'd source; deadline-boxed sprint; recorded in D-011).
No OpenAI key by human decision → single-provider panel is a stated limitation (two distinct
cutoffs only).
Cost this session: USD 0 so far today beyond the $0.054 total (no new LLM runs at log time).
Broke / changed: nothing broke; D-009's open items resolved by D-011.
Gate status: Phase-0 feasibility — **PASSED** (human sign-off 2026-07-16). Phase-1 MVP gate open.
Next action: data-engineer thin slice (dispatched): ~50 seeded questions spanning pre/post
cutoff × 3 panel models, crowd prob at T, cached elicitation, forecasts table → then
quant-analyst scores it (Brier vs crowd + one calibration figure) → MVP gate check
(reproducible, cost logged, numbers sane) → human sign-off.
Blockers: none.

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
