# Forecasting AI Progress: Are Markets and Models Calibrated?

**Status:** work in progress — v1 pre-registered (RQ1–RQ3 confirmatory core; RQ4 preliminary,
play-money). Pipeline build in progress; results not yet final.

An empirical study of how well **prediction-market crowds** and **large language models**
forecast **AI progress itself** — benchmark saturation, model releases, capability
milestones, compute trends, and AI-lab outcomes — and, crucially, **which source carries
information the other systematically misses**.

Most LLM-forecasting work asks "can models forecast as well as crowds?" on general questions.
We narrow to the AI-progress domain (where forecasts feed directly into governance and
early-warning discussions) and shift the question from a raw accuracy horse-race to
**information content**: after controlling for training-data contamination, do markets and
models disagree in structured, characterizable ways?

## Research questions

- **RQ1 — Calibration.** Are AI-progress forecasts (market vs. model) well-calibrated, or
  systematically biased (over- vs. under-predicting progress)?
- **RQ2 — Skill vs. memorization.** How much apparent skill survives once we restrict to
  questions resolving *after* each model's training cutoff?
- **RQ3 — Information content.** Does the market price contain information about resolution
  that the model's forecast does not (and vice versa)? Measured via forecast-encompassing /
  incremental-information tests.
- **RQ4 — Microstructure.** Does any apparent forecasting edge survive realistic market
  frictions (liquidity, slippage, fees), and does post-hoc recalibration recover value?

Hypotheses, directional predictions, and decision thresholds are **pre-registered** in
[`SCOPE.md`](SCOPE.md) before data collection.

## Method (summary)

1. Collect resolved binary AI-progress questions from public sources (Metaculus, Manifold).
2. Snapshot the crowd probability at a fixed lead time before resolution.
3. Elicit probabilities from a panel of LLMs under a fixed protocol (no live web access).
4. Score all forecasters with proper scoring rules (Brier, log-loss) and calibration
   metrics (reliability diagrams, ECE, Murphy decomposition).
5. Split by each model's knowledge cutoff; treat pre-cutoff performance as a memorization
   probe, post-cutoff as genuine skill.
6. Test information content and (on post-cutoff questions) a friction-aware backtest.
7. Report honestly, including null and unexpected results.

See [`DATA.md`](DATA.md) for sources, schema, and contamination handling.

## Repository map

```
CLAUDE.md            Coding + collaboration rules for AI agents working in this repo
HANDOFF.md           Multi-agent orchestration model and iteration protocol
SCOPE.md             Pre-registered research design (RQs, hypotheses, success criteria)
DATA.md              Data sources, schema, provenance, contamination handling
.claude/agents/      Specialized subagent role definitions
.claude/skills/      Research + reasoning skills (methodology, scoring, stats, ...)
docs/                Writing style, production log, decision record, experiment registry
data/release/        Curated, versioned dataset artifact (committed)
```
(Directories `src/`, `tests/`, `data/raw/`, `paper/` are created during the build.)

## Reproducibility

Every result is produced by a deterministic, config-driven pipeline with fixed seeds and
cached LLM responses. Raw payloads are excluded from version control; provenance
(query parameters, timestamps, content hashes) is recorded so runs can be reproduced.

## Cost

Total LLM API spend is tracked per run in [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md).
The full study is designed to run for a modest budget (low tens of USD) using batched
requests and prompt caching.

## Relationship to prior work

This project builds on public work on LLM forecasting and prediction markets, on the
knowledge-cutoff / contamination problem in LLM evaluation, and on the economics of
transformative AI. Specific references are catalogued in `SCOPE.md` and the final report.

## License

Code: MIT. Dataset artifact (`data/release/`): CC-BY-4.0. See `SCOPE.md` for citation.
