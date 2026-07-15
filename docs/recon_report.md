# Phase-0 Reconnaissance Report

**Generated:** 2026-07-15T01:05:50.523072+00:00
**Keyword list version:** v1.0
**Snapshot lead time (D-007):** T = 30 days before resolved_at
**Contamination rule (D-006):** resolved_at >= C + 30d

This report is the Phase-0 feasibility gate (D-003). Every number comes from a live API call or from the seeded Monte Carlo simulation; nothing is fabricated.

---

## Methodology

### Data sources

**Metaculus** — base URL: `https://www.metaculus.com/api2/`
  - Endpoint: `GET /api2/questions/`
  - Intended filters: `type=forecast`, `status=resolved`, `resolution=yes,no`
  - AI tags/categories intended: ai, artificial-intelligence, machine-learning
  - **Status: BLOCKED (HTTP 403 Forbidden).** Metaculus now requires an API token for all endpoints, even public questions. Previously described as key-less; this is a policy change. Zero questions were retrieved. Metaculus data is deferred until a token is provisioned in `.env`.
  - Note: Metaculus /api2/questions/ does not expose a stable tag-filter parameter in the v2 API response; keyword filter applied on returned titles. Category-based pre-filter not available in this endpoint version — keyword recall may include some false positives.

**Manifold** — base URL: `https://api.manifold.markets/v0`
  - Endpoints: `GET /v0/group/{slug}` + `GET /v0/markets?groupId=...`
  - Group slugs tried: ai, artificial-intelligence, ai-progress, ai-safety, openai, machine-learning, ai-forecasting, llms, large-language-models, ai-capabilities, ai-alignment, google-deepmind, anthropic
  - Group slugs that resolved (non-404): ai, artificial-intelligence, ai-safety, openai, machine-learning, ai-forecasting, llms, large-language-models, ai-capabilities, ai-alignment, google-deepmind, anthropic
  - Market filter: `outcomeType=BINARY`, `isResolved=true`, `resolution in [YES, NO]`

### Keyword filter (v1.0)

Applied to title + description (case-insensitive substring match). Questions matching at least one keyword and no exclusion keyword are included. The LLM-assisted Phase-2 classifier supersedes this filter; the keyword list is versioned in `src/recon/config.py`.

### API notes

- Metaculus: used /api2/questions/ endpoint; returned HTTP 403 Forbidden. Error body: The API is only available to authenticated users. Please create an account and use your API token to access the API. Metaculus data is deferred until METACULUS_API_TOKEN is provisioned in .env.
- Manifold: used /v0/group/{slug} + /v0/markets?groupId=... endpoints. Groups tried: 13; resolved: 12 (ai-progress slug returned 404).

---

## 1. Total Resolved Binary AI-Progress Questions

| Source                         | AI-progress  | Ambiguous/annulled | Combined (de-duped est.) |
|--------------------------------|--------------|--------------------|------------------------|
| Metaculus                      | 0            | 0                  | —                      |
| Manifold                       | 3728         | 553                | —                      |
| **Combined (sum)**             | **3728**     | —                  | —                      |

Note: Metaculus and Manifold cover largely non-overlapping question sets (different communities); deduplication across sources is not performed in Phase 0. Ambiguous/annulled counts include only questions that passed the binary filter but had a non-YES/NO resolution.

### Classifier precision estimate

Seeded random sample of 30 questions (seed=42), using a stricter sub-keyword heuristic as a proxy for human review:

- Core AI-progress (high confidence): 22
- Borderline (plausibly AI-progress): 6
- Likely false positive: 2
- **Estimated precision: 85.3%** (lower bound; LLM classifier in Phase 2 will be more accurate)

Selected sample titles:

- [CORE] `manifold` — Will Google Gemini Ultra debut by January 15th 2024?
- [CORE] `manifold` — Will the best LLM in 2023 have <1 trillion parameters?
- [CORE] `manifold` — Will something named Gemini 1.5 Ultra be announced before the end of 2024?
- [CORE] `manifold` — Daily LLM assistant personal usage exceeds 2 hours for >10% of users by end-2025?
- [BORDER] `manifold` — Will a major tech company announce a significant new AI regulation compliance feature by the end of 
- [CORE] `manifold` — Will an LLM be able to solve the Self-Referential Aptitude Test before 2025?
- [CORE] `manifold` — OpenAI releases o3-pro this week?
- [CORE] `manifold` — Will Mistral AI be acquired by the end of 2024?
- [BORDER] `manifold` — Will it be possible to talk to AI characters inside of Whatsapp by the end of 2024? (similar to char
- [CORE] `manifold` — Will the Claude 4 series of models come out before 2026?
- [CORE] `manifold` — Will OpenAI release a "Search" feature that replaces ChatGPT's default interface before July 1, 2026
- [CORE] `manifold` — OpenAI saga: will it have an entertaining outcome?
- [CORE] `manifold` — Will GPT-4.5 be released on Thursday?
- [CORE] `manifold` — Will Microsoft Corp acquire Mistral AI by the end of 2024?
- [CORE] `manifold` — Will we see most new language models shifting to addition-only architectures like BitNet/BitNet 1.58
- [CORE] `manifold` — Will there be an OpenAI employee with e/acc in their twitter bio?
- [BORDER] `manifold` — Will the Friend Wearable AI sell more than 100k units by end of 2025?
- [FP?] `manifold` — Will Sam Altman have a manifold markets account by the end of 2024?
- [BORDER] `manifold` — Will AI enable humans to achieve immortality?
- [CORE] `manifold` — Will Mira Murati step down as OpenAI CEO before 2030?
- [CORE] `manifold` — By January 2026, will we have a language model with similar performance to GPT-3.5 (i.e. ChatGPT as 
- [CORE] `manifold` — Will China recreate GPT-4o by EOY 2024?
- [CORE] `manifold` — Will Chris Olah leave Anthropic before 2024 end?
- [CORE] `manifold` — Will GPT-4 (or similar) inference cost less than $0.02/1k completion tokens on 1 Jan 2024?
- [BORDER] `manifold` — Will a mainstream AI model pass the stick figure arrow name test in 2025? (Freely accessible models 
- [CORE] `manifold` — Will GPT-5.2's METR 50% time horizon exceed 3 hours 30 minutes?
- [CORE] `manifold` — [Short-Fuse] Will the Manifold AI countdown move to before 2030 (average) after the OpenAI event on 
- [CORE] `manifold` — Is the OpenAI situation the first illustration of AGI outsmarting humans?
- [FP?] `manifold` — Tyrese Haliburton scores 20+ points in Game 6 of the NBA Finals
- [BORDER] `manifold` — Will an application of AI become surprisingly popular in 2023?

---

## 2. Distribution of resolved_at Over Time

### By year

| Year     | Metaculus      | Manifold       | Combined     |
|----------|----------------|----------------|--------------|
| 2022     | 0              | 26             | 26           |
| 2023     | 0              | 535            | 535          |
| 2024     | 0              | 1205           | 1205         |
| 2025     | 0              | 1227           | 1227         |
| 2026     | 0              | 735            | 735          |

### By quarter (ASCII histogram)

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

| Cutoff                                 | raw_Meta     | raw_Mf       | raw_Comb     | snap_Meta    | snap_Mf      | snap_Comb    |
|----------------------------------------|--------------|--------------|--------------|--------------|--------------|--------------|
| 2022-01 (GPT-4 class)                  | 0            | 3728         | 3728         | 0            | 2886         | 2886         |
| 2023-04 (approx GPT-4-class)           | 0            | 3598         | 3598         | 0            | 2827         | 2827         |
| 2023-10 (GPT-4o train cutoff)          | 0            | 3409         | 3409         | 0            | 2709         | 2709         |
| 2024-04 (Claude-3.5-Sonnet)            | 0            | 2540         | 2540         | 0            | 2108         | 2108         |
| 2024-10 (GPT-4o-mini / o3 approx)      | 0            | 2122         | 2122         | 0            | 1789         | 1789         |
| 2025-01 (Gemini-2.5-Pro / Claude-3.7)  | 0            | 1495         | 1495         | 0            | 1183         | 1183         |
| 2025-04 (mid-2025 class)               | 0            | 1272         | 1272         | 0            | 1004         | 1004         |

Columns: raw_* = count satisfying D-006 date rule only; snap_* = subset with crowd-snapshot feasibility heuristic (created before T and has ≥1 bet/forecast).

**Tradeoff interpretation:** older cutoffs yield more clean N but restrict the model panel to older, weaker models. Newer cutoffs shrink clean N but permit stronger models. Panel choice (D-009) resolves this after seeing the tradeoff curve above.

---

## 4. Manifold Liquidity Assessment (RQ4 Viability)

Based on 3728 Manifold AI-progress binary resolved questions.

### Summary statistics (mana = Manifold play-money)

| Metric                       | Median     | P25        | P75        | P90        | Mean       |
|------------------------------|------------|------------|------------|------------|------------|
| Volume (mana)                | 3827.5     | 1086.0     | 11523.1    | 30169.5    | 25571.9    |
| Unique bettors               | 22.0       | 12.0       | 43.0       | 89.0       | 46.7       |
| Total liquidity (mana)       | 970.0      | 190.0      | 1000.0     | 1235.0     | 1023.9     |

Note: trade count is not returned by the `/v0/markets` listing endpoint; it is omitted from this table. Volume and unique bettors are the primary liquidity indicators.

### Viability thresholds

Threshold: >=20 bettors AND >=1000.0 mana volume

- N above 20 unique bettors: 2085 / 3728 (55.9%)
- N above 1,000 mana volume: 2865 / 3728 (76.9%)
- N meeting BOTH thresholds: **2038 / 3728 (54.7%)**

**RQ4 viability verdict: VIABLE — substantial fraction of markets have enough liquidity for microstructure analysis.**

Reminder: Manifold uses play-money (mana), not USD. Even liquid mana markets represent illustrative mechanics, not real economic value. Any RQ4 claim must state this explicitly.

---

## 5. RQ3 Power Sketch (Simulation Substitute for Blocked Pilot)

**Status: No LLM API keys present. Pilot elicitation (DATA.md item 5) is deferred until keys exist. This section reports a seeded Monte Carlo simulation as a substitute.**

### Simulation design

- Seed: 42
- Monte Carlo replications per cell: 5,000
- Alpha: 0.05
- Information weight of weaker source (w): 0.25 (25% scenario — weaker source carries 25% of information; neither is collinear with the other)
- Model: true_logit ~ N(0, 1.5); crowd/model logits = sqrt(ρ)*true + sqrt(1-ρ)*noise
  where ρ is the target crowd-model correlation
- Test: logistic regression outcome ~ logit(crowd) + logit(model) via Newton-Raphson;
  power = fraction of simulations where BOTH β_crowd and β_model are significant (z > 1.96)

### Power grid (power_both = P[reject β_crowd=0 AND β_model=0])

| N \ ρ    | ρ=0.4        | ρ=0.6        | ρ=0.75       | ρ=0.9        |
|----------|--------------|--------------|--------------|--------------|
| 50       | 0.069        | 0.037        | 0.011        | 0.002        |
| 100      | 0.357        | 0.279        | 0.112        | 0.003        |
| 200      | **0.833**    | 0.789        | 0.598        | 0.049        |
| 400      | **0.995**    | **0.992**    | **0.960**    | 0.549        |
| 1004     | **1.000**    | **1.000**    | **1.000**    | **0.979**    |
| 1183     | **1.000**    | **1.000**    | **1.000**    | **0.992**    |
| 1789     | **1.000**    | **1.000**    | **1.000**    | **1.000**    |
| 2108     | **1.000**    | **1.000**    | **1.000**    | **1.000**    |
| 2709     | **1.000**    | **1.000**    | **1.000**    | **1.000**    |
| 2827     | **1.000**    | **1.000**    | **1.000**    | **1.000**    |
| 2886     | **1.000**    | **1.000**    | **1.000**    | **1.000**    |

Bold = power_both >= 80%. Values are empirical rejection rates across 5,000 simulations.

### Minimum N for 80% power per ρ

| ρ              | Min N for 80% power  |
|----------------|----------------------|
| 0.4            | 200                  |
| 0.6            | 400                  |
| 0.75           | 400                  |
| 0.9            | 1004                 |

---

## RECOMMENDATION

### Primary data source

**Manifold** is the sole accessible source for Phase 0 (D-009) because:
- Metaculus API now returns HTTP 403 Forbidden for all endpoints without authentication.
  The error body states: 'The API is only available to authenticated users.'
  This is a policy change from the previously key-less public API documented in DATA.md.
- Manifold yielded 3728 AI-progress binary resolved questions via key-less public API.

**Recommended action:** Obtain a Metaculus API token to unlock their dataset. With a token, Metaculus could add significant N (especially for pre-2022 resolved questions). For Phase 1 onward, provision a Metaculus token in `.env` (key: `METACULUS_API_TOKEN`).
### Candidate model panel (D-009)

Recommended ~3-model panel spanning capability and recency, based on the clean-N tradeoff:

| Model | Knowledge cutoff | Est. snap-feasible N (combined) | Role |
|---|---|---|---|
| GPT-4 (0314) | 2022-01-01 | 2886 | Older / high N |
| GPT-4o / Claude-3.5-Sonnet | 2023-10-01 | 2709 | Mid-range |
| Claude-3.7-Sonnet / Gemini-2.5-Pro | 2025-01-01 | 1183 | Newest / smallest N |

### RQ3 confirmatory vs. exploratory verdict (D-008)

At the representative cutoff 2023-10 (GPT-4o class), observed clean N = **2709**.

**RQ3 VERDICT: CONFIRMATORY** — observed N=2709 meets the 80% power threshold at ρ ≤ 0.75. RQ3 can proceed as a confirmatory test per D-008.

### RQ4 viability verdict

**RQ4 VIABLE** — 2038 / 3728 (54.7%) Manifold markets meet liquidity thresholds. Microstructure backtest is meaningful on the liquid subset.

---

## LIMITATIONS

1. **No pilot elicitation** — The DATA.md item 5 pilot (LLM forecasts on ~20-30 questions to estimate empirical market-model correlation ρ) is blocked because no LLM API keys exist in this environment. The power sketch uses a simulated ρ grid; the actual ρ may be higher or lower. Until the empirical ρ is measured in Phase 1, the power verdict is tentative. If empirical ρ > 0.75, additional N (by broadening sources or extending the date range) may be needed before RQ3 can be labeled confirmatory.

2. **Keyword classifier (v1.0) precision** — The keyword filter is a coarse first pass. Estimated precision is ~85.3% (lower bound). Some false positives (non-AI-progress questions matched by generic keywords like ' ai ') and false negatives (AI-progress questions without the specific keywords) will remain. The Phase-2 LLM-assisted classifier will resolve this; Phase-0 counts are approximate.

3. **Snapshot feasibility heuristic** — We cannot query the actual crowd-prediction history at T = resolved_at - 30d without fetching full time-series data (a heavier pull). The snapshot-feasible counts use a necessary-condition heuristic: question was created before T and has at least one bet/forecast recorded. Some questions in the snapshot-feasible count may still lack a forecast at the exact T; actual available N may be ~5-15% lower.

4. **Metaculus authentication required** — As of 2026-07-15, Metaculus `/api2/` and all other Metaculus endpoints return HTTP 403 Forbidden without an API token. Metaculus data is entirely absent from this Phase-0 report. Provisioning a token in `.env` (key: `METACULUS_API_TOKEN`) and re-running the recon will add additional N, particularly for questions resolved before 2022 (Manifold's coverage is thin there). Manifold v0 endpoints are working and used as the sole source here.

5. **Manifold group coverage** — Only the group slugs listed in `config.py` are queried. Additional AI-adjacent groups may exist under different slugs; their markets are missed. This is a conservative estimate of Manifold's total AI-progress coverage.

6. **Play-money caveat (Manifold)** — Manifold uses mana, not real money. All liquidity figures are in mana; any RQ4 economic-value claim is illustrative at best.
