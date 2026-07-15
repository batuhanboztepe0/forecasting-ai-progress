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

<!-- Add D-010+ as the project makes further decisions (final panel/source after recon, any
     post-freeze hypothesis change, metric/analysis choices). -->
