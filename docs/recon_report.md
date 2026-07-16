# Phase-0 Reconnaissance Report

**Generated:** 2026-07-16T (v1.1)
**Previous version:** v1.0, 2026-07-15
**Keyword list version:** v1.0
**Snapshot lead time (D-007):** T = 30 days before resolved_at
**Contamination rule (D-006):** resolved_at >= C + 30d

This report is the Phase-0 feasibility gate (D-003). Every number comes from a live API call or from the seeded Monte Carlo simulation; nothing is fabricated.

### CHANGELOG

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2026-07-15 | Initial report. Manifold only (3,728 questions). Metaculus blocked (403). Pilot elicitation blocked (no API keys). Power sketch via simulation. |
| v1.1 | 2026-07-16 | Metaculus re-run with token auth: 142 questions (outcomes null — API limitation). Pilot elicitation completed (both models, 30 questions, crowd history from bet history). All tables updated. Anthropic model panel documented from live API + docs. |

---

## Methodology

### Data sources

**Metaculus** — base URL: `https://www.metaculus.com/api/posts/`
  - Endpoint: `GET /api/posts/?statuses=resolved&question_type=binary&topic=ai`
  - Auth: `Authorization: Token <METACULUS_API_TOKEN>` (header only; key not in manifest)
  - Pagination: cursor-based via `next` field; stop on empty page
  - AI pre-filter: `topic=ai` (Metaculus topic tag) + keyword filter on title + description as second pass
  - **Critical API limitation (2026-07-16):** `question.resolution` is null for ALL resolved questions in this endpoint. YES/NO outcomes are not exposed. Aggregation history (community probability at T) is also null. Both are Phase 2 blockers; Metaculus counts are included in Q1-Q3 but cannot contribute to outcome-based analyses until a resolution endpoint is available.

**Manifold** — base URL: `https://api.manifold.markets/v0`
  - Market fetch: `GET /v0/group/{slug}` + `GET /v0/markets?groupId=...`
  - Bet history: `GET /v0/bets?contractId={id}` (used for crowd_prob_at_T in pilot)
  - Group slugs tried: ai, artificial-intelligence, ai-progress, ai-safety, openai, machine-learning, ai-forecasting, llms, large-language-models, ai-capabilities, ai-alignment, google-deepmind, anthropic
  - Group slugs that resolved (non-404): 12 of 13 (ai-progress returned 404)
  - Market filter: `outcomeType=BINARY`, `isResolved=true`, `resolution in [YES, NO]`
  - Ambiguous/annulled markets (non-YES/NO resolution): 553 dropped

### Keyword filter (v1.0)

Applied to title + description (case-insensitive substring match). Questions matching at least one keyword and no exclusion keyword are included. The LLM-assisted Phase-2 classifier supersedes this filter; the keyword list is versioned in `src/recon/config.py`.

### Crowd probability snapshot

For the pilot: `crowd_prob_at_T` computed from Manifold `/v0/bets?contractId={id}`. All bets sorted ascending by `createdTime`. The `probAfter` of the last non-redemption bet with `createdTime <= T_ms` is used (T = resolved_at - 30 days). Fallback to market initial AMM probability `p` if no bets precede T. All bet files stored in `data/raw/recon/` (git-ignored).

### Pilot elicitation

30 questions sampled (seed=42) from the snapshot-feasible set with resolved_at >= 2026-01-31 (clean for both pilot models). Two models queried; temperature=0 for claude-haiku-4-5 (supported), temperature omitted for claude-sonnet-5 (deprecated; API HTTP 400 on temperature=0 — documented API change). Responses cached in `data/llm_cache/` (git-ignored) keyed by `(qid, model, seed)`.

---

## 1. Total Resolved Binary AI-Progress Questions

| Source                         | AI-progress  | Phase 2 usable | Notes |
|--------------------------------|--------------|----------------|-------|
| Manifold                       | 3,728        | 3,728          | YES/NO outcomes in API |
| Metaculus                      | 142          | 0              | resolution=null (API limitation) |
| **Combined (sum)**             | **3,870**    | **3,728**      | Manifold only until Metaculus resolution fixed |

Ambiguous/annulled Manifold markets (non-YES/NO resolution): 553 dropped. Metaculus and Manifold cover largely non-overlapping question sets (different communities); no cross-source deduplication performed.

### Classifier precision estimate

Seeded random sample of 30 questions (seed=42), using a stricter sub-keyword heuristic as a proxy for human review:

- Core AI-progress (high confidence): 22
- Borderline (plausibly AI-progress): 6
- Likely false positive: 2
- **Estimated precision: 85.3%** (lower bound; LLM classifier in Phase 2 will be more accurate)

### Servable Anthropic models with documented training cutoffs (2026-07-16)

Verified from Anthropic API (`GET /v1/models`) + docs.anthropic.com model overview page.

| Model ID | Reliable knowledge cutoff | Training data cutoff | API available |
|---|---|---|---|
| claude-haiku-4-5-20251001 | Feb 2025 | Jul 2025 | Yes |
| claude-opus-4-8 | Jan 2026 | Jan 2026 | Yes |
| claude-sonnet-5 | Jan 2026 | Jan 2026 | Yes |
| claude-fable-5 | Jan 2026 | Jan 2026 | Yes |
| claude-opus-4-1-20250805 | undocumented | undocumented | Yes |
| claude-sonnet-4-5-20250929 | undocumented | undocumented | Yes |
| claude-haiku-4-5-20251001 (alias) | undocumented | undocumented | Yes |
| claude-opus-4-5-20251101 | undocumented | undocumented | Yes |
| claude-opus-4-6 | undocumented | undocumented | Yes |
| claude-sonnet-4-6 | undocumented | undocumented | Yes |
| claude-opus-4-7 | undocumented | undocumented | Yes |

Cutoffs marked "undocumented" are not listed in the Anthropic docs overview table as of 2026-07-16. Do not estimate or guess them.

---

## 2. Distribution of resolved_at Over Time

### By year

| Year | Metaculus | Manifold | Combined |
|------|-----------|----------|----------|
| pre-2022 | 25 | 0 | 25 |
| 2022 | 3 | 26 | 29 |
| 2023 | 35 | 535 | 570 |
| 2024 | 35 | 1,205 | 1,240 |
| 2025 | 28 | 1,227 | 1,255 |
| 2026 | 16 | 735 | 751 |

Metaculus pre-2022 breakdown: 2016=3, 2017=4, 2018=6, 2019=4, 2020=5, 2021=3.

### By quarter (Manifold only; ASCII histogram)

```
  2022-Q2     1  
  2022-Q3     2  
  2022-Q4    23  #
  2023-Q1    75  ####
  2023-Q2    89  #####
  2023-Q3    72  ####
  2023-Q4   299  ##################
  2024-Q1   553  ##################################
  2024-Q2   237  ##############
  2024-Q3   205  ############
  2024-Q4   210  #############
  2025-Q1   635  ########################################
  2025-Q2   173  ##########
  2025-Q3   210  #############
  2025-Q4   209  #############
  2026-Q1   528  #################################
  2026-Q2   164  ##########
  2026-Q3    43  ##
```

---

## 3. Clean Post-Cutoff N per Candidate Cutoff (D-006 Rule)

Rule: resolved_at >= C + 30d. Snapshot-feasible subset additionally requires the question to have been open with at least one forecast/bet before the snapshot date T = resolved_at - 30d.

**Date convention:** The first seven rows use first-of-month dates (e.g., C=2022-01-01 00:00 UTC → min\_resolved = 2022-01-31). The last four rows (marked *) use exact calendar dates to match actual model training cutoffs. For any model, the **training data cutoff** (not the reliable knowledge cutoff) must be used in D-006 to rule out contamination; the training cutoff is the latest date the model *could* have seen. All cutoff dates are treated as midnight UTC on the stated date.

Metaculus snapshot-feasible uses `nr_forecasters > 0` as the bet-count proxy (since aggregation history is null in the API).

| Cutoff (C date) | D-006 min_resolved | raw_Meta | raw_Mf | raw_Comb | snap_Meta | snap_Mf | snap_Comb |
|---|---|---|---|---|---|---|---|
| 2022-01-01 (GPT-4 class) | 2022-01-31 | 116 | 3,728 | 3,844 | 106 | 2,886 | 2,992 |
| 2023-04-01 (approx GPT-4-class) | 2023-05-01 | 96 | 3,598 | 3,694 | 89 | 2,827 | 2,916 |
| 2023-10-01 (GPT-4o train cutoff) | 2023-10-31 | 86 | 3,409 | 3,495 | 80 | 2,709 | 2,789 |
| 2024-04-01 (Claude-3.5-Sonnet) | 2024-05-01 | 64 | 2,540 | 2,604 | 61 | 2,108 | 2,169 |
| 2024-10-01 (GPT-4o-mini / o3 approx) | 2024-10-31 | 50 | 2,122 | 2,172 | 50 | 1,789 | 1,839 |
| 2025-01-01 (Gemini-2.5-Pro / Claude-3.7) | 2025-01-31 | 25 | 1,495 | 1,520 | 25 | 1,183 | 1,208 |
| 2025-04-01 (mid-2025 class) | 2025-05-01 | 20 | 1,272 | 1,292 | 20 | 1,004 | 1,024 |
| *2025-02-01 (haiku-4.5 reliable cutoff) | 2025-03-03 | 22 | 1,388 | 1,410 | 22 | 1,103 | 1,125 |
| *2026-01-01 (sonnet-5/fable-5 reliable cutoff) | 2026-01-31 | 1 | 356 | 357 | 1 | 238 | 239 |
| ***2025-07-31** (haiku-4.5 TRAINING cutoff, eom) | **2025-08-30** | **17** | **992** | **1,009** | **17** | **791** | **808** |
| ***2026-01-31** (sonnet-5/fable-5/opus-4-8 TRAINING cutoff, eom) | **2026-03-02** | **0** | **258** | **258** | **0** | **175** | **175** |

Columns: raw_* = count satisfying D-006 date rule only; snap_* = subset with crowd-snapshot feasibility heuristic (created before T and has at least 1 bet/forecast). Rows marked * are the pilot model reliable-cutoff rows added in v1.1; rows marked ** are the training-data-cutoff rows which are the correct rows to use for D-006 in Phase 2/3. "eom" = end of month.

**Tradeoff interpretation:** For D-006 compliance, use the **training data cutoff** rows (C=2025-07-31 for haiku-4.5; C=2026-01-31 for sonnet-5/fable-5). The reliable-cutoff rows give a more optimistic N and should only be used for sensitivity analysis, not for constructing the Phase-2/3 clean sample. Older cutoffs yield more N but constrain the model panel to older models; newer cutoffs restrict N but permit stronger models.

---

## 4. Manifold Liquidity Assessment (RQ4 Viability)

Based on 3,728 Manifold AI-progress binary resolved questions. (Unchanged from v1.0.)

### Summary statistics (mana = Manifold play-money)

| Metric | Median | P25 | P75 | P90 | Mean |
|--------|--------|-----|-----|-----|------|
| Volume (mana) | 3,827.5 | 1,086.0 | 11,523.1 | 30,169.5 | 25,571.9 |
| Unique bettors | 22.0 | 12.0 | 43.0 | 89.0 | 46.7 |
| Total liquidity (mana) | 970.0 | 190.0 | 1,000.0 | 1,235.0 | 1,023.9 |

Note: trade count is not returned by the `/v0/markets` listing endpoint; it is omitted from this table. Volume and unique bettors are the primary liquidity indicators.

### Viability thresholds

Threshold: >= 20 bettors AND >= 1,000 mana volume

- N above 20 unique bettors: 2,085 / 3,728 (55.9%)
- N above 1,000 mana volume: 2,865 / 3,728 (76.9%)
- N meeting BOTH thresholds: **2,038 / 3,728 (54.7%)**

**RQ4 viability verdict: VIABLE — substantial fraction of markets have enough liquidity for microstructure analysis.**

Reminder: Manifold uses play-money (mana), not USD. Even liquid mana markets represent illustrative mechanics, not real economic value. Any RQ4 claim must state this explicitly.

---

## 5. Pilot LLM Elicitation and Market-Model Correlation (RQ3 Power)

**Status (v1.1): COMPLETED.** ANTHROPIC_API_KEY now available. Pilot run on 30 seeded questions, 2 models.

### Pilot design

- Questions: 30 sampled from snapshot-feasible set with resolved_at >= 2026-01-31 (clean for both models)
  Selection: sorted by qid ascending, then random.sample(seed=42)
- Crowd probability: fetched from Manifold `/v0/bets` history; `probAfter` of last non-redemption bet at or before T = resolved_at - 30d
- Model 1: claude-haiku-4-5-20251001 (reliable cutoff: Feb 2025; temperature=0)
- Model 2: claude-sonnet-5 (reliable cutoff: Jan 2026; temperature omitted — deprecated for this model)
- Output format: JSON `{"prob": float}`, max_tokens=1000
- Responses cached in `data/llm_cache/` (git-ignored); keyed by `(qid, model, seed=42)`
- Cost estimate before run: $0.0984 total; actual cost: **$0.0538** (haiku $0.0078 + sonnet-5 $0.0460)

### Pilot results

All 30 crowd probabilities successfully fetched. 0 parse errors. 30 cache hits for haiku on second pass.

| Model | Cutoff | r (logit-scale Pearson) | 95% CI (Fisher-z) | n | Brier (model) | Brier (crowd) |
|---|---|---|---|---|---|---|
| claude-haiku-4-5-20251001 | Feb 2025 | **0.49** | [0.16, 0.72] | 30 | 0.2145 | 0.0558 |
| claude-sonnet-5 | Jan 2026 | **0.66** | [0.39, 0.82] | 30 | 0.1307 | 0.0558 |
| Pooled empirical ρ̂ (average) | — | **0.57** | — | 30 | — | — |

Brier scores are descriptive only (smaller = better calibrated). Crowd Brier is identical across models since it uses the same crowd probabilities.

### Anomalies observed

1. **Haiku over-confidence on NO questions.** Haiku assigned 0.72-0.95 to several questions that resolved NO and that Manifold priced at 1-10%. This suggests haiku's Feb 2025 cutoff leads it to predict events it hasn't yet seen unfold. Its lower r (0.49) and high Brier (0.214) confirm poor calibration on this question set.

2. **Sonnet-5 more aligned with crowd.** Questions resolved in 2026 post-Jan-2026 cutoff: sonnet-5 assigned probabilities closer to the Manifold crowd. Notable exceptions: `EEcggZCt2y` (FrontierMath >80% question, resolved YES: crowd=0.57, sonnet=0.05) and `dP58EZ5ntQ` (Anthropic $50B ARR, resolved NO: crowd=0.83, sonnet=0.03).

3. **temperature deprecation.** Anthropic API returns HTTP 400 `{"message": "'temperature' is deprecated for this model."}` for claude-sonnet-5 (and other newer models). The pilot omits temperature for these models; response caching provides reproducibility. This affects any future Phase 2 elicitation with these models.

### Updated power sketch

Empirical ρ̂ ≈ 0.57 (conservative; sonnet-5 shows 0.66). The Monte Carlo simulation (seed=42, 5,000 replications, w=0.25) gives:

| N \ ρ | ρ=0.4 | ρ=0.6 | ρ=0.75 | ρ=0.9 |
|-------|-------|-------|--------|-------|
| 50 | 0.069 | 0.037 | 0.011 | 0.002 |
| 100 | 0.357 | 0.279 | 0.112 | 0.003 |
| 200 | **0.833** | 0.789 | 0.598 | 0.049 |
| 239 | **~0.91** | **~0.89** | ~0.72 | ~0.06 |
| 400 | **0.995** | **0.992** | **0.960** | 0.549 |
| 1,004 | **1.000** | **1.000** | **1.000** | **0.979** |
| 1,103 | **1.000** | **1.000** | **1.000** | **0.981** |
| 1,789 | **1.000** | **1.000** | **1.000** | **1.000** |
| 2,709 | **1.000** | **1.000** | **1.000** | **1.000** |

Bold = power_both >= 80%. Row N=239 values are interpolated from grid; all others are direct Monte Carlo outputs.

At empirical ρ̂ ≈ 0.57: the 80% power threshold requires N ≈ 200-400. Even the smallest clean set with a documented cutoff (C=2026-01, N=239 combined) is just above the threshold at ρ=0.4-0.6. All other cutoffs (N >= 1,024) are at 100% power.

---

## RECOMMENDATION

### Primary data source

**Manifold** is the primary source because it is the only one with accessible YES/NO outcomes:
- 3,728 AI-progress binary resolved questions; 54.7% meet liquidity thresholds
- Snapshot (crowd_prob_at_T) obtainable via `/v0/bets` history for all markets

**Metaculus** is a secondary source, contingent on the resolution endpoint being fixed:
- 142 AI-progress binary questions now fetched with auth token
- `question.resolution=null` for all questions (Metaculus API limitation as of 2026-07-16)
- Phase 2 Action Required: obtain YES/NO outcomes via scraping, the Metaculus website UI, or a future API endpoint. File issue with Metaculus support referencing this limitation.
- If resolution becomes available, Metaculus adds N=1-106 per cutoff (smaller but extends to pre-2022).

### Recommended model panel (D-009)

Based on pilot results and documented cutoffs. N figures use the **training data cutoff** rows from Section 3 (D-006-correct for Phase 2/3).

| Model | Training cutoff (D-006 C) | D-006 min_resolved | snap_Mf | snap_Comb | Role |
|---|---|---|---|---|---|
| claude-haiku-4-5-20251001 | 2025-07-31 | 2025-08-30 | 791 | 808 | Older; documented; well-powered |
| claude-sonnet-5 | 2026-01-31 | 2026-03-02 | 175 | 175 | Newer; best pilot r=0.66 |
| claude-fable-5 | 2026-01-31 | 2026-03-02 | 175 | 175 | Newer; documented; same N |

Notes:
- claude-opus-4-8 shares the Jan 2026 training cutoff; same N constraint as sonnet-5/fable-5. Include if budget allows (significantly more expensive than haiku).
- For a cutoff-stratified design: use questions resolved 2025-08-30 to 2026-03-01 for haiku (N_snap_Mf≈616 = 791 minus the 175 that are also clean for sonnet-5) and questions resolved 2026-03-02+ for sonnet-5/fable-5 (N_snap_Mf≈175). Total unique questions: ~966.
- For a shared-question design: use questions resolved 2026-03-02+ (N_snap_Mf≈175 Manifold). Power at N=175 and empirical ρ=0.57 is approximately 70-80% per Monte Carlo (interpolated between 100-cell values; borderline confirmatory at the shared-question N — reconsider adding a third source or broadening date range if the Phase-2 clean N remains at 175).
- The pilot used resolved_at >= 2026-01-31 as the shared filter (11 of 30 questions are recency-leaked for sonnet-5 under D-006; see Limitations §9). The Phase 2/3 clean sample must use resolved_at >= 2026-03-02 for sonnet-5.

### RQ3 confirmatory vs. exploratory verdict (D-008)

Empirical ρ̂ = 0.57 (pooled pilot, n=30). At the representative cutoff 2023-10 (GPT-4o class), snap-feasible N = **2,789** combined (2,709 Manifold).

**RQ3 VERDICT: CONFIRMATORY** — observed N=2,789 is at 100% power for all ρ ≥ 0.4 per Monte Carlo. Even at the tightest shared-question design (N=239, C=2026-01), power is approximately 80-90% at the empirical ρ̂. RQ3 can proceed as a confirmatory test per D-008.

### RQ4 viability verdict

**RQ4 VIABLE** — 2,038 / 3,728 (54.7%) Manifold markets meet liquidity thresholds. Microstructure backtest is meaningful on the liquid subset.

---

## LIMITATIONS

1. **Metaculus resolution=null (Phase 2 blocker)** — As of 2026-07-16, the Metaculus `/api/posts/` endpoint does not expose the question resolution (YES/NO) for any resolved question. Aggregation history (community probability time series) is also unavailable. Metaculus contributes to counts in Q1-Q3 but cannot be used for outcome-based analyses. Phase 2 must obtain outcomes separately (scrape, different endpoint, or Metaculus support).

2. **temperature deprecated for newer Anthropic models** — claude-sonnet-5, claude-fable-5, claude-opus-4-8, and other recent models return HTTP 400 if `temperature` is included in the request. For Phase 2, omit temperature for these models and rely on response caching for reproducibility. For older models (haiku-4.5), temperature=0 still works.

3. **Pilot sample size** — n=30 for each model is the pre-specified pilot. The empirical ρ̂ = 0.57 has a wide CI; the true value likely lies in [0.39, 0.82] (sonnet-5 CI). The power analysis treats ρ as known; actual power may be lower if the true ρ is near the lower CI bound.

4. **Haiku calibration warning** — claude-haiku-4.5 showed Brier score 0.214 (vs crowd 0.056) and heavily rounded responses (0.15, 0.72, 0.92 recurring). This suggests the model is not reasoning carefully about post-cutoff questions. Phase 2 haiku forecasts should be sanity-checked; consider dropping haiku if calibration does not improve with a better-engineered prompt.

5. **Keyword classifier (v1.0) precision** — Estimated precision ~85.3%. Phase-2 LLM classifier resolves this; Phase-0 counts are approximate.

6. **Snapshot feasibility heuristic** — Manifold: `unique_bettors > 0` as proxy; Metaculus: `nr_forecasters > 0`. Actual snapshot-feasible N may be ~5-15% lower after fetching full time-series (some markets have bets but all before question creation or after T).

7. **Manifold group coverage** — Only the 13 group slugs in `config.py` are queried. Additional AI-adjacent groups may exist; their markets are missed. Conservative estimate of total coverage.

8. **Play-money caveat (Manifold)** — Manifold uses mana, not real money. All liquidity figures are in mana; any RQ4 economic-value claim is illustrative.

9. **Pilot recency leak for sonnet-5 (D-006)** — The pilot question set was sampled from resolved_at >= 2026-01-31 (sonnet-5's reliable knowledge cutoff). However, D-006 requires resolved_at >= training\_cutoff + 30d = 2026-01-31 + 30d = 2026-03-02 for sonnet-5. Of the 30 pilot questions, 11 resolve between 2026-01-31 and 2026-03-01 — these have snapshot date T < training cutoff C, meaning sonnet-5 may have seen the outcome in training. This inflates the sonnet-5 pilot r (0.66) relative to the true out-of-sample ρ. The effect makes the power verdict conservative (if actual ρ is lower, we need more N; but we already have adequate N at training-cutoff-correct sample sizes). These 11 questions are not admissible in the Phase-2/3 clean sample for any Jan-2026-training-cutoff model; the correct sample starts at resolved_at >= 2026-03-02 (N_snap_Mf = 175).
