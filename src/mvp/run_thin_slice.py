"""
run_thin_slice.py — Single entrypoint for Phase-1 MVP thin slice (D-011).

Usage:
    python3 src/mvp/run_thin_slice.py            # live (calls Anthropic API)
    python3 src/mvp/run_thin_slice.py --offline  # offline (cache only)

Outputs:
    data/interim/mvp_sample.json        — 50 selected questions (committed via .gitignore: not committed)
    data/interim/mvp_crowd_probs.json   — crowd_prob_at_T per question (not committed)
    data/interim/mvp_forecasts.csv      — final forecasts table (not committed)
    data/mvp_manifest.json              — provenance record (committed)
    docs/EXPERIMENTS.md                 — appended run row (committed)

All intermediate data in data/interim/ is git-ignored.  The committed
artifact is mvp_forecasts.csv (path logged in manifest) + manifest + EXPERIMENTS row.

Pipeline:
  1. Select 50 questions (seeded, D-011 spec)
  2. Fetch crowd_prob_at_T for questions not already in cache
  3. Estimate cost and hard-stop if > $25
  4. Elicit all 50 × 3 models (protocol v1)
  5. Write mvp_forecasts.csv
  6. Write mvp_manifest.json
  7. Append row to EXPERIMENTS.md
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

# Ensure both src/mvp/ (this dir) and src/recon/ are importable.
# mvp_config.py (unique name) in src/mvp/ avoids shadowing src/recon/config.py.
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
    ELICITATION_PROTOCOL_VERSION,
    RAW_DIR,
    LLM_CACHE_DIR,
    INTERIM_DIR,
    EXPERIMENTS_PATH,
    MVP_MANIFEST_PATH,
    MVP_SAMPLE_PATH,
    MVP_CROWD_PATH,
    MVP_FORECASTS_PATH,
    PILOT_QUESTIONS_PATH,
    PILOT_CROWD_PROBS_PATH,
)
from sample_questions import load_or_build_sample
from elicit import (
    estimate_cost,
    run_elicitation,
    system_prompt_hash,
)

# Reuse the recon crowd-history fetcher
sys.path.insert(0, _RECON)
from fetch_crowd_history import crowd_prob_at_snapshot


# ------------------------------------------------------------------ #
# Crowd probability helpers
# ------------------------------------------------------------------ #

def load_or_fetch_crowd_probs(
    questions: list,
    pilot_crowd_probs: dict,
    offline: bool,
    verbose: bool,
) -> dict:
    """
    Load cached crowd probabilities, re-using pilot values where available.
    Fetch from Manifold /v0/bets for missing questions (unless offline).

    Args:
        questions: Thin-slice question list.
        pilot_crowd_probs: Pilot crowd probs dict (qid -> float|None).
        offline: If True, skip API calls.
        verbose: Print progress.

    Returns:
        Dict qid -> crowd_prob_at_T (float or None).
    """
    if os.path.exists(MVP_CROWD_PATH):
        with open(MVP_CROWD_PATH, encoding="utf-8") as fh:
            existing = json.load(fh)
        if all(q["qid"] in existing for q in questions):
            if verbose:
                print(f"  Crowd probs: loaded all {len(questions)} from {MVP_CROWD_PATH}",
                      flush=True)
            return existing

    crowd = {}
    n_reuse = n_fetch = n_fail = 0

    for q in questions:
        qid = q["qid"]

        # Re-use pilot values first
        if qid in pilot_crowd_probs and pilot_crowd_probs[qid] is not None:
            crowd[qid] = pilot_crowd_probs[qid]
            n_reuse += 1
            continue

        # Already fetched and cached from a prior run
        if os.path.exists(MVP_CROWD_PATH):
            with open(MVP_CROWD_PATH, encoding="utf-8") as fh:
                existing = json.load(fh)
            if qid in existing:
                crowd[qid] = existing[qid]
                n_reuse += 1
                continue

        if offline:
            crowd[qid] = None
            n_fail += 1
            continue

        # Live fetch
        if verbose:
            print(f"    Fetching bets for {qid}...", flush=True)
        prob = crowd_prob_at_snapshot(q, verbose=False)
        crowd[qid] = prob
        if prob is not None:
            n_fetch += 1
        else:
            n_fail += 1
        time.sleep(0.4)

    os.makedirs(INTERIM_DIR, exist_ok=True)
    with open(MVP_CROWD_PATH, "w", encoding="utf-8") as fh:
        json.dump(crowd, fh, indent=2)

    if verbose:
        print(f"  Crowd probs: reuse={n_reuse} fetch={n_fetch} fail={n_fail}", flush=True)

    return crowd


# ------------------------------------------------------------------ #
# CSV output
# ------------------------------------------------------------------ #

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


def write_forecasts_csv(
    questions: list,
    crowd_probs: dict,
    elicitation: dict,
    verbose: bool = True,
) -> str:
    """
    Write the mvp_forecasts.csv output table.

    Columns: qid, source, title_hash, resolved_at, outcome,
             crowd_prob_at_T, model, model_prob, is_post_cutoff,
             elicited_at, cache_hit

    Args:
        questions: Thin-slice question list.
        crowd_probs: qid -> crowd_prob_at_T.
        elicitation: Output of run_elicitation().
        verbose: Print path after write.

    Returns:
        Path to written CSV.
    """
    # Index records by (qid, model)
    rec_index: dict = {}
    for r in elicitation["records"]:
        rec_index[(r["qid"], r["model"])] = r

    # Index questions
    q_by_qid = {q["qid"]: q for q in questions}

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

            # is_post_cutoff: resolved_at >= model's training cutoff + 30d
            cutoff_str = TRAINING_CUTOFFS.get(model, "")
            cutoff_dt = _parse_dt(cutoff_str)
            if cutoff_dt and resolved_dt:
                min_resolved = cutoff_dt + timedelta(days=SNAPSHOT_LEAD_DAYS)
                is_post = (resolved_dt >= min_resolved)
            else:
                is_post = None

            rows.append({
                "qid":               qid,
                "source":            q.get("source", "manifold"),
                "title_hash":        _sha256_str(q.get("title", "")),
                "resolved_at":       q.get("resolved_at", ""),
                "outcome":           outcome,
                "crowd_prob_at_T":   f"{crowd_p:.6f}" if crowd_p is not None else "",
                "model":             model,
                "model_prob":        f"{model_prob:.4f}" if model_prob is not None else "",
                "is_post_cutoff":    ("1" if is_post else "0") if is_post is not None else "",
                "elicited_at":       elicited_at,
                "cache_hit":         "1" if cache_hit else "0",
            })

    os.makedirs(INTERIM_DIR, exist_ok=True)
    with open(MVP_FORECASTS_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "qid", "source", "title_hash", "resolved_at", "outcome",
            "crowd_prob_at_T", "model", "model_prob", "is_post_cutoff",
            "elicited_at", "cache_hit",
        ])
        writer.writeheader()
        writer.writerows(rows)

    if verbose:
        print(f"  Wrote {len(rows)} rows to {MVP_FORECASTS_PATH}", flush=True)

    return MVP_FORECASTS_PATH


# ------------------------------------------------------------------ #
# Manifest
# ------------------------------------------------------------------ #

def write_manifest(
    questions: list,
    crowd_probs: dict,
    elicitation: dict,
    run_start_utc: str,
) -> None:
    """Write data/mvp_manifest.json with full provenance."""
    q_content_hashes = {
        q["qid"]: _sha256_str(
            q["qid"] + "|" + (q.get("title") or "") + "|" + (q.get("description") or "")
        )
        for q in questions
    }

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

    manifest = {
        "run_id": "mvp-thin-slice-2026-07-16",
        "run_start_utc": run_start_utc,
        "manifest_written_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_SEED,
        "d011_decision": "docs/DECISIONS.md#D-011",
        "source": "manifold",
        "n_questions": len(questions),
        "strata": {
            "post_cutoff": sum(1 for q in questions if q.get("thin_slice_stratum") == "post_cutoff"),
            "pre_cutoff": sum(1 for q in questions if q.get("thin_slice_stratum") == "pre_cutoff"),
        },
        "panel_models": PANEL_MODELS,
        "training_cutoffs": TRAINING_CUTOFFS,
        "elicitation_protocol": {
            "version": ELICITATION_PROTOCOL_VERSION,
            "system_prompt_sha256": system_prompt_hash(),
            "max_tokens": 1000,
            "temperature": {
                m: 0 if m in ["claude-haiku-4-5-20251001"] else "omitted"
                for m in PANEL_MODELS
            },
            "thinking": "omitted for all models",
            "prob_range": [0.01, 0.99],
            "cache_key_scheme": "sha256(qid|model|protocol_version|seed)[:32]; files at data/llm_cache/mvp_v1_{model}_{key}.json (git-ignored)",
        },
        "crowd_snapshot": {
            "method": "Manifold /v0/bets; probAfter of last non-redemption bet at or before T; T = resolved_at - 30d",
            "n_valid": sum(1 for v in crowd_probs.values() if v is not None),
            "n_missing": sum(1 for v in crowd_probs.values() if v is None),
        },
        "elicitation_results": {
            "total_input_tokens": elicitation["total_input_tokens"],
            "total_output_tokens": elicitation["total_output_tokens"],
            "total_usd": round(elicitation["total_usd"], 5),
            "n_cache_hits": elicitation["n_cache_hits"],
            "n_api_calls": elicitation["n_api_calls"],
            "n_parse_errors": elicitation["n_parse_errors"],
            "n_refusals": elicitation["n_refusals"],
            "per_model": {
                m: {
                    "n_success": n_success[m],
                    "n_parse_errors": n_parse_err[m],
                    "n_refusals": n_refusals[m],
                }
                for m in PANEL_MODELS
            },
        },
        "question_content_hashes_sha256_prefix16": q_content_hashes,
        "auth": "keys loaded from .env only; never written to this file or any tracked file",
        "artifact": MVP_FORECASTS_PATH,
    }

    os.makedirs(os.path.dirname(MVP_MANIFEST_PATH), exist_ok=True)
    with open(MVP_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"  Wrote manifest to {MVP_MANIFEST_PATH}", flush=True)


# ------------------------------------------------------------------ #
# EXPERIMENTS.md update
# ------------------------------------------------------------------ #

def append_experiments(elicitation: dict) -> None:
    """Append two rows (run record + cost ledger per model) to EXPERIMENTS.md."""
    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    run_id = "mvp-thin-slice-2026-07-16"

    # Skip if already present (idempotent)
    if run_id in content:
        print(f"  EXPERIMENTS.md already contains {run_id}; skipping append.", flush=True)
        return

    # Compute per-model token breakdown from records
    per_model_tokens: dict = {m: {"in": 0, "out": 0, "usd": 0.0} for m in PANEL_MODELS}
    for r in elicitation["records"]:
        m = r.get("model", "")
        if m in per_model_tokens:
            per_model_tokens[m]["in"]  += r.get("input_tokens", 0)
            per_model_tokens[m]["out"] += r.get("output_tokens", 0)
            per_model_tokens[m]["usd"] += r.get("usd", 0.0)

    total_usd = elicitation["total_usd"]

    # Parse current running total from EXPERIMENTS.md
    import re
    m = re.search(r"\*\*Running total: USD ([\d.]+)\*\*", content)
    prev_total = float(m.group(1)) if m else 0.0
    new_total = round(prev_total + total_usd, 4)

    # Build run-record row
    run_row = (
        f"| {run_id} | 2026-07-16 | 1 | elicitation | "
        f"src/mvp/config.py@HEAD | {RANDOM_SEED} | "
        f"haiku-4-5,sonnet-5,opus-4-8 | 50 | "
        f"data/interim/mvp_forecasts.csv | "
        f"MVP thin slice: 50q×3 models protocol-v1; "
        f"n_success per model see cost ledger; "
        f"n_cache={elicitation['n_cache_hits']} "
        f"parse_err={elicitation['n_parse_errors']} "
        f"refusals={elicitation['n_refusals']} |"
    )

    # Build cost-ledger rows
    cost_rows = []
    cumulative = prev_total
    for model in PANEL_MODELS:
        tok = per_model_tokens[model]
        cumulative = round(cumulative + tok["usd"], 5)
        cost_rows.append(
            f"| {run_id} | {model} | {tok['in']:,} | {tok['out']:,} "
            f"| no | partial | {tok['usd']:.4f} | {cumulative:.4f} |"
        )

    # Insert run row before _example_ row
    run_row_line = run_row + "\n"
    example_marker = "| _example_ | 2026-01-01 | 1"
    content = content.replace(example_marker, run_row_line + example_marker)

    # Insert cost rows before _example_ cost row
    cost_example_marker = "| _example_ | claude-sonnet"
    cost_insert = "\n".join(cost_rows) + "\n"
    content = content.replace(cost_example_marker, cost_insert + cost_example_marker)

    # Update running total
    content = re.sub(
        r"\*\*Running total: USD [\d.]+\*\*",
        f"**Running total: USD {new_total}**",
        content
    )

    with open(EXPERIMENTS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  Updated EXPERIMENTS.md (running total: ${prev_total:.4f} → ${new_total:.4f})",
          flush=True)


# ------------------------------------------------------------------ #
# Secret-leak scan
# ------------------------------------------------------------------ #

def _leak_scan() -> bool:
    """
    Grep changed tracked files for the first 8 chars of each .env key.
    Returns True if PASS (no leaks), False if FAIL.
    """
    import glob

    env_path = os.path.join(
        os.path.abspath(os.path.join(_HERE, "..", "..")), ".env"
    )
    secrets = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and v and len(v) >= 8:
                    secrets[k] = v

    if not secrets:
        return True  # nothing to check

    repo_root = os.path.abspath(os.path.join(_HERE, "..", ".."))
    files_to_check = (
        glob.glob(os.path.join(repo_root, "src/**/*.py"), recursive=True)
        + glob.glob(os.path.join(repo_root, "docs/*.md"))
        + [os.path.join(repo_root, "data", "mvp_manifest.json")]
        + [os.path.join(repo_root, "data", "recon_manifest.json")]
    )

    leaks = []
    for path in files_to_check:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        for k, v in secrets.items():
            if v[:8] in content:
                leaks.append(f"{os.path.relpath(path, repo_root)}: prefix of {k}")

    if leaks:
        print(f"  SECRET LEAK SCAN: FAIL — {leaks}", flush=True)
        return False
    print("  SECRET LEAK SCAN: PASS", flush=True)
    return True


# ------------------------------------------------------------------ #
# Entrypoint
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Phase-1 MVP thin slice: elicitation pipeline (D-011)"
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Cache-only mode; no API calls. Fails loud on missing cache entries."
    )
    args = parser.parse_args()

    run_start = datetime.now(timezone.utc).isoformat()
    print(f"\n=== MVP Thin Slice — run start {run_start} "
          f"({'OFFLINE' if args.offline else 'LIVE'}) ===\n", flush=True)

    # Step 1: Select questions
    print("Step 1: Load/build question sample...", flush=True)
    questions = load_or_build_sample(verbose=True)
    print(f"  {len(questions)} questions selected.\n", flush=True)

    # Step 2: Load pilot crowd probs for reuse
    pilot_crowd: dict = {}
    if os.path.exists(PILOT_CROWD_PROBS_PATH):
        with open(PILOT_CROWD_PROBS_PATH, encoding="utf-8") as fh:
            pilot_crowd = json.load(fh)

    # Step 3: Fetch/load crowd probabilities
    print("Step 2: Load/fetch crowd_prob_at_T...", flush=True)
    crowd_probs = load_or_fetch_crowd_probs(
        questions, pilot_crowd, offline=args.offline, verbose=True
    )
    n_crowd_ok = sum(1 for v in crowd_probs.values() if v is not None)
    print(f"  Crowd probs available: {n_crowd_ok}/{len(questions)}\n", flush=True)

    # Step 4: Cost estimate + hard stop
    print("Step 3: Cost estimate...", flush=True)
    est_usd = estimate_cost(len(questions))
    print(f"  Estimated cost: ${est_usd:.4f} (hard stop: ${COST_HARD_STOP_USD:.0f})",
          flush=True)
    if est_usd > COST_HARD_STOP_USD:
        raise RuntimeError(
            f"Projected cost ${est_usd:.2f} exceeds hard stop ${COST_HARD_STOP_USD:.0f}. "
            "Aborting."
        )
    print(f"  Cost check: PASS\n", flush=True)

    # Step 5: Elicitation
    print("Step 4: Run elicitation (protocol v1)...", flush=True)
    elicitation = run_elicitation(questions, offline=args.offline, verbose=True)
    print(f"\n  Actual cost: ${elicitation['total_usd']:.4f}\n", flush=True)

    # Step 6: Write forecasts CSV
    print("Step 5: Write forecasts CSV...", flush=True)
    csv_path = write_forecasts_csv(questions, crowd_probs, elicitation, verbose=True)
    print(flush=True)

    # Step 7: Write manifest
    print("Step 6: Write mvp_manifest.json...", flush=True)
    write_manifest(questions, crowd_probs, elicitation, run_start_utc=run_start)
    print(flush=True)

    # Step 8: Update EXPERIMENTS.md
    print("Step 7: Update EXPERIMENTS.md...", flush=True)
    append_experiments(elicitation)
    print(flush=True)

    # Step 9: Secret leak scan
    print("Step 8: Secret leak scan...", flush=True)
    leak_ok = _leak_scan()
    print(flush=True)

    # Summary
    print("=== SUMMARY ===", flush=True)
    per_model = elicitation.get("records", [])
    for model in PANEL_MODELS:
        model_recs = [r for r in per_model if r.get("model") == model]
        n_ok  = sum(1 for r in model_recs if r.get("model_prob") is not None)
        n_err = sum(1 for r in model_recs if r.get("parse_error"))
        n_ref = sum(1 for r in model_recs if r.get("is_refusal"))
        print(f"  {model}: success={n_ok} parse_err={n_err} refusals={n_ref}",
              flush=True)

    print(f"\n  Total USD: ${elicitation['total_usd']:.4f}", flush=True)
    print(f"  CSV: {csv_path}", flush=True)
    print(f"  Manifest: {MVP_MANIFEST_PATH}", flush=True)
    print(f"  Leak scan: {'PASS' if leak_ok else 'FAIL'}", flush=True)

    if not leak_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
