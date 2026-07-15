# EXPERIMENTS.md

Registry of every run and the running **cost ledger**. Append-only. This is how the project
stays reproducible and on-budget; the orchestrator checks the running total against the
`SCOPE.md` guardrail.

## Run registry

Every run (data pull, elicitation, analysis) gets a row. Runs must be reproducible from their
config + seed.

| run_id | date | phase | type | config ref (path@commit) | seed | models | N | key result / artifact | notes |
|---|---|---|---|---|---|---|---|---|---|
| _example_ | 2026-01-01 | 1 | elicitation | configs/mvp.yaml@abc123 | 42 | c-sonnet, gpt-mini | 100 | data/interim/mvp_scores.parquet | dry run |

## Cost ledger (LLM API)

Append one row per run that hits the API. Keep the running total current.

| run_id | model | input_tokens | output_tokens | batch? | cache? | USD | cumulative USD |
|---|---|---|---|---|---|---|---|
| _example_ | claude-sonnet | 120,000 | 40,000 | yes | yes | 0.00 | 0.00 |

**Running total: USD 0.00** &nbsp; (guardrail: escalate if a single run is projected > USD 25;
target full study ≲ USD 20–35 — see `SCOPE.md` §6.)

## Notes

- Cost = actual billed, not estimated, once known. Estimate first, reconcile after.
- If a run is served from cache, record USD 0 and note "cache hit".
- Link large result artifacts by path; keep raw payloads out of git (see `.gitignore`).
