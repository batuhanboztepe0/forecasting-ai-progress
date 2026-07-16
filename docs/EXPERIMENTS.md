# EXPERIMENTS.md

Registry of every run and the running **cost ledger**. Append-only. This is how the project
stays reproducible and on-budget; the orchestrator checks the running total against the
`SCOPE.md` guardrail.

## Run registry

Every run (data pull, elicitation, analysis) gets a row. Runs must be reproducible from their
config + seed.

| run_id | date | phase | type | config ref (path@commit) | seed | models | N | key result / artifact | notes |
|---|---|---|---|---|---|---|---|---|---|
| recon-2026-07-15 | 2026-07-15 | 0 | data-pull+simulation | src/recon/config.py@HEAD | 42 | none (no API keys) | 3728 | data/interim/questions_combined.json | Phase-0 recon: 3728 Manifold AI-progress binary questions; Metaculus blocked (auth required); no LLM calls; pilot elicitation deferred |
| recon-metaculus-2026-07-16 | 2026-07-16 | 0 | data-pull | src/recon/fetch_metaculus_v11.py@HEAD | 42 | none | 142 | data/interim/metaculus_questions.json | Metaculus re-pull with Token auth: 142 AI-progress binary questions (resolution=null — API limitation; Phase 2 blocker); 443 raw fetched, 5 real pages |
| pilot-elicitation-2026-07-16 | 2026-07-16 | 0 | elicitation+correlation | src/recon/pilot_elicitation.py@HEAD | 42 | claude-haiku-4-5-20251001, claude-sonnet-5 | 30 | data/interim/pilot_elicitation_results.json | Pilot: 30 questions, 2 models; crowd_prob_at_T from Manifold bets; haiku r=0.49 CI=[0.16,0.72]; sonnet-5 r=0.66 CI=[0.39,0.82]; pooled rho=0.57; temperature deprecated for sonnet-5 |
| mvp-thin-slice-2026-07-16 | 2026-07-16 | 1 | elicitation | src/mvp/mvp_config.py@HEAD | 42 | haiku-4-5,sonnet-5,opus-4-8 | 50 | data/interim/mvp_forecasts.csv | MVP thin slice: 50q×3 models protocol-v1; n_success per model see cost ledger; n_cache=30 parse_err=0 refusals=0 |
| mvp-scoring-2026-07-16 | 2026-07-16 | 1 | analysis | src/analysis/score_mvp.py@HEAD | — | none (no API calls) | 50 | data/interim/mvp_scores.csv, docs/figures/mvp_calibration.png, docs/mvp_results.md | Brier/BSS/CITL scoring + 2×2 reliability diagram; USD 0.00; self-test PASS |
| _example_ | 2026-01-01 | 1 | elicitation | configs/mvp.yaml@abc123 | 42 | c-sonnet, gpt-mini | 100 | data/interim/mvp_scores.parquet | dry run |

## Cost ledger (LLM API)

Append one row per run that hits the API. Keep the running total current.

| run_id | model | input_tokens | output_tokens | batch? | cache? | USD | cumulative USD |
|---|---|---|---|---|---|---|---|
| recon-2026-07-15 | none | 0 | 0 | no | no | 0.00 | 0.00 |
| recon-metaculus-2026-07-16 | none | 0 | 0 | no | no | 0.00 | 0.00 |
| pilot-elicitation-2026-07-16 | claude-haiku-4-5-20251001 | 5,476 | 460 | no | partial | 0.0078 | 0.0078 |
| pilot-elicitation-2026-07-16 | claude-sonnet-5 | 7,632 | 1,541 | no | no | 0.0460 | 0.0538 |
| mvp-thin-slice-2026-07-16 | claude-haiku-4-5-20251001 | 7,601 | 705 | no | partial | 0.0111 | 0.0651 |
| mvp-thin-slice-2026-07-16 | claude-sonnet-5 | 9,854 | 811 | no | partial | 0.0278 | 0.0930 |
| mvp-thin-slice-2026-07-16 | claude-opus-4-8 | 9,854 | 600 | no | partial | 0.0643 | 0.1572 |
| _example_ | claude-sonnet | 120,000 | 40,000 | yes | yes | 0.00 | 0.00 |

**Running total: USD 0.1572** &nbsp; (guardrail: escalate if a single run is projected > USD 25;
target full study ≲ USD 20–35 — see `SCOPE.md` §6.)

Notes:
- pilot-elicitation haiku: temperature=0 (supported); 30 cache hits on second pass counted as 0 tokens
- pilot-elicitation sonnet-5: temperature omitted (deprecated for this model, HTTP 400); responses cached in data/llm_cache/ (git-ignored)

## Planned v1 budget (D-011; estimate — reconcile against the ledger as runs land)

| item | calls (est.) | model | est. USD (batched) |
|---|---|---|---|
| Phase 1 thin slice (~50 q × 3 models) | ~150 | panel | ~0.30 (no batch — latency) |
| Phase 2 LLM-assist classifier (~5,700 candidates) | ~5,700 | haiku-4-5 | ~1.1–2.3 |
| Phase 2 elicitation (~1,600 q) | 1,600 | haiku-4-5 | ~0.7–1.4 |
| Phase 2 elicitation (~1,600 q) | 1,600 | sonnet-5 (intro pricing) | ~1.4–2.9 |
| Phase 2 elicitation (~1,600 q) | 1,600 | opus-4-8 | ~3.6–7.2 |
| Variance probe (100 q × 3 repeats) | 300 | sonnet-5 | ~0.3–0.6 |
| Contingency (retries, parse failures, prompt iteration) | — | — | ~3–5 |
| **Core total** | | | **~8–15** |
| Optional fable-5 frontier probe (~475 q, always-on thinking) | ~475 | fable-5 | ~10 (only if time/budget allow) |

Guardrails unchanged: escalate if a single run projects > USD 25; full study ≤ USD 35.

## Notes

- Cost = actual billed, not estimated, once known. Estimate first, reconcile after.
- If a run is served from cache, record USD 0 and note "cache hit".
- Link large result artifacts by path; keep raw payloads out of git (see `.gitignore`).
