# SCOPE.md — pre-registered research design

**Status:** Phase 0 (feasibility) — pre-registration; v1 design locked (see `docs/DECISIONS.md`
D-005..D-009). Freeze this file before Phase 2 data collection; changes after freeze must be
logged in `docs/DECISIONS.md`.

## 1. Motivation

Forecasts about AI progress increasingly inform policy, investment, and governance — including
proposals for early-warning indicators tied to rapid capability gains. Two forecasting sources
are readily available: **prediction-market / community crowds** and **large language models**.
Their quality on the *AI-progress domain specifically* is under-examined, and the standard
comparison (an accuracy horse-race) obscures the more useful question of whether the two
sources encode *different* information. This project measures calibration, separates genuine
skill from training-data memorization, and tests for incremental information content.

Framing draws on the economics of transformative AI (e.g., work on when automating AI research
could produce explosive growth, and scenario analyses of the AGI transition) and on ongoing
efforts to forecast AI progress. Full references live in the report's bibliography; the build
maintains a working reference list under `docs/` (see `literature-review` skill).

## 2. Research questions and pre-registered hypotheses

Each hypothesis has a **direction**, a **test**, and a **decision threshold** fixed in advance.
Report effect sizes and confidence intervals, not just p-values. Control the false-discovery
rate across the hypothesis family (Benjamini–Hochberg, q = 0.10).

- **RQ1 — Calibration.**
  - **H1.** AI-progress forecasts are miscalibrated in a *directional* way (systematic over- or
    under-prediction of progress). Test: calibration-in-the-large (mean forecast vs. base rate)
    + calibration slope from a logistic recalibration regression. Threshold: reject "well
    calibrated" if calibration-in-the-large differs from 0 at the 95% level with |bias| ≥ 0.05.
- **RQ2 — Skill vs. memorization.**
  - **H2.** Apparent model skill drops on questions resolving *after* the model's cutoff.
    Test: paired difference in Brier skill score, pre- vs. post-cutoff, per model. Threshold:
    report per-model effect + CI; flag any model whose post-cutoff skill CI includes ≤ 0
    (no better than the naive base-rate forecaster).
  - Pre-cutoff performance is treated as a **memorization probe**, not evidence of foresight.
- **RQ3 — Information content (the differentiated core).**
  - **H3a.** The market carries information about resolution beyond the model's forecast.
  - **H3b.** The model carries information beyond the market.
    Test: forecast-encompassing regression (resolution ~ logit(market) + logit(model)); a
    source "encompasses" the other if the other's coefficient is not distinguishable from 0.
    Report both directions; the interesting, publishable outcomes are asymmetric encompassing.
  - **Power & fallback (pre-registered, D-008).** RQ3 hinges on adequate clean N *and* on the
    market/model forecasts not being so collinear that the encompassing coefficients are
    unidentified. Phase-0 recon reports the clean N and the market–model forecast correlation and
    sketches power. If underpowered, RQ3 is reported as **exploratory** (pooled/descriptive),
    never as a confirmatory finding.
- **RQ4 — Microstructure / economic value.**
  - **H4.** Any calibration/accuracy edge on post-cutoff questions does **not** survive
    realistic frictions (liquidity, slippage, fees). Test: friction-aware backtest P&L with
    bootstrap CI; secondary — does post-hoc recalibration (Platt / isotonic, fit out-of-sample)
    move P&L? Threshold: report P&L CI; "survives" only if it excludes ≤ 0 net of costs.

Null results on any hypothesis are reported as findings.

## 3. In scope / out of scope

**In:** resolved *binary* AI-progress questions; public crowd/market data; a fixed LLM panel;
proper scoring, calibration, encompassing tests, a friction-aware backtest; one released
dataset artifact.

**Out (for v1):** non-binary/numeric questions; live/forward trading; fine-tuning; causal
claims about *why* a source is (mis)informed; non-AI-progress domains. These are "future work".

**v1 scope cut (D-005).** v1 delivers RQ1–RQ3 as the confirmatory core and RQ4 as a
**preliminary** check (play-money frictions, reported with caveats; first to be deferred to
future work if time is short). Single 30-day snapshot horizon (D-007); ~3-model panel (D-009).
Multi-horizon robustness and a real-money RQ4 are future work.

## 4. Success criteria

The project succeeds if it delivers, regardless of which way the results fall:
1. A reproducible pipeline (clean-checkout reproduction of headline numbers).
2. A curated, documented, versioned dataset of AI-progress forecasts with resolutions.
3. Clear answers (or well-characterized nulls) to RQ1–RQ4 with effect sizes + CIs.
4. A written report in the human's thesis voice, honestly situated against prior work.

**Quality bar target: 8/10** reliably; **9/10** is reachable only if RQ3 yields a genuine,
characterizable information asymmetry *and* the dataset artifact is clean and reusable.

**What this project stands on.** The contribution is the *design and honesty* — contamination
control, the information-content reframing, pre-registration, reproducibility, and a reusable
dataset — not any particular empirical outcome. A cleanly characterized null is a success; the
methodology's job is to make whatever result emerges trustworthy. We report the real numbers with
CIs and do not stake the project's value on which way they fall.

## 5. Deliverables

- Public GitHub repo (this).
- `data/release/` dataset + datasheet.
- `paper/` report (LaTeX → PDF), figures reproducible from `src/`.
- Optional: a short write-up suitable for a blog/preprint.

## 6. Budget & guardrails

- LLM API: target the full run under ~USD 20–35 via batching + prompt caching; hard stop and
  escalate if a single run is projected to exceed USD 25. Track every run in
  `docs/EXPERIMENTS.md`.
- Time: **v1 is a deadline-boxed sprint** (MVP by day 2; see `HANDOFF.md` schedule), phased with
  gates. MVP first, no premature scaling. If a gate slips, de-scope RQ4 before compromising the
  RQ1–RQ3 core.

## 7. Phase checklist (update in place)

- [ ] Phase 0 — feasibility (novelty verdict + data recon) — **blocking**
- [ ] Phase 1 — MVP end-to-end thin slice
- [ ] Phase 2 — full data + scoring core (tested)
- [ ] Phase 3 — RQ1–RQ4 analyses + red-team
- [ ] Phase 4 — write-up + dataset release + reproducibility check

## 8. Design decisions (resolved; recon-dependent items flagged)

- **Snapshot lead time:** single **T = 30 days** before `resolved_at` for v1 (D-007); 7/90-day
  robustness is future work.
- **Contamination rule:** **C ≤ T** — model cutoff at or before the snapshot, stricter than
  "resolved after cutoff", to close the information-recency leak (D-006).
- **Model panel:** ~3 models with published cutoffs spanning capability, batched + cached,
  cost-bounded; exact list set after recon (older cutoffs give more post-cutoff N) (D-009).
- **Source mix:** both Metaculus and Manifold queried in recon; the clean post-cutoff N (and RQ4
  liquidity) decides the primary (D-009).
- **Elicitation repeats:** set in Phase 0 from a cost/variance sketch (small, e.g. 3–5).
- **Ambiguous/annulled resolutions:** dropped, count logged (per `DATA.md`).
