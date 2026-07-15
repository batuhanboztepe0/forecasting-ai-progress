---
name: literature-review
description: How to survey prior work and honestly assess novelty for this study. Use for the Phase-0 novelty check, for situating the contribution, and whenever a claim needs a citation. Consult before asserting anything is "novel" and before writing any related-work text, so the contribution is positioned accurately and citations are real.
---

# Literature Review

Position the work honestly against a fast-moving field. Overclaiming novelty is worse than a
modest, correctly-situated contribution.

## What to search

- LLM forecasting; LLMs vs. prediction-market/community crowds; forecasting benchmarks.
- Knowledge-cutoff / training-data contamination in LLM evaluation; "memorization vs.
  forecasting"; prompted-cutoff failure.
- Forecast evaluation methodology: proper scoring, calibration, forecast encompassing.
- Economics of transformative AI; forecasting AI progress; early-warning indicators.

## How to assess novelty

For each near-neighbor paper, write one line: what it did, on what data, and **exactly how this
study differs** (domain = AI-progress questions; contribution = information-content/encompassing
under a contamination control; artifact = a released dataset). Then give an honest verdict:
- **novel** (clear gap), **incremental** (extends known results — say so and frame as
  replication+extension), or **already-done** (pivot or narrow before proceeding).
Record the verdict + closest references in `docs/DECISIONS.md`.

## Citation discipline

- Cite only sources you have actually opened and read. Never invent a citation, an author list,
  or a result. If unsure of a detail, omit the claim.
- Keep a `references.bib`; every related-work sentence maps to an entry.
- Prefer primary sources (papers, official reports) over secondary summaries.

## Output

A short novelty memo (verdict + differentiation + closest work) and a maintained `references.bib`.
