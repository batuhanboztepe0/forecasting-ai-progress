---
name: statistical-inference
description: How to do the inference correctly for this study. Use whenever building confidence intervals, running hypothesis tests, comparing forecasters, checking statistical power, or correcting for multiple comparisons. Consult before reporting any p-value or CI so the uncertainty quantification is defensible.
---

# Statistical Inference

Defensible uncertainty for a small-to-moderate, paired, dependent dataset.

## Default to estimation

Lead with effect sizes and CIs; treat significance as secondary. A CI that spans the null is
the finding "undetermined at this sample size" — report it as such.

## Confidence intervals

- **Bootstrap** (resample questions) is the workhorse for score differences, skill scores, and
  P&L — it handles non-normal, dependent statistics. Report the method, resamples, and seed.
- Use **paired** resampling when the same questions are scored by multiple forecasters.
- For proportions/bins use Wilson or Jeffreys, not the normal approximation.

## Hypothesis tests

- Match the test to the pre-registered claim in `SCOPE.md`. Paired differences for
  forecaster comparisons.
- For regressions (calibration slope, encompassing), use robust SEs; cluster if questions share
  structure (e.g., same underlying event/source).
- Report the test, the assumption checks, the effect, and the CI — not a bare p-value.

## Power & sample size

- Before trusting a null, sketch the power: given the observed variance and the post-cutoff N,
  what effect could this study have detected? A null with low power means "underpowered", not
  "no effect". Put this in the recon report and the limitations.

## Multiple comparisons

- The RQ family has several tests. Control the false-discovery rate (Benjamini–Hochberg,
  q = 0.10) across confirmatory tests. Exploratory tests are labeled and not counted as
  confirmatory evidence.

## Common traps

Pseudo-replication (treating dependent observations as independent), unpaired comparisons of
paired data, reading non-significance as proof of no effect, p-hacking via bin/threshold choice,
and forgetting that ECE and skill scores are themselves estimates with sampling error.
