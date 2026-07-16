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
| _example_ | 2026-01-01 | 1 | elicitation | configs/mvp.yaml@abc123 | 42 | c-sonnet, gpt-mini | 100 | data/interim/mvp_scores.parquet | dry run |

## Cost ledger (LLM API)

Append one row per run that hits the API. Keep the running total current.

| run_id | model | input_tokens | output_tokens | batch? | cache? | USD | cumulative USD |
|---|---|---|---|---|---|---|---|
| recon-2026-07-15 | none | 0 | 0 | no | no | 0.00 | 0.00 |
| recon-metaculus-2026-07-16 | none | 0 | 0 | no | no | 0.00 | 0.00 |
| pilot-elicitation-2026-07-16 | claude-haiku-4-5-20251001 | 5,476 | 460 | no | partial | 0.0078 | 0.0078 |
| pilot-elicitation-2026-07-16 | claude-sonnet-5 | 7,632 | 1,541 | no | no | 0.0460 | 0.0538 |
| _example_ | claude-sonnet | 120,000 | 40,000 | yes | yes | 0.00 | 0.00 |

**Running total: USD 0.054** &nbsp; (guardrail: escalate if a single run is projected > USD 25;
target full study ≲ USD 20–35 — see `SCOPE.md` §6.)

Notes:
- pilot-elicitation haiku: temperature=0 (supported); 30 cache hits on second pass counted as 0 tokens
- pilot-elicitation sonnet-5: temperature omitted (deprecated for this model, HTTP 400); responses cached in data/llm_cache/ (git-ignored)

## Notes

- Cost = actual billed, not estimated, once known. Estimate first, reconcile after.
- If a run is served from cache, record USD 0 and note "cache hit".
- Link large result artifacts by path; keep raw payloads out of git (see `.gitignore`).
