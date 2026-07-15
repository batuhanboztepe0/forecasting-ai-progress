---
name: research-methodology
description: Rigorous empirical-research practice for this study. Use whenever designing an experiment, defining a hypothesis, deciding what counts as evidence, or worrying about validity, confounds, pre-registration, or honest reporting of null results. Consult this before running any analysis that will feed a claim, and any time someone proposes changing a hypothesis or interpreting a result.
---

# Research Methodology

Empirical rigor for a forecasting-evaluation study. The goal is credible, reproducible claims —
including credible *negative* claims.

## Pre-registration

- Fix RQs, directional predictions, tests, and decision thresholds **before seeing outcomes**
  (`SCOPE.md`). Freeze before Phase 2.
- Confirmatory = pre-registered. Everything else is **exploratory** and must be labeled so in
  the report. Exploratory findings suggest hypotheses; they don't confirm them.
- Any post-freeze change is a logged decision (`docs/DECISIONS.md`) with reasoning.

## Validity

- **Internal:** the biggest threats here are data leakage (outcome reaching a forecaster) and
  training-data contamination. Snapshot strictly pre-outcome; restrict skill claims to
  post-cutoff questions.
- **Construct:** "AI progress" and "well-calibrated" must be operationalized explicitly; keep
  the classifier prompt and metric definitions versioned.
- **External:** be honest about generalization — play-money markets, a specific question set,
  a specific time window. State these as limitations, don't hide them.

## Evidence standards

- Report **effect size + confidence interval**, not just significance.
- Prefer estimation over binary reject/accept; a wide CI that includes the null is the finding
  "we can't tell", which is legitimate and must be stated.
- Control multiplicity across the hypothesis family (Benjamini–Hochberg).

## Honest null results

A refuted pre-registered hypothesis is a result, not a failure. Do not tune, drop, or reframe
to manufacture a positive. If nothing is significant, that is the paper's honest contribution.

## Reproducibility

Seeded, config-driven, deterministic; raw data preserved (git-ignored) with committed
provenance. A third party should reproduce headline numbers from the repo alone.
