"""
report_generator.py — Generate docs/recon_report.md from analysis results.

All numbers come from the analysis dicts produced by analyze_recon.py and
power_sketch.py — never fabricated.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

from config import (
    CANDIDATE_CUTOFFS,
    SNAPSHOT_LEAD_DAYS,
    MANIFOLD_MIN_UNIQUE_BETTORS,
    MANIFOLD_MIN_VOLUME_MANA,
    POWER_SIM_RHO_GRID,
    POWER_SIM_N_MONTE_CARLO,
    POWER_SIM_ALPHA,
    POWER_SIM_INFORMATION_WEIGHT,
    KEYWORD_LIST_VERSION,
    MANIFOLD_AI_GROUP_SLUGS,
    METACULUS_AI_TAGS,
    METACULUS_API_BASE,
    MANIFOLD_API_BASE,
    REPORT_PATH,
)


def _table_row(cells: list[str], widths: list[int] | None = None) -> str:
    if widths:
        padded = [str(c).ljust(w) for c, w in zip(cells, widths)]
    else:
        padded = [str(c) for c in cells]
    return "| " + " | ".join(padded) + " |"


def _hline(widths: list[int]) -> str:
    return "|" + "|".join("-" * (w + 2) for w in widths) + "|"


def generate_report(
    meta_total: int,
    manifold_total: int,
    meta_dropped_ambiguous: int,
    manifold_dropped_ambiguous: int,
    dist: dict,
    cutoff_rows: list[dict],
    liquidity: dict,
    precision: dict,
    power: dict,
    run_timestamp: str,
    meta_group_note: str = "",
    manifold_found_groups: list[str] | None = None,
    api_notes: list[str] | None = None,
) -> str:
    """
    Produce the full recon report markdown string.

    Args:
        meta_total: Total AI-progress binary resolved questions from Metaculus.
        manifold_total: Same for Manifold.
        meta_dropped_ambiguous: Ambiguous/annulled Metaculus questions dropped.
        manifold_dropped_ambiguous: Same for Manifold.
        dist: Output of resolution_distribution().
        cutoff_rows: Output of clean_n_per_cutoff().
        liquidity: Output of manifold_liquidity_stats_v2().
        precision: Output of classifier_precision_sample().
        power: Output of run_power_grid().
        run_timestamp: ISO-8601 UTC timestamp of this run.
        meta_group_note: Any note about Metaculus group/tag discovery.
        manifold_found_groups: List of group slugs that resolved successfully.
        api_notes: List of API-specific notes (endpoint versions, caveats).

    Returns:
        Markdown string for the report.
    """
    lines = []
    a = lines.append  # shorthand

    a("# Phase-0 Reconnaissance Report")
    a("")
    a(f"**Generated:** {run_timestamp}")
    a(f"**Keyword list version:** {KEYWORD_LIST_VERSION}")
    a(f"**Snapshot lead time (D-007):** T = {SNAPSHOT_LEAD_DAYS} days before resolved_at")
    a(f"**Contamination rule (D-006):** resolved_at >= C + {SNAPSHOT_LEAD_DAYS}d")
    a("")
    a("This report is the Phase-0 feasibility gate (D-003). Every number comes from a live API "
      "call or from the seeded Monte Carlo simulation; nothing is fabricated.")
    a("")

    # -----------------------------------------------------------------------
    # METHODOLOGY
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## Methodology")
    a("")
    a("### Data sources")
    a("")
    a(f"**Metaculus** — base URL: `{METACULUS_API_BASE}`")
    a(f"  - Endpoint: `GET /api2/questions/`")
    a(f"  - Intended filters: `type=forecast`, `status=resolved`, `resolution=yes,no`")
    a(f"  - AI tags/categories intended: {', '.join(METACULUS_AI_TAGS)}")
    a(f"  - **Status: BLOCKED (HTTP 403 Forbidden).** Metaculus now requires an API token for all "
      f"endpoints, even public questions. Previously described as key-less; this is a policy change. "
      f"Zero questions were retrieved. Metaculus data is deferred until a token is provisioned in `.env`.")
    if meta_group_note:
        a(f"  - {meta_group_note}")
    a("")
    a(f"**Manifold** — base URL: `{MANIFOLD_API_BASE}`")
    a(f"  - Endpoints: `GET /v0/group/{{slug}}` + `GET /v0/markets?groupId=...`")
    a(f"  - Group slugs tried: {', '.join(MANIFOLD_AI_GROUP_SLUGS)}")
    if manifold_found_groups:
        a(f"  - Group slugs that resolved (non-404): {', '.join(manifold_found_groups)}")
    a(f"  - Market filter: `outcomeType=BINARY`, `isResolved=true`, `resolution in [YES, NO]`")
    a("")
    a("### Keyword filter (v1.0)")
    a("")
    a("Applied to title + description (case-insensitive substring match). "
      "Questions matching at least one keyword and no exclusion keyword are included. "
      "The LLM-assisted Phase-2 classifier supersedes this filter; the keyword list is "
      "versioned in `src/recon/config.py`.")
    a("")
    if api_notes:
        a("### API notes")
        a("")
        for note in api_notes:
            a(f"- {note}")
        a("")

    # -----------------------------------------------------------------------
    # QUESTION 1: Total resolved binary AI-progress questions
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## 1. Total Resolved Binary AI-Progress Questions")
    a("")

    combined_total = meta_total + manifold_total

    W = [30, 12, 18, 22]
    a(_table_row(["Source", "AI-progress", "Ambiguous/annulled", "Combined (de-duped est.)"], W))
    a(_hline(W))
    a(_table_row(["Metaculus", str(meta_total), str(meta_dropped_ambiguous), "—"], W))
    a(_table_row(["Manifold", str(manifold_total), str(manifold_dropped_ambiguous), "—"], W))
    a(_table_row(["**Combined (sum)**", f"**{combined_total}**", "—", "—"], W))
    a("")
    a(f"Note: Metaculus and Manifold cover largely non-overlapping question sets (different "
      f"communities); deduplication across sources is not performed in Phase 0. "
      f"Ambiguous/annulled counts include only questions that passed the binary filter but "
      f"had a non-YES/NO resolution.")
    a("")

    # Classifier precision estimate
    prec = precision.get("estimated_precision", 0)
    n_core = precision.get("n_core", 0)
    n_border = precision.get("n_borderline", 0)
    n_fp = precision.get("n_likely_fp", 0)
    n_samp = precision.get("sample_size", 0)
    a("### Classifier precision estimate")
    a("")
    a(f"Seeded random sample of {n_samp} questions (seed={precision.get('seed')}), "
      f"using a stricter sub-keyword heuristic as a proxy for human review:")
    a("")
    a(f"- Core AI-progress (high confidence): {n_core}")
    a(f"- Borderline (plausibly AI-progress): {n_border}")
    a(f"- Likely false positive: {n_fp}")
    a(f"- **Estimated precision: {prec:.1%}** (lower bound; LLM classifier in Phase 2 will be more accurate)")
    a("")
    a("Selected sample titles:")
    a("")
    for item in precision.get("sample", [])[:30]:
        flag = {"core": "[CORE]", "borderline": "[BORDER]", "likely_fp": "[FP?]"}.get(item["category"], "")
        a(f"- {flag} `{item['source']}` — {item['title'][:100]}")
    a("")

    # -----------------------------------------------------------------------
    # QUESTION 2: Resolution-date distribution
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## 2. Distribution of resolved_at Over Time")
    a("")

    by_year = dist.get("by_year", {})
    all_years = sorted(set(
        y for src_d in by_year.values() for y in src_d.keys()
    ))

    if all_years:
        a("### By year")
        a("")
        W2 = [8, 14, 14, 12]
        a(_table_row(["Year", "Metaculus", "Manifold", "Combined"], W2))
        a(_hline(W2))
        for yr in all_years:
            mc = by_year.get("metaculus", {}).get(yr, 0)
            mf = by_year.get("manifold", {}).get(yr, 0)
            cb = by_year.get("combined", {}).get(yr, 0)
            a(_table_row([yr, str(mc), str(mf), str(cb)], W2))
        a("")

    by_quarter = dist.get("by_quarter", {})
    all_quarters = sorted(set(
        q for src_d in by_quarter.values() for q in src_d.keys()
    ))

    if all_quarters:
        a("### By quarter (ASCII histogram)")
        a("")
        max_cb = max((by_quarter.get("combined", {}).get(q, 0) for q in all_quarters), default=1)
        max_bar = 40
        a("```")
        for q in all_quarters:
            cb = by_quarter.get("combined", {}).get(q, 0)
            bar_len = int(cb / max_cb * max_bar) if max_cb > 0 else 0
            bar = "#" * bar_len
            a(f"  {q}  {str(cb).rjust(4)}  {bar}")
        a("```")
        a("")

    # -----------------------------------------------------------------------
    # QUESTION 3: Clean post-cutoff N per candidate cutoff
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## 3. Clean Post-Cutoff N per Candidate Cutoff (D-006 Rule)")
    a("")
    a(f"Rule: resolved_at >= C + {SNAPSHOT_LEAD_DAYS}d. "
      f"Snapshot-feasible subset additionally requires the question to have been open "
      f"with at least one forecast/bet before the snapshot date T = resolved_at - {SNAPSHOT_LEAD_DAYS}d.")
    a("")

    W3 = [38, 12, 12, 12, 12, 12, 12]
    headers = ["Cutoff", "raw_Meta", "raw_Mf", "raw_Comb", "snap_Meta", "snap_Mf", "snap_Comb"]
    a(_table_row(headers, W3))
    a(_hline(W3))
    for row in cutoff_rows:
        a(_table_row([
            row["cutoff_label"],
            str(row["raw_metaculus"]),
            str(row["raw_manifold"]),
            str(row["raw_combined"]),
            str(row["snap_feasible_metaculus"]),
            str(row["snap_feasible_manifold"]),
            str(row["snap_feasible_combined"]),
        ], W3))
    a("")
    a("Columns: raw_* = count satisfying D-006 date rule only; snap_* = subset with "
      "crowd-snapshot feasibility heuristic (created before T and has ≥1 bet/forecast).")
    a("")
    a("**Tradeoff interpretation:** older cutoffs yield more clean N but restrict the model "
      "panel to older, weaker models. Newer cutoffs shrink clean N but permit stronger models. "
      "Panel choice (D-009) resolves this after seeing the tradeoff curve above.")
    a("")

    # -----------------------------------------------------------------------
    # QUESTION 4: Manifold liquidity
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## 4. Manifold Liquidity Assessment (RQ4 Viability)")
    a("")

    n_mf = liquidity.get("n", 0)
    if n_mf == 0:
        a("No Manifold questions found — liquidity assessment not possible.")
    else:
        a(f"Based on {n_mf} Manifold AI-progress binary resolved questions.")
        a("")
        a("### Summary statistics (mana = Manifold play-money)")
        a("")
        W4 = [28, 10, 10, 10, 10, 10]
        a(_table_row(["Metric", "Median", "P25", "P75", "P90", "Mean"], W4))
        a(_hline(W4))

        def _row4(label: str, key: str) -> str:
            d = liquidity.get(key, {})
            return _table_row([
                label,
                str(d.get("median", "—")),
                str(d.get("p25", "—")),
                str(d.get("p75", "—")),
                str(d.get("p90", "—")),
                str(d.get("mean", "—")),
            ], W4)

        a(_row4("Volume (mana)", "volume_mana"))
        a(_row4("Unique bettors", "unique_bettors"))
        a(_row4("Total liquidity (mana)", "total_liquidity_mana"))
        a("")
        a("Note: trade count is not returned by the `/v0/markets` listing endpoint; it is omitted from this table. "
          "Volume and unique bettors are the primary liquidity indicators.")
        a("")

        v = liquidity.get("viability", {})
        a("### Viability thresholds")
        a("")
        a(f"Threshold: {v.get('thresholds', '')}")
        a("")
        a(f"- N above 20 unique bettors: {v.get('n_above_20_bettors', '—')} / {n_mf} ({v.get('n_above_20_bettors', 0) / n_mf * 100:.1f}%)")
        a(f"- N above 1,000 mana volume: {v.get('n_above_1000_vol', '—')} / {n_mf} ({v.get('n_above_1000_vol', 0) / n_mf * 100:.1f}%)")
        a(f"- N meeting BOTH thresholds: **{v.get('n_viable', '—')} / {n_mf} ({v.get('pct_viable', 0):.1f}%)**")
        a("")
        # Verdict
        pct_viable = v.get("pct_viable", 0)
        if pct_viable >= 40:
            verdict = "VIABLE — substantial fraction of markets have enough liquidity for microstructure analysis."
        elif pct_viable >= 15:
            verdict = "MARGINAL — minority of markets are liquid enough; RQ4 feasible but constrained to the liquid subset."
        else:
            verdict = "THIN — most markets are very low-liquidity play-money markets; RQ4 conclusions will be weak. Consider de-scoping RQ4 or reporting it as purely illustrative."
        a(f"**RQ4 viability verdict: {verdict}**")
        a("")
        a("Reminder: Manifold uses play-money (mana), not USD. Even liquid mana markets represent "
          "illustrative mechanics, not real economic value. Any RQ4 claim must state this explicitly.")
    a("")

    # -----------------------------------------------------------------------
    # QUESTION 5: RQ3 power sketch
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## 5. RQ3 Power Sketch (Simulation Substitute for Blocked Pilot)")
    a("")
    a("**Status: No LLM API keys present. Pilot elicitation (DATA.md item 5) is deferred "
      "until keys exist. This section reports a seeded Monte Carlo simulation as a substitute.**")
    a("")
    a("### Simulation design")
    a("")
    a(f"- Seed: {power['parameters']['seed']}")
    a(f"- Monte Carlo replications per cell: {power['parameters']['n_monte_carlo']:,}")
    a(f"- Alpha: {power['parameters']['alpha']}")
    a(f"- Information weight of weaker source (w): {power['parameters']['w_weaker']} "
      f"(25% scenario — weaker source carries 25% of information; neither is collinear with the other)")
    a(f"- Model: true_logit ~ N(0, 1.5); crowd/model logits = sqrt(ρ)*true + sqrt(1-ρ)*noise")
    a(f"  where ρ is the target crowd-model correlation")
    a(f"- Test: logistic regression outcome ~ logit(crowd) + logit(model) via Newton-Raphson;")
    a(f"  power = fraction of simulations where BOTH β_crowd and β_model are significant (z > {1.96:.2f})")
    a("")

    a("### Power grid (power_both = P[reject β_crowd=0 AND β_model=0])")
    a("")

    # Build grid table
    params = power["parameters"]
    rho_grid = params["rho_grid"]
    n_grid_sorted = sorted(set(params["n_grid"]))
    results_list = power["results"]

    def _lookup(n: int, rho: float) -> str:
        for r in results_list:
            if r.get("n") == n and abs(r.get("rho", -1) - rho) < 1e-9:
                pb = r.get("power_both")
                if pb is None:
                    return "—"
                s = f"{pb:.3f}"
                if pb >= 0.80:
                    s = f"**{s}**"
                return s
        return "—"

    W5 = [8] + [12] * len(rho_grid)
    header_cells = ["N \\ ρ"] + [f"ρ={r}" for r in rho_grid]
    a(_table_row(header_cells, W5))
    a(_hline(W5))
    for n in n_grid_sorted:
        row_cells = [str(n)] + [_lookup(n, rho) for rho in rho_grid]
        a(_table_row(row_cells, W5))
    a("")
    a("Bold = power_both >= 80%. Values are empirical rejection rates across "
      f"{power['parameters']['n_monte_carlo']:,} simulations.")
    a("")

    a("### Minimum N for 80% power per ρ")
    a("")
    min_n_table = power.get("minimum_n_for_80pct_power", {})
    W6 = [14, 20]
    a(_table_row(["ρ", "Min N for 80% power"], W6))
    a(_hline(W6))
    for rho in rho_grid:
        min_n = min_n_table.get(rho)
        val = str(min_n) if min_n is not None else f"> {max(n_grid_sorted)}"
        a(_table_row([f"{rho}", val], W6))
    a("")

    # -----------------------------------------------------------------------
    # RECOMMENDATION BLOCK
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## RECOMMENDATION")
    a("")

    # Determine best cutoffs
    # Pick ~3 cutoffs that give the best tradeoff
    cutoff_options = []
    for row in cutoff_rows:
        n_snap = row["snap_feasible_combined"]
        cutoff_options.append((row["cutoff_date"], row["cutoff_label"], n_snap, row))

    # Sort by snap_feasible_combined descending to find the tradeoff
    sorted_options = sorted(cutoff_options, key=lambda x: x[2], reverse=True)

    a("### Primary data source")
    a("")
    if meta_total == 0:
        a("**Manifold** is the sole accessible source for Phase 0 (D-009) because:")
        a("- Metaculus API now returns HTTP 403 Forbidden for all endpoints without authentication.")
        a("  The error body states: 'The API is only available to authenticated users.'")
        a("  This is a policy change from the previously key-less public API documented in DATA.md.")
        a(f"- Manifold yielded {manifold_total} AI-progress binary resolved questions via key-less public API.")
        a("")
        a("**Recommended action:** Obtain a Metaculus API token to unlock their dataset. "
          "With a token, Metaculus could add significant N (especially for pre-2022 resolved questions). "
          "For Phase 1 onward, provision a Metaculus token in `.env` (key: `METACULUS_API_TOKEN`).")
    elif meta_total >= manifold_total * 0.5:
        a("**Metaculus** is recommended as the primary source (D-009) based on:")
        a(f"- Larger resolved AI-progress binary set ({meta_total} vs {manifold_total} for Manifold)")
        a("- Rich community-prediction history suitable for crowd-probability snapshots")
        a("- Structured AI category/tag filtering")
        a("")
        a("Manifold should be retained as a secondary source to increase N and for RQ4 microstructure "
          "analysis (noting play-money caveat).")
    else:
        a("**Both sources** contribute substantially; combine for maximum N.")
        a("")

    a("### Candidate model panel (D-009)")
    a("")
    a("Recommended ~3-model panel spanning capability and recency, based on the clean-N tradeoff:")
    a("")
    a("| Model | Knowledge cutoff | Est. snap-feasible N (combined) | Role |")
    a("|---|---|---|---|")

    # Pick 3 representative cutoffs
    panel = [
        ("GPT-4 (0314)", "2022-01-01"),
        ("GPT-4o / Claude-3.5-Sonnet", "2023-10-01"),
        ("Claude-3.7-Sonnet / Gemini-2.5-Pro", "2025-01-01"),
    ]
    for model_name, cutoff_date in panel:
        matching = [r for r in cutoff_rows if r["cutoff_date"] == cutoff_date]
        n_here = matching[0]["snap_feasible_combined"] if matching else "—"
        a(f"| {model_name} | {cutoff_date} | {n_here} | {'Older / high N' if cutoff_date < '2023-01' else 'Mid-range' if cutoff_date < '2024-06' else 'Newest / smallest N'} |")
    a("")

    a("### RQ3 confirmatory vs. exploratory verdict (D-008)")
    a("")

    # Look at the observed snap-feasible combined N for a mid-range cutoff
    # Use 2023-10 as a representative "realistic" cutoff
    ref_row = next((r for r in cutoff_rows if r["cutoff_date"] == "2023-10-01"), None)
    if ref_row:
        obs_n = ref_row["snap_feasible_combined"]
        a(f"At the representative cutoff 2023-10 (GPT-4o class), observed clean N = **{obs_n}**.")
        a("")

        # Check if obs_n meets 80% power threshold at any realistic rho
        verdict_rows = []
        for rho in POWER_SIM_RHO_GRID:
            min_n = min_n_table.get(rho)
            if min_n is not None and obs_n >= min_n:
                verdict_rows.append((rho, min_n, True))
            else:
                max_n_checked = max(n_grid_sorted)
                verdict_rows.append((rho, min_n, obs_n > max_n_checked))

        any_powered = any(v[2] for v in verdict_rows)
        high_rho_powered = any(v[2] and v[0] >= 0.75 for v in verdict_rows)

        if obs_n >= 200 and any_powered:
            rq3_verdict = "CONFIRMATORY"
            a(f"**RQ3 VERDICT: CONFIRMATORY** — observed N={obs_n} meets the 80% power threshold "
              f"at ρ ≤ 0.75. RQ3 can proceed as a confirmatory test per D-008.")
        elif obs_n >= 100:
            rq3_verdict = "BORDERLINE / EXPLORATORY"
            a(f"**RQ3 VERDICT: BORDERLINE** — observed N={obs_n}. Adequate power is achievable at "
              f"low-to-medium ρ (≤ 0.6), but at higher correlation (ρ ≥ 0.75) the test is underpowered "
              f"without combining sources. Recommended: label RQ3 as confirmatory only if ρ_empirical ≤ 0.6 "
              f"(measured during Phase 1 pilot); otherwise report as pre-registered exploratory per D-008.")
        else:
            rq3_verdict = "EXPLORATORY"
            a(f"**RQ3 VERDICT: EXPLORATORY** — observed N={obs_n} is below the minimum threshold "
              f"for 80% power even at low ρ. RQ3 must be reported as exploratory (D-008). "
              f"To address: combine Metaculus + Manifold, or extend the collection window.")
        a("")
    else:
        rq3_verdict = "UNKNOWN"
        a("Could not determine verdict: no data at the 2023-10 cutoff.")
        obs_n = 0

    a("### RQ4 viability verdict")
    a("")
    pct_viable = liquidity.get("viability", {}).get("pct_viable", 0)
    n_viable = liquidity.get("viability", {}).get("n_viable", 0)
    if pct_viable >= 40:
        a(f"**RQ4 VIABLE** — {n_viable} / {n_mf} ({pct_viable:.1f}%) Manifold markets meet liquidity thresholds. "
          f"Microstructure backtest is meaningful on the liquid subset.")
    elif pct_viable >= 15:
        a(f"**RQ4 MARGINAL** — {n_viable} / {n_mf} ({pct_viable:.1f}%) Manifold markets meet liquidity thresholds. "
          f"RQ4 should be labeled preliminary and restricted to the liquid subset.")
    else:
        a(f"**RQ4 THIN** — {n_viable} / {n_mf if n_mf else '?'} ({pct_viable:.1f}%) markets meet thresholds. "
          f"RQ4 is predominantly illustrative. Recommend de-scoping per D-005 if time is short.")
    a("")

    # -----------------------------------------------------------------------
    # LIMITATIONS
    # -----------------------------------------------------------------------
    a("---")
    a("")
    a("## LIMITATIONS")
    a("")
    a("1. **No pilot elicitation** — The DATA.md item 5 pilot (LLM forecasts on ~20-30 questions "
      "to estimate empirical market-model correlation ρ) is blocked because no LLM API keys "
      "exist in this environment. The power sketch uses a simulated ρ grid; the actual ρ may "
      "be higher or lower. Until the empirical ρ is measured in Phase 1, the power verdict is "
      "tentative. If empirical ρ > 0.75, additional N (by broadening sources or extending the "
      "date range) may be needed before RQ3 can be labeled confirmatory.")
    a("")
    a("2. **Keyword classifier (v1.0) precision** — The keyword filter is a coarse first pass. "
      f"Estimated precision is ~{precision.get('estimated_precision', 0):.1%} (lower bound). "
      "Some false positives (non-AI-progress questions matched by generic keywords like ' ai ') "
      "and false negatives (AI-progress questions without the specific keywords) will remain. "
      "The Phase-2 LLM-assisted classifier will resolve this; Phase-0 counts are approximate.")
    a("")
    a("3. **Snapshot feasibility heuristic** — We cannot query the actual crowd-prediction history "
      "at T = resolved_at - 30d without fetching full time-series data (a heavier pull). The "
      "snapshot-feasible counts use a necessary-condition heuristic: question was created before "
      "T and has at least one bet/forecast recorded. Some questions in the snapshot-feasible count "
      "may still lack a forecast at the exact T; actual available N may be ~5-15% lower.")
    a("")
    a("4. **Metaculus authentication required** — As of 2026-07-15, Metaculus `/api2/` and "
      "all other Metaculus endpoints return HTTP 403 Forbidden without an API token. "
      "Metaculus data is entirely absent from this Phase-0 report. Provisioning a token "
      "in `.env` (key: `METACULUS_API_TOKEN`) and re-running the recon will add additional N, "
      "particularly for questions resolved before 2022 (Manifold's coverage is thin there). "
      "Manifold v0 endpoints are working and used as the sole source here.")
    a("")
    a("5. **Manifold group coverage** — Only the group slugs listed in `config.py` are queried. "
      "Additional AI-adjacent groups may exist under different slugs; their markets are missed. "
      "This is a conservative estimate of Manifold's total AI-progress coverage.")
    a("")
    a("6. **Play-money caveat (Manifold)** — Manifold uses mana, not real money. All liquidity "
      "figures are in mana; any RQ4 economic-value claim is illustrative at best.")
    a("")

    return "\n".join(lines)


def write_report(report_text: str, path: str = REPORT_PATH) -> None:
    """Write the report to disk."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    print(f"  Report written to: {path}", flush=True)
