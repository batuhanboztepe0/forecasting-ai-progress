"""
run_thin_slice_v2.py — Phase-1 plumbing-check re-run under elicitation protocol v2 (D-012).

This is a PLUMBING CHECK, not an accuracy bake-off.  The quant-analyst scores separately.

Usage:
    python3 src/mvp/run_thin_slice_v2.py            # live (calls Anthropic API)
    python3 src/mvp/run_thin_slice_v2.py --offline  # cache-only (post-live determinism check)

Outputs (all git-ignored except manifest):
    data/interim/mvp_forecasts_v2.csv   — v2 forecasts; same schema as v1 + protocol column
    data/mvp_manifest.json              — updated to include v2 run (v1 entry preserved)
    docs/EXPERIMENTS.md                 — v2 run + cost rows appended

Pipeline:
  1. Load 50 questions from data/interim/mvp_sample.json (SAME as v1 — no re-sampling)
  2. Load crowd_prob_at_T from data/interim/mvp_crowd_probs.json (SAME — no re-fetch)
  3. Estimate cost; hard-stop if > $1 (D-012 spec)
  4. Elicit all 50 × 3 models under protocol v2
  5. Write mvp_forecasts_v2.csv
  6. Run offline pass → compare SHA-256 of both CSVs (determinism check)
  7. Update mvp_manifest.json (append v2; preserve v1)
  8. Append run + cost rows to EXPERIMENTS.md
  9. Print acceptance criteria 1–5
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.abspath(os.path.join(_HERE, ".."))
_RECON = os.path.join(_SRC, "recon")
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mvp_config import (
    RANDOM_SEED,
    PANEL_MODELS,
    TRAINING_CUTOFFS,
    SNAPSHOT_LEAD_DAYS,
    COST_HARD_STOP_USD,
    ELICITATION_PROTOCOL_VERSION_V2,
    INTERIM_DIR,
    EXPERIMENTS_PATH,
    MVP_MANIFEST_PATH,
    MVP_SAMPLE_PATH,
    MVP_CROWD_PATH,
    MVP_FORECASTS_PATH,
    MVP_FORECASTS_V2_PATH,
)
from elicit_v2 import (
    estimate_cost_v2,
    run_elicitation_v2,
    system_prompt_hash_v2,
)

# Hard stop for this plumbing check run (D-012: ~$0.15–0.40; stop if > $1)
_V2_COST_HARD_STOP_USD: float = 1.0


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _sha256_file(path: str) -> str:
    """SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ------------------------------------------------------------------ #
# CSV output
# ------------------------------------------------------------------ #

def write_forecasts_v2_csv(
    questions: list,
    crowd_probs: dict,
    elicitation: dict,
    out_path: str,
    verbose: bool = True,
) -> str:
    """
    Write the mvp_forecasts_v2.csv output table.

    Same schema as mvp_forecasts.csv plus a 'protocol' column (value: 'v2').
    v1 file is never touched.

    Args:
        questions: Thin-slice question list.
        crowd_probs: qid -> crowd_prob_at_T.
        elicitation: Output of run_elicitation_v2().
        out_path: Destination path.
        verbose: Print path after write.

    Returns:
        Path to the written CSV.
    """
    rec_index: dict = {}
    for r in elicitation["records"]:
        rec_index[(r["qid"], r["model"])] = r

    rows = []
    for q in questions:
        qid = q["qid"]
        resolved_dt = _parse_dt(q.get("resolved_at", ""))
        outcome = q.get("outcome")
        crowd_p = crowd_probs.get(qid)

        for model in PANEL_MODELS:
            rec = rec_index.get((qid, model), {})
            model_prob = rec.get("model_prob")
            elicited_at = rec.get("elicited_at_utc", "")
            cache_hit = rec.get("cache_hit", False)

            cutoff_str = TRAINING_CUTOFFS.get(model, "")
            cutoff_dt = _parse_dt(cutoff_str)
            if cutoff_dt and resolved_dt:
                min_resolved = cutoff_dt + timedelta(days=SNAPSHOT_LEAD_DAYS)
                is_post = (resolved_dt >= min_resolved)
            else:
                is_post = None

            rows.append({
                "qid":             qid,
                "source":          q.get("source", "manifold"),
                "title_hash":      _sha256_str(q.get("title", "")),
                "resolved_at":     q.get("resolved_at", ""),
                "outcome":         outcome,
                "crowd_prob_at_T": f"{crowd_p:.6f}" if crowd_p is not None else "",
                "model":           model,
                "model_prob":      f"{model_prob:.4f}" if model_prob is not None else "",
                "is_post_cutoff":  ("1" if is_post else "0") if is_post is not None else "",
                "elicited_at":     elicited_at,
                "cache_hit":       "1" if cache_hit else "0",
                "protocol":        ELICITATION_PROTOCOL_VERSION_V2,
            })

    os.makedirs(INTERIM_DIR, exist_ok=True)
    fieldnames = [
        "qid", "source", "title_hash", "resolved_at", "outcome",
        "crowd_prob_at_T", "model", "model_prob", "is_post_cutoff",
        "elicited_at", "cache_hit", "protocol",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if verbose:
        print(f"  Wrote {len(rows)} rows to {out_path}", flush=True)

    return out_path


# ------------------------------------------------------------------ #
# Manifest update (append v2; preserve v1)
# ------------------------------------------------------------------ #

def update_manifest_v2(
    questions: list,
    crowd_probs: dict,
    elicitation: dict,
    run_start_utc: str,
) -> None:
    """
    Append a v2 run entry to mvp_manifest.json without removing v1 entries.

    The manifest is converted to a list [v1_entry, v2_entry] if it was a
    flat dict; subsequent writes keep the list format.

    Args:
        questions: Thin-slice question list.
        crowd_probs: qid -> crowd_prob_at_T.
        elicitation: Output of run_elicitation_v2().
        run_start_utc: ISO timestamp of run start.
    """
    # Load existing manifest
    existing = None
    if os.path.exists(MVP_MANIFEST_PATH):
        with open(MVP_MANIFEST_PATH, encoding="utf-8") as fh:
            existing = json.load(fh)

    # Normalise to list
    if isinstance(existing, list):
        manifest_list = existing
    elif isinstance(existing, dict):
        manifest_list = [existing]
    else:
        manifest_list = []

    # Build v2 entry
    n_success = {m: 0 for m in PANEL_MODELS}
    n_parse_err = {m: 0 for m in PANEL_MODELS}
    n_refusals = {m: 0 for m in PANEL_MODELS}
    for r in elicitation["records"]:
        m = r.get("model", "")
        if m not in n_success:
            continue
        if r.get("model_prob") is not None:
            n_success[m] += 1
        elif r.get("is_refusal"):
            n_refusals[m] += 1
        else:
            n_parse_err[m] += 1

    v2_entry = {
        "run_id":               "mvp-thin-slice-v2-2026-07-16",
        "run_start_utc":        run_start_utc,
        "manifest_written_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed":          RANDOM_SEED,
        "d012_decision":        "docs/DECISIONS.md#D-012",
        "source":               "manifold",
        "n_questions":          len(questions),
        "panel_models":         PANEL_MODELS,
        "training_cutoffs":     TRAINING_CUTOFFS,
        "elicitation_protocol": {
            "version":              ELICITATION_PROTOCOL_VERSION_V2,
            "system_prompt_sha256": system_prompt_hash_v2(),
            "max_tokens":           1000,
            "temperature": {
                m: 0 if m == "claude-haiku-4-5-20251001" else "omitted"
                for m in PANEL_MODELS
            },
            "thinking":        "omitted for all models",
            "prob_range":      [0.01, 0.99],
            "cache_key_scheme": (
                "sha256(qid|model|v2|seed)[:32]; "
                "files at data/llm_cache/mvp_v2_{model}_{key}.json (git-ignored)"
            ),
        },
        "crowd_snapshot": {
            "method":    "reused from v1 (mvp_crowd_probs.json); no re-fetch",
            "n_valid":   sum(1 for v in crowd_probs.values() if v is not None),
            "n_missing": sum(1 for v in crowd_probs.values() if v is None),
        },
        "elicitation_results": {
            "total_input_tokens":  elicitation["total_input_tokens"],
            "total_output_tokens": elicitation["total_output_tokens"],
            "total_usd":           round(elicitation["total_usd"], 5),
            "n_cache_hits":        elicitation["n_cache_hits"],
            "n_api_calls":         elicitation["n_api_calls"],
            "n_parse_errors":      elicitation["n_parse_errors"],
            "n_refusals":          elicitation["n_refusals"],
            "per_model": {
                m: {
                    "n_success":     n_success[m],
                    "n_parse_errors": n_parse_err[m],
                    "n_refusals":    n_refusals[m],
                }
                for m in PANEL_MODELS
            },
        },
        "artifact":  MVP_FORECASTS_V2_PATH,
        "auth":      "keys loaded from .env only; never written to this file",
    }

    manifest_list.append(v2_entry)

    os.makedirs(os.path.dirname(MVP_MANIFEST_PATH), exist_ok=True)
    with open(MVP_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest_list, fh, ensure_ascii=False, indent=2)
    print(f"  Updated manifest (now {len(manifest_list)} entries): {MVP_MANIFEST_PATH}",
          flush=True)


# ------------------------------------------------------------------ #
# EXPERIMENTS.md update
# ------------------------------------------------------------------ #

def append_experiments_v2(elicitation: dict) -> None:
    """
    Append v2 run row and per-model cost rows to EXPERIMENTS.md.

    Idempotent: skips if the v2 run_id is already present.

    Args:
        elicitation: Output of run_elicitation_v2().
    """
    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    run_id = "mvp-thin-slice-v2-2026-07-16"
    if run_id in content:
        print(f"  EXPERIMENTS.md already contains {run_id}; skipping.", flush=True)
        return

    # Per-model token breakdown
    per_model_tokens: dict = {m: {"in": 0, "out": 0, "usd": 0.0} for m in PANEL_MODELS}
    for r in elicitation["records"]:
        m = r.get("model", "")
        if m in per_model_tokens:
            per_model_tokens[m]["in"]  += r.get("input_tokens", 0)
            per_model_tokens[m]["out"] += r.get("output_tokens", 0)
            per_model_tokens[m]["usd"] += r.get("usd", 0.0)

    total_usd = elicitation["total_usd"]

    # Parse current running total
    m = re.search(r"\*\*Running total: USD ([\d.]+)\*\*", content)
    prev_total = float(m.group(1)) if m else 0.0
    new_total = round(prev_total + total_usd, 4)

    # Run-record row
    run_row = (
        f"| {run_id} | 2026-07-16 | 1 | elicitation | "
        f"src/mvp/elicit_v2.py@HEAD | {RANDOM_SEED} | "
        f"haiku-4-5,sonnet-5,opus-4-8 | 50 | "
        f"data/interim/mvp_forecasts_v2.csv | "
        f"Phase-1 plumbing check protocol-v2 (D-012); "
        f"n_cache={elicitation['n_cache_hits']} "
        f"parse_err={elicitation['n_parse_errors']} "
        f"refusals={elicitation['n_refusals']} |"
    )

    # Cost-ledger rows
    cost_rows = []
    cumulative = prev_total
    for model in PANEL_MODELS:
        tok = per_model_tokens[model]
        cumulative = round(cumulative + tok["usd"], 5)
        cost_rows.append(
            f"| {run_id} | {model} | {tok['in']:,} | {tok['out']:,} "
            f"| no | no | {tok['usd']:.4f} | {cumulative:.4f} |"
        )

    # Insert before _example_ rows
    run_row_line = run_row + "\n"
    example_marker = "| _example_ | 2026-01-01 | 1"
    content = content.replace(example_marker, run_row_line + example_marker)

    cost_example_marker = "| _example_ | claude-sonnet"
    cost_insert = "\n".join(cost_rows) + "\n"
    content = content.replace(cost_example_marker, cost_insert + cost_example_marker)

    # Update running total
    content = re.sub(
        r"\*\*Running total: USD [\d.]+\*\*",
        f"**Running total: USD {new_total}**",
        content,
    )

    with open(EXPERIMENTS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  Updated EXPERIMENTS.md (running total: ${prev_total:.4f} → ${new_total:.4f})",
          flush=True)


# ------------------------------------------------------------------ #
# Acceptance criteria reporting
# ------------------------------------------------------------------ #

def _load_v1_probs_per_model() -> dict:
    """
    Read mvp_forecasts.csv (v1) and return {model: [probs]} for degeneracy check.

    Returns empty dict if v1 CSV is not found.
    """
    result: dict = {m: [] for m in PANEL_MODELS}
    if not os.path.exists(MVP_FORECASTS_PATH):
        return result
    with open(MVP_FORECASTS_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            m = row.get("model", "")
            p_str = row.get("model_prob", "")
            if m in result and p_str:
                try:
                    result[m].append(round(float(p_str), 4))
                except ValueError:
                    pass
    return result


def print_acceptance_report(
    elicitation: dict,
    sha256_run1: str,
    sha256_run2: str,
) -> None:
    """
    Print the 5 acceptance criteria required by the task spec.

    Args:
        elicitation: Output of run_elicitation_v2() (first / live run).
        sha256_run1: SHA-256 of the CSV from the live run.
        sha256_run2: SHA-256 of the CSV from the offline (cache-only) re-run.
    """
    records = elicitation["records"]
    n_total = len(records)

    # ---- Criterion 1: completion + parse errors + refusals ----
    n_success = sum(1 for r in records if r.get("model_prob") is not None)
    n_parse   = elicitation["n_parse_errors"]
    n_refusal = elicitation["n_refusals"]
    print("\n=== ACCEPTANCE CRITERIA ===", flush=True)
    print(f"1. Elicitations: {n_success}/{n_total} completed  "
          f"parse_errors={n_parse}  refusals={n_refusal}", flush=True)

    # ---- Criterion 2: reasoning-length sanity ----
    # Estimate tokens as characters / 4 (rough approximation).
    reasoning_token_ests = []
    for r in records:
        rc = r.get("reasoning_chars", 0)
        if r.get("model_prob") is not None and rc > 0:
            reasoning_token_ests.append(rc / 4.0)

    if reasoning_token_ests:
        r_min = min(reasoning_token_ests)
        r_med = statistics.median(reasoning_token_ests)
        r_max = max(reasoning_token_ests)
        print(f"2. Reasoning length (est. tokens, chars/4): "
              f"min={r_min:.1f}  median={r_med:.1f}  max={r_max:.1f}", flush=True)
    else:
        print("2. Reasoning length: no data (all parse errors?)", flush=True)

    # ---- Criterion 3: haiku degeneracy ----
    v2_probs_per_model: dict = {m: [] for m in PANEL_MODELS}
    for r in records:
        m = r.get("model", "")
        p = r.get("model_prob")
        if m in v2_probs_per_model and p is not None:
            v2_probs_per_model[m].append(round(p, 4))

    v1_probs_per_model = _load_v1_probs_per_model()

    print("3. Distinct probabilities per model (v1 → v2):", flush=True)
    for m in PANEL_MODELS:
        v1_distinct = len(set(v1_probs_per_model.get(m, [])))
        v2_distinct = len(set(v2_probs_per_model.get(m, [])))
        v1_vals = sorted(set(v1_probs_per_model.get(m, [])))
        v2_vals = sorted(set(v2_probs_per_model.get(m, [])))
        short = m.split("-")[1]  # haiku / sonnet / opus
        print(f"   {short}: v1={v1_distinct} {v1_vals}  →  v2={v2_distinct} {v2_vals[:10]}",
              flush=True)

    # ---- Criterion 4: offline determinism ----
    determinism_pass = (sha256_run1 == sha256_run2)
    print(f"4. Offline determinism: {'PASS' if determinism_pass else 'FAIL'}  "
          f"sha256_run1={sha256_run1[:16]}...  "
          f"sha256_run2={sha256_run2[:16]}...", flush=True)
    if not determinism_pass:
        print("   WARNING: SHA-256 mismatch — cache may not be complete.", flush=True)

    # ---- Criterion 5: cost per model and total ----
    per_model_usd: dict = {m: 0.0 for m in PANEL_MODELS}
    per_model_in:  dict = {m: 0   for m in PANEL_MODELS}
    per_model_out: dict = {m: 0   for m in PANEL_MODELS}
    for r in records:
        m = r.get("model", "")
        if m in per_model_usd:
            per_model_usd[m] += r.get("usd", 0.0)
            per_model_in[m]  += r.get("input_tokens", 0)
            per_model_out[m] += r.get("output_tokens", 0)

    print("5. Actual cost:", flush=True)
    for m in PANEL_MODELS:
        short = m.split("-")[1]
        print(f"   {short}: in={per_model_in[m]:,} out={per_model_out[m]:,} "
              f"usd=${per_model_usd[m]:.4f}", flush=True)
    print(f"   TOTAL: usd=${elicitation['total_usd']:.4f}", flush=True)


# ------------------------------------------------------------------ #
# Entrypoint
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Phase-1 plumbing-check re-run under elicitation protocol v2 (D-012)"
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Cache-only mode; no API calls."
    )
    args = parser.parse_args()

    run_start = datetime.now(timezone.utc).isoformat()
    print(f"\n=== MVP Thin Slice v2 — run start {run_start} "
          f"({'OFFLINE' if args.offline else 'LIVE'}) ===\n", flush=True)

    # Step 1: Load the SAME 50 questions used in v1 (no re-sampling)
    print("Step 1: Load questions from mvp_sample.json (same as v1)...", flush=True)
    if not os.path.exists(MVP_SAMPLE_PATH):
        raise FileNotFoundError(
            f"mvp_sample.json not found at {MVP_SAMPLE_PATH}. "
            "Run run_thin_slice.py first."
        )
    with open(MVP_SAMPLE_PATH, encoding="utf-8") as fh:
        questions = json.load(fh)
    print(f"  {len(questions)} questions loaded.\n", flush=True)

    # Step 2: Load crowd probs (no re-fetch — use existing v1 crowd snapshot)
    print("Step 2: Load crowd_prob_at_T from mvp_crowd_probs.json...", flush=True)
    if not os.path.exists(MVP_CROWD_PATH):
        raise FileNotFoundError(
            f"mvp_crowd_probs.json not found at {MVP_CROWD_PATH}. "
            "Run run_thin_slice.py first."
        )
    with open(MVP_CROWD_PATH, encoding="utf-8") as fh:
        crowd_probs = json.load(fh)
    n_crowd_ok = sum(1 for v in crowd_probs.values() if v is not None)
    print(f"  Crowd probs available: {n_crowd_ok}/{len(questions)}\n", flush=True)

    # Step 3: Cost estimate with v2-specific hard stop of $1
    print("Step 3: Cost estimate (v2)...", flush=True)
    est_usd = estimate_cost_v2(len(questions))
    print(f"  Estimated cost: ${est_usd:.4f} (hard stop: ${_V2_COST_HARD_STOP_USD:.2f})",
          flush=True)
    if est_usd > _V2_COST_HARD_STOP_USD:
        raise RuntimeError(
            f"Projected v2 cost ${est_usd:.2f} exceeds hard stop "
            f"${_V2_COST_HARD_STOP_USD:.2f}. Aborting."
        )
    # Also check against global hard stop
    if est_usd > COST_HARD_STOP_USD:
        raise RuntimeError(
            f"Projected v2 cost ${est_usd:.2f} exceeds global hard stop "
            f"${COST_HARD_STOP_USD:.0f}. Aborting."
        )
    print("  Cost check: PASS\n", flush=True)

    # Step 4: Live elicitation (protocol v2)
    print("Step 4: Run elicitation (protocol v2)...", flush=True)
    elicitation = run_elicitation_v2(questions, offline=args.offline, verbose=True)
    print(f"\n  Actual cost: ${elicitation['total_usd']:.4f}\n", flush=True)

    # Step 5: Write v2 forecasts CSV
    print("Step 5: Write mvp_forecasts_v2.csv...", flush=True)
    write_forecasts_v2_csv(questions, crowd_probs, elicitation, MVP_FORECASTS_V2_PATH,
                           verbose=True)
    sha256_run1 = _sha256_file(MVP_FORECASTS_V2_PATH)
    print(f"  SHA-256 (run 1): {sha256_run1}\n", flush=True)

    # Step 6: Offline re-run for determinism check (cache-only)
    print("Step 6: Offline determinism check (re-run from cache)...", flush=True)
    elicitation_offline = run_elicitation_v2(questions, offline=True, verbose=False)

    # Write to a temp path for comparison
    tmp_csv_path = MVP_FORECASTS_V2_PATH + ".tmp_det_check"
    write_forecasts_v2_csv(questions, crowd_probs, elicitation_offline, tmp_csv_path,
                           verbose=False)
    sha256_run2 = _sha256_file(tmp_csv_path)
    os.remove(tmp_csv_path)
    print(f"  SHA-256 (run 2, cache-only): {sha256_run2}", flush=True)
    determinism_ok = (sha256_run1 == sha256_run2)
    print(f"  Determinism: {'PASS' if determinism_ok else 'FAIL'}\n", flush=True)

    if not determinism_ok:
        raise RuntimeError(
            "Determinism check FAILED: SHA-256 mismatch between live and cached runs."
        )

    # Step 7: Update manifest
    print("Step 7: Update mvp_manifest.json...", flush=True)
    update_manifest_v2(questions, crowd_probs, elicitation, run_start_utc=run_start)
    print(flush=True)

    # Step 8: Update EXPERIMENTS.md
    print("Step 8: Update EXPERIMENTS.md...", flush=True)
    append_experiments_v2(elicitation)
    print(flush=True)

    # Step 9: Acceptance criteria report
    print_acceptance_report(elicitation, sha256_run1, sha256_run2)

    print(f"\n=== v2 plumbing check COMPLETE ===", flush=True)
    print(f"  CSV:      {MVP_FORECASTS_V2_PATH}", flush=True)
    print(f"  Manifest: {MVP_MANIFEST_PATH}", flush=True)
    print(f"  Experiments: {EXPERIMENTS_PATH}", flush=True)


if __name__ == "__main__":
    main()
