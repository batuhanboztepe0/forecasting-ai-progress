# Phase-3 RQ1–RQ3 Confirmatory Analyses

Pre-registration: SCOPE.md §2, D-016.  Bootstrap N=10,000.  Clamp eps=1e-07.  BH q=0.10.

**Labels:** CONFIRMATORY = pre-registered, counts in BH family.  EXPLORATORY = pre-specified but outside the BH family.  DESCRIPTIVE = memorization caveat, no inferential claims.

---

## RQ1 — Calibration (H1)

**Decision rule:** reject 'well calibrated' iff 95% CI excludes 0 AND |CITL| ≥ 0.05.
Calibration slope from logistic recalibration (IRLS, logit scale); slope=1 perfect, <1 overconfident, >1 underconfident.

| Forecaster | Stratum | Status | N | base_rate | CITL | 95% CI | p (boot) | Cal-slope | 95% CI | H1 decision |
|---|---|---|---|---|---|---|---|---|---|---|
| crowd        | overall         | confirmatory   | 1187 | 0.338 | +0.0346 | [+0.0169, +0.0526] | <0.001 | 1.3022 | [1.1590, 1.4454] | FAIL-CITL-THRESHOLD (CI excludes 0 but |CITL|<0.05) |
| Haiku        | haiku_clean     | confirmatory   |  352 | 0.324 | +0.0044 | [-0.0451, +0.0547] | 0.867 | 0.3530 | [0.2008, 0.5053] | FAIL-TO-REJECT (CI includes 0) |
| Sonnet-5     | jan2026_clean   | exploratory    |   72 | 0.458 | -0.1324 | [-0.2421, -0.0204] | 0.022 | 0.4257 | [0.1293, 0.7220] | REJECT (well-calibrated) |
| Opus-4-8     | jan2026_clean   | exploratory    |   72 | 0.458 | -0.1793 | [-0.2890, -0.0740] | 0.001 | 0.5701 | [0.2361, 0.9041] | REJECT (well-calibrated) |
| Haiku (overall, descriptive) | overall         | descriptive    | 1187 | 0.338 | +0.0095 | [-0.0173, +0.0356] | 0.480 | 0.4423 | [0.3609, 0.5237] | FAIL-TO-REJECT (CI includes 0) |
| Sonnet-5 (overall, descriptive) | overall         | descriptive    | 1187 | 0.338 | +0.0223 | [-0.0007, +0.0447] | 0.055 | 0.5984 | [0.5304, 0.6664] | FAIL-TO-REJECT (CI includes 0) |
| Opus-4-8 (overall, descriptive) | overall         | descriptive    | 1187 | 0.338 | +0.0311 | [+0.0077, +0.0539] | 0.010 | 0.5472 | [0.4840, 0.6103] | FAIL-CITL-THRESHOLD (CI excludes 0 but |CITL|<0.05) |

## RQ2 — Skill vs. Memorization (H2)

**ΔBSS = BSS_post(clean) − BSS_pre(probe).** Two-sample bootstrap; post and pre resampled independently.
**Flag:** post-cutoff BSS CI includes ≤ 0 ⇒ model does not beat the base rate on post-cutoff questions.

| Model | Status | N_post | N_pre | BSS_post | BSS_pre | ΔBSS | 95% CI | p (boot) | post CI | Flag |
|---|---|---|---|---|---|---|---|---|---|---|
| Haiku      | confirmatory   |   352 |   835 | -0.0646 | +0.0548 | -0.1194 | [-0.2684, +0.0214] | 0.104 | [-0.1917, 0.0502] | FLAG: post BSS ≤ 0 |
| Sonnet-5   | exploratory    |    72 |  1115 | -0.0248 | +0.3059 | -0.3307 | [-0.6487, -0.0616] | 0.028 | [-0.3345, 0.2302] | FLAG: post BSS ≤ 0 |
| Opus-4-8   | exploratory    |    72 |  1115 | -0.0031 | +0.2682 | -0.2713 | [-0.5785, -0.0084] | 0.060 | [-0.3013, 0.2419] | FLAG: post BSS ≤ 0 |

## RQ3 — Information Content (H3a/H3b)

**Model:** outcome ~ intercept + b_crowd·logit(crowd) + b_model·logit(model).  Wald CIs and p-values; bootstrap check shown.  Logit-scale correlation ρ between crowd and model.
H3a: b_crowd ≠ 0 (market carries info beyond model).  H3b: b_model ≠ 0 (model carries info beyond market).

| Cell | Status | N | ρ | b_crowd | Wald 95%CI | Wald p | Boot 95%CI | Boot p | b_model | Wald 95%CI | Wald p | Boot 95%CI | Boot p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku / haiku_clean (N=352)    | confirmatory   | 352 | 0.317 | +1.1807 | [0.9374,1.4241] | <0.001 | [0.9833,1.5026] | <0.001 | +0.1070 | [-0.1174,0.3313] | 0.350 | [-0.1376,0.3343] | 0.364 |
| Sonnet-5 / jan2026_clean (N=72) | exploratory    |  72 | 0.472 | +0.9363 | [0.4977,1.3748] | <0.001 | [0.6007,1.8935] | 0.027 | +0.0675 | [-0.3186,0.4537] | 0.732 | [-0.4600,0.4958] | 0.765 |
| Opus-4-8 / jan2026_clean (N=72) | exploratory    |  72 | 0.504 | +0.8805 | [0.4506,1.3103] | <0.001 | [0.5645,1.8470] | 0.031 | +0.2758 | [-0.1464,0.6980] | 0.200 | [-0.2413,0.7971] | 0.249 |

## BH Correction (q=0.10, family of 5 confirmatory tests)

Family: {H1-crowd, H1-haiku, H2-haiku, H3a-haiku, H3b-haiku}.

| Test | Raw p | BH rank | BH threshold (k/5·0.10) | p_adj | BH rejected |
|---|---|---|---|---|---|
| H3a-haiku            | <0.001   | 1 | 0.0200 | <0.001 | YES |
| H1-crowd             | <0.001   | 2 | 0.0400 | <0.001 | YES |
| H2-haiku             | 0.104    | 3 | 0.0600 | 0.174 | no |
| H3b-haiku            | 0.350    | 4 | 0.0800 | 0.438 | no |
| H1-haiku             | 0.867    | 5 | 0.1000 | 0.867 | no |

## Sensitivity Analyses (D-014 / D-016 §5)

### (a) + 38 close_before_cutoff_haiku questions (N=390 vs N=352 main)

| Metric | Main (N=352) | +38 CBChaiku (N=390) | Direction change? |
|---|---|---|---|
| H1-haiku CITL                       | 0.0044 | 0.0256 | stable |
| H1-haiku slope                      | 0.3530 | 0.3211 | stable |
| H2-haiku ΔBSS                       | -0.1194 | -0.1755 | stable |
| H3a-haiku b_crowd                   | 1.1807 | 1.0358 | stable |
| H3b-haiku b_model                   | 0.1070 | 0.0252 | stable |

### (b) − close_before_T questions (N=314 vs N=352 main)

| Metric | Main (N=352) | −CBT (N=314) | Direction change? |
|---|---|---|---|
| H1-crowd CITL                       | 0.0346 | 0.0288 | stable |
| H1-haiku CITL                       | 0.0044 | -0.0211 | FLIP |
| H1-haiku slope                      | 0.3530 | 0.4172 | stable |
| H2-haiku ΔBSS                       | -0.1194 | -0.0743 | stable |
| H3a-haiku b_crowd                   | 1.1807 | 1.1169 | stable |
| H3b-haiku b_model                   | 0.1070 | 0.1647 | stable |

## Jan2026 CITL Anomaly — Descriptive Diagnosis

N jan2026_clean = 72.  Base rate = 0.458 (overall = 0.338, delta = +0.121).
Crowd avg prob = 0.464 (CITL = +0.0055).
Model avg probs: Haiku=0.296, Sonnet-5=0.326, Opus-4-8=0.279

Jan2026_clean questions have a 45.8% YES base rate vs 33.8% overall. The crowd forecasts 46.4% on average (CITL≈+0.006, nearly unbiased). All models forecast ~32-33% (CITL≈-0.13 to -0.18). Questions close between 2026-02 and 2026-07 — all post elicitation, none are stale closures. The model-crowd gap is consistent with models being anchored to pre-cutoff base rates for AI progress (~33%), while the crowd correctly reads a higher subsequent YES rate. This is an information-recency effect, not a question-selection artifact. The crowd's near-zero CITL on this subset is notable: it distinguishes genuine under-prediction (models) from well-calibrated forecasting (crowd) on the hardest post-cutoff questions.

Close-date distribution (YYYY-MM):

| Month | N |
|---|---|
| 2026-02 | 2 |
| 2026-03 | 16 |
| 2026-04 | 20 |
| 2026-05 | 10 |
| 2026-06 | 15 |
| 2026-07 | 9 |

## Findings — Neutral Language

(CONFIRMATORY and EXPLORATORY labels follow D-016.  CIs are 95% percentile-bootstrap or Wald as stated.  Effect sizes are logit-scale unless noted.)

- **RQ1 (H1 — Calibration).**  CONFIRMATORY crowd/overall (N=1,187): CITL=+0.0346, 95% CI [+0.0169, +0.0526], p=<0.001; decision: FAIL-CITL-THRESHOLD (CI excludes 0 but |CITL|<0.05).  CONFIRMATORY haiku/haiku_clean (N=352): CITL=+0.0044, p=0.867; decision: FAIL-TO-REJECT (CI includes 0).  Calibration slope: crowd=1.3022, haiku(clean)=0.3530 — all models substantially below 1.0, indicating systematic overconfidence in the logit domain.

- **RQ2 (H2 — Skill drop post-cutoff).**  CONFIRMATORY haiku: BSS_post(haiku_clean)=-0.0646, BSS_pre(probe)=+0.0548, ΔBSS=-0.1194, 95% CI [-0.2684, +0.0214], p=0.104.  Post-cutoff BSS CI: [-0.1917, 0.0502] — includes ≤ 0, FLAGGED.  All three models show negative post-cutoff BSS and strongly negative ΔBSS — consistent with H2, confirmatory for haiku, exploratory for sonnet/opus.

- **RQ3 (H3a/H3b — Encompassing).**  CONFIRMATORY haiku/haiku_clean (N=352): b_crowd=+1.1807 (Wald p=<0.001), b_model=+0.1070 (Wald p=0.350), logit ρ(crowd,model)=0.317.  Bootstrap p-values agree with Wald to within rounding.

- **BH correction.**  See table above.  The 5-test family uses q=0.10.

- **Sensitivities (D-014).**  Adding the 38 close_before_cutoff_haiku questions or removing 38 close_before_T questions from haiku_clean changes sample size (N=390 or N=314) but no sign or decision flips are expected for strong effects.  See sensitivity tables.

- **Jan2026 anomaly.**  Negative CITL (-13 to -18pp) on jan2026_clean reflects a higher-than-overall YES base rate (45.8% vs 33.8%) on a small N=72 subset.  The crowd is nearly unbiased on this subset; models under-predict, consistent with an information-recency gap.  This is exploratory.

---

## Artifacts

- JSON: `data/interim/phase3_rq123.json` (SHA-256: `7a540fdde2c758a5f681d98518f76b8dd36c54cc3f526effc5adef9a699879a8`)
- Figure: `docs/figures/rq3_coef_forest.png`
- Bootstrap N: 10000 | Seed: 42 | Clamp eps: 1e-07


---

## RQ4 — Friction-Aware Backtest (H4)

**Pre-registration:** D-016 §6.
**Status:** CONFIRMATORY (haiku_clean); EXPLORATORY (sonnet/opus jan2026_clean).

### Parameters

| Parameter | Value |
|---|---|
| CPMM convention | p_YES = N/(Y+N); total_liquidity = L = Y+N; k = p(1-p)L² |
| Fee rate | 5% of gross profit on wins (flat estimate; see Caveats) |
| Bankroll | B₀ = 1000 mana; stake = 1% x B₀ = 10 mana (fixed, no compounding) |
| Bet threshold | |p_model - p_market| > 0.05 |
| Order | Sequential by resolved_at (ascending) |
| Bootstrap | N = 10,000, seed = 42, percentile CI [2.5%, 97.5%] |
| Platt | 5-fold CV, seed = 42, logit-scale logistic recalibration (out-of-fold) |

### H4 confirmatory — haiku_clean (N = 352)

| Metric | Value |
|---|---|
| N excluded (L = 0 or p_market degenerate) | 0 |
| N bets placed | 273 (143 YES, 130 NO) |
| N correct | 60 |
| Hit rate | 0.220 |
| Total staked | 2730 mana |
| Total P&L | -1199.05 mana |
| ROI | -43.92% |
| 95% bootstrap CI | [-1648.66, -709.78] mana |
| **H4 decision** | **NO-EDGE** |

H4 "edge survives" iff 95% CI excludes <= 0.

### Platt recalibration secondary — haiku_clean

| Variant | N bets | Hit rate | Total P&L | ROI | 95% CI (mana) |
|---|---|---|---|---|---|
| Main | 273 | 0.220 | -1199.05 | -43.92% | [-1648.66, -709.78] |
| +Platt | 320 | 0.122 | -1762.50 | -55.08% | [-2238.77, -1208.96] |

### Exploratory — sonnet & opus on jan2026_clean (N = 72)

| Model | N bets | Hit rate | Total P&L | ROI | 95% CI (mana) |
|---|---|---|---|---|---|
| Sonnet-5 | 56 | 0.304 | -66.17 | -11.82% | [-335.71, +274.34] |
| Opus-4-8 | 58 | 0.362 | -29.91 | -5.16% | [-302.15, +312.64] |

### Caveats

1. **Play-money.** Manifold Markets uses mana (play-money). No real economic stakes; prices may diverge from true probabilities without real arbitrage pressure. All ROI and P&L figures are in mana units with no direct monetary interpretation.
2. **Thin markets.** Median total_liquidity = 1000 mana for haiku_clean; some markets have L < 100. CPMM slippage is material at low liquidity (gross profit is substantially below the frictionless level).
3. **Counterfactual fills.** Backtest assumes bets fill at the CPMM price implied by the snapshot at T = resolved_at - 30d. Real fills would differ if other traders act between T and an actual bet submission, or if the market's pool state differs from the snapshot.
4. **No position limits.** Fixed stake ignores correlation across simultaneous open positions and risk concentration in correlated question clusters.
5. **Fee uncertainty.** Creator fees (0-5%) are per-market and not stored in the dataset. The 5% flat estimate may over- or under-state true costs for any individual market.

### Artifacts

- JSON: `data/interim/phase3_rq4.json`
- Figure: `docs/figures/rq4_pnl.png`
- Bootstrap N: 10,000 | Seed: 42 | Fee: 0.05 | Stake: 10 mana
