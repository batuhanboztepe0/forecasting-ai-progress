# Datasheet for the AI-Progress Forecasting Dataset

Version 1.0 — 2026-07-17

---

## 1. Motivation

**Purpose.** This dataset was created to quantify whether frontier LLMs have genuine forecasting
skill on AI-progress questions — distinguishing memorisation of training-data outcomes from
actual reasoning about uncertain future events — and to measure how LLM forecasts compare with
Manifold prediction-market crowds on the same questions.

**Who created it and why.** Batuhan Boztepe (Anthropic Fellow, 2026). The study is a
reproducible, publicly archived experiment in the spirit of open science. All design decisions
are pre-registered (see `docs/SCOPE.md`, `docs/DECISIONS.md`).

**Funding.** Anthropic Fellowship (API credits and compute).

---

## 2. Composition

### 2a. Questions (`questions.csv`, 1,187 rows)

Each row is a resolved binary prediction-market question. Fields:

| Field | Type | Description |
|---|---|---|
| `qid` | string | Unique question identifier (`manifold_<slug>`) |
| `source` | string | Data source (`manifold`) |
| `title` | string | Question title as fetched from the Manifold API |
| `created_at` | ISO-8601 | Market creation timestamp |
| `close_at` | ISO-8601 | Market close (trading stops) timestamp |
| `resolved_at` | ISO-8601 | Official resolution timestamp |
| `outcome` | int 0/1 | Resolution outcome (1 = YES, 0 = NO) |
| `crowd_prob_at_T` | float [0,1] | Crowd probability at snapshot T = resolved_at − 30 days |
| `total_liquidity` | float | Total Mana added as liquidity (proxy pool depth for CPMM) |
| `unique_bettors_at_T` | int | Number of unique bettors with at least one bet before T |
| `volume_mana_at_T` | int | Cumulative bet volume (Mana) before T |
| `trade_count_at_T` | int | Number of trades before T |
| `content_hash` | hex | SHA-256 of `title` (content fingerprint) |
| `classifier_verdict` | string | LLM classifier v1.1 decision (`keep` = AI-progress question) |
| `stratum` | string | Analysis stratum (`haiku_clean` or `pre_cutoff_probe`) |
| `close_before_cutoff_haiku` | int 0/1 | D-014 flag: market closed before haiku training cutoff (2025-07-31) |
| `close_before_cutoff_jan2026` | int 0/1 | D-014 flag: market closed before sonnet/opus training cutoff (2026-01-31) |
| `close_before_T` | int 0/1 | D-014 flag: market closed before snapshot T (crowd price equals closing price) |

**Strata.** `haiku_clean` (N=352): questions where the model is information-disadvantaged
vs the crowd (resolved_at ≥ cutoff + 30 d AND close_at ≥ cutoff). Confirmatory stratum for
haiku. `pre_cutoff_probe` (N=835): remaining questions; used in RQ2's memorisation contrast.
Note: the analysis scripts and `docs/phase3_results.md` refer to this stratum as
"haiku_probe" — the two names are synonymous (complement of `haiku_clean`, N=835).

### 2b. Forecasts (`forecasts.csv`, 3,761 rows)

Each row is one model's probability elicitation for one question, one repeat.

| Field | Type | Description |
|---|---|---|
| `qid` | string | Links to `questions.csv` |
| `model` | string | Anthropic model ID |
| `protocol` | string | Elicitation protocol version (`v2`) |
| `repeat` | int 0–2 | Repeat index (0 = main run; 1–2 = variance probe, sonnet-5 only) |
| `model_prob` | float [0,1] | Parsed probability from the model's JSON output |
| `elicited_at` | ISO-8601 | Timestamp the model response was cached |
| `cache_hit` | bool | True if served from local cache (no new API call) |
| `parse_error` | bool | True if the model output could not be parsed (probability is missing) |
| `outcome` | int 0/1 | Resolution outcome (included for scoring; never in model prompts) |
| `crowd_prob_at_T` | float [0,1] | Crowd probability at T (included for scoring) |
| `resolved_at` | ISO-8601 | Resolution timestamp (for sorting in RQ4 backtest) |
| `is_post_cutoff` | int 0/1 | 1 if resolved_at ≥ model_cutoff + 30 d (per D-006) |
| `close_before_cutoff_haiku` | int 0/1 | D-014 flag (see questions.csv) |
| `close_before_cutoff_jan2026` | int 0/1 | D-014 flag |
| `close_before_T` | int 0/1 | D-014 flag |

**Models.** Three panel models (all from Anthropic; D-011):
- `claude-haiku-4-5-20251001` — training cutoff ≈ 2025-07-31
- `claude-sonnet-5` — training cutoff ≈ 2026-01-31
- `claude-opus-4-8` — training cutoff ≈ 2026-01-31

Repeats 1 and 2 for sonnet-5 on a seeded 100-question variance probe (seed=42).

### 2c. Raw responses

Raw LLM response text and batch API payloads are excluded from the release (they are
git-ignored). Only parsed probabilities are distributed.

### 2d. Missing data

`parse_error=True`: 0 rows in the current release (all 3,761 elicitations parsed successfully).

---

## 3. Collection Process

### 3a. Source

Manifold Markets public prediction market API (https://manifold.markets/api). Data collected
2026-07-15 to 2026-07-16 via authenticated GET requests. All markets are publicly accessible;
no personal or private user data was collected.

### 3b. Keyword filter v1.0

An initial broad keyword regex matched question titles against AI-related terms
(`\b(AI|LLM|GPT|Claude|Gemini|machine learning|...)\b`). This produced a candidate pool of
approximately 5,700 questions out of a broader Manifold corpus.

### 3c. LLM classifier v1.1

A Claude `haiku-4-5-20251001` Batch-API classifier was applied to every candidate title to
determine whether the question primarily concerns demonstrable AI-capability progress (not AI
policy, deployment, regulation, or social impact).

**Audited error estimates (two independent 40-question audit samples):**
- Keep-precision: 40/40 (100%) and 38–40/40 (95–100%) — no false positives in either sample
- Drop-side false-negative rate: approximately 7.5% (3/40 relevant questions missed);
  95% binomial CI approximately 3–20% (Wilson interval)

Net effect: the dataset under-represents a minority of valid AI-progress questions (≈7.5%
exclusion error) but contains essentially no false positives. The false-negative direction
introduces a slight selection bias toward "mainstream" AI topics.

### 3d. Snapshot definition (D-007)

`crowd_prob_at_T` is the Manifold market probability at T = resolved_at − 30 days, computed
from the full per-question bet history. Bets placed after T are excluded.

The minimum-activity filter requires at least 1 bet before T. For 152/1,187 questions
(close_before_T=1) the market closed before T; in these cases `crowd_prob_at_T` equals the
market's final closing price (38 in `haiku_clean`, 114 in `pre_cutoff_probe`).

### 3e. Training-cutoff contamination rules

Three contamination rules were applied (D-006, D-013, D-014):

**D-006 (snapshot-aware rule):** For a genuine model-vs-crowd comparison, a question is
classified as "clean" for model M with cutoff C iff resolved_at ≥ C + 30 days. This ensures
the model is information-disadvantaged (the crowd's T-snapshot predates C; the model has no
outcome information not available to the crowd).

**D-013 (classifier realignment):** Classifier v1.1 replaced v1.0 after a red-team audit
found scope drift; v1.1 aligns with the pre-registered domain definition (AI-capability
progress). All 1,187 questions carry `classifier_verdict = keep` under v1.1.

**D-014 (close-date refinement):** A question is clean for model M iff BOTH resolved_at ≥
C + 30d AND close_at ≥ C. Questions with close_at < C have their outcome effectively
determined before the model's training cutoff (only the admin resolution lag is post-cutoff).
These questions are flagged via `close_before_cutoff_haiku` / `close_before_cutoff_jan2026`
and moved to the probe stratum for that model. Effect: haiku confirmatory N = 352 (vs 390
before D-014); 38 flagged questions are analysed in the memorisation probe.

### 3f. Elicitation protocol v2 (D-012)

Each model was asked to forecast the probability of YES resolution in a single, fixed
prompt (no system prompt). The prompt supplies: the question title, the snapshot date T, and
a fixed instruction to reason briefly (1–2 sentences) and then emit exactly:
`{"prob": <float>}`.

**Prompt SHA-256:** `16108381d2bc51ca...` (full hash in `data/phase2_manifest.json`,
field `step_b_elicitation.system_prompt_hash`).

Key design choices (no leakage):
- `outcome` and `resolved_at` are never interpolated into the prompt text (asserted in
  the elicitation script).
- Title-only: question descriptions were not fetched to avoid the post-resolution
  description-edit leakage channel (Manifold's API returns current, editable text).
- Temperature = default (no override); models seeded deterministically via the Batches API
  cache (same prompt → same cached response).

Elicitation ran via Anthropic Message Batches API (50% discount) on 2026-07-16.
Batch IDs and per-model costs are recorded in `docs/EXPERIMENTS.md`.

---

## 4. Preprocessing / Cleaning

- Markets with fewer than 1 bet before T were excluded.
- Questions resolving N/A (ambiguous) were excluded.
- Duplicate question slugs (identical qid) were deduplicated; none found.
- `close_at` values in the original Manifold JSON were taken verbatim (UTC); no timezone
  correction was applied.

---

## 5. Uses

**Intended use.** Quantitative evaluation of LLM forecasting skill on AI-progress questions;
comparison of LLM and prediction-market forecasts; calibration analysis.

**Out-of-scope use.**
- Do not use `crowd_prob_at_T` as a training signal for models that will be tested on the
  same questions (data leakage).
- Play-money prices (Manifold Mana) should not be treated as real financial probabilities;
  the incentive structure differs from real-money markets (see caveats below).
- Do not use outcomes to evaluate forecasters who could have seen the outcomes in training
  without accounting for the cutoff flags.

---

## 6. Distribution

**License.** CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/).

**Attribution required.** When using this dataset, cite:

> Boztepe, B. (2026). *AI-Progress Forecasting Dataset v1.0*. Anthropic Fellow Project.
> Data sourced from Manifold Markets (https://manifold.markets) under Manifold's public API
> terms of service.

Manifold Markets attribution: data is derived from Manifold's public API. Manifold operates
under a Creative Commons licence for market data; see https://manifold.markets/terms for
current terms.

**Release date.** 2026-07-17.

---

## 7. Known Caveats and Limitations

1. **Title-only elicitation.** Models see only the question title, not the description or
   resolution criteria. Human forecasters on Manifold had access to full descriptions, giving
   them an information advantage. Model-beats-crowd findings are therefore conservative;
   crowd-beats-model findings may partly reflect information asymmetry.

2. **Play-money incentives.** Manifold uses fictional Mana currency. Price discovery may be
   noisier than real-money markets. The RQ4 backtest uses Mana throughout; no real financial
   inference should be drawn.

3. **Single provider.** All three panel models are from Anthropic. Cross-provider comparison
   is future work.

4. **Two training cutoffs.** The panel covers two cutoffs: 2025-07-31 (haiku) and 2026-01-31
   (sonnet/opus). Generalisation to other cutoffs is untested.

5. **T = 30 days only.** A single snapshot horizon was used. Multi-horizon robustness is
   future work.

6. **CPMM approximation (RQ4).** The stored `total_liquidity` field is Manifold's
   `addedLiquidity` (cumulative Mana deposited), not actual pool shares; live-API spot checks
   found actual pool sums 7–12× larger. The backtest uses standard binary CPMM as an
   approximation. The H4 NO-EDGE conclusion is robust to this (losses dominate wins; hit rate
   ≈22%).

7. **Classifier false-negative rate.** Approximately 7.5% of valid AI-progress questions may
   have been excluded by the v1.1 classifier. This affects absolute counts but not the
   within-sample analysis (all included questions are true positives).

---

## 8. Maintenance

This is a v1.0 snapshot; no live updates are planned. Bug reports: open a GitHub issue.
Contact: boztepe.batuhan12363@gmail.com.
