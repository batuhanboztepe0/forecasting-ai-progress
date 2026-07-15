# HANDOFF.md — how this project runs

This repo is built by an **orchestrator + specialized subagents**, designed for **long,
autonomous work sessions** that can be paused and resumed across chats without losing state.

## Core principle: the repo is the memory

There is no reliance on chat history. **All durable state lives in tracked files.**
Any fresh orchestrator session reconstructs full context by reading, in order:

1. `CLAUDE.md` — rules of engagement
2. `SCOPE.md` — what we're doing and why (pre-registered)
3. `DATA.md` — data reality and constraints
4. `docs/DECISIONS.md` — what's been decided and why
5. `docs/PRODUCTION_LOG.md` — what's been done and what's next
6. `docs/EXPERIMENTS.md` — which runs exist and their results/cost

If a new chat begins with *"you are the orchestrator, resume the project"*, that agent MUST
read those six files first, restate the current phase and the next action, and only then act.

## Resume protocol (cross-chat)

When the human says they are **switching to a new orchestrator chat**, the current agent must
leave the repo in a resumable state:

- Append a `PRODUCTION_LOG.md` entry: what was completed, current phase, exact next action,
  any open blockers.
- Record any new decisions in `DECISIONS.md`.
- Ensure `SCOPE.md` "Status" and the phase checklist reflect reality.
- Commit. The commit message is the handoff summary.

The next chat's first job is to read state and echo it back for confirmation before doing work.

## Commit discipline

- One commit per gated step or state update; never leave a gate outcome uncommitted.
- Message format: `phase-<n>: <summary>` — the message doubles as the handoff summary.
- Before every commit, the state files (`PRODUCTION_LOG`, `DECISIONS`, `SCOPE` status/checklist)
  must reflect reality; the orchestrator updates them, then commits.
- Never commit secrets or raw payloads: keys live in `.env`; raw/interim data and LLM caches under
  `data/raw`, `data/interim`, `llm_cache` (all git-ignored). Check `git status` before any push.

## Phases and gates

Work proceeds through gated phases. **A gate must pass before the next phase starts**; gate
outcomes are logged in `PRODUCTION_LOG.md`. This structure lets a long-horizon session run
many steps unattended while still stopping at the right checkpoints.

- **Phase 0 — Feasibility (blocking).**
  - Targeted literature check: is the specific contribution novel vs. existing work? (See
    `literature-review` skill.) Record findings + a novelty verdict in `DECISIONS.md`.
  - Data reconnaissance: count resolved binary AI-progress questions and, per candidate model
    cutoff, how many resolve *after* it. (See `DATA.md` recon protocol.)
  - **Gate:** enough post-cutoff questions for adequately powered RQ2/RQ3 AND a defensible
    novelty angle. If not, revise `SCOPE.md` (broaden sources / narrow claims) before Phase 1.
- **Phase 1 — MVP end-to-end (thin slice).** Small N, few models, one prompt variant; full
  pipeline from collection → scoring → one calibration plot. Proves the plumbing.
  - **Gate:** reproducible run, cost logged, numbers sane.
- **Phase 2 — Full data + scoring core.** Complete collection, snapshotting, elicitation at
  target N/models, proper-scoring + calibration metrics with tests.
  - **Gate:** metrics pass known-input unit tests; provenance recorded.
- **Phase 3 — Core analyses.** RQ1–RQ4: calibration, cutoff split, information-content tests,
  friction-aware backtest + recalibration.
  - **Gate:** red-team review passes (no leakage, no underpowered/overclaimed results).
- **Phase 4 — Write-up + release.** Report in `docs/WRITING_STYLE.md` voice; curated dataset
  to `data/release/`; reproducibility check from a clean checkout.
  - **Gate:** a third party could reproduce headline numbers from the repo alone.

## v1 sprint schedule (deadline-boxed; see D-005)

v1 is built in a focused sprint, one phase-gate per checkpoint. De-scope RQ4 before compromising
the RQ1–RQ3 core if a day slips.

| Day | Phase | Deliverable | Gate |
|---|---|---|---|
| 1 | Setup + 0 | git init; novelty memo; recon (both sources: clean N, market–model correlation, power sketch) | Feasibility — is RQ3 powered? de-scope now if not |
| 2 | 1 | Thin slice: collect → snapshot → elicit (~3 models) → score → one calibration figure | MVP — reproducible, cost logged |
| 3 | 2 + 3a | Full data + scoring core with unit tests; RQ1 calibration + RQ2 cutoff split | metrics pass known-input tests |
| 4 | 3b + 4 | RQ3 encompassing (+RQ4 preliminary); red-team; write-up; dataset release; clean-checkout repro | ship — public repo |

## Agent roles (see `.claude/agents/`)

- **orchestrator** — owns the plan, sequences phases, dispatches subagents, enforces gates,
  keeps state files current, tracks budget. Does little work itself; delegates.
- **researcher** — literature, methodology, pre-registration integrity.
- **data-engineer** — collection, snapshotting, schema, provenance, recon.
- **quant-analyst** — scoring, calibration, statistical inference, microstructure/backtest.
- **scientific-writer** — the report, in the human's thesis voice; honest framing.
- **red-team-reviewer** — adversarial audit before any claim ships (leakage, p-hacking,
  power, novelty, reproducibility).

Dispatch pattern: orchestrator states the task + acceptance criteria → subagent executes
against the relevant skill → orchestrator verifies against the gate → logs the outcome.

## Iteration model (this is a science loop, not a waterfall)

Each unit of work is a small loop: **hypothesis/spec → implement → run → red-team → log →
decide**. Negative results are first-class: if a run refutes a pre-registered hypothesis,
that is a result, recorded as such — not a bug to be tuned away. The `PRODUCTION_LOG.md` is
the running narrative of this loop and doubles as the "how we built it with Claude Code"
report; keep it candid (what broke, what we changed, why).

## Long-horizon execution notes

- Run the top-level session with the most capable long-workflow model available so subagents
  can inherit it and chew through multiple phases per session.
- Prefer many small, checkpointed steps over one giant step; write state after each so an
  interruption never costs more than the last step.
- The orchestrator should maintain a live TODO reflecting the current phase's gate criteria.
