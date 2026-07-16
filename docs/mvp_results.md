# MVP Scoring Results — Phase 1 Thin Slice

**N = 50 questions × 3 models (Haiku, Sonnet-5, Opus-4-8) + Manifold crowd.**  
All figures are descriptive; n = 50 is too small for confirmatory tests or confidence intervals.
Crowd pre/post split uses the Haiku cutoff (2025-07-31) for table symmetry; labeled accordingly.
BSS = Brier Skill Score vs. the climatology (base-rate) forecaster; positive = beats base rate.
CITL = Calibration-in-the-Large (mean forecast − base rate); positive = systematic over-prediction.

## Scores table

| Forecaster | N (pre/post) | Brier overall | Brier pre | Brier post | BSS overall | BSS pre | BSS post | CITL overall |
|---|---|---|---|---|---|---|---|---|
| crowd (haiku split) | 25/25 | 0.0863 | 0.1250 | 0.0477 | +0.6153 | +0.4928 | +0.7387 | +0.0157 |
| Haiku | 25/25 | 0.2572 | 0.2807 | 0.2336 | -0.1460 | -0.1391 | -0.2810 | +0.1872 |
| Sonnet-5 | 35/15 | 0.1208 | 0.1297 | 0.0999 | +0.4617 | +0.4242 | +0.5502 | +0.0628 |
| Opus-4-8 | 35/15 | 0.1153 | 0.1297 | 0.0816 | +0.4863 | +0.4243 | +0.6328 | +0.0938 |

## Observations (descriptive, n = 50, no hypothesis tests)

The Manifold crowd achieves an overall Brier score of 0.0863 (BSS +0.6153 vs. base rate, CITL +0.0157), suggesting it extracts meaningful signal from the question set while remaining close to the base rate on average.
Among the three models, Haiku scores Brier 0.2572 overall (BSS -0.1460, CITL +0.1872); Sonnet-5 scores 0.1208 (BSS +0.4617, CITL +0.0628); Opus-4-8 scores 0.1153 (BSS +0.4863, CITL +0.0938).
Post-cutoff n is 25 for Haiku and only 15 for Sonnet-5 and Opus-4-8; pre/post Brier differences at this sample size are highly variable and should not be interpreted as evidence for or against H2 (RQ2 is Phase-2 confirmatory).
The reliability diagram (docs/figures/mvp_calibration.png) shows that the crowd tracks the diagonal well in the low- and high-probability regions. All three models show non-trivial deviation from perfect calibration at n=50, but with ≤ 12 points per bin, individual bin estimates are noisy.

## Anomaly flags

- FLAG (H2-relevant): Haiku — post-cutoff BSS=-0.2810 ≤ 0 (n_post=25); no better than the naive base-rate on post-cutoff questions. N=50 — do not treat as confirmatory.
- FLAG: Haiku — |CITL|=0.1872 > 0.15; large over-prediction bias.

## Limitations

- n = 50 is the MVP thin slice — diagnostic only.
- No bootstrap CIs at this stage (Phase-2 gate: n ≥ 175 clean post-cutoff questions).
- Single 30-day snapshot horizon per D-007; no multi-horizon robustness.
- Sonnet-5 and Opus-4-8 share the same training cutoff (2026-01-31), so their post-cutoff N is only 15, limiting pre/post contrast for those models.
- Reliability diagram uses 5 fixed-width bins; with n ≤ 12 per bin, calibration estimates are unstable.
- Crowd CITL could reflect prediction-market microstructure (thin markets, fee pressure) as well as forecaster bias.
- Single-provider model panel (Anthropic only); no cross-provider generalization (D-011).

## Artifacts

- Figure: `docs/figures/mvp_calibration.png`
- Scores: `data/interim/mvp_scores.csv`
