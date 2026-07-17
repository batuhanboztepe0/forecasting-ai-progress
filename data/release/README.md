# AI-Progress Forecasting Dataset — Reproduction Guide

This directory contains the public release of the AI-Progress Forecasting Dataset v1.0.
See `DATASHEET.md` for full provenance, methodology, and caveats.

## Files

| File | Rows | Description |
|---|---|---|
| `questions.csv` | 1,187 | One row per resolved AI-progress market question |
| `forecasts.csv` | 3,761 | One row per (question, model, repeat) probability elicitation |
| `reference_results.json` | — | Committed reference values for the reproduction check |
| `DATASHEET.md` | — | Standard datasheet for the dataset |
| `README.md` | — | This file |

## Reproduction: headline numbers from a clean clone

### Prerequisites

```bash
# Python 3.11+ required
pip install numpy scipy matplotlib
```

The runner imports `rq_confirmatory` and `rq4_backtest` from `src/analysis/` — no
additional installation step is needed beyond the requirements above.

### Steps

```bash
# 1. Clone the repo
git clone <repo-url>
cd forecasting-ai-progress

# 2. Run the end-to-end reproduction check
python3.11 src/analysis/reproduce_from_release.py
```

That single command:

1. Loads `data/release/questions.csv` and `data/release/forecasts.csv`.
2. Converts questions to the JSON format required by the analysis library.
3. Monkey-patches path constants in `rq_confirmatory` and `rq4_backtest` so
   they read from `data/release/` and write to `temp/reproduce_out/`.
4. Runs RQ1–RQ3 confirmatory + sensitivity analyses and the RQ4 backtest
   (same seeds, same code — results are bit-identical).
5. Compares 28 key numbers against `data/release/reference_results.json`
   (tolerance 1e-6 on floats).
6. Prints a PASS/FAIL table and exits 0 (all pass) or non-zero (mismatch).

### Expected output (final lines)

```
TOTAL: 28 PASS / 0 FAIL
======================================================================

REPRODUCTION PASSED: all headline numbers match within tolerance.
```

### Optional arguments

```bash
# Write outputs to a custom directory
python3.11 src/analysis/reproduce_from_release.py --out-dir /tmp/my_repro

# Widen the tolerance (default 1e-6)
python3.11 src/analysis/reproduce_from_release.py --tol 1e-4
```

## What is checked

| Test group | N checks | Covers |
|---|---|---|
| RQ1 (CITL + CI + p + decision) | 10 | Crowd and haiku calibration |
| RQ2 (ΔBSS + CI + p) | 4 | Haiku pre/post Brier skill score contrast |
| RQ3 (b_crowd, b_model, p-values) | 4 | Encompassing regression coefficients |
| BH family corrections | 5 | Benjamini-Hochberg family rejection decisions |
| RQ4 (P&L, CI, decision) | 5 | Haiku CPMM backtest results |
| **Total** | **28** | |

## Headline findings

All findings are pre-registered in `SCOPE.md`. Key confirmatory results:

- **H1 (calibration):** Crowd CITL = +0.035 (CI excludes 0, but |CITL| < 0.05 threshold —
  FAIL-CITL-THRESHOLD). Haiku CITL = +0.004 (CI includes 0 — FAIL-TO-REJECT).
- **H2 (skill decay):** Haiku ΔBSS = −0.119 (post−pre); CI [−0.268, +0.021], p = 0.104 —
  FAIL-TO-REJECT at q=0.10 after BH correction.
- **H3a (crowd coefficient):** b_crowd = 1.18, p < 0.0001 — BH-rejected (crowd
  independently forecasts outcome).
- **H3b (model coefficient):** b_model = 0.11, p = 0.350 — not BH-rejected (model adds no
  independent information beyond the crowd, conditional on having access to crowd prices).
- **H4 (trading edge):** Total P&L = −1199 Mana, CI [−1649, −710] — NO-EDGE.

See `docs/phase3_results.md` for the full analysis narrative.

## License

CC-BY-4.0. Attribution: Boztepe, B. (2026). *AI-Progress Forecasting Dataset v1.0*.
Manifold Markets data sourced under Manifold's public API terms (https://manifold.markets/terms).
