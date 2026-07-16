# DECISIONS.md

Architecture/methodology decision record. Each decision is append-only and immutable; to change
one, add a new decision that supersedes it (reference the old ID). This is how a public,
scientifically-honest project shows its reasoning — including reversals.

## Format

```
### D-00N — <title>   (status: accepted | superseded by D-00M)   YYYY-MM-DD
Context: <the situation / forces>
Decision: <what we decided>
Reasoning: <why; alternatives considered>
Consequences: <what this implies, including risks>
```

---

### D-001 — Research question and framing   (status: accepted)
Context: Generic "are LLMs calibrated vs. crowds?" is a saturated, incremental question.
Decision: Study the **AI-progress domain specifically**, and shift from an accuracy horse-race
to **information content** (does market carry signal the model lacks, and vice versa), under a
contamination control, plus a friction-aware backtest.
Reasoning: Narrower domain is decision-relevant (governance/early-warning); information-content
via forecast-encompassing is the economically interesting and less-saturated question; the
microstructure angle is a genuine differentiator. Positions against prior calibration work as
replication+extension, with the encompassing/microstructure results as the contribution.
Consequences: Requires enough post-cutoff AI-progress questions (feasibility risk — see D-003).

### D-002 — Contamination handling   (status: accepted)
Context: Instructing a model to ignore post-cutoff information does not reliably prevent leakage
(established in the literature).
Decision: Genuine-skill claims (RQ2/RQ3) use **only** questions resolving after each model's own
cutoff. Pre-cutoff performance is reported as a memorization probe, never as foresight.
Reasoning: The only clean signal is post-cutoff; per-model cutoffs mean the split is per-model.
Consequences: Shrinks usable N (feasibility risk); makes the Phase-0 recon a hard gate.

### D-003 — Feasibility is a blocking gate   (status: accepted)
Context: The whole contribution depends on an adequate post-cutoff clean sample and on the
contribution being novel.
Decision: Phase 0 (novelty check + data reconnaissance) must pass before any heavy build.
Reasoning: Cheaper to learn "not enough clean data" or "already done" now than after building.
Consequences: First real work is the recon report + novelty memo, not the pipeline.

### D-004 — Repo is the single source of truth for state   (status: accepted)
Context: Work spans multiple chats and long autonomous sessions.
Decision: All durable state lives in tracked files (SCOPE/DATA/DECISIONS/PRODUCTION_LOG/
EXPERIMENTS); agents reconstruct context from them, not from chat history.
Reasoning: Enables clean cross-chat resume and long-horizon execution; also serves as the public
record of process.
Consequences: Discipline required — state files must be updated before every handoff/commit.

### D-005 — v1 scope: RQ1–RQ3 core, RQ4 preliminary, deadline-boxed   (status: accepted)   2026-07-15
Context: v1 is built in a short, focused sprint (MVP by day 2, ship by day 4). The full 4-RQ study
at depth does not fit that box without rushing the core.
Decision: v1 delivers RQ1 (calibration), RQ2 (cutoff split), and RQ3 (encompassing) as the
confirmatory core; RQ4 (friction backtest) is a **preliminary** check with explicit play-money
caveats and is the first thing de-scoped to future work if time is short. Single 30-day horizon
(D-007); ~3-model panel (D-009).
Reasoning: The contribution is design and honesty, not breadth (SCOPE §4). A clean, reproducible
RQ1–RQ3 with a released dataset is a stronger artifact than an overreaching, rushed 4-RQ study.
RQ4 is the weakest claim anyway (play-money), so it is the right de-scope lever.
Consequences: Multi-horizon robustness and a real-money RQ4 are explicit future work; the report
must frame the scope cut on the merits, not as a shortcut.

### D-006 — Snapshot-aware contamination rule (C ≤ T)   (status: accepted; refines D-002)   2026-07-15
Context: D-002 restricts skill claims to questions resolving after the model cutoff (R > C). That
prevents memorizing the outcome but leaves an information-recency leak: if the snapshot T precedes
the cutoff (T < C < R), the model was trained on T→C data the T-snapshot crowd never saw.
Decision: For the clean model-vs-crowd sample, require C ≤ T, i.e. resolved_at ≥ C + 30d. Prefer
questions where C is close to T so RQ3 tests aggregation quality rather than mere recency.
Reasoning: Under C ≤ T the model is at worst information-disadvantaged vs the contemporaneous
crowd, so any model edge is conservative and interpretable; closes the obvious red-team on RQ3.
Consequences: Shrinks usable N by roughly one lead-time; sharpens the feasibility gate (D-003).

### D-007 — Single 30-day snapshot horizon for v1   (status: accepted)   2026-07-15
Context: SCOPE §8 left the crowd-snapshot lead time open (single vs. multi-horizon).
Decision: v1 uses a single lead time T = 30 days before resolved_at. 7/90-day horizons are future
robustness work.
Reasoning: One horizon keeps the MVP and the multiplicity correction simple and fits the sprint;
30 days is long enough that forecasting is non-trivial yet short enough that a crowd history
usually exists.
Consequences: No within-study horizon-robustness claim in v1; note as a limitation.

### D-008 — RQ3 power: report market–model correlation; pre-registered exploratory fallback   (status: accepted)   2026-07-15
Context: The encompassing regression outcome ~ logit(market) + logit(model) has two predictors
that both track the truth; high collinearity plus small clean N can leave the coefficients
unidentified (wide CIs → "can't tell").
Decision: Phase-0 recon reports the clean post-cutoff N *and* the market–model forecast correlation
(estimated on a small pilot) and sketches power. If underpowered, RQ3 is reported as exploratory
(pooled/descriptive), never confirmatory.
Reasoning: Protects integrity: we pre-commit to the fallback before seeing results, so a null or
unidentified RQ3 is an honest finding, not a failure to be tuned away.
Consequences: RQ3's confirmatory status is contingent on the recon; the report must label it so.

### D-009 — Sources decided by recon; ~3-model cost-bounded panel   (status: accepted)   2026-07-15
Context: SCOPE §8 left source mix and model panel open; both depend on how much clean post-cutoff
data actually exists.
Decision: Phase-0 recon queries both Metaculus and Manifold; the clean post-cutoff N (and, for RQ4,
Manifold liquidity) decides the primary source. The panel is ~3 models with published cutoffs
spanning capability, batched + cached, cost-bounded; the exact list is fixed after recon, favoring
older cutoffs where they yield more post-cutoff questions.
Reasoning: Avoids a premature lock; lets feasibility data drive the choice, per D-003.
Consequences: Panel and primary source are provisional until the recon report; log the final choice
as a follow-up note here.

<!-- Add D-012+ as the project makes further decisions (any post-freeze hypothesis change,
     metric/analysis choices). -->

### D-010 — Phase-0 novelty verdict   (status: accepted)   2026-07-15
Context: D-003 requires a passing novelty check before any heavy build. The contribution (D-001)
claims novelty on four axes: (a) AI-progress domain restriction, (b) forecast-encompassing test
between market and LLM forecasts (RQ3), (c) C ≤ T snapshot-aware contamination rule (D-006),
(d) released curated AI-progress dataset with crowd snapshots.
Decision: Verdict is **INCREMENTAL**. The project proceeds. Calibration (RQ1) is replication
and extension in a decision-relevant domain. The encompassing framing + C ≤ T rule + AI-progress
restriction + dataset release is the differentiating combination; no single existing paper
delivers all four. Full search, closest works, and reasoning are in `docs/novelty_memo.md`.
Closest works:
- Halawi et al., NeurIPS 2024 (arXiv 2402.18563) — general-domain LLM vs. crowd accuracy, post-cutoff filter, no encompassing
- Schoenegger et al., Science Advances 2024 (arXiv 2402.19379) — 12-LLM ensemble vs. 925-human crowd, no contamination control, no encompassing
- Karger et al. / ForecastBench, ICLR 2025 (arXiv 2409.19839) — prospective contamination-free benchmark, no domain stratification, no encompassing
- Alur et al. / AIA Forecaster, arXiv 2511.07678 (2025) — simplex regression on LLM + market across all domains; closest to RQ3 but uses forecast-combination framing, not encompassing, and no AI-progress domain or C ≤ T rule
- Zou et al. / Autocast, NeurIPS 2022 (arXiv 2206.15474) — foundational LM forecasting benchmark
Reasoning: None of the above apply all four differentiators simultaneously. The AIA Forecaster is
the nearest competitor for RQ3 but differs in statistical framing (combination vs. encompassing)
and domain. The field is active; a domain-specific encompassing paper could appear before
publication — monitor continuously.
Consequences: Report positions RQ1 as replication+extension in the AI-progress domain; RQ3
(encompassing) and the dataset artifact are the primary contributions. Exploratory fallback for
RQ3 pre-committed per D-008 if N is insufficient. Phase-0 data recon proceeds as the next
blocking gate.

### D-011 — Phase-0 gate PASSED; v1 source, panel, cutoffs, elicitation plan, budget   (status: accepted; resolves D-009's open items)   2026-07-16
Context: Recon v1.1 (docs/recon_report.md): Manifold yields 3,728 usable resolved binary
AI-progress questions; Metaculus API returns 142 questions but resolution=null (outcomes
inaccessible as of 2026-07-16). Empirical pilot market–model correlation ρ̂ = 0.57 (n=30).
Only an Anthropic API key is provisioned (human decision: no OpenAI). Servable Anthropic
models with documented training cutoffs: claude-haiku-4-5 (Jul 2025); claude-sonnet-5,
claude-opus-4-8, claude-fable-5 (Jan 2026). Verified pricing per MTok (in/out): haiku $1/$5,
sonnet-5 $2/$10 intro ($3/$15 after 2026-08-31), opus-4-8 $5/$25, fable-5 $10/$50; Batch API
−50%. Fable-5's thinking cannot be disabled and bills as output tokens. Human gate sign-off
2026-07-16.
Decision:
1. **Source:** v1 uses Manifold only. Metaculus deferred to future work unless its resolution
   endpoint becomes usable (N=142 is marginal regardless). Polymarket (real-money) noted as a
   future-work upgrade for RQ4 — not in v1 (unrecon'd source, deadline-boxed sprint).
2. **Cutoff basis:** TRAINING-data cutoff, end-of-month, conservative (per D-006 intent):
   haiku-4-5 C = 2025-07-31; sonnet-5 / opus-4-8 C = 2026-01-31. Named constants in config.
3. **Panel (~3 models, D-009):** claude-haiku-4-5-20251001, claude-sonnet-5, claude-opus-4-8 —
   small/mid/frontier spread, all with documented cutoffs. Fable-5 is EXCLUDED from the core
   panel on cost grounds (always-on billed thinking; would dominate the whole budget); optional
   post-MVP "frontier probe" on the 175-question clean shared set (~$5–10 batched) if time and
   budget allow.
4. **Elicitation set:** the haiku-clean snapshot-feasible set (resolved_at ≥ 2025-08-30,
   N≈791) plus a seeded pre-cutoff memorization-probe sample (~800, resolved < 2025-08-30).
   All three models answer all questions; each model's pre/post split is computed against its
   own training cutoff. Repeats: 1 per (question, model); a 3× variance probe on a seeded
   100-question subset (sonnet-5) quantifies sampling variance, since temperature is not
   accepted on the newest models (determinism rests on response caching).
5. **RQ3 status (D-008):** CONFIRMATORY on the haiku-cutoff clean sample (N≈791, power ≈100%
   at ρ̂=0.57); EXPLORATORY for the Jan-2026-cutoff models (N=175, ~70–75% power). The report
   must label each accordingly.
6. **Budget envelope:** core plan ≈ USD 8–15 with batching+caching (classifier ~$1–2, three-model
   elicitation ~$6–8, probes/contingency ~$3–5); optional fable probe +~$10. Guardrails
   unchanged: escalate if any single run projects > $25; full study target ≤ $35.
Reasoning: Manifold is the only source with accessible outcomes; training cutoff is the only
defensible C under D-006; opus-4-8 delivers frontier capability at half fable-5's token price
with controllable thinking, keeping the study reproducible and in budget; the shared question
set maximizes RQ2's per-model pre/post contrast at fixed cost.
Consequences: Single-provider panel with only two distinct cutoffs — a stated limitation (RQ2
capability-recency spread is narrow; no cross-provider generalization claim). Play-money-only
RQ4 caveat stands; Polymarket and a multi-provider panel are explicit future work.

### D-012 — Elicitation protocol v2 (reasoning-first) for Phase 2+   (status: accepted)   2026-07-16
Context: Phase-1 MVP ran protocol v1 (bare JSON probability ask). The MVP gate carried a
pre-registered A/B decision: keep v1, or switch to v2 (1–2 sentences of reasoning before the same
JSON contract), decided before any full-scale data to avoid post-hoc tuning. A targeted literature
check (researcher, 2026-07-16, verified against the papers) found: ForecastBench (arXiv 2409.19839)
directly compares scratchpad vs. zero-shot elicitation and scratchpad wins consistently (e.g.,
Brier 0.122 vs. 0.131 for Claude-3.5-Sonnet, ~7% relative); Halawi et al. (arXiv 2402.18563) and
Schoenegger et al. (arXiv 2402.19379) both use reasoning-first elicitation and ran no bare-ask
control; one caveat study (arXiv 2506.01578) warns explicit "Bayesian reasoning" framings can hurt
accuracy, so v2 keeps the reasoning instruction brief and neutral.
Decision: Adopt protocol v2 for all Phase-2+ elicitation, identically for all panel models: the
model writes 1–2 sentences of key considerations (a base-rate anchor where natural; no Bayesian
framing) and then the same JSON output contract as v1. Selection is on the a priori literature
grounds above (human sign-off 2026-07-16). The 50-question slice re-run (~$0.15) is a plumbing
check — parse rate, refusals, cost, cache determinism — NOT an accuracy bake-off; v2 stands
regardless of which protocol scores better on those 50 questions.
Reasoning: Reasoning-first is the field's standard elicitation and the only direct comparison
favors it; the stronger protocol gives every panel model its best fair shot, making model-vs-crowd
comparisons meaningful. Fixing the choice a priori (not by slice accuracy) avoids selecting the
protocol on data that feeds the confirmatory sample.
Consequences: MVP v1 numbers are protocol-inconsistent with Phase-2 numbers (kept as a descriptive
protocol-sensitivity comparison only). Output cost rises ~$1–2 at full scale. Haiku's
canonical-probability anomaly may persist or resolve under v2 — monitored and reported either way.

### D-013 — Classifier v1.1 realignment to the pre-registered domain definition; snapshot inclusion rule   (status: accepted)   2026-07-16
Context: Phase-2 step A ran the LLM-assisted question classifier (prompt v1.0, haiku) over the
3,728 keyword candidates and dropped 50.8% — far above the ~15% false-positive rate the recon
estimated. Orchestrator audit of a seeded 40-question sample of DROPS found ~5–8 (12–20%) are
in-domain by the letter of DATA.md's pre-registered definition — the v1.0 prompt applied a
narrow "capabilities/benchmarks/releases" reading and systematically excluded two categories
DATA.md explicitly includes: adoption/impact claims about AI, and AI-lab/company outcomes (e.g.,
dropped: "OpenAI discovers the first proof of the Collatz conjecture" — a capability milestone;
"Will OpenAI raise over $5B by end of 2024" — a lab/company outcome; "AI-generated YouTube video
reaches 10M views" — adoption/impact). Extrapolated, ~240–380 questions may be wrongly excluded.
The audit of 40 KEPT questions found 40/40 relevant (precision is not the problem).
Decision: (1) Rewrite the classifier prompt as v1.1, aligned verbatim to DATA.md's five
categories (benchmarks/saturation; model releases and capabilities incl. AI-achieved milestones;
compute/scaling; adoption/impact of AI; AI-lab/company outcomes), still excluding personal/joke
questions, market-meta questions, personnel gossip, naming trivia, and governance/regulation-only
questions. (2) Re-run the FULL candidate pool under v1.1 (~$0.87 batched); both versions'
decisions stay cached and auditable; the final sample uses v1.1 only — no per-question
cherry-picking between versions. (3) Snapshot inclusion rule, made explicit: a question enters
the sample only if it has ≥1 bet at/before T; the AMM initial price is not a crowd forecast, so
no refill from 0-trade questions (step A's 2 attempted refills are discarded).
Reasoning: The sample must match the pre-registered domain definition (DATA.md), not a silently
narrowed one — this is enforcement of pre-registration, not a definition change. The fix is
decided before any elicitation or outcome analysis on the affected questions, so it cannot be
outcome-driven. Full re-run (not drops-only reclassification) keeps the procedure symmetric.
Consequences: +~$0.87 classifier cost; strata Ns change (recorded in EXPERIMENTS/log once
re-run completes); classifier v1.0 decisions retained for audit; a residual borderline band
(e.g., governance questions) is documented as excluded BY RULE in the datasheet.

### D-014 — Actual Phase-2 Ns; close-date contamination refinement; pre-registered sensitivity set   (status: accepted; refines D-006, updates D-011 §5)   2026-07-16
Context: Pre-elicitation red-team audit (2026-07-16) of the v1.1 sample found four issues.
(1) D-011 declared RQ3 confirmatory citing haiku-clean N≈791; after LLM classification (D-013)
and snapshot feasibility, the actual haiku-clean N = 390 — the confirmatory label must rest on
the actual N. (2) 38/390 haiku-clean questions have close_at BEFORE haiku's training cutoff
(worst gap 549 days): the question window ended pre-cutoff and only the platform's formal
resolution timestamp is post-cutoff (admin lag), so the outcome was likely knowable in training
data — D-006's C ≤ T rule keys on resolved_at and does not catch this. (3) 76/390 haiku-clean
questions have close_at < T, where crowd_prob_at_T equals the market's closing price (no trades
after close) and the "as of T" prompt vantage postdates the market's close. (4) Elicited text is
title-only (descriptions were never fetched/stored) — this avoids the post-resolution
description-edit leakage channel (Manifold's API returns current, editable text) but gives
models less information than platform forecasters had.
Decision:
1. **Clean-sample rule refined (per model):** a question is clean for a model with cutoff C iff
   resolved_at ≥ C + 30d AND close_at ≥ C. Questions failing the close_at condition move out of
   that model's clean stratum and are analyzed with the memorization probe, flagged
   `close_before_cutoff_<model>`. Applied per model cutoff (haiku 2025-07-31; sonnet/opus
   2026-01-31); actual Ns after flagging are recorded in the manifest and EXPERIMENTS.
2. **RQ3 status at actual N:** haiku-clean confirmatory N = 352 (390 − 38); power ≈99% at pilot
   ρ̂ = 0.57 per the recon power sketch (80% threshold ≈ N 200) — CONFIRMATORY label re-affirmed
   on the actual sample. D-011 §5's N≈791 figure is superseded. Jan-2026 subset remains
   EXPLORATORY (N = 102 before per-model close_at flagging).
3. **Pre-registered sensitivity analyses** (Phase 3, reported regardless of outcome):
   (a) RQ1–RQ3 with vs. without the close_before_cutoff questions; (b) RQ1/RQ3 with vs. without
   close_at < T questions (crowd snapshot = closing price for those).
4. **Title-only elicitation retained deliberately** (historical description text is not
   retrievable; current text is a leakage channel). Documented as a limitation with its
   direction: the crowd has an information advantage, so model-beats-crowd findings are
   conservative and crowd-beats-model findings must note the asymmetry.
5. **Provenance fixes before elicitation:** manifest SHA-256 must hash the file bytes as
   written; the stale v1.0 `strata` block is removed (strata_v11 authoritative); manifest phase
   label corrected.
Reasoning: All refinements are decided before any Phase-2 elicitation results exist, so none can
be outcome-driven. The close_at ≥ C condition restores D-006's intent (model at worst
information-disadvantaged vs. the crowd's effective information time, which for a closed market
ends at close_at, not T).
Consequences: Smaller confirmatory N (352, still amply powered); probe side gains 38 flagged
questions (informative for RQ2's memorization contrast); elicitation proceeds over all 1,187
questions regardless (strata are analysis-time labels), so no re-collection is needed.
