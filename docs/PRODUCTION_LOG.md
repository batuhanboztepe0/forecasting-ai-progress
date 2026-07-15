# PRODUCTION_LOG.md

The running narrative of how this project was actually built with Claude Code — the candid
engineering + science journal. It doubles as the cross-chat handoff record. **Append newest
entries at the top.** Keep it honest: what was done, what broke, what changed, and why.

## How to use

- One entry per work session (or per meaningful step). Never rewrite history; append.
- On a chat switch, the last entry MUST state: what's done, the current phase, the **exact next
  action**, and any blockers, so a fresh orchestrator can resume.
- Reference decisions in `DECISIONS.md` and runs in `EXPERIMENTS.md` rather than duplicating them.

## Entry template

```
### YYYY-MM-DD — <short title> — Phase <n>
Done: <what was completed this session>
Findings/decisions: <key results; link DECISIONS.md IDs>
Cost this session: <USD, if any LLM runs; link EXPERIMENTS.md run IDs>
Broke / changed: <what went wrong and how it was addressed>
Gate status: <which gate; pass/fail + why>
Next action: <the single next concrete step>
Blockers: <none | ...>
```

---

### 2026-07-15 — v1 scope locked; design decisions integrated — Phase 0
Done: Full-repo read + design discussion with the human. Locked the v1 scope and the workflow;
integrated decisions into SCOPE.md, DATA.md, HANDOFF.md, README.md and recorded D-005..D-009.
Findings/decisions: v1 = RQ1–RQ3 confirmatory core + RQ4 preliminary (D-005); snapshot-aware
contamination rule C ≤ T (D-006); single 30-day horizon (D-007); RQ3 exploratory fallback + report
market–model correlation (D-008); sources/panel decided by recon (D-009). Positioning: the project
stands on methodology and honesty, not on a particular empirical outcome (SCOPE §4).
Cost this session: none (no API calls).
Broke / changed: Refined D-002's cutoff rule (R > C) into the stricter C ≤ T (D-006).
Workflow: faithful repo model — orchestrator dispatches named subagents serially; stop at each
phase gate. Not yet a git repo; `git init` is step 0 of the sprint.
Gate status: Phase 0 still open — feasibility (novelty + recon) not yet run.
Next action: Start Phase 0 — `git init` + first commit, then (1) `researcher` novelty check and
(2) `data-engineer` recon on Metaculus + Manifold (clean post-cutoff N per candidate cutoff,
market–model correlation on a small pilot, Manifold liquidity, RQ3 power sketch). Do NOT start
Phase 1 until the feasibility gate passes.
Blockers: none. Note: `docs/WRITING_STYLE.md` is still a stub (only bites at Phase 4).

### (bootstrap) — Scaffold created — Phase 0
Done: Repository scaffold authored — CLAUDE.md, HANDOFF.md, SCOPE.md, DATA.md, agents, skills,
docs. Research direction fixed: calibration + information content of AI-progress forecasts
(market vs. model), contamination-controlled, with a friction-aware backtest.
Findings/decisions: See DECISIONS.md D-001..D-004.
Cost this session: none (no API calls).
Broke / changed: n/a.
Gate status: Phase 0 not yet passed — feasibility (novelty check + data reconnaissance) pending.
Next action: Run the Phase-0 feasibility gate — (1) `researcher` novelty check; (2)
`data-engineer` reconnaissance per DATA.md (counts of resolved binary AI-progress questions and
the per-cutoff post-cutoff clean sample). Do NOT start Phase 1 until this gate passes.
Blockers: none.
