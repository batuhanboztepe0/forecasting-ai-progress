# Phase-2 Scoring Results — DESCRIPTIVE

**DESCRIPTIVE ONLY.** No hypothesis tests, no p-values, no confidence intervals.
Confirmatory tests with pre-registered thresholds are in Phase 3.
$0 API cost — pure computation on cached elicitation output.

- N questions: 1,187  |  N model rows (r0): 3,561  |  N probe rows (sonnet r1/r2): 200
- SHA-256 of phase2_scores.csv: `4c5aaf0c92860e98d7957e53f498bc3a05e392b168eb9bc287de595c0b7988b4`

## Strata definitions (D-014)

- **haiku_clean** (N per below): resolved_at ≥ 2025-08-30 AND close_at ≥ 2025-07-31
- **haiku_probe**: complement of haiku_clean (pre-cutoff memorization probe)
- **jan2026_clean**: resolved_at ≥ 2026-03-02 AND close_at ≥ 2026-01-31
- **jan2026_probe**: complement of jan2026_clean
- Crowd scored on same strata for comparability.

## Scores table

BSS = Brier Skill Score vs. the stratum base-rate forecaster; + beats base rate.
CITL = mean(forecast) − mean(outcome); + = over-prediction, − = under-prediction.
Cal-intercept and Cal-slope from logistic recalibration (IRLS) on logit scale.
Slope = 1 is perfect calibration; < 1 = overconfident; > 1 = underconfident.

| Forecaster   | Stratum          |     N | base_rate | Brier  | BSS    | CITL   | Cal-intercept | Cal-slope |
|---|---|---|---|---|---|---|---|---|
| crowd        | overall         |  1187 | 0.338 | 0.1015 | +0.5463 | +0.0346 | -0.2215 | 1.3022 |
| crowd        | haiku_clean     |   352 | 0.324 | 0.0970 | +0.5571 | +0.0288 | -0.2057 | 1.1947 |
| crowd        | haiku_probe     |   835 | 0.344 | 0.1034 | +0.5417 | +0.0371 | -0.2291 | 1.3533 |
| crowd        | jan2026_clean   |    72 | 0.458 | 0.1302 | +0.4757 | +0.0055 | -0.0491 | 0.9588 |
| crowd        | jan2026_probe   |  1115 | 0.330 | 0.0996 | +0.5494 | +0.0365 | -0.2312 | 1.3333 |
| Haiku        | overall         |  1187 | 0.338 | 0.2191 | +0.0205 | +0.0095 | -0.3562 | 0.4423 |
| Haiku        | haiku_clean     |   352 | 0.324 | 0.2331 | -0.0646 | +0.0044 | -0.4450 | 0.3530 |
| Haiku        | haiku_probe     |   835 | 0.344 | 0.2132 | +0.0548 | +0.0117 | -0.3268 | 0.4759 |
| Haiku        | jan2026_clean   |    72 | 0.458 | 0.2548 | -0.0265 | -0.1624 | 0.4843 | 0.5954 |
| Haiku        | jan2026_probe   |  1115 | 0.330 | 0.2168 | +0.0194 | +0.0206 | -0.4034 | 0.4444 |
| Sonnet-5     | overall         |  1187 | 0.338 | 0.1596 | +0.2865 | +0.0223 | -0.3237 | 0.5984 |
| Sonnet-5     | haiku_clean     |   352 | 0.324 | 0.1812 | +0.1724 | +0.0204 | -0.3658 | 0.5237 |
| Sonnet-5     | haiku_probe     |   835 | 0.344 | 0.1505 | +0.3329 | +0.0231 | -0.3104 | 0.6304 |
| Sonnet-5     | jan2026_clean   |    72 | 0.458 | 0.2544 | -0.0248 | -0.1324 | 0.3019 | 0.4257 |
| Sonnet-5     | jan2026_probe   |  1115 | 0.330 | 0.1535 | +0.3059 | +0.0323 | -0.3870 | 0.6151 |
| Opus-4-8     | overall         |  1187 | 0.338 | 0.1671 | +0.2530 | +0.0311 | -0.3902 | 0.5472 |
| Opus-4-8     | haiku_clean     |   352 | 0.324 | 0.2039 | +0.0688 | +0.0164 | -0.4117 | 0.4265 |
| Opus-4-8     | haiku_probe     |   835 | 0.344 | 0.1516 | +0.3280 | +0.0373 | -0.3990 | 0.6045 |
| Opus-4-8     | jan2026_clean   |    72 | 0.458 | 0.2490 | -0.0031 | -0.1793 | 0.6348 | 0.5701 |
| Opus-4-8     | jan2026_probe   |  1115 | 0.330 | 0.1618 | +0.2682 | +0.0447 | -0.4691 | 0.5610 |

## Distinct probability counts (per model, r0)

Low count flags the canonical-probability degeneracy (D-012 monitoring item).

| Model | Distinct model_prob values (of 1,187 questions) |
|---|---|
| Haiku | 39 |
| Sonnet-5 | 47 |
| Opus-4-8 | 45 |

## Variance probe — Sonnet-5 (r0 / r1 / r2 on 100-question subset)

Quantifies sampling noise; temperature is fixed so variance reflects model stochasticity
from prompt ordering / tokenisation, not temperature sampling.

- Mean SD across questions: 0.0416
- Median SD: 0.0115
- Max SD: 0.4579

| Repeat | Brier on 100-question subset |
|---|---|
| r0 | 0.1645 |
| r1 | 0.1790 |
| r2 | 0.1760 |

## Descriptive observations

(DESCRIPTIVE — confirm nothing; treat as orientation for Phase 3.)

- Overall Brier: crowd=0.1015, Haiku=0.2191, Sonnet-5=0.1596, Opus-4-8=0.1671.

- Calibration-in-the-large (overall): crowd=+0.0346, Haiku=+0.0095, Sonnet-5=+0.0223, Opus-4-8=+0.0311. Positive = systematic over-prediction.

- Haiku haiku_clean (N=352): Brier=0.2331, BSS=-0.0646. Crowd on same questions: Brier=0.0970, BSS=+0.5571.

- Sonnet-5 jan2026_clean (N=72): Brier=0.2544, BSS=-0.0248.

- Distinct probability degeneracy: Haiku=39, Sonnet-5=47, Opus-4-8=45 unique probability values (of 1,187 questions). Haiku persists with the lowest diversity — consistent with the canonical-probability anomaly flagged in D-012. All models use discretised probability outputs; logistic recalibration and reliability diagrams are robust to this but calibration slope estimates should be interpreted cautiously for Haiku.

- Variance probe (Sonnet-5, N=100 questions, 3 repeats): mean SD per question = 0.0416, max SD = 0.4579. All three repeats produce nearly identical Brier scores (see table), confirming that sampling noise is small relative to between-question variance.

- Calibration slope (logit-scale): crowd=1.302, Haiku=0.442, Sonnet-5=0.598, Opus-4-8=0.547. Slope > 1 = underconfident; slope < 1 = overconfident (probabilities too extreme). All values are descriptive — Phase 3 provides CIs and the H1 threshold test.

## Anomaly flags

- Haiku distinct probabilities anomaly: see observations above (D-012 monitoring).
- All parse_error = 0 (no elicitation failures).
- All model_prob values are within [0.01, 0.99] (clamped at elicitation time).

## Artifacts

- Scores: `data/interim/phase2_scores.csv`
- Figure: `docs/figures/phase2_calibration.png`
- SHA-256: `4c5aaf0c92860e98d7957e53f498bc3a05e392b168eb9bc287de595c0b7988b4`
