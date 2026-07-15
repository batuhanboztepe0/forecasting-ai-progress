---
name: reproducible-pipeline
description: How to build the data + experiment pipeline so runs are deterministic, cached, cost-tracked, and reproducible from a clean checkout. Use when writing any data-collection, elicitation, or analysis code, when caching LLM calls, or when tracking API cost. Consult before adding any step that hits an API or produces a result artifact.
---

# Reproducible Pipeline

Same config + same seed → same result. This is a hard requirement, not a nicety.

## Configuration & determinism

- One config source of truth (e.g., a versioned YAML/TOML). No magic literals in code — model
  panel, cutoff dates, snapshot lead times, edge thresholds, seeds all live in config.
- Seed every stochastic step (sampling, bootstrap, any RNG). Record the seed with each result.
- Pure functions at the core; push I/O, clock, and API access to injectable boundaries so the
  logic is testable without the network.

## Layered data flow

`raw → interim → release`. Raw = exact API responses (git-ignored) + committed manifest
(query params, timestamps, content hashes). Interim = derived tables (git-ignored, regenerable).
Release = curated artifact (committed, with datasheet). Never edit raw by hand.

## LLM caching & cost

- Cache every model response keyed by `(qid, model, variant, repeat, seed, prompt_hash)`.
  Re-runs hit cache; nothing is paid twice.
- Use **batch requests** (large discount) and **prompt caching** for the shared instruction
  block. Cap output tokens on reasoning models.
- **Cost ledger:** every run appends model, input/output tokens, and USD to
  `docs/EXPERIMENTS.md`. The orchestrator checks spend against the `SCOPE.md` guardrail.

## Testing

- Known-input unit tests for every metric (a hand-checked example → exact expected value).
- A tiny fixture dataset for a fast end-to-end pipeline test that runs offline (mocked API).

## Reproduction contract

From a clean checkout: install, provide keys via `.env`, run `make`/one command per phase, and
regenerate headline numbers + figures. If it doesn't reproduce that way, it isn't done.

## Public-safety

Keys only from `.env` (git-ignored). Never commit raw payloads, caches, or secrets — enforced by
`.gitignore`. Verify before every commit.
