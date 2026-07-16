# Protocol v2 Sensitivity Check

**Status: descriptive documentation only — n = 50, no hypothesis tests, no CIs.**
Protocol v2 (reasoning-first elicitation) was adopted a priori on literature grounds per D-012
before any accuracy data were examined. This table documents sensitivity; it is not a selection
criterion and does not alter the D-012 decision.

---

## Score comparison: v1 (bare-JSON ask) vs. v2 (reasoning-first)

Crowd row is identical in both protocols because the same Manifold market snapshots are used;
it is shown once for reference. Model pre/post splits are unchanged (same questions, same cutoffs).

| Forecaster | Protocol | N (pre/post) | Brier overall | Brier pre | Brier post | BSS overall | BSS pre | BSS post | CITL overall |
|---|---|---|---|---|---|---|---|---|---|
| crowd (haiku split) | v1 = v2 | 25/25 | 0.0863 | 0.1250 | 0.0477 | +0.6153 | +0.4928 | +0.7387 | +0.0157 |
| Haiku | v1 | 25/25 | 0.2572 | 0.2807 | 0.2336 | -0.1460 | -0.1391 | -0.2810 | +0.1872 |
| Haiku | v2 | 25/25 | 0.1603 | 0.1942 | 0.1265 | +0.2854 | +0.2117 | +0.3067 | +0.0552 |
| Sonnet-5 | v1 | 35/15 | 0.1208 | 0.1297 | 0.0999 | +0.4617 | +0.4243 | +0.5502 | +0.0628 |
| Sonnet-5 | v2 | 35/15 | 0.1372 | 0.1428 | 0.1241 | +0.3887 | +0.3663 | +0.4415 | +0.0758 |
| Opus-4-8 | v1 | 35/15 | 0.1153 | 0.1297 | 0.0816 | +0.4863 | +0.4243 | +0.6328 | +0.0938 |
| Opus-4-8 | v2 | 35/15 | 0.1184 | 0.1205 | 0.1135 | +0.4723 | +0.4651 | +0.4892 | +0.0894 |

BSS = Brier Skill Score vs. base-rate (climatology) forecaster; positive = beats base rate.
CITL = Calibration-in-the-Large (mean forecast − base rate); positive = systematic over-prediction.

---

## Distinct-probability counts (probability diversity indicator)

Rounding to two decimal places per protocol; more distinct values suggests a richer probability
distribution rather than clustering at a small grid of values.

| Forecaster | v1 distinct probs | v2 distinct probs |
|---|---|---|
| Haiku | 8 | 19 |
| Sonnet-5 | 22 | 20 |
| Opus-4-8 | 21 | 25 |

---

## Descriptive observations (n = 50; no hypothesis tests)

Under protocol v2, Haiku's Brier score improves substantially (0.257 → 0.160) and its
previously anomalous negative BSS (−0.146) becomes positive (+0.285); the large CITL bias
(+0.187 v1) also drops markedly (+0.055 v2), and the v1 anomaly flags for Haiku are absent
under v2. This is consistent with the literature finding (ForecastBench, arXiv 2409.19839)
that brief reasoning improves elicitation most for weaker models. Sonnet-5 shows a small
Brier increase (0.121 → 0.137) and Opus-4-8 is essentially unchanged (0.115 → 0.118);
the direction of these small differences is within the noise expected for n = 50 and
does not constitute evidence against v2. The crowd row is identical across protocols
because it uses the same Manifold market snapshots; no re-elicitation occurred. Haiku's
distinct-probability count rises from 8 to 19 under v2, consistent with reasoning eliciting
a richer probability scale rather than over-concentrating on a small discrete grid.

---

## Adoption statement

Protocol v2 was selected a priori on literature grounds (D-012, 2026-07-16) before any
protocol-accuracy data on the 50-question thin slice were examined. The table above is
sensitivity documentation only — it characterizes how scores differ across protocols for
the same question set and is not used as a selection criterion. The v2 adoption stands
regardless of which protocol produces numerically lower Brier scores on these 50 questions.

---

## Limitations

- n = 50 is the MVP thin slice; protocol-sensitivity differences at this scale are highly
  variable and must not be interpreted as confirmatory evidence for either protocol.
- No bootstrap CIs or hypothesis tests at this stage; descriptive only.
- Crowd row is unchanged by design (same Manifold snapshots); crowd-vs-model differences
  are not affected by the protocol comparison.
- Single 30-day snapshot horizon per D-007; no multi-horizon robustness.
- Single-provider panel (Anthropic only) per D-011; no cross-provider generalization.

## Artifacts

- v2 scores: `data/interim/mvp_scores_v2.csv` (SHA-256: 47bb9c858f05e546b71fcb28ac280f683b645ba04c832477d7741751229e18a9)
- v2 figure: `docs/figures/mvp_calibration_v2.png`
- Scoring code: `src/analysis/score_mvp.py` (run with `--protocol v2`)
- API calls made: 0 (pure scoring computation on cached elicitation data)
