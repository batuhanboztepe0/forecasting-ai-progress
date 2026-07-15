# DATA.md — data sources, schema, and handling

## Sources

- **Metaculus** — community forecasts on resolved binary questions, with a time-stamped
  community-prediction history. Rich AI-progress category. Respect the API terms and rate
  limits; attribute appropriately.
- **Manifold Markets** — user-created binary markets with a full bet/trade history and an
  automated market maker (AMM). Free, key-less public API. Note: **play-money (mana)** — usable
  for probabilities and microstructure mechanics, but "economic value" (RQ4) is weaker than a
  real-money venue; state this limitation explicitly in the report.
- **Optional / later:** a real-money venue (e.g., an on-chain market) for a stronger RQ4, if a
  clean post-cutoff sample exists and terms permit. Not required for v1.

Only collect data that the source's terms permit. Do not scrape anything behind auth or
disallowed by robots/ToS. No personal data about individual users is collected or stored.

## What counts as an "AI-progress question"

A resolved binary question whose subject is the trajectory of AI itself: benchmark results or
saturation, model releases and capabilities, compute/scaling milestones, adoption/impact
claims about AI, or AI-lab/company outcomes. Classification is done with an explicit keyword +
LLM-assisted filter; the classifier prompt and decisions are versioned so the sample is
auditable.

## Core schema (per question)

| field | meaning |
|---|---|
| `qid` | stable source id |
| `source` | metaculus \| manifold |
| `title`, `description` | question text as shown to forecasters |
| `created_at`, `close_at`, `resolved_at` | lifecycle timestamps (UTC) |
| `outcome` | resolved YES=1 / NO=0 (drop ambiguous/annulled; log count) |
| `crowd_prob_at[T]` | crowd probability at snapshot lead time(s) T before `resolved_at` |
| `microstructure` | (Manifold) liquidity, trade series, AMM params at snapshot |
| `content_hash` | hash of the exact text shown to models (provenance) |

Model elicitations are stored separately, keyed by `(qid, model, variant, repeat, seed)`.

## Snapshot definition (validity-critical)

The crowd probability must be taken at a point where the **outcome is not yet known**. For v1 the
lead time is fixed at **T = 30 days** before `resolved_at` (single horizon; D-007), recorded as of
that instant from the source's history. Never use the final pre-resolution price. The same `T`
bounds the information a model is asked to use. (7/90-day horizons are future robustness.)

## Contamination / knowledge-cutoff handling (do not skip)

Established finding in the literature: instructing a model to "ignore anything after date T"
does **not** reliably prevent it from using leaked post-cutoff knowledge. Therefore:

- **Genuine-skill claims (RQ2/RQ3) use only questions resolving after each model's cutoff.**
- **Pre-cutoff questions are a memorization probe**, reported as such, never as foresight.
- **Snapshot-aware cutoff rule (v1, D-006).** For a clean model-vs-crowd comparison, require the
  model cutoff `C` to be **at or before the snapshot** `T = resolved_at − 30d`, i.e.
  `resolved_at ≥ C + 30d`. "Resolved after cutoff" (`R > C`) alone leaves an information-recency
  leak: if `T < C < R`, the model saw `T→C` data the `T`-snapshot crowd never did. Under `C ≤ T`
  the model is at worst information-*disadvantaged*, so any model edge is conservative and
  interpretable. Prefer questions where `C` is *close to* `T` so RQ3 tests aggregation, not recency.
- Maintain a versioned map of `model → knowledge_cutoff_date` in config (a named constant,
  not a magic literal). Each model's pre/post split is computed against its own cutoff.
- The elicitation prompt still instructs "as of T, no external information", and we may
  *measure* leakage (compliance vs. implicit use) as a secondary check — but we do not rely on
  it for cleanliness.

## Phase-0 reconnaissance protocol (blocking gate)

Before building anything heavy, quantify feasibility. Produce a short recon report answering:

1. Total resolved binary AI-progress questions available, per source.
2. Distribution of `resolved_at` over time.
3. **For each candidate model cutoff, how many questions resolve *after* it** (the clean
   RQ2/RQ3 sample) — overall and per source.
4. Manifold: typical liquidity/volume on those questions (is microstructure meaningful?).
5. **RQ3 power sketch (D-008).** On a small pilot subset (~20–30 clean questions, a few models),
   estimate the market–model forecast correlation; with the clean N, judge whether the
   encompassing coefficients are identifiable or whether RQ3 must be reported as exploratory.

Decision rule (record in `DECISIONS.md`): if the post-cutoff clean sample is too small for
adequately powered encompassing tests, either broaden sources / horizons or narrow the claims
in `SCOPE.md` before proceeding. A rough power sketch for RQ3 belongs in the recon report.

## Provenance & reproducibility

- Store the **raw API responses** (git-ignored) plus a committed manifest of query params,
  timestamps, and content hashes, so a run can be reconstructed.
- All derived tables are produced by deterministic, seeded code from the raw layer.
- Data layout: `data/raw/` (ignored), `data/interim/` (ignored), `data/release/` (committed,
  curated, with a datasheet documenting fields, collection date, filters, and known caveats).

## Licensing & attribution

Respect each source's data license and attribution requirements in the released artifact.
The curated release is distributed CC-BY-4.0 with per-source attribution noted in the datasheet.
