---
name: forecasting-evaluation
description: How to score and compare probabilistic forecasts correctly. Use whenever computing Brier or log-loss, building reliability diagrams, measuring calibration (ECE, calibration-in-the-large, calibration slope), decomposing a score, or comparing forecasters (skill scores, encompassing). Consult before writing any metric code so the scoring is proper and the calibration analysis is sound.
---

# Forecasting Evaluation

Correct measurement of binary probabilistic forecasts. Implement metrics as pure, unit-tested
functions.

## Proper scoring rules

- **Brier score:** mean of `(p - y)^2` over questions, `y ∈ {0,1}`. Lower is better. Proper.
- **Log-loss:** `-mean(y·log p + (1-y)·log(1-p))`. Proper; sensitive to confident errors —
  clip probabilities to `[ε, 1-ε]` and report ε.
- Use proper rules only. Do not score with accuracy/thresholded metrics for probability quality.

## Decomposition (Murphy / Brier)

`Brier = Reliability − Resolution + Uncertainty` (over bins).
- **Reliability:** calibration error (lower is better).
- **Resolution:** how much forecasts separate outcomes (higher is better).
- **Uncertainty:** base-rate variance `p̄(1−p̄)` — a property of the questions, not the forecaster.
Report all three; they explain *why* a forecaster scores as it does.

## Calibration

- **Reliability diagram:** binned predicted vs. observed frequency, with per-bin CIs
  (Wilson/Jeffreys). Use quantile bins to keep counts stable; report bin counts.
- **ECE:** weighted mean |predicted − observed| across bins. Report bin scheme + count; ECE is
  scheme-sensitive.
- **Calibration-in-the-large:** mean forecast vs. overall base rate (directional bias).
- **Calibration slope:** from `logit(y) ~ a + b·logit(p)`. b=1 well-calibrated; b<1
  over-confident; b>1 under-confident. `a` captures systematic bias.

## Comparing forecasters

- **Skill score** vs. a reference (use the base-rate/climatology forecaster):
  `1 − Brier_model / Brier_ref`. >0 beats the reference.
- **Paired comparison:** compare per-question score differences (paired bootstrap / paired
  test), not unpaired means — the same questions are scored by each forecaster.
- **Encompassing (information content):** regress `outcome ~ logit(f_A) + logit(f_B)`; a
  forecaster "encompasses" the other if the other's coefficient is indistinguishable from 0.
  Report both directions.

## Pitfalls

Probabilities of exactly 0/1 (clip), tiny bins (unstable calibration), unpaired comparisons,
mixing questions with wildly different base rates without noting it, and treating a lower Brier
as "skill" without the memorization/cutoff control.
