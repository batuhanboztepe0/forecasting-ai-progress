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

### 2026-07-17 — Post-ship lookahead-bias audit: CLEAN; disclosure polish pushed — Phase 4 (post-ship)
Done: On the human's request, a final lookahead/temporal-leakage audit ran as a fresh 3-lens
adversarial workflow (empirical data-temporal integrity, prompt/exposure, design-level), with
refutation votes armed for any BLOCKER/MAJOR. Verdict: **CLEAN — 0 blockers, 0 majors.**
Verified empirically: 30-question seeded re-derivation of crowd_prob_at_T from raw bet files
(no post-T bet influences any snapshot); prompt-construction path interpolates only title +
T (15 cached prompts scanned, nothing post-T); classifier inputs clean; backtest uses only
T-time information, Platt out-of-fold; D-014 filter re-verified (N=352). Design-level channels
judged symmetric or disclosed: retrospective T anchoring (identical for crowd and models),
resolution-only selection, per-model samples, backtest ordering.
Findings/decisions: minor disclosure gaps fixed post-publication (transparent correction):
(1) report body said "76 questions in haiku_clean" with close_at<T — correct value under the
final D-014 stratum is 38 (152 corpus-wide); fixed in §3.4 and Limitations. (2) Title
post-resolution edit risk now disclosed (scan of all 1,187 titles: zero genuine leaks).
(3) Manifold auto-resolve share (609/1,187 close_at==resolved_at) now noted. (4) Selection-on-
resolution limitation made explicit. (5) Abstract now names the confirmatory cell (haiku,
N=352) for the headline result. (6) DATASHEET: content_hash formula precise; description-field
wording corrected ("returned empty", not "not fetched").
Cost this session: $0 API. Final total USD 7.5120.
Broke / changed: n/a. Results and JSONs untouched (byte-identical).
Gate status: all gates passed; post-ship audit CLEAN.
Next action: none (future work list stands).
Blockers: none.

### 2026-07-17 — SHIPPED: Phase-4 gate signed off; v1 pushed to public GitHub — Phase 4 (done)
Done: Human reviewed the report and delegated the final ship call to the orchestrator with
instruction to push on approval. Orchestrator approved (all four gate criteria met and
empirically verified; final red-team fixes in). SCOPE Phase-4 ticked. Pre-push checks: working
tree clean, .env untracked, secret scan over tracked files clean. Pushed main to
github.com/batuhanboztepe0/forecasting-ai-progress.
Findings/decisions: none new. v1 is complete: 4 phases, 18 decisions (D-001..D-018), USD 7.51
total API cost, clean-checkout reproduction verified (73 tests + 28/28 headline checks).
Gate status: ALL GATES PASSED. v1 shipped.
Next action: future work only (Polymarket real-money RQ4, multi-provider panel, Metaculus if
resolutions become available, multi-horizon robustness, fable-5 probe).
Blockers: none.

### 2026-07-17 — Phase 4 complete: report + release + verified clean-checkout repro; ship pending sign-off — Phase 4
Done: (1) data-engineer built data/release/ (questions.csv 1,187 rows, forecasts.csv 3,761
rows, DATASHEET.md, README.md, reference_results.json) + src/analysis/reproduce_from_release.py.
(2) scientific-writer drafted paper/report.md (~3,900 words, docs/thesis/WRITING_STYLE.md voice;
orchestrator placed the file after a Write-permission block and cross-checked the 5 headline
numbers against the JSONs — all exact). (3) Clean-checkout reproduction VERIFIED by orchestrator:
fresh git clone → 73/73 unit tests → 28/28 headline numbers reproduced from release data.
(4) Final pre-ship red-team (scoped to report + release): FIX-FIRST with 2 blockers + 3 majors +
4 minors — ALL FIXED and re-verified: B-1 release stratum column now applies D-014 (352/835;
runner re-passed 28/28), B-2 close_before_T count corrected (152 total, stratum-qualified),
citations verified against live arXiv (6/6 exist, no hallucinations; 2 year errors fixed,
D-018), probe base rate 0.341→0.344, sensitivity rounding −0.176→−0.175, stratum-name synonym
noted, em-dashes 0. README updated with status/results/reproduce. temp/ (runner output)
gitignored. Process note: orchestrator's post-clone verification commands briefly ran inside
the scratch clone (persistent Bash cwd); caught and re-run in the real repo — no state damage.
Findings/decisions: D-018 (citation corrections).
Cost this session: $0 API. Running total USD 7.5120 (final; under the $8–15 envelope).
Broke / changed: n/a.
Gate status: Phase-4 gate ("a third party could reproduce headline numbers from the repo
alone") — MET and empirically verified. **PENDING human ship sign-off.**
Next action: human sign-off → tick Phase 4 in SCOPE → (optional, human decision) create the
public GitHub remote and push.
Blockers: human sign-off.

### 2026-07-17 — Phase-3 gate PASSED (human sign-off); Phase 4 open — Phase 3→4
Done: Human signed off Phase 3. SCOPE Phase-3 ticked. Human Phase-4 decisions: report =
English Markdown (paper/report.md), not LaTeX (logged D-017); voice = docs/thesis/
WRITING_STYLE.md (located; CLAUDE.md's docs/WRITING_STYLE.md path was stale).
Findings/decisions: D-017.
Cost this session: $0. Running total USD 7.5120.
Broke / changed: n/a.
Gate status: Phase-4 gate open ("a third party could reproduce headline numbers from the repo
alone"). BLOCKING items: data/release/ dataset + datasheet (red-team MAJOR 6), clean-checkout
reproduction verified, final red-team pass on the write-up.
Next action: parallel — data-engineer builds data/release/ (curated dataset + datasheet +
repro README, CC-BY-4.0, Manifold attribution); scientific-writer drafts paper/report.md per
WRITING_STYLE. Then: clean-checkout repro check, final red-team pass, README, ship.
Blockers: none.

### 2026-07-17 — Phase-3 red-team gate: PASS_WITH_FIXES → fixes applied; gate deliverables complete — Phase 3
Done: Red-team gate ran as a 16-agent adversarial workflow: 4 independent lenses (leakage/
contamination, statistical validity, RQ4 market mechanics with live-API+docs verification,
reproducibility/claims-vs-artifacts), every BLOCKER/MAJOR candidate then attacked by 2
independent refutation voters. Result: **0 blockers, 6 majors survived** — all documentation/
labeling issues; NO confirmatory number or decision invalidated. Key positive verifications:
elicitation prompts clean (raw cache inspected); snapshots match raw bet files (incl. a
close_at<T case); haiku_clean N=352 membership independently recomputed, exact match; H3a/H3b
coefficients and H1-crowd CITL independently reproduced to 4+ decimals; BH procedure re-derived
by hand; **RQ4's 22% hit rate confirmed NOT an inverted-sign artifact** (bet direction re-derived
from raw forecasts); CPMM convention errors quantified (<5% per winning bet under any defensible
convention) — H4 NO-EDGE robust. Fixes applied by quant-analyst (docs/comments/labels only;
both results JSONs byte-unchanged, SHA-256 verified; 73 tests green): BH-vs-conjunction
bridging + footnote, RQ4 relabeled PRELIMINARY per D-005, Maniswap/addedLiquidity/fee caveats,
comment fixes, sensitivity sign-flip + RQ2 base-rate + RQ3 clamp-asymmetry disclosures.
**CORRECTION (append-only):** the earlier Phase-3a entry cited H3a CI "[0.722, 1.640]" — wrong.
Source was the quant agent's summary message, inconsistent with its own JSON artifact; the
orchestrator copied it unverified. Correct values (phase3_rq123.json): Wald [0.937, 1.424],
seeded bootstrap [0.983, 1.503]. Caught by the red-team gate (MAJOR 4). Effect size, direction,
p-value, and the H3a decision are unaffected.
Findings/decisions: MAJOR 6 (clean-checkout repro impossible while phase2 data is git-ignored
and data/release/ doesn't exist) is by design the Phase-4 deliverable — carried into Phase 4 as
a BLOCKING item: dataset release + reproduction from clean clone verified before ship.
Cost this session: $0 API (workflow agents are session-side, not project API). Running total
USD 7.5120.
Broke / changed: n/a beyond the correction above.
Gate status: Phase-3 gate (red-team) — deliverables complete, fixes applied and verified.
**PENDING human sign-off.**
Next action: human sign-off on Phase-3 → Phase 4: scientific-writer report (docs/WRITING_STYLE
voice), data/release/ dataset + datasheet (CC-BY-4.0, per-source attribution), README, clean-
checkout reproduction check, final red-team pass on the write-up.
Blockers: human sign-off.

### 2026-07-17 — Phase 3a: RQ1–RQ3 confirmatory package complete — Phase 3
Done: quant-analyst ran the D-016 plan exactly (rq_confirmatory.py; results JSON
SHA-256-stable across runs; 73 unit tests re-verified green by orchestrator). Outputs:
data/interim/phase3_rq123.json, docs/phase3_results.md, docs/figures/rq3_coef_forest.png.
Findings/decisions (confirmatory, BH q=0.10 over the 5-test family):
- **H3a CONFIRMED** (haiku/haiku_clean N=352): b_crowd=+1.181 [0.722, 1.640], p<0.001,
  BH-rejected — the market carries information beyond the model.
- **H3b null**: b_model=+0.107 [−0.116, +0.330], p=0.35 — haiku adds no detectable information
  beyond the market. Together: asymmetric encompassing — crowd encompasses haiku.
- **H1 null in both confirmatory cells**: crowd CITL=+0.035 [0.017, 0.053] — CI excludes 0
  (BH-rejected statistically) but |CITL|<0.05, so the pre-registered conjunction FAILS →
  "well calibrated" not rejected (two-part decision reported explicitly). Haiku CITL=+0.004,
  p=0.87. Slopes: crowd 1.30 (mildly underconfident), haiku 0.35 (severely overconfident).
- **H2-haiku not rejected** (marginal): ΔBSS=−0.119 [−0.268, +0.021], p=0.104; but the
  pre-registered flag fires: haiku post-cutoff BSS=−0.065, CI includes ≤0 (no better than
  base rate on clean questions).
- Exploratory (labeled): same encompassing asymmetry for sonnet/opus; large skill drops
  (ΔBSS −0.33/−0.27); jan2026 CITL anomaly diagnosed as information-recency (stratum base
  rate 45.8% vs 33.8% overall; crowd tracks it, models anchor low; not time-clustered).
- Sensitivities (D-014): NO decision flips; one benign sign flip (H1-haiku CITL +0.004→−0.021
  under (b), both sides of the threshold-null).
Cost this session: $0 (no API). Running total USD 7.5120.
Broke / changed: n/a.
Gate status: Phase-3 gate (red-team) pending — RQ4 preliminary next, then the full-package
red-team audit.
Next action: quant-analyst RQ4 preliminary backtest per D-016 §6; then red-team-reviewer full
Phase-3 audit; then Phase-4.
Blockers: none.

### 2026-07-17 — Phase-2 gate PASSED (human sign-off); fable probe skipped; Phase 3 open — Phase 2→3
Done: Human signed off the Phase-2 gate and decided the optional fable-5 probe: SKIP (future
work). Logged D-015 (fable skip) and D-016 (Phase-3 analysis plan details fixed before any
confirmatory run: RQ1 sample assignment, RQ2 contrast implementation, RQ3 cells, the exact
5-test BH family, D-014 sensitivity set, RQ4 strategy spec). SCOPE Phase-2 ticked.
Findings/decisions: D-015, D-016.
Cost this session: $0 new. Running total USD 7.5120.
Broke / changed: n/a.
Gate status: Phase-2 — **PASSED** (human sign-off 2026-07-17). Phase-3 gate open (red-team
review must pass before results ship).
Next action: quant-analyst runs RQ1–RQ3 confirmatory package per D-016 (+ sensitivities), then
RQ4 preliminary backtest; then red-team-reviewer audits the full Phase-3 package (leakage,
p-hacking, power, overclaim) before anything ships; then Phase 4 (write-up + release).
Blockers: none.

### 2026-07-17 — Step B COMPLETE + Phase-2 scoring; gate deliverables done, PENDING sign-off — Phase 2
Done: Human raised the console monthly limit to $30. Opus r0 batch (1,160 new + 27 cache) and
the variance probe (sonnet-5, 100 q × repeats 1+2) completed: full panel now 3,761 forecasts,
0 parse errors, 0 refusals across all five batches; determinism PASS (CSV rebuild from cache
bit-identical, SHA-256 58b1e7de…); manifest step_b block has all 5 batch IDs + prompt hash.
quant-analyst scored everything descriptively (score_phase2.py; 7/7 sanity gates incl.
flag-vs-recompute cross-check with 0 mismatches; 73 unit tests re-run green; scores CSV
SHA-256-identical across runs) → data/interim/phase2_scores.csv,
docs/figures/phase2_calibration.png, docs/phase2_results.md.
Findings/decisions (DESCRIPTIVE — confirmatory tests are Phase 3): Crowd Brier 0.1015
(BSS +0.546) overall, n=1,187. Models overall: sonnet-5 0.1596 (+0.287), opus-4-8 0.1671
(+0.253), haiku 0.2191 (+0.021). On each model's OWN post-cutoff clean sample no model beats
base rate (BSS: haiku −0.065 n=352; sonnet −0.025, opus −0.003 n=72 exploratory) — direction
consistent with H2, untested as yet. All models overconfident on logit scale (cal-slope
0.35–0.60); crowd mildly underconfident (1.30). Variance probe: mean per-question SD 0.042,
repeat Brier spread ~0.015 — sampling noise small vs model-crowd gap; one outlier (SD 0.458)
to inspect. Distinct probs: haiku 39, sonnet 47, opus 45 / 1,187 — discretized but far less
degenerate than v1. ANOMALY for Phase-3 red-team: models' CITL on jan2026_clean is −13 to
−18 pp (systematic under-prediction of YES on that small subset).
Cost this session: opus $2.2408 + probe $0.2301. Running total USD 7.5120 (envelope $8–15).
Broke / changed: opus batch took 4h52m to flip to ended (vs 49m haiku, 3m sonnet) — load
artifact, no data issue. EXPERIMENTS run-registry rows for step B re-organized per-model by
data-engineer.
Gate status: Phase-2 gate — BOTH criteria MET and orchestrator-verified: (1) metrics pass
known-input unit tests (73/73, verified twice); (2) provenance recorded (file-byte SHA-256
manifest verified on disk, 5 batch IDs, raw JSONL, ledger current). **PENDING human sign-off.**
Next action: human sign-off on Phase-2 gate → Phase 3 (RQ1–RQ4 confirmatory analyses per
SCOPE §2 with pre-registered thresholds + BH q=0.10, D-014 sensitivity set, then red-team gate).
Optional decision that can wait until Phase 3: fable-5 frontier probe (D-011; ~$5–10).
Blockers: human sign-off.

### 2026-07-16 — Step B PARTIAL: haiku+sonnet complete; opus blocked by console monthly usage limit — Phase 2
Done: Credits landed (first block was propagation delay; orchestrator verified with a minimal
billed call). Step B ran: haiku r0 and sonnet-5 r0 batches completed perfectly — 1160/1160
success each, 0 parse errors, 0 refusals (+27 MVP-v2 cache reuses covering the remaining 27 of
1,187). Raw JSONL + phase2_v2 cache (2,401 entries) intact. Actual cost haiku $0.5082
(vs $0.62 projected), sonnet $1.3618 (vs $1.25). Ledger updated.
Findings/decisions: none scientific. Batch latency asymmetric (haiku ~49 min, sonnet ~3 min) —
server-load artifact, no data issue.
Cost this session: +$1.8700. Running total USD 5.0410.
Broke / changed: **BLOCKER — opus-4-8 batch submission rejected: console MONTHLY USAGE LIMIT
reached** ("regain access 2026-08-01 00:00 UTC"). This is the account's self-configured monthly
spend cap, not credits. Because the script runs sequentially, the variance probe (sonnet r1/r2)
also did not run; phase2_forecasts.csv, determinism SHA-256s, and manifest step_b block deferred
until the panel is complete.
Gate status: Phase-2 gate — scoring core criterion MET (73 tests, verified); elicitation 2/3
models done; gate check waits on opus + probe.
Next action: HUMAN — raise the monthly usage limit in console.anthropic.com (Settings → Limits /
Plans & Billing; needs ≈$4 headroom: opus $3.12 + probe $0.21) OR wait for the 2026-08-01 reset.
Then re-run `python3.11 src/phase2/elicit_phase2.py` (haiku/sonnet skip via cache; only opus +
probe submit). Then: CSV + determinism + manifest, quant-analyst scoring, gate check, sign-off.
Blockers: Anthropic console monthly usage limit (user action or 2026-08-01 reset).

### 2026-07-16 — Scoring core green (73 tests); D-014 fixes applied; step B BLOCKED on API credits — Phase 2
Done: (1) quant-analyst delivered the Phase-2 scoring core: src/analysis/scoring.py (Brier, BSS,
log-loss with explicit clamping, CITL, Newton-IRLS logistic recalibration with no new deps,
reliability bins, seeded paired-bootstrap CIs) + splits.py (D-014 clean rule, cutoffs imported
from phase2_config, boundary conventions tested inclusive-≥) + 73 known-input unit tests —
orchestrator-verified green via `python3.11 -m pytest src/analysis/tests/ -q`. (2) data-engineer
applied all red-team/D-014 fixes, each verified: manifest SHA-256 now hashes file bytes (matches
disk), stale v1.0 strata block removed, phase label fixed, D-014 flags on all 1,187 records.
Actual clean Ns under the refined rule: haiku 352 (38 flagged close-before-cutoff → probe side;
RQ3 CONFIRMATORY, power ≈99% at ρ̂=0.57), jan-2026 72 (30/102 flagged; EXPLORATORY). (3) Step B
elicitation script ready (src/phase2/elicit_phase2.py: checkpoint/resume, hard no-leakage
assertion verified, 27 MVP-v2 cache hits preloaded, determinism check built in; projected cost
$5.195 batched = $0.62 haiku + $1.25 sonnet + $3.12 opus + $0.21 variance probe — within the
$25 guardrail).
Findings/decisions: none new (D-014 executed as specified).
Cost this session: $0 new (batch submission failed before billing). Running total USD 3.1710.
Broke / changed: **BLOCKER — Anthropic API credit balance exhausted**: batch submission returned
HTTP 400 "credit balance is too low". Nothing wrong with the pipeline; purely account credits.
Gate status: Phase-2 gate — scoring-core criterion (known-input unit tests) MET and verified;
provenance criterion MET for step A (hashes verified on disk); elicitation pending credits.
Next action: HUMAN — top up Anthropic API credits. Then resume step B:
`python3.11 src/phase2/elicit_phase2.py` from repo root (no code changes needed), or tell the
orchestrator to re-dispatch the data-engineer. After forecasts land: quant-analyst scores
phase2_forecasts.csv, orchestrator runs the Phase-2 gate check, stop for human sign-off.
Blockers: Anthropic API credits (user-provided). Projected remaining core spend ≈ $5.20
(new total ≈ $8.37, within the $8–15 envelope).

### 2026-07-16 — Phase-2 step A: collection + classifier (v1.0→v1.1 realignment) — Phase 2
Done: data-engineer built the Phase-2 pipeline (src/phase2/): LLM classifier over the 3,728
keyword candidates (the handoff's "~5,700" was the dedup-dropped count — reconciled), stratum
builder, crowd-snapshot fetcher with checkpointing, provenance manifest. Classifier v1.0 dropped
50.8% — orchestrator audit of a seeded 40-drop sample found ~5–8 in-domain per DATA.md (v1.0
silently narrowed the pre-registered definition; adoption/impact and lab/company outcomes
excluded). Logged D-013 and re-ran the full pool under a DATA.md-aligned v1.1 prompt (both
versions cached and auditable; no per-question mixing). Orchestrator then audited v1.1 three
ways: 40 keeps (40/40 in-domain, all five categories represented), 40 overall drops, and 40
newly-dropped v1.0-keeps.
Findings/decisions: v1.1 kept 1,694 / dropped 2,034 (recovered 198 v1.0 false drops — e.g.
"OpenAI $1B revenue", "AI YouTube video 100M views", "Altman-funded fabs"; newly dropped 340
v1.0 junk keeps — personal-belief, market-meta, joke-framed questions). Residual drop-side
false-negative rate ≈7.5% clear (95% CI ~3–20%; idiosyncratic misreads + release-timing gray
zone), keeps precision ≈95–100% — ACCEPTED: residuals are not category-systematic, classifier
never sees resolutions (cannot bias model-vs-crowd comparisons; only trims N), and further
iteration would risk sample-tuning. Error rates to be documented in the datasheet. Final strata
(v1.1): haiku-clean 390; pre-cutoff probe 797 (3 hard-dropped: 2 zero-trade + 1 Manifold 503,
per D-013 ≥1-bet-at/before-T rule, no AMM fallback); jan-2026-clean 102 (still exploratory per
D-011 §5); total 1,187 records, all with non-null crowd_prob_at_T + microstructure.
Cost this session: classifier v1.0 $0.8659 + v1.1 $1.8024 (v1.1 prompt ~3× longer). Running
total USD 3.1710.
Broke / changed: v1.1 net keeps DOWN vs v1.0 (-142) — surprising but correct (v1.0 was keeping
junk); one Manifold 503 fetch error treated as hard drop.
Gate status: Phase-2 gate open. Pre-elicitation red-team review of sample definition +
elicitation plan queued (protects the ~$6–11 elicitation spend).
Next action: red-team-reviewer pass (leakage, sample validity) → fix anything material → step B
batched elicitation (1,187 q × 3 models, protocol v2, + 100-q × 3 variance probe on sonnet-5).
Blockers: none.

### 2026-07-16 — Protocol v2 plumbing check PASSED; Phase-2 build starts — Phase 2
Done: data-engineer re-ran the 50-question slice under protocol v2 (D-012): 150/150 elicitations,
0 parse errors, 0 refusals, reasoning brief (median ~98 tokens), cache-deterministic (SHA-256 of
output CSV identical live vs. cache-only). quant-analyst re-scored with the v1 machinery
(known-input self-test PASS; deterministic across runs) → data/interim/mvp_scores_v2.csv,
docs/figures/mvp_calibration_v2.png, docs/protocol_v2_check.md (descriptive sensitivity only).
Findings/decisions: Haiku's v1 canonical-probability degeneracy substantially resolved under v2
(8→19 distinct probabilities; Brier 0.257→0.160; CITL +0.187→+0.055; v1 anomaly flags absent).
Sonnet-5 and Opus-4-8 essentially unchanged (small differences within n=50 noise). Consistent
with ForecastBench's scratchpad-beats-zero-shot finding, strongest for weaker models. Per D-012
no decision rides on these numbers — v2 was adopted a priori.
Cost this session: mvp-thin-slice-v2 $0.3455. Running total USD 0.5027.
Broke / changed: data/mvp_manifest.json restructured from single entry to a 2-entry list (v1
entry preserved verbatim).
Gate status: Phase-2 gate open (metrics pass known-input unit tests; provenance recorded);
pre-scale-up plumbing check PASSED.
Next action: data-engineer Phase-2 step A — full collection + LLM classifier (haiku over the
recon candidate pool), final elicitation set per D-011 §4 (≈791 haiku-clean + ≈800 pre-cutoff
probe), crowd_prob_at_T + microstructure snapshots, provenance manifest. Then step B — batched
elicitation (~1,600 q × 3 models under protocol v2, est. $6–11; hard stop if any run projects
> $25). Then quant-analyst scoring core with known-input unit tests. Stop at Phase-2 gate.
Blockers: none.

### 2026-07-16 — Phase-1 gate PASSED; protocol v2 locked (D-012); Phase 2 open — Phase 1→2
Done: Fresh orchestrator resumed per HANDOFF (six state files read, state echoed, repo verified
against handoff commit 36c6e8c). Before the A/B ask, researcher ran a targeted literature check
verified against the papers: ForecastBench (2409.19839) directly tests scratchpad vs. zero-shot
elicitation and scratchpad wins consistently; Halawi (2402.18563) and Schoenegger (2402.19379)
both elicit reasoning-first with no bare-ask control; caveat — avoid explicit Bayesian-framing
instructions (2506.01578). Human signed off the MVP gate (PASS) and chose protocol v2. D-012
logged; SCOPE Phase-1 ticked and SCOPE frozen for Phase-2 collection.
Findings/decisions: D-012 — protocol v2 adopted on a priori grounds; the 50-question v2 re-run
is a plumbing check only (parse rate/refusals/cost/determinism), explicitly not an accuracy
bake-off, so protocol selection never conditions on data feeding the confirmatory sample.
Cost this session: no project-API runs at log time. Running total USD 0.1572.
Broke / changed: n/a.
Gate status: Phase-1 MVP — **PASSED** (human sign-off 2026-07-16). Phase-2 gate open (metrics
pass known-input unit tests; provenance recorded).
Next action: data-engineer re-runs the 50-question slice under protocol v2 (plumbing check),
then Phase-2 full build: collection + LLM classifier (~5,700 candidates, haiku), batched
elicitation (~1,600 q × 3 models, est. $6–11, hard stop if a run projects > $25), scoring core
with known-input unit tests. Stop at Phase-2 gate for human sign-off.
Blockers: none.

### 2026-07-16 — Cross-chat handoff; MVP gate + protocol decision pending — Phase 1
Done: Human requested a fresh orchestrator chat. Repo left in resumable state per HANDOFF.
Clarification recorded so the next orchestrator does not re-litigate it: **haiku-4-5 remains in
the panel under BOTH protocol options** — the pending A/B decision changes only the elicitation
prompt, identically for all three models (A = protocol v1, bare JSON ask, haiku reported as-is;
B = protocol v2, 1–2 sentences of reasoning before the JSON, to be logged as D-012 and re-run on
the 50-question slice ~$0.15 before any Phase-2 scale-up). Dropping haiku was considered and
recommended AGAINST: the RQ3-confirmatory clean sample (N≈791) is defined by haiku's training
cutoff and requires haiku's forecasts — without haiku, RQ3 falls back to exploratory (N=175,
per D-008), and the weak-forecaster contrast that powers RQ2 is lost.
Findings/decisions: none new; MVP results and the haiku root-cause are in the previous entry.
Cost this session: no new LLM runs. Running total USD 0.1572.
Broke / changed: n/a.
Gate status: Phase-1 MVP — deliverables complete and committed (ac2a8c2); **PENDING human
sign-off + protocol v1-vs-v2 decision**.
Next action (fresh orchestrator): read the six state files per HANDOFF §Core principle, restate
current state, collect the human's MVP sign-off and A/B decision. If B: log D-012, data-engineer
re-runs the 50-question slice under protocol v2, quant-analyst re-scores, compare, then Phase 2.
If A: straight to Phase 2 — full collection, LLM classifier (haiku, ~5,700 candidates), batched
elicitation (~1,600 q × 3 models, est. $6–11), scoring core with known-input unit tests (day-3
schedule). Workflow unchanged: orchestrator dispatches named subagents serially; agents never
commit; stop at every phase gate.
Blockers: human decision (MVP sign-off + A/B).

### 2026-07-16 — Phase-1 MVP thin slice complete; gate pending sign-off — Phase 1
Done: Full end-to-end thin slice. data-engineer: 50 seeded questions (25 post-/25 pre-cutoff,
15 clean for all three models) × 3 panel models → 150/150 elicitations (0 parse errors, 0
refusals), crowd_prob_at_T for all 50, protocol v1 frozen in `src/mvp/mvp_config.py`, offline
re-run bit-identical from cache, provenance in `data/mvp_manifest.json`. quant-analyst:
`src/analysis/score_mvp.py` (known-input self-test PASS; SHA-256-identical outputs across runs)
→ `data/interim/mvp_scores.csv`, `docs/figures/mvp_calibration.png`, `docs/mvp_results.md`.
Findings/decisions: Crowd Brier 0.086 (BSS +0.62); sonnet-5 0.121 (+0.46); opus-4-8 0.115
(+0.49); haiku 0.257 (BSS −0.15, i.e. worse than base rate). Orchestrator audited the haiku
anomaly against raw cached responses: NOT a parse artifact — haiku genuinely emits a small set
of canonical probabilities (0.15×16, 0.72×16, 0.92×8 out of 50). Elicitation-design/model
limitation; informative for RQ2 but degrades haiku's calibration measurements. All descriptive,
n=50, no claims (per docs/mvp_results.md).
Cost this session: mvp-thin-slice $0.1032; scoring $0.00. Running total USD 0.1572.
Broke / changed: `python3` on this machine is 3.14 without matplotlib; scoring runs under
python3.11 (Homebrew) — documented in the script; clean-checkout repro must note the matplotlib
dependency. No other breakage.
Gate status: Phase-1 MVP — reproducible ✓, cost logged ✓, numbers sane ✓ (one flagged,
root-caused anomaly). **PENDING human sign-off**, with one pre-Phase-2 decision attached:
elicitation protocol v1 (bare JSON ask) vs v2 (brief reasoning before the JSON, applied to ALL
models identically, decided now — before full-scale data — to avoid post-hoc tuning; would be
logged as D-012 and re-run on the 50-question slice first).
Next action: Human sign-off on MVP gate + protocol v1-vs-v2 decision → Phase 2 (full collection,
LLM classifier, batched elicitation at target N, scoring core with unit tests).
Blockers: none.

### 2026-07-16 — Phase-0 gate PASSED (human sign-off); D-011 locked; Phase 1 started — Phase 0→1
Done: Human signed off on the feasibility gate and delegated the budget-driven panel decision.
Logged D-011 (source = Manifold-only; TRAINING cutoffs 2025-07-31 / 2026-01-31; panel =
haiku-4-5 + sonnet-5 + opus-4-8; fable-5 excluded from core on cost — always-on billed thinking
at $10/$50 per MTok — optional post-MVP frontier probe; elicitation set ≈791 clean + ≈800
pre-cutoff probe, 1 repeat + 3× variance probe; budget envelope ~$8–15 core). Ticked Phase 0 in
SCOPE and updated §8 recon-dependent items to reference D-011. Added the planned-budget table to
EXPERIMENTS.md. Verified current model pricing from the claude-api reference (not memory).
Findings/decisions: D-011. Polymarket raised by the human — assessed as a genuine future-work
upgrade for a real-money RQ4, not v1 (unrecon'd source; deadline-boxed sprint; recorded in D-011).
No OpenAI key by human decision → single-provider panel is a stated limitation (two distinct
cutoffs only).
Cost this session: USD 0 so far today beyond the $0.054 total (no new LLM runs at log time).
Broke / changed: nothing broke; D-009's open items resolved by D-011.
Gate status: Phase-0 feasibility — **PASSED** (human sign-off 2026-07-16). Phase-1 MVP gate open.
Next action: data-engineer thin slice (dispatched): ~50 seeded questions spanning pre/post
cutoff × 3 panel models, crowd prob at T, cached elicitation, forecasts table → then
quant-analyst scores it (Brier vs crowd + one calibration figure) → MVP gate check
(reproducible, cost logged, numbers sane) → human sign-off.
Blockers: none.

### 2026-07-16 — Recon v1.1: Metaculus with token + empirical pilot ρ — Phase 0
Done: Human provisioned `.env` (METACULUS_API_TOKEN, ANTHROPIC_API_KEY). data-engineer re-run:
(1) Metaculus pulled with auth via `/api/posts/` — 142 AI-progress binary questions found, but
`question.resolution` is null for ALL of them (API limitation as of 2026-07-16) → countable, not
analyzable; (2) pilot elicitation completed (30 seeded questions × 2 models, crowd prob at T from
Manifold bet history); (3) orchestrator-caught fix-ups: manifest restructured to cover all three
pulls with SHA-256 hashes, and the cutoff table corrected to TRAINING-data cutoffs (end-of-month,
conservative) instead of "reliable knowledge" cutoffs.
Findings/decisions: **Empirical ρ̂ = 0.57** pooled (haiku-4.5: 0.49 [0.16, 0.72]; sonnet-5: 0.66
[0.39, 0.82], logit-scale, n=30). Under training cutoffs the clean snapshot-feasible N: haiku-4.5
(C=2025-07-31) → 808 combined (791 Manifold), power ≈100% at ρ̂; Claude-5-family (C=2026-01-31) →
175 → a standalone shared-question encompassing test at the newest cutoff is UNDERPOWERED (~70-75%);
RQ3 confirmatory status rides on the haiku-cutoff sample. **RQ3: CONFIRMATORY** per D-008.
11/30 pilot questions have T < C for sonnet-5 (recency leak) — inflates ρ̂, i.e. conservative for
the power verdict; those questions are inadmissible in the Phase-2/3 clean sample for Jan-2026
models (documented in recon report LIMITATIONS §9). Haiku pilot calibration poor (Brier 0.214 vs
crowd 0.056) — keep but monitor. `temperature` is deprecated on newest Anthropic models (HTTP 400)
— response caching is the determinism mechanism for them.
Cost this session: USD 0.054 (run `pilot-elicitation-2026-07-16`; running total USD 0.054).
Broke / changed: v1.1 initially shipped without updating the manifest (caught at orchestrator
verification; fixed same day). Cutoff basis corrected from "reliable" to training cutoff — lowers
clean N (1,125→808; 239→175) but is the defensible reading of D-006.
Gate status: Phase-0 feasibility — ALL deliverables complete incl. empirical ρ. **PENDING human
gate decisions**; orchestrator recommends PASS (novelty incremental-but-defensible, N ample,
RQ3 confirmatory, RQ4 viable, cost negligible).
Next action: Human decides: (1) Manifold-only v1 (Metaculus → future work)?; (2) panel:
haiku-4-5 + sonnet-5 + fable-5 (Anthropic-only, two cutoffs) vs. adding OPENAI_API_KEY for an
older-cutoff model (2-3× clean N, stronger RQ2); (3) training-cutoff constants confirmation.
Then: log D-011, tick Phase 0 in SCOPE, commit, start Phase 1 thin slice.
Blockers: awaiting human gate decisions.

### 2026-07-15 — Phase-0 feasibility: novelty check + data recon complete — Phase 0
Done: (1) researcher novelty check → `docs/novelty_memo.md`, `docs/references.md`, D-010 appended.
(2) data-engineer recon → `docs/recon_report.md`, `src/recon/` (re-runnable, seeded),
`data/recon_manifest.json`, run `recon-2026-07-15` logged in EXPERIMENTS.md.
Findings/decisions: Novelty verdict **INCREMENTAL** (D-010): RQ1 is replication+extension; the
differentiating combination is AI-progress domain + encompassing framing + C ≤ T + dataset
release; closest work is AIA Forecaster (arXiv 2511.07678, forecast-combination not encompassing).
Recon: **Metaculus API now requires auth (HTTP 403)** — zero Metaculus data this phase; Manifold
alone yields 3,728 resolved binary AI-progress questions (keyword filter v1.0, precision ~85%).
Snapshot-feasible clean N: 2,886 (2022-01 cutoff) → 2,709 (2023-10) → 1,183 (2025-01) → 1,004
(2025-04). RQ4 liquidity viable: 54.7% of markets ≥20 bettors and ≥1,000 mana volume. Seeded
power sketch (seed 42): 80% power at N=200–400 for ρ ≤ 0.75, N≈1,000 at ρ = 0.9 → RQ3
provisionally **CONFIRMATORY**; D-008 exploratory fallback stays armed until empirical ρ is
measured (pilot blocked — no API keys).
Cost this session: USD 0.00 (no LLM calls; see run `recon-2026-07-15`).
Broke / changed: DATA.md's "key-less Metaculus API" assumption no longer holds (policy change);
needs `METACULUS_API_TOKEN` in `.env` or a Manifold-only v1. Pilot elicitation (DATA.md recon
item 5) blocked by missing `.env`; substituted a simulation-based power grid, clearly labeled.
Process note: data-engineer subagent committed its own work (b903b0f) — contents verified clean
(no raw data, no secrets), but per HANDOFF the orchestrator commits; future dispatches will say so
explicitly.
Gate status: Phase-0 feasibility — deliverables complete, **PENDING human sign-off**.
Orchestrator's read: pass — novelty defensible (incremental, honestly positioned), N ample,
RQ4 viable; RQ3 confirmatory label is robust to the known haircuts (precision ~85%, snapshot
heuristic −5–15%) at ρ ≤ 0.75, marginal only for the newest cutoff if ρ ≈ 0.9.
Next action: Human gate decisions: (1) accept Manifold as v1 primary source vs. provision
`METACULUS_API_TOKEN` and re-run recon; (2) lock the ~3-model panel (log as D-011); (3) provide
LLM API keys in `.env` so Phase 1 can run the pilot ρ estimate + thin slice.
Blockers: `.env` keys (LLM API required for Phase 1; Metaculus token optional) — user-provided.

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
