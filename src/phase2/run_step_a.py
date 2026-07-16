"""
run_step_a.py — Phase-2 Step A orchestrator.

Runs the full pipeline:
  1. LLM-assisted classifier (haiku-4-5, Message Batches API)
  2. Build elicitation strata (haiku-clean + pre-cutoff probe)
  3. Crowd snapshots (T = 30d before resolved_at) + microstructure
  4. Assemble DATA.md core-schema output (phase2_questions.json)
  5. Write phase2_manifest.json + update docs/EXPERIMENTS.md

Usage:
  python3 run_step_a.py [--dry-run]

  --dry-run: Skip API calls; use cached results only. Useful for
             validating output schema after a live run.

Hard rules enforced:
  - No resolution information in classifier prompts.
  - Cost stops at $5 for classifier, $25 for any single run.
  - All raw payloads stored under data/raw/ (git-ignored).
  - No secrets in tracked files.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from phase2_config import (  # noqa: E402
    QUESTIONS_COMBINED_PATH,
    CLASSIFIER_RESULTS_PATH,
    PHASE2_QUESTIONS_PATH,
    PHASE2_MANIFEST_PATH,
    AUDIT_SAMPLE_PATH,
    EXPERIMENTS_PATH,
    INTERIM_DIR,
    RAW_DIR,
    CLASSIFIER_VERSION,
    CLASSIFIER_MODEL,
    HAIKU_CLEAN_MIN_RESOLVED,
    JAN2026_CLEAN_MIN_RESOLVED,
    SNAPSHOT_LEAD_DAYS,
    DECISION_KEEP,
)
from classify import run_classifier
from build_sets import build_elicitation_sets, build_audit_sample
from crowd_snapshots import fetch_all_snapshots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _load_questions() -> list:
    """Load all questions from recon output."""
    with open(QUESTIONS_COMBINED_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _build_core_schema(
    q: dict,
    snapshot: dict,
    content_hash: str,
    stratum: str,
) -> dict:
    """
    Build a DATA.md core-schema record for a single question.

    Stratum tag (not in DATA.md schema but useful for downstream):
      'haiku_clean' | 'pre_cutoff_probe'

    Never includes outcome/resolution in the classifier/elicitation-facing
    text fields; outcome is stored in 'outcome' for scoring only.
    """
    return {
        # --- Core schema fields ---
        "qid":              q["qid"],
        "source":           q.get("source", "manifold"),
        "title":            (q.get("title") or "").strip(),
        "description":      (q.get("description") or "").strip()[:600],
        "created_at":       q.get("created_at", ""),
        "close_at":         q.get("close_at", ""),
        "resolved_at":      q.get("resolved_at", ""),
        "outcome":          q.get("outcome"),  # 0 or 1 (scoring only)
        "crowd_prob_at_T":  snapshot.get("crowd_prob_at_T"),
        "content_hash":     content_hash,
        # --- Microstructure (Manifold) ---
        "microstructure": {
            "snapshot_T_date":    snapshot.get("snapshot_T_date"),
            "trade_count_at_T":   snapshot.get("trade_count_at_T"),
            "unique_bettors_at_T": snapshot.get("unique_bettors_at_T"),
            "volume_mana_at_T":   snapshot.get("volume_mana_at_T"),
            "total_liquidity":    snapshot.get("total_liquidity"),
            "used_fallback_p":    snapshot.get("used_fallback_p", False),
        },
        # --- Provenance ---
        "stratum":               stratum,
        "url":                   q.get("url", ""),
        "classifier_version":    CLASSIFIER_VERSION,
        "snapshot_lead_days":    SNAPSHOT_LEAD_DAYS,
    }


def _append_experiments_row(
    run_id: str,
    phase: int,
    run_type: str,
    model: str,
    n_questions: int,
    input_tokens: int,
    output_tokens: int,
    batch: bool,
    usd: float,
    running_total: float,
    note: str = "",
) -> float:
    """
    Append a row to docs/EXPERIMENTS.md cost ledger.

    Args:
        running_total: Running total BEFORE this run.

    Returns:
        New running total (running_total + usd).
    """
    new_total = running_total + usd
    batch_str = "yes" if batch else "no"

    # --- Run registry row ---
    run_row = (
        f"| {run_id} | {datetime.now(timezone.utc).strftime('%Y-%m-%d')} "
        f"| {phase} | {run_type} "
        f"| src/phase2/run_step_a.py@HEAD | 42 | {model} | {n_questions} "
        f"| data/interim/phase2_questions.json "
        f"| {note} |"
    )

    # --- Cost ledger row ---
    cost_row = (
        f"| {run_id} | {model} | {input_tokens:,} | {output_tokens:,} "
        f"| {batch_str} | {'yes' if batch else 'no'} "
        f"| {usd:.4f} | {new_total:.4f} |"
    )

    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    # Append run registry row before the _example_ row
    reg_marker = "| _example_ | 2026-01-01"
    if reg_marker in content and run_row.split("|")[1].strip() not in content:
        content = content.replace(reg_marker, run_row + "\n" + reg_marker)

    # Append cost ledger row before the _example_ cost row
    cost_marker = "| _example_ | claude-sonnet"
    if cost_marker in content and run_id + " |" not in content.split("## Cost ledger")[1]:
        content = content.replace(cost_marker, cost_row + "\n" + cost_marker)

    # Update running total line
    old_total_line = f"**Running total: USD {running_total:.4f}**"
    new_total_line = f"**Running total: USD {new_total:.4f}**"
    content = content.replace(old_total_line, new_total_line)

    with open(EXPERIMENTS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)

    return new_total


def _read_running_total() -> float:
    """Read current running total from EXPERIMENTS.md."""
    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        for line in fh:
            if "Running total: USD" in line:
                parts = line.strip().split("USD")
                if len(parts) >= 2:
                    try:
                        return float(parts[1].strip().split()[0].rstrip("*"))
                    except ValueError:
                        pass
    return 0.0


def _write_manifest(
    manifest: dict,
    path: str,
) -> None:
    """Write committed manifest JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)


def _write_phase2_questions(records: list, path: str) -> None:
    """Write final phase2_questions.json."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(dry_run: bool = False) -> None:
    """
    Orchestrate Phase-2 Step A.

    Args:
        dry_run: If True, skip all API calls; use caches only.
    """
    print("=" * 60, flush=True)
    print("Phase-2 Step A: classifier + elicitation sets + snapshots", flush=True)
    print(f"  dry_run={dry_run}", flush=True)
    print(f"  timestamp={datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 60, flush=True)

    # ------------------------------------------------------------------ #
    # 0. Load candidate pool
    # ------------------------------------------------------------------ #
    print("\n[0] Loading candidate pool...", flush=True)
    all_questions = _load_questions()
    print(f"  Loaded {len(all_questions)} questions from {QUESTIONS_COMBINED_PATH}", flush=True)

    # ------------------------------------------------------------------ #
    # 1. LLM-assisted classifier
    # ------------------------------------------------------------------ #
    print("\n[1] Running LLM classifier...", flush=True)

    # Check for cached full-run results
    classifier_results = None
    if os.path.exists(CLASSIFIER_RESULTS_PATH):
        with open(CLASSIFIER_RESULTS_PATH, encoding="utf-8") as fh:
            classifier_results = json.load(fh)
        print(f"  Loaded classifier results from cache: "
              f"keep={classifier_results['n_keep']} "
              f"drop={classifier_results['n_drop']} "
              f"parse_err={classifier_results['n_parse_error']}",
              flush=True)
    else:
        if dry_run:
            print("  [DRY RUN] No classifier cache found; skipping API call.", flush=True)
            sys.exit(1)

        classifier_results = run_classifier(all_questions, verbose=True)

        # Save full results
        os.makedirs(INTERIM_DIR, exist_ok=True)
        results_to_save = dict(classifier_results)
        results_to_save.pop("decisions", None)  # save decisions separately
        decisions_path = os.path.join(INTERIM_DIR, "phase2_classifier_decisions.json")
        with open(decisions_path, "w", encoding="utf-8") as fh:
            json.dump(classifier_results["decisions"], fh, ensure_ascii=False, indent=2)
        with open(CLASSIFIER_RESULTS_PATH, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in classifier_results.items() if k != "decisions"},
                      fh, ensure_ascii=False, indent=2)
        print(f"  Classifier results saved to {CLASSIFIER_RESULTS_PATH}", flush=True)

    # Re-load decisions if needed
    if "decisions" not in classifier_results:
        decisions_path = os.path.join(INTERIM_DIR, "phase2_classifier_decisions.json")
        with open(decisions_path, encoding="utf-8") as fh:
            classifier_results["decisions"] = json.load(fh)

    decisions = classifier_results["decisions"]

    # ------------------------------------------------------------------ #
    # 2. Build audit sample (committed artifact)
    # ------------------------------------------------------------------ #
    print("\n[2] Building audit sample...", flush=True)
    audit_sample = build_audit_sample(decisions, all_questions, verbose=True)

    # ------------------------------------------------------------------ #
    # 3. Build elicitation strata
    # ------------------------------------------------------------------ #
    print("\n[3] Building elicitation strata...", flush=True)
    strata = build_elicitation_sets(all_questions, decisions, verbose=True)

    haiku_clean      = strata["haiku_clean"]
    pre_cutoff_probe = strata["pre_cutoff_probe"]
    jan2026_subset   = strata["jan2026_clean_subset"]

    print(
        f"  haiku-clean: {len(haiku_clean)} | "
        f"probe: {len(pre_cutoff_probe)} | "
        f"jan2026: {len(jan2026_subset)}",
        flush=True,
    )

    # All questions to snapshot
    all_selected = haiku_clean + pre_cutoff_probe
    # De-duplicate (should not be needed; guard)
    seen: set = set()
    all_selected_dedup = []
    for q in all_selected:
        if q["qid"] not in seen:
            seen.add(q["qid"])
            all_selected_dedup.append(q)

    print(f"\n  Total selected for snapshots: {len(all_selected_dedup)}", flush=True)

    # ------------------------------------------------------------------ #
    # 4. Crowd snapshots + microstructure
    # ------------------------------------------------------------------ #
    print("\n[4] Fetching crowd snapshots...", flush=True)
    if dry_run:
        print("  [DRY RUN] Skipping API calls; checking checkpoint...", flush=True)

    snapshots, drop_qids, content_hashes = fetch_all_snapshots(
        all_selected_dedup, verbose=True
    )

    print(
        f"\n  Snapshots complete: {len(snapshots)} valid | "
        f"{len(drop_qids)} dropped for no activity at T",
        flush=True,
    )

    # ------------------------------------------------------------------ #
    # 5. Refill from same stratum if drop_qids > 0
    # ------------------------------------------------------------------ #
    # Build a pool of reserve questions from each stratum (LLM-kept, snapshot-feasible,
    # not already selected) for potential refill.
    if drop_qids:
        print(f"\n  Attempting to refill {len(drop_qids)} dropped questions...", flush=True)
        selected_qids = {q["qid"] for q in all_selected_dedup}
        dropped_set = set(drop_qids)

        # Identify stratum for each dropped qid
        haiku_qids  = {q["qid"] for q in haiku_clean}
        probe_qids  = {q["qid"] for q in pre_cutoff_probe}
        import random
        from datetime import timedelta as _td
        from phase2_config import HAIKU_CLEAN_MIN_RESOLVED as _HC_MIN
        def _parse_dt_local(s):
            from datetime import datetime as _dt, timezone as _tz
            if not s:
                return None
            try:
                s = s.replace("Z", "+00:00")
                d = _dt.fromisoformat(s)
                return d.replace(tzinfo=_tz.utc) if d.tzinfo is None else d
            except ValueError:
                return None

        hc_min_dt = _parse_dt_local(_HC_MIN)
        rng_refill = random.Random(42 + 1)  # different seed for refill

        haiku_drops  = [qid for qid in drop_qids if qid in haiku_qids]
        probe_drops  = [qid for qid in drop_qids if qid in probe_qids]

        # Reserve pool: kept questions not yet selected
        reserve = [
            q for q in all_questions
            if q["qid"] not in selected_qids
            and decisions.get(q["qid"], {}).get("decision") == DECISION_KEEP
            and q.get("outcome") in (0, 1)
        ]

        # Haiku-clean reserves
        haiku_reserve = sorted(
            [q for q in reserve
             if (_parse_dt_local(q.get("resolved_at")) or datetime(1970, 1, 1, tzinfo=timezone.utc))
             >= hc_min_dt],
            key=lambda q: q["qid"]
        )
        probe_reserve = sorted(
            [q for q in reserve
             if (_parse_dt_local(q.get("resolved_at")) or datetime(1970, 1, 1, tzinfo=timezone.utc))
             < hc_min_dt],
            key=lambda q: q["qid"]
        )

        refill_qs = []
        for _drops, _pool in [(haiku_drops, haiku_reserve), (probe_drops, probe_reserve)]:
            n_refill = min(len(_drops), len(_pool))
            if n_refill > 0:
                refills = rng_refill.sample(_pool, n_refill)
                refill_qs.extend(refills)
                print(f"    Refilling {n_refill} questions from reserve.", flush=True)

        if refill_qs:
            refill_snaps, refill_drops, refill_hashes = fetch_all_snapshots(
                refill_qs, verbose=True
            )
            snapshots.update(refill_snaps)
            content_hashes.update(refill_hashes)
            # Remove from drop list if refill succeeded
            for q in refill_qs:
                if q["qid"] in snapshots:
                    if q["qid"] in dropped_set:
                        dropped_set.discard(q["qid"])
            drop_qids = list(dropped_set)
            print(f"    After refill: {len(drop_qids)} still dropped.", flush=True)

    # ------------------------------------------------------------------ #
    # 6. Assemble final DATA.md core-schema records
    # ------------------------------------------------------------------ #
    print("\n[5] Assembling core-schema records...", flush=True)
    records = []
    for q in haiku_clean:
        qid = q["qid"]
        snap = snapshots.get(qid)
        if snap is None:
            continue  # dropped; logged above
        rec = _build_core_schema(q, snap, content_hashes.get(qid, ""), "haiku_clean")
        records.append(rec)

    for q in pre_cutoff_probe:
        qid = q["qid"]
        snap = snapshots.get(qid)
        if snap is None:
            continue
        rec = _build_core_schema(q, snap, content_hashes.get(qid, ""), "pre_cutoff_probe")
        records.append(rec)

    # Sort by resolved_at for determinism
    records.sort(key=lambda r: r.get("resolved_at", ""))

    n_haiku_final = sum(1 for r in records if r["stratum"] == "haiku_clean")
    n_probe_final = sum(1 for r in records if r["stratum"] == "pre_cutoff_probe")
    n_jan26_final = sum(
        1 for r in records
        if r["stratum"] == "haiku_clean"
        and r.get("resolved_at", "") >= JAN2026_CLEAN_MIN_RESOLVED
    )

    print(
        f"\n  Final dataset:"
        f"\n    haiku-clean:        {n_haiku_final}"
        f"\n    pre-cutoff probe:   {n_probe_final}"
        f"\n    jan-2026-clean:     {n_jan26_final}"
        f"\n    total:              {len(records)}",
        flush=True,
    )

    _write_phase2_questions(records, PHASE2_QUESTIONS_PATH)
    print(f"\n  Saved {len(records)} records to {PHASE2_QUESTIONS_PATH}", flush=True)

    # ------------------------------------------------------------------ #
    # 7. Write committed manifest
    # ------------------------------------------------------------------ #
    print("\n[6] Writing provenance manifest...", flush=True)

    # SHA-256 of phase2_questions.json
    phase2_q_hash = _sha256_text(json.dumps(records, ensure_ascii=False))

    # Compute per-question content hashes (already in content_hashes)
    raw_bet_file_hashes = {}
    from phase2_config import RAW_DIR as _RAW_DIR, RECON_RAW_DIR as _RECON_RAW_DIR
    for q in all_selected_dedup:
        mid = q["qid"].replace("manifold_", "", 1)
        for base in [_RAW_DIR, _RECON_RAW_DIR]:
            path = os.path.join(base, f"bets_{mid}.json")
            if os.path.exists(path):
                try:
                    h = _sha256_text(open(path, encoding="utf-8").read())
                    raw_bet_file_hashes[mid] = h
                except OSError:
                    pass
                break

    manifest = {
        "manifest_version": "2.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "2-step-A",
        "random_seed": 42,
        "classifier": {
            "version":         CLASSIFIER_VERSION,
            "model":           CLASSIFIER_MODEL,
            "n_candidates":    classifier_results.get("n_candidates", len(all_questions)),
            "n_keep":          classifier_results.get("n_keep", 0),
            "n_drop":          classifier_results.get("n_drop", 0),
            "n_parse_error":   classifier_results.get("n_parse_error", 0),
            "cost_usd":        classifier_results.get("cost_usd", 0.0),
            "used_batch_api":  classifier_results.get("used_batch_api", False),
            "system_hash":     classifier_results.get("classifier_system_hash", ""),
        },
        "strata": {
            "haiku_clean": {
                "min_resolved": HAIKU_CLEAN_MIN_RESOLVED,
                "n": n_haiku_final,
            },
            "pre_cutoff_probe": {
                "max_resolved": HAIKU_CLEAN_MIN_RESOLVED,
                "n": n_probe_final,
            },
            "jan2026_clean_subset": {
                "min_resolved": JAN2026_CLEAN_MIN_RESOLVED,
                "n": n_jan26_final,
            },
        },
        "snapshots": {
            "lead_days": SNAPSHOT_LEAD_DAYS,
            "n_valid": len(snapshots),
            "n_dropped_no_activity": len(drop_qids),
            "dropped_qids": drop_qids,
        },
        "artifacts": {
            "phase2_questions_json": {
                "path": "data/interim/phase2_questions.json",
                "n_records": len(records),
                "sha256": phase2_q_hash,
            },
            "classifier_audit_sample_json": {
                "path": "data/interim/classifier_audit_sample.json",
                "n_records": len(audit_sample),
            },
            "classifier_decisions_json": {
                "path": "data/interim/phase2_classifier_decisions.json",
            },
        },
        "raw_bet_file_hashes_sha256": raw_bet_file_hashes,
    }

    _write_manifest(manifest, PHASE2_MANIFEST_PATH)
    print(f"  Manifest written to {PHASE2_MANIFEST_PATH}", flush=True)

    # ------------------------------------------------------------------ #
    # 8. Update EXPERIMENTS.md
    # ------------------------------------------------------------------ #
    print("\n[7] Updating EXPERIMENTS.md...", flush=True)
    running_total = _read_running_total()
    print(f"  Running total before this run: ${running_total:.4f}", flush=True)

    cls_cost = classifier_results.get("cost_usd", 0.0)
    new_total = _append_experiments_row(
        run_id="phase2-classifier-2026-07-16",
        phase=2,
        run_type="llm-classifier",
        model=CLASSIFIER_MODEL,
        n_questions=classifier_results.get("n_candidates", 0),
        input_tokens=classifier_results.get("input_tokens", 0),
        output_tokens=classifier_results.get("output_tokens", 0),
        batch=classifier_results.get("used_batch_api", False),
        usd=cls_cost,
        running_total=running_total,
        note=(
            f"Phase-2 AI-progress classifier v1.0: "
            f"keep={classifier_results.get('n_keep', 0)} "
            f"drop={classifier_results.get('n_drop', 0)}"
        ),
    )
    print(f"  New running total: ${new_total:.4f}", flush=True)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60, flush=True)
    print("Phase-2 Step A COMPLETE", flush=True)
    print(f"  Candidate pool:   {classifier_results.get('n_candidates', 0)}", flush=True)
    print(f"  Classifier kept:  {classifier_results.get('n_keep', 0)}", flush=True)
    print(f"  Classifier drop:  {classifier_results.get('n_drop', 0)}", flush=True)
    print(f"  Parse errors:     {classifier_results.get('n_parse_error', 0)}", flush=True)
    print(f"  Classifier cost:  ${cls_cost:.4f} (batch={classifier_results.get('used_batch_api')})", flush=True)
    print(f"  haiku-clean:      {n_haiku_final}", flush=True)
    print(f"  pre-cutoff probe: {n_probe_final}", flush=True)
    print(f"  jan-2026-clean:   {n_jan26_final}", flush=True)
    print(f"  dropped (no snap):{len(drop_qids)}", flush=True)
    print(f"  Total records:    {len(records)}", flush=True)
    print(f"  EXPERIMENTS total: ${new_total:.4f}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase-2 Step A pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Use caches only; skip live API calls")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
