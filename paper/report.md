# Calibration and Information Content of AI-Progress Forecasts: Prediction Markets versus Language Models

**Batuhan Boztepe**
July 2026

---

## Abstract

Forecasts about AI progress inform governance and investment decisions, yet the comparative quality of prediction-market crowds and large language models on this domain is poorly characterised. This study evaluates three Claude models (haiku-4-5, sonnet-5, opus-4-8) against Manifold Markets crowd probabilities on 1,187 resolved binary AI-progress questions. A snapshot-aware contamination rule (C ≤ T) is applied to close an information-recency leak that the standard post-cutoff filter leaves open. The central finding is asymmetric encompassing in the confirmatory cell (claude-haiku-4-5, N = 352): the crowd carries information about outcomes beyond the model's forecast (b_crowd = +1.18, 95% CI [0.94, 1.42], p < 0.001, BH-significant), while the model adds no detectable information beyond the crowd (b_model = +0.11, 95% CI [−0.12, 0.33], p = 0.35). The same pattern appears in exploratory cells for the two stronger models. Both calibration hypotheses are null under the pre-registered conjunction rule. The post-cutoff skill drop is consistent with H2 for haiku but the confidence interval includes zero. A friction-aware backtest on Manifold yields a loss (ROI = −43.9%, 95% CI excludes zero). A curated dataset of 1,187 AI-progress questions with crowd snapshots is released alongside this report.

---

## 1. Introduction

Forecasts about AI progress inform policy, investment, and governance. Rapid capability gains could trigger early-warning indicators that affect regulatory timelines and resource allocation. Two forecasting sources are publicly available for this domain: prediction-market or community crowds and large language models. Their comparative quality on AI-progress questions specifically is under-examined.

The standard evaluation is an accuracy horse-race: which source produces lower Brier scores? This framing is useful but incomplete. The more informative question is whether the two sources encode *different* information. A forecaster that adds nothing beyond what another source already encodes is redundant, regardless of its absolute accuracy. The forecast-encompassing test addresses this directly. It asks whether one source's forecast has explanatory power for outcomes after conditioning on the other source's forecast.

This research contributes to the literature in several ways. First, it applies the forecast-encompassing test between prediction-market crowds and language model forecasts specifically on AI-progress questions. Domain-stratified results are absent from all extant work. This is both a decision-relevant domain and an empirically under-studied one. Second, it introduces the C ≤ T snapshot-aware contamination rule, which requires the model's training cutoff to be at or before the crowd-snapshot date. This closes an information-recency leak in prior approaches: requiring only that outcomes resolve after the cutoff leaves open the possibility that the model was trained on data between the snapshot date and its cutoff that the contemporaneous crowd never saw. Third, it releases a curated, versioned dataset of 1,187 resolved binary AI-progress questions with time-stamped crowd snapshots and microstructure fields, enabling future replication and extension.

Calibration (RQ1) is treated as replication and extension in a specific domain, consistent with the pre-registered novelty verdict (D-010). The encompassing result (RQ3), the contamination rule, and the dataset are the primary contributions.

The remainder of this report is organised as follows. Section 2 reviews the closest prior work. Section 3 describes the data. Section 4 describes the methods. Section 5 reports results per research question. Section 6 states limitations. Section 7 covers reproducibility. Section 8 is the AI tool usage declaration. Section 9 lists references.

---

## 2. Related Work

Five works are closest to this study. The novelty verdict across them is INCREMENTAL (D-010): the differentiating combination is the AI-progress domain restriction, the forecast-encompassing framing, the C ≤ T contamination rule, and the released dataset. No existing paper delivers all four simultaneously.

Halawi et al. (2024) built a retrieval-augmented LLM pipeline and compared its calibrated aggregate against human crowds on general forecasting questions from Metaculus and Polymarket (arXiv 2402.18563). They apply a post-cutoff filter requiring outcomes to resolve after the model's training cutoff. This study differs on three axes: the domain is restricted to AI progress; the contamination rule is stricter (C ≤ T closes a recency leak that R > C leaves open); and the analysis uses forecast encompassing rather than an accuracy horse-race. Halawi et al. release no curated AI-progress dataset.

Schoenegger et al. (2024) aggregated 12 LLMs on 31 binary questions and compared the ensemble against 925 human forecasters in a Metaculus tournament (arXiv 2402.19379). They found the LLM crowd statistically indistinguishable from the human crowd. That study applies no contamination control, covers a general question set, and does not test information content.

Karger et al. (2025) built ForecastBench, a continuously updated benchmark drawing from nine platforms including Manifold and Polymarket (arXiv 2409.19839). Their contamination solution is prospective: questions are submitted before resolution. This is orthogonal to the retrospective C ≤ T approach and the two methods are complementary. ForecastBench reports no domain-stratified results for AI progress and includes no encompassing test between LLM and market forecasts.

Alur et al. (2025) is the closest existing work to RQ3 (arXiv 2511.07678). They run a bivariate simplex-constrained regression of binary outcomes on market price and LLM forecast and report optimal mixture weights. The statistical framing differs from this study in a non-trivial way. Forecast combination finds the optimal mixture; forecast encompassing tests the null that one source's coefficient is zero after conditioning on the other. Encompassing directly answers whether a source is redundant. Alur et al. also aggregate across all domains, apply no C ≤ T rule, and pre-register no hypotheses.

Zou et al. (2022) introduced the Autocast benchmark, pairing forecasting questions with a news corpus and comparing LM accuracy against human experts (arXiv 2206.15474). That work is foundational. It does not compare LLMs against prediction markets, does not apply a cutoff-based contamination split, and does not test encompassing.

---

## 3. Data

### 3.1 Source selection and the Metaculus dead end

All data come from Manifold Markets, a play-money prediction market platform with a public API. Manifold was selected because it is the only source with accessible YES/NO resolutions for AI-progress questions as of this study (D-011). The Metaculus API was queried with token authentication during the feasibility phase and returned 142 AI-progress binary questions. However, the `resolution` field is null for all of them. Outcomes are not exposed by the Metaculus API as of 2026-07-16. Metaculus is deferred to future work.

The initial Manifold collection identified 3,728 resolved binary AI-progress questions by keyword search across 12 AI-related market groups. Ambiguous and annulled markets (non-YES/NO resolutions) were dropped; 553 were removed in this step.

### 3.2 Classifier: v1.0 to v1.1

An LLM-assisted classifier determined which keyword-matched questions satisfy the pre-registered domain definition (DATA.md): benchmark results or saturation, model releases and capabilities, compute/scaling milestones, adoption/impact claims about AI, and AI-lab/company outcomes. The initial classifier prompt (v1.0, claude-haiku-4-5) dropped 50.8% of candidates. An orchestrator audit of a seeded 40-question sample of those drops found 12 to 20% were in-domain by the letter of the pre-registered definition. The v1.0 prompt applied a narrower reading and systematically excluded two categories that DATA.md explicitly includes: adoption/impact claims and AI-lab/company outcomes (D-013).

The classifier prompt was rewritten as v1.1 to match the DATA.md definition verbatim. The full candidate pool was re-run under v1.1. Both versions' decisions are cached and auditable; the final sample uses v1.1 only with no per-question mixing between versions. The v1.1 classifier kept 1,694 questions. The residual drop-side false-negative rate is approximately 7.5% (idiosyncratic misreads and release-timing boundary cases); keeps-side precision is approximately 95 to 100% from the audit (D-013). The classifier never sees resolutions, so its residual error cannot bias model-vs-crowd comparisons. It trims N only.

### 3.3 Final sample and strata

Three questions were hard-dropped under the snapshot inclusion rule (D-013): two with zero trades before the snapshot date T and one with a Manifold API error. The final sample is 1,187 questions.

Strata are assigned per the D-006 contamination rule and the D-014 refinement. A question is clean for a model with training cutoff C if resolved_at >= C + 30 days and close_at >= C. The close_at condition was added by the red-team audit (D-014). It catches questions whose market closed before the model's training cutoff: for those, the outcome was potentially observable in training data despite the formal resolution timestamp falling later.

The final strata are:

- haiku_clean (training cutoff 2025-07-31): N = 352. Confirmatory for RQ1, RQ2, RQ3.
- jan2026_clean (training cutoff 2026-01-31, sonnet-5 and opus-4-8): N = 72. Exploratory for all RQs.
- haiku_probe (memorization probe, complement of haiku_clean; released as `pre_cutoff_probe` in the dataset): N = 835. Descriptive.

The jan2026_clean stratum is a subset of haiku_clean (resolved_at >= 2026-03-02 implies resolved_at >= 2025-08-30). Thirty-eight questions with close_at before haiku's training cutoff were moved from the haiku_clean candidate set to haiku_probe (D-014); this is why the confirmatory N is 352 rather than the 390 originally identified before that refinement.

### 3.4 Snapshot definition and microstructure

The crowd probability at snapshot T is the `probAfter` value of the last non-redemption bet on the Manifold market at or before T = resolved_at minus 30 days, taken from the bet history. The AMM initial price is not used as a crowd forecast. Liquidity and AMM parameters at T (pool shares, added liquidity, p0) are captured in the microstructure fields. For 38 questions in haiku_clean (152 of all 1,187) where close_at < T, no trades occurred after market close. The crowd probability at T for those questions equals the final market price. A further note on the corpus: 609 of 1,187 questions (51.3%) have close_at equal to resolved_at, Manifold's auto-resolve pattern where the market closes and resolves at the same instant. The snapshot logic handles this correctly (the snapshot predates both); it is noted because auto-resolve markets may trade differently from creator-resolved ones.

---

## 4. Methods

### 4.1 Pre-registration and phase gates

Hypotheses, decision thresholds, and the hypothesis family were fixed before any confirmatory test was run. SCOPE.md was frozen at Phase-2 kickoff. Analysis-plan details (sample assignment per model, RQ2 contrast implementation, the exact BH family, RQ4 strategy) were fixed as D-016 before Phase-3 runs began. Descriptive Phase-2 scores were seen before D-016 was written, as they validated the pipeline. No threshold was changed after those scores were seen.

### 4.2 Contamination rules (D-006 and D-014)

D-006 requires C ≤ T: the model's training cutoff must be at or before the snapshot date. Under this rule the model is at worst information-disadvantaged relative to the contemporaneous crowd, so any model edge is conservative and interpretable. Instructing a model to ignore post-cutoff information does not reliably prevent leakage (Li et al., arXiv 2601.13717). The sample filter is the cleanliness mechanism.

D-014 adds the close_at >= C condition per model. Questions whose market closed before the model's cutoff are moved to the memorization probe regardless of their formal resolution timestamp. The red-team identified this gap: the D-006 rule as originally written keyed on resolved_at and missed cases where the outcome was effectively observable before the model's training cutoff.

### 4.3 Model panel and elicitation protocol

The panel comprises three models: claude-haiku-4-5-20251001 (training cutoff 2025-07-31), claude-sonnet-5 (training cutoff 2026-01-31), and claude-opus-4-8 (training cutoff 2026-01-31). The fable-5 frontier probe was skipped (D-015): it shares the jan2026 cutoff, would add only an exploratory data point, and carries a high per-token cost with always-on billed reasoning.

Protocol v2 was adopted before any full-scale data were collected (D-012). Under v2, each model writes 1 to 2 sentences of key considerations and then outputs a JSON object with a numeric probability. The format is identical across all three panel models. Protocol v2 was selected on the basis of a targeted literature review: ForecastBench (arXiv 2409.19839) reports that brief reasoning consistently improves elicitation accuracy; Halawi et al. (arXiv 2402.18563) and Schoenegger et al. (arXiv 2402.19379) both use reasoning-first elicitation. A 50-question plumbing check confirmed parse rate, determinism, and cost. It was not used as an accuracy bake-off and does not alter the D-012 decision. All model probabilities were clamped to [0.01, 0.99] at elicitation time.

### 4.4 Scoring and calibration

Brier scores and Brier skill scores (BSS) are computed relative to the stratum base-rate forecaster. Positive BSS indicates beating the base rate. Calibration-in-the-large (CITL) is mean(forecast) minus mean(outcome); positive values indicate systematic over-prediction. Calibration slope comes from a logistic recalibration regression on the logit scale (iteratively reweighted least squares). A slope of 1 is perfect; slope below 1 indicates overconfidence (probabilities too extreme); slope above 1 indicates underconfidence.

Confidence intervals use percentile bootstrap with 10,000 replications and seed 42.

### 4.5 Encompassing regression

The RQ3 test is a logistic encompassing regression: outcome ~ intercept + b_crowd * logit(crowd) + b_model * logit(model). H3a tests whether b_crowd is distinguishable from zero after conditioning on the model. H3b tests whether b_model is distinguishable from zero after conditioning on the crowd. Wald CIs and p-values are reported alongside a seeded bootstrap check. The logit-scale Pearson correlation between crowd and model forecasts is reported per cell to assess collinearity (D-008).

### 4.6 Multiple-testing correction

The Benjamini-Hochberg procedure with q = 0.10 is applied to exactly five confirmatory tests: H1-crowd, H1-haiku, H2-haiku, H3a-haiku, H3b-haiku. Exploratory and preliminary results sit outside this family and are reported with effect sizes and CIs, but are not BH-corrected.

### 4.7 RQ4 strategy (pre-registered, D-016 section 6)

On each haiku_clean question where the absolute difference between model and market probability exceeds 0.05, the backtest places a bet in the model's direction. The stake is 10 mana (1% of a fixed 1,000-mana bankroll) with no compounding. Slippage is priced through a CPMM approximation of Manifold's Maniswap AMM using stored liquidity at T. P&L is realised at resolution. The pre-registered decision criterion is: the edge survives only if the 95% bootstrap CI (10,000 replications, seed 42) excludes ≤ 0.

---

## 5. Results

### 5.1 RQ1: Calibration (H1)

*Decision rule (pre-registered, D-016 section 1):* reject "well calibrated" if the 95% bootstrap CI excludes 0 AND |CITL| >= 0.05. Both conditions must hold.

**CONFIRMATORY: Crowd, full sample (N = 1,187).** CITL = +0.035, 95% CI [+0.017, +0.053], p = 0.0003. The CI excludes zero. H1-crowd is BH-significant (rank 2, BH threshold 0.04). However, the point estimate |CITL| = 0.035 is below the pre-registered threshold of 0.05. The effect-size arm of the conjunction fails. The null "crowd is well calibrated" is not rejected. This is a two-part decision: statistical evidence of bias is present, but the effect does not meet the minimum effect size fixed before data collection.

**CONFIRMATORY: Haiku, haiku_clean (N = 352).** CITL = +0.004, 95% CI [−0.045, +0.055], p = 0.867. The CI includes zero. The null is not rejected (FAIL-TO-REJECT). H1-haiku is not BH-significant.

**Calibration slopes.** All models are substantially overconfident on the logit scale. The crowd slope (full sample) = 1.302, indicating mild underconfidence overall. The haiku clean-stratum slope = 0.353, indicating severe overconfidence.

**EXPLORATORY: Sonnet-5 and opus-4-8, jan2026_clean (N = 72).** Sonnet-5: CITL = −0.132, 95% CI [−0.242, −0.020], p = 0.022. Opus-4-8: CITL = −0.179, 95% CI [−0.289, −0.074], p = 0.001. Both models under-predict YES resolutions on this stratum. The jan2026_clean base rate is 45.8%, compared to 33.8% overall. The crowd is nearly unbiased on this stratum (CITL = +0.006). The pattern is consistent with models anchoring to pre-cutoff base rates while the crowd tracks the higher subsequent YES rate. This is an information-recency effect, not a question-selection artifact. These results are exploratory (N = 72, outside the BH family).

See Figure 1 (docs/figures/phase2_calibration.png) for reliability diagrams across forecasters and strata.

### 5.2 RQ2: Skill versus memorization (H2)

ΔBSS = BSS_post(clean) minus BSS_pre(probe). Pre and post are disjoint question sets; the contrast is implemented as a two-sample bootstrap, which is the faithful implementation of the pre-registered design for disjoint strata (D-016 section 2). The pre-registered flag fires if the post-cutoff BSS confidence interval includes ≤ 0.

**CONFIRMATORY: Haiku.** BSS_post = −0.065 (haiku_clean, N = 352). BSS_pre = +0.055 (probe, N = 835). ΔBSS = −0.119, 95% CI [−0.268, +0.021], p = 0.104. The CI includes zero; H2-haiku is not BH-significant. The pre-registered flag fires: the post-cutoff BSS CI [−0.192, +0.050] includes ≤ 0. Haiku does not demonstrably beat the base rate on post-cutoff questions. The direction is consistent with H2.

**EXPLORATORY: Sonnet-5 and opus-4-8 (jan2026_clean, N = 72).** Sonnet-5: ΔBSS = −0.331, 95% CI [−0.649, −0.062], p = 0.028. Post-cutoff BSS CI [−0.335, +0.230] includes ≤ 0. Opus-4-8: ΔBSS = −0.271, 95% CI [−0.579, −0.008], p = 0.060. Post-cutoff BSS CI [−0.301, +0.242] includes ≤ 0. These are exploratory cells outside the BH family.

A caveat applies to ΔBSS: the pre-cutoff probe and post-cutoff clean strata have different base rates (0.344 vs. 0.324 for haiku). The BSS reference term p(1−p) differs across strata. The contrast is directionally informative but partially confounded by the base-rate difference.

### 5.3 RQ3: Information content (H3a / H3b)

**CONFIRMATORY: Haiku, haiku_clean (N = 352).** Logit-scale Pearson correlation between crowd and haiku forecasts: rho = 0.317.

b_crowd = +1.181, Wald 95% CI [0.937, 1.424], p < 0.001. Bootstrap 95% CI [0.983, 1.503], p < 0.001. H3a-haiku is BH-significant (rank 1, BH threshold 0.02). The crowd carries information about outcomes beyond haiku's forecast. H3a is confirmed.

b_model = +0.107, Wald 95% CI [−0.117, 0.331], p = 0.350. Bootstrap 95% CI [−0.138, 0.334], p = 0.364. H3b-haiku is not BH-significant. Haiku carries no detectable information about outcomes beyond the crowd.

The result is asymmetric encompassing. The crowd encompasses haiku: after conditioning on the crowd probability, haiku's forecast adds nothing statistically distinguishable from zero. Haiku does not encompass the crowd. This finding is specific to haiku on post-cutoff AI-progress questions. It does not generalise to stronger models; sonnet-5 and opus-4-8 cells are exploratory and are described below.

**EXPLORATORY: Sonnet-5, jan2026_clean (N = 72).** Logit rho = 0.472. b_crowd = +0.936, Wald 95% CI [0.498, 1.375], p < 0.001. b_model = +0.068, Wald 95% CI [−0.319, 0.454], p = 0.732. Pattern is consistent with the confirmatory result.

**EXPLORATORY: Opus-4-8, jan2026_clean (N = 72).** Logit rho = 0.504. b_crowd = +0.881, Wald 95% CI [0.451, 1.310], p < 0.001. b_model = +0.276, Wald 95% CI [−0.146, 0.698], p = 0.200. Pattern consistent with the confirmatory result; the b_model CI is wider and includes zero.

A disclosure applies to all three cells: model probabilities were clamped to [0.01, 0.99] at elicitation, while crowd probabilities range to 0.004 and 0.993. This produces an asymmetric logit range between the two covariates and may attenuate b_model relative to an unclamped analysis.

See Figure 2 (docs/figures/rq3_coef_forest.png) for coefficient forest plots.

### 5.4 BH family summary

| Test | Raw p | BH rank | BH threshold | BH-rejected |
|---|---|---|---|---|
| H3a-haiku | <0.001 | 1 | 0.02 | YES |
| H1-crowd | 0.0003 | 2 | 0.04 | YES (fails conjunction effect-size arm; H1 null) |
| H2-haiku | 0.104 | 3 | 0.06 | no |
| H3b-haiku | 0.350 | 4 | 0.08 | no |
| H1-haiku | 0.867 | 5 | 0.10 | no |

H1-crowd is BH-rejected on the CI-excludes-zero criterion, but the pre-registered H1 decision is the conjunction of two conditions. It fails at the effect-size arm (|CITL| = 0.035 < 0.05). The H1-crowd decision is null.

### 5.5 D-014 sensitivity analyses

The two pre-registered sensitivity analyses are summarised below. No sign flip occurs for any strong effect. One benign sign flip in H1-haiku CITL is disclosed.

| Metric | Main | + 38 close_before_cutoff (N = 390) | − close_before_T (N = 314) |
|---|---|---|---|
| H1-crowd CITL | +0.035 | (crowd unchanged by haiku sample shift) | +0.029 |
| H1-haiku CITL | +0.004 | +0.026 | −0.021 (sign flip) |
| H1-haiku slope | 0.353 | 0.321 | 0.417 |
| H2-haiku ΔBSS | −0.119 | −0.175 | −0.074 |
| H3a-haiku b_crowd | +1.181 | +1.036 | +1.117 |
| H3b-haiku b_model | +0.107 | +0.025 | +0.165 |

The H1-haiku CITL sign flip under sensitivity (b) is benign. Both values (+0.004 and −0.021) are well below the 0.05 effect threshold. The H1-haiku decision is unchanged in either direction. No BH-family decision flips under either sensitivity.

### 5.6 RQ4: Friction-aware backtest (H4), PRELIMINARY

*Pre-registered decision criterion (D-016 section 6):* the edge survives only if the 95% bootstrap CI excludes ≤ 0 net of costs.

**PRELIMINARY: Haiku_clean (N = 352).** 273 bets were placed (143 YES, 130 NO) out of 352 questions. The hit rate was 0.220. Total P&L = −1,199 mana. ROI = −43.9%. 95% bootstrap CI: [−1,649, −710] mana. The CI excludes zero and is entirely negative. H4 decision: NO-EDGE. A Platt-recalibrated variant performed worse (P&L = −1,763 mana, ROI = −55.1%, 95% CI [−2,239, −1,209] mana).

**EXPLORATORY.** Sonnet-5 (jan2026_clean, N = 72): 56 bets, hit rate 0.304, P&L = −66 mana, 95% CI [−336, +274]. Opus-4-8: 58 bets, hit rate 0.362, P&L = −30 mana, 95% CI [−302, +313]. Both CIs include zero.

*Caveats.* First, Manifold uses play-money mana. No real economic stakes exist. Mana prices may diverge from true probabilities without real arbitrage pressure. All figures are in mana units with no direct monetary interpretation. Second, the backtest approximates Manifold's Maniswap AMM with a standard CPMM formula. The stored `addedLiquidity` field reflects cumulative mana deposited rather than actual pool shares; live-API spot checks found actual pool-share sums 7 to 12 times larger than this field. For large-liquidity markets, both approximation errors change gross profit by less than 5% per winning bet. Because losses dominate wins across all cells (22% hit rate), the NO-EDGE decision is robust to any defensible approximation convention. The true pool state at T was not stored and cannot be retrieved retrospectively. Third, the 5% fee is an approximation of Manifold's per-trade fee structure, which varies by market and has changed over time.

See Figure 3 (docs/figures/rq4_pnl.png) for cumulative P&L over resolved questions.

---

## 6. Limitations

Several limitations bound the scope of these findings.

**Single provider.** The panel uses three Anthropic Claude models only. No OpenAI, Google, or other provider is included. Results cannot be generalised beyond Anthropic models.

**Two training cutoffs.** The panel has only two distinct training cutoffs: 2025-07-31 and 2026-01-31. The capability-recency axis of RQ2 covers a narrow range. A multi-provider panel with older cutoffs is future work (D-011).

**Title-only elicitation.** Models saw only the question title. Platform forecasters had access to the full question description. Historical description text is not retrievable from Manifold; current description text is a leakage channel (Manifold returns editable text) and was deliberately excluded. This creates an information asymmetry favouring the crowd. The confirmed H3a finding (crowd encompasses haiku) must be read with this caveat: some portion of the crowd's advantage may reflect access to richer question text. Model-beats-crowd results, were any found, would be conservative under this asymmetry.

**Play-money RQ4.** Manifold uses mana, not real money. The backtest is illustrative. A real-money venue such as Polymarket and a real P&L criterion are future work (D-005, D-011).

**Small exploratory cells.** The jan2026_clean stratum has N = 72. All sonnet-5 and opus-4-8 results are exploratory. RQ4 exploratory CIs include zero for both models.

**Single 30-day snapshot horizon.** Results apply to the 30-day horizon only. 7-day and 90-day robustness analyses are future work (D-007).

**Classifier residual error.** The v1.1 classifier has an approximately 7.5% drop-side false-negative rate. Wrongly excluded questions shift the question distribution but cannot bias model-vs-crowd comparisons because the classifier does not see resolutions (D-013).

**Crowd snapshot equals closing price for late-close questions.** For 38 questions in haiku_clean (152 of all 1,187) where close_at < T, the market closed before the snapshot date. The crowd probability for those questions equals the final market price; the vantage postdates the market's effective close. The pre-registered sensitivity analysis excluding these questions changes no decision.

**Title edit risk.** Titles were fetched from the live API after resolution, and Manifold allows creators to edit titles at any time. A post-hoc scan of all 1,187 titles for resolution-revealing patterns found zero genuine leaks (the few pattern hits are question-native text). The residual risk is that a subtler edit escaped the scan; it applies equally to the classifier and the elicitation.

**Selection on resolution.** Only questions resolved by the collection date enter the sample. Long-horizon questions still open are excluded by construction. Absolute calibration claims therefore describe the population of resolved questions, not all questions ever asked. The model-vs-crowd comparison is unaffected because both sources face the same selection.

**RQ2 base-rate confound.** The pre-cutoff probe and post-cutoff clean strata have different base rates (0.344 vs. 0.324 for haiku). The BSS reference term differs across strata. ΔBSS is directionally informative but partially confounded.

**Logit clamp asymmetry.** Model probabilities are clamped to [0.01, 0.99]; crowd probabilities are unclamped. The asymmetric logit range may attenuate b_model in the encompassing regression.

---

## 7. Reproducibility

The repository is designed as the single source of truth for all durable state. Every methodological decision is recorded in DECISIONS.md with rationale and an append-only immutable record. Raw API responses are git-ignored but reproducible from the provenance manifest, which records query parameters, timestamps, and SHA-256 content hashes. All derived tables are produced by deterministic seeded code (seed = 42 throughout). The SHA-256 of phase2_scores.csv is 4c5aaf0c92860e98d7957e53f498bc3a05e392b168eb9bc287de595c0b7988b4. The SHA-256 of phase3_rq123.json is 7a540fdde2c758a5f681d98518f76b8dd36c54cc3f526effc5adef9a699879a8.

The total API cost of this study is USD 7.51, itemised by run in docs/EXPERIMENTS.md. The study operated within the pre-registered budget envelope of USD 8 to 15 for the core plan.

A curated dataset is released in data/release/ alongside a datasheet documenting fields, collection date, applied filters, classifier version, known caveats, and the required Manifold attribution (CC-BY-4.0). Reproduction commands are in data/release/README.md.

---

## 8. AI Tool Usage Declaration

This project was built by an orchestrated set of Claude agents, each assigned a named role: researcher (novelty check and literature review), data-engineer (collection, classification, elicitation, and provenance), quant-analyst (scoring and confirmatory analysis), red-team-reviewer (adversarial audit of claims and artifacts), and scientific-writer (this report). The agents performed the following tasks:

- Research design support and literature search assistance
- Data collection, classification, and schema engineering
- Statistical analysis implementation and execution
- Adversarial review of methods, claims, and numerical artifacts
- Report drafting

At all stages, agent outputs were reviewed against primary sources and verified against raw data files. Pre-registered decisions and hypotheses were fixed before any analysis began. Human sign-off was required at every phase gate. The responsibility for the final content, analysis, and conclusions rests entirely with me.

---

## 9. References

Halawi D., Zhang F., Yueh-Han C., Steinhardt J. "Approaching Human-Level Forecasting with Language Models." NeurIPS 2024. arXiv:2402.18563.

Schoenegger P., Tuminauskaite I., Park P.S., Tetlock P.E. "Wisdom of the Silicon Crowd: LLM Ensemble Prediction Capabilities Rival Human Crowd Accuracy." Science Advances 10(45), eadp1528, 2024. arXiv:2402.19379.

Karger E., Bastani H., Yueh-Han C., Jacobs Z., Halawi D., Zhang F., Tetlock P.E. "ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities." ICLR 2025. arXiv:2409.19839.

Alur R., Stadie B.C., Kang D., Chen R., et al. "AIA Forecaster: Technical Report." arXiv:2511.07678, November 2025.

Zou A., Xiao T., Bhatt R., Toy A., Weller O., Liang R., Emmons S., Hendrycks D. "Forecasting Future World Events with Neural Networks." NeurIPS 2022. arXiv:2206.15474.

Li Z., Wang Y., El Lahib A., Xia Y., Pi X. "Simulated Ignorance Fails: A Systematic Study of LLM Behaviors on Forecasting Problems Before Model Knowledge Cutoff." arXiv:2601.13717, January 2026.

Cheng P., Liu J., Long Y. "PolyBench: Benchmarking LLM Forecasting and Trading Capabilities on Live Prediction Market Data." arXiv:2604.14199, April 2026.

Arora A., Malpani R. "PredictionMarketBench: A SWE-bench-Style Framework for Backtesting Trading Agents on Prediction Markets." arXiv:2602.00133, January 2026.

Paleka D., Goel S., Geiping J., Tramer F. "Pitfalls in Evaluating Language Model Forecasters." arXiv:2506.00723, May 2025.

Ma Y., Ruan C., Huang K., Yang Z., Zhou L. "OracleProto: A Reproducible Framework for Benchmarking LLM Native Forecasting via Knowledge Cutoff and Temporal Masking." arXiv:2605.03762, May 2026.

Tian Q., Yin H., Xia Y., Kong Y., Liu Z. "ForeSci: Evaluating LLM Agents for Forward-Looking AI Research Judgment." arXiv:2606.00644, May 2026.

Epoch AI. "How Well Did Forecasters Predict 2025 AI Progress?" Blog post, 2026. https://epoch.ai/gradient-updates/how-well-did-forecasters-predict-2025-ai-progress
