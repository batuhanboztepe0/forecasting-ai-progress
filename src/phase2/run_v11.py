"""
run_v11.py — Phase-2 classifier v1.1 re-run (D-013 realignment).

Runs:
  1. LLM classifier v1.1 over all 3,728 candidates (separate Batch API job,
     version-scoped cache; v1.0 decisions untouched and auditable).
  2. Rebuild strata from v1.1 keeps only; no per-question version mixing.
  3. Crowd snapshots — reuse cached bet files where available; fetch new
     ones for v1.1-only recovered questions.
     D-013 inclusion rule: ≥1 bet at/before T; 0-trade questions are hard
     dropped.  No refill path.
  4. Rewrite data/interim/phase2_questions.json + data/phase2_manifest.json
     (v1.1 section appended; v1.0 provenance block retained).
  5. New audit samples: 40 KEPT + 40 DROPPED → classifier_audit_sample_v11.json.
  6. EXPERIMENTS.md: new run row + cost ledger row.

Usage:
  python3 run_v11.py

Hard rules: no resolution info in prompts, no commits, fail loud.
"""

import json
import os
import sys
import random
import hashlib
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from phase2_config import (  # noqa
    QUESTIONS_COMBINED_PATH,
    CLASSIFIER_VERSION_V11,
    CLASSIFIER_RESULTS_PATH_V11,
    CROWD_SNAPSHOT_CHECKPOINT_V11,
    PHASE2_QUESTIONS_PATH,
    AUDIT_SAMPLE_V11_PATH,
    PHASE2_MANIFEST_PATH,
    EXPERIMENTS_PATH,
    INTERIM_DIR,
    RAW_DIR,
    HAIKU_CLEAN_MIN_RESOLVED,
    JAN2026_CLEAN_MIN_RESOLVED,
    SNAPSHOT_LEAD_DAYS,
    DECISION_KEEP,
    DECISION_DROP,
    CLASSIFIER_MODEL,
    RANDOM_SEED,
    AUDIT_SAMPLE_N,
    AUDIT_SAMPLE_SEED,
)
from classify import run_classifier
from build_sets import build_elicitation_sets
from crowd_snapshots import fetch_all_snapshots


# ---------------------------------------------------------------------------
# Helpers (subset of run_step_a.py helpers — no duplication of logic)
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _load_questions() -> list:
    with open(QUESTIONS_COMBINED_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _build_core_schema(q: dict, snapshot: dict, content_hash: str, stratum: str) -> dict:
    """Build DATA.md core-schema record. Outcome stored for scoring only."""
    return {
        "qid":            q["qid"],
        "source":         q.get("source", "manifold"),
        "title":          (q.get("title") or "").strip(),
        "description":    (q.get("description") or "").strip()[:600],
        "created_at":     q.get("created_at", ""),
        "close_at":       q.get("close_at", ""),
        "resolved_at":    q.get("resolved_at", ""),
        "outcome":        q.get("outcome"),
        "crowd_prob_at_T": snapshot.get("crowd_prob_at_T"),
        "content_hash":   content_hash,
        "microstructure": {
            "snapshot_T_date":     snapshot.get("snapshot_T_date"),
            "trade_count_at_T":    snapshot.get("trade_count_at_T"),
            "unique_bettors_at_T": snapshot.get("unique_bettors_at_T"),
            "volume_mana_at_T":    snapshot.get("volume_mana_at_T"),
            "total_liquidity":     snapshot.get("total_liquidity"),
            "used_fallback_p":     snapshot.get("used_fallback_p", False),
        },
        "stratum":               stratum,
        "url":                   q.get("url", ""),
        "classifier_version":    CLASSIFIER_VERSION_V11,
        "snapshot_lead_days":    SNAPSHOT_LEAD_DAYS,
    }


def _build_audit_samples(
    decisions_v11: dict,
    all_questions: list,
) -> list:
    """
    Build seeded 40-KEPT + 40-DROPPED audit samples for v1.1 (seed=42).

    Returns combined list with 'audit_stratum' field ('kept'|'dropped').
    Writes to AUDIT_SAMPLE_V11_PATH.
    """
    qid_to_q = {q["qid"]: q for q in all_questions}

    kept_qids   = sorted(qid for qid, d in decisions_v11.items()
                         if d.get("decision") == DECISION_KEEP)
    dropped_qids = sorted(qid for qid, d in decisions_v11.items()
                          if d.get("decision") == DECISION_DROP)

    rng = random.Random(AUDIT_SAMPLE_SEED)
    kept_sample   = rng.sample(kept_qids,   min(AUDIT_SAMPLE_N, len(kept_qids)))
    dropped_sample = rng.sample(dropped_qids, min(AUDIT_SAMPLE_N, len(dropped_qids)))

    records = []
    for qid in sorted(kept_sample):
        q = qid_to_q.get(qid, {})
        d = decisions_v11[qid]
        records.append({
            "audit_stratum": "kept",
            "qid":           qid,
            "title":         (q.get("title") or "").strip(),
            "resolved_at":   q.get("resolved_at", ""),
            "decision":      d["decision"],
            "justification": d.get("justification", ""),
            "parse_error":   d.get("parse_error", False),
        })
    for qid in sorted(dropped_sample):
        q = qid_to_q.get(qid, {})
        d = decisions_v11[qid]
        records.append({
            "audit_stratum": "dropped",
            "qid":           qid,
            "title":         (q.get("title") or "").strip(),
            "resolved_at":   q.get("resolved_at", ""),
            "decision":      d["decision"],
            "justification": d.get("justification", ""),
            "parse_error":   d.get("parse_error", False),
        })

    os.makedirs(INTERIM_DIR, exist_ok=True)
    with open(AUDIT_SAMPLE_V11_PATH, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"  Audit sample written to {AUDIT_SAMPLE_V11_PATH} "
          f"({len(kept_sample)} kept + {len(dropped_sample)} dropped)", flush=True)
    return records


def _append_experiments_v11(
    classifier_results: dict,
    running_total: float,
) -> float:
    """Append v1.1 classifier row to EXPERIMENTS.md, return new total."""
    usd = classifier_results.get("cost_usd", 0.0)
    new_total = running_total + usd
    in_tok  = classifier_results.get("input_tokens", 0)
    out_tok = classifier_results.get("output_tokens", 0)
    batch   = classifier_results.get("used_batch_api", False)
    n_keep  = classifier_results.get("n_keep", 0)
    n_drop  = classifier_results.get("n_drop", 0)

    run_row = (
        f"| phase2-classifier-v11-2026-07-16 | 2026-07-16 "
        f"| 2 | llm-classifier | src/phase2/run_v11.py@HEAD | 42 | {CLASSIFIER_MODEL} "
        f"| 3728 | data/interim/phase2_questions.json "
        f"| D-013 realignment v1.1: keep={n_keep} drop={n_drop} |"
    )
    cost_row = (
        f"| phase2-classifier-v11-2026-07-16 | {CLASSIFIER_MODEL} "
        f"| {in_tok:,} | {out_tok:,} "
        f"| {'yes' if batch else 'no'} | no "
        f"| {usd:.4f} | {new_total:.4f} |"
    )

    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    reg_marker  = "| _example_ | 2026-01-01"
    cost_marker = "| _example_ | claude-sonnet"

    if reg_marker in content and "phase2-classifier-v11" not in content:
        content = content.replace(reg_marker, run_row + "\n" + reg_marker)
    if cost_marker in content and "phase2-classifier-v11-2026-07-16" not in content.split("## Cost ledger")[1]:
        content = content.replace(cost_marker, cost_row + "\n" + cost_marker)

    # Update running total
    old_line = f"**Running total: USD {running_total:.4f}**"
    new_line = f"**Running total: USD {new_total:.4f}**"
    content = content.replace(old_line, new_line)

    with open(EXPERIMENTS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)
    return new_total


def _read_running_total() -> float:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60, flush=True)
    print("Phase-2 classifier v1.1 re-run (D-013)", flush=True)
    print(f"  timestamp={datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 60, flush=True)

    # ------------------------------------------------------------------ #
    # 0. Load candidate pool
    # ------------------------------------------------------------------ #
    print("\n[0] Loading 3,728 candidates...", flush=True)
    all_questions = _load_questions()
    print(f"  Loaded {len(all_questions)}", flush=True)

    # ------------------------------------------------------------------ #
    # 1. Run / load v1.1 classifier
    # ------------------------------------------------------------------ #
    print("\n[1] Running classifier v1.1...", flush=True)

    classifier_results = None
    decisions_path_v11 = os.path.join(INTERIM_DIR, "phase2_classifier_decisions_v11.json")

    if os.path.exists(CLASSIFIER_RESULTS_PATH_V11):
        with open(CLASSIFIER_RESULTS_PATH_V11, encoding="utf-8") as fh:
            classifier_results = json.load(fh)
        with open(decisions_path_v11, encoding="utf-8") as fh:
            classifier_results["decisions"] = json.load(fh)
        print(f"  Loaded from cache: keep={classifier_results['n_keep']} "
              f"drop={classifier_results['n_drop']}", flush=True)
    else:
        classifier_results = run_classifier(
            all_questions, version=CLASSIFIER_VERSION_V11, verbose=True
        )
        decisions_v11 = classifier_results.pop("decisions")
        os.makedirs(INTERIM_DIR, exist_ok=True)
        with open(decisions_path_v11, "w", encoding="utf-8") as fh:
            json.dump(decisions_v11, fh, ensure_ascii=False, indent=2)
        with open(CLASSIFIER_RESULTS_PATH_V11, "w", encoding="utf-8") as fh:
            json.dump(classifier_results, fh, ensure_ascii=False, indent=2)
        classifier_results["decisions"] = decisions_v11
        print(f"  Saved v1.1 results", flush=True)

    decisions_v11 = classifier_results["decisions"]

    # Delta vs v1.0
    decisions_path_v10 = os.path.join(INTERIM_DIR, "phase2_classifier_decisions.json")
    v10_keep = set()
    if os.path.exists(decisions_path_v10):
        with open(decisions_path_v10, encoding="utf-8") as fh:
            dv10 = json.load(fh)
        v10_keep = {qid for qid, d in dv10.items() if d.get("decision") == DECISION_KEEP}
    v11_keep = {qid for qid, d in decisions_v11.items() if d.get("decision") == DECISION_KEEP}

    recovered    = v11_keep - v10_keep   # v1.0-drop → v1.1-keep
    newly_dropped = v10_keep - v11_keep  # v1.0-keep → v1.1-drop

    print(f"\n  v1.1 keep={len(v11_keep)} | v1.0 keep={len(v10_keep)}")
    print(f"  Recovered (v1.0-drop → v1.1-keep): {len(recovered)}")
    print(f"  Newly dropped (v1.0-keep → v1.1-drop): {len(newly_dropped)}", flush=True)

    # ------------------------------------------------------------------ #
    # 2. Build audit samples (40 KEPT + 40 DROPPED)
    # ------------------------------------------------------------------ #
    print("\n[2] Building v1.1 audit samples...", flush=True)
    audit_records = _build_audit_samples(decisions_v11, all_questions)

    # ------------------------------------------------------------------ #
    # 3. Build elicitation strata from v1.1 keeps
    # ------------------------------------------------------------------ #
    print("\n[3] Building v1.1 elicitation strata...", flush=True)
    strata = build_elicitation_sets(all_questions, decisions_v11, verbose=True)

    haiku_clean      = strata["haiku_clean"]
    pre_cutoff_probe = strata["pre_cutoff_probe"]
    jan2026_subset   = strata["jan2026_clean_subset"]

    all_selected: list = []
    seen: set = set()
    for q in haiku_clean + pre_cutoff_probe:
        if q["qid"] not in seen:
            seen.add(q["qid"])
            all_selected.append(q)

    print(f"\n  Total selected for snapshots: {len(all_selected)}", flush=True)

    # ------------------------------------------------------------------ #
    # 4. Crowd snapshots — D-013 hard-drop rule, no refill
    # ------------------------------------------------------------------ #
    print("\n[4] Fetching crowd snapshots (v1.1, D-013 hard-drop)...", flush=True)
    snapshots, drop_qids, content_hashes = fetch_all_snapshots(
        all_selected,
        checkpoint_path=CROWD_SNAPSHOT_CHECKPOINT_V11,
        verbose=True,
    )

    print(
        f"\n  Snapshots: {len(snapshots)} valid | {len(drop_qids)} dropped "
        f"(0-bets-at-T, hard drop per D-013)",
        flush=True,
    )

    # ------------------------------------------------------------------ #
    # 5. Assemble final records
    # ------------------------------------------------------------------ #
    print("\n[5] Assembling core-schema records...", flush=True)
    records = []
    for q in haiku_clean:
        snap = snapshots.get(q["qid"])
        if snap is None:
            continue
        records.append(_build_core_schema(
            q, snap, content_hashes.get(q["qid"], ""), "haiku_clean"
        ))
    for q in pre_cutoff_probe:
        snap = snapshots.get(q["qid"])
        if snap is None:
            continue
        records.append(_build_core_schema(
            q, snap, content_hashes.get(q["qid"], ""), "pre_cutoff_probe"
        ))
    records.sort(key=lambda r: r.get("resolved_at", ""))

    n_haiku_final = sum(1 for r in records if r["stratum"] == "haiku_clean")
    n_probe_final = sum(1 for r in records if r["stratum"] == "pre_cutoff_probe")
    n_jan26_final = sum(
        1 for r in records
        if r["stratum"] == "haiku_clean"
        and r.get("resolved_at", "") >= JAN2026_CLEAN_MIN_RESOLVED
    )

    print(
        f"\n  Final v1.1 dataset:"
        f"\n    haiku-clean:      {n_haiku_final}"
        f"\n    pre-cutoff probe: {n_probe_final}"
        f"\n    jan-2026-clean:   {n_jan26_final}"
        f"\n    total:            {len(records)}",
        flush=True,
    )

    # Write phase2_questions.json (rewrites v1.0 version)
    os.makedirs(INTERIM_DIR, exist_ok=True)
    with open(PHASE2_QUESTIONS_PATH, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"\n  Saved {len(records)} records to {PHASE2_QUESTIONS_PATH}", flush=True)

    # ------------------------------------------------------------------ #
    # 6. Update manifest (append v1.1 section; keep v1.0 block)
    # ------------------------------------------------------------------ #
    print("\n[6] Updating phase2_manifest.json...", flush=True)
    manifest: dict = {}
    if os.path.exists(PHASE2_MANIFEST_PATH):
        with open(PHASE2_MANIFEST_PATH, encoding="utf-8") as fh:
            manifest = json.load(fh)

    phase2_q_hash = _sha256(json.dumps(records, ensure_ascii=False))

    manifest["classifier_v11"] = {
        "version":         CLASSIFIER_VERSION_V11,
        "model":           CLASSIFIER_MODEL,
        "n_candidates":    classifier_results.get("n_candidates", len(all_questions)),
        "n_keep":          classifier_results.get("n_keep", 0),
        "n_drop":          classifier_results.get("n_drop", 0),
        "n_parse_error":   classifier_results.get("n_parse_error", 0),
        "cost_usd":        classifier_results.get("cost_usd", 0.0),
        "used_batch_api":  classifier_results.get("used_batch_api", False),
        "system_hash":     classifier_results.get("classifier_system_hash", ""),
        "delta_vs_v10": {
            "v10_keep":     len(v10_keep),
            "v11_keep":     len(v11_keep),
            "recovered":    len(recovered),
            "newly_dropped": len(newly_dropped),
        },
    }
    manifest["strata_v11"] = {
        "haiku_clean":       {"min_resolved": HAIKU_CLEAN_MIN_RESOLVED, "n": n_haiku_final},
        "pre_cutoff_probe":  {"max_resolved": HAIKU_CLEAN_MIN_RESOLVED, "n": n_probe_final},
        "jan2026_clean_subset": {"min_resolved": JAN2026_CLEAN_MIN_RESOLVED, "n": n_jan26_final},
    }
    manifest["snapshots_v11"] = {
        "lead_days":              SNAPSHOT_LEAD_DAYS,
        "d013_rule":              ">=1 bet at/before T required; 0-trade hard drop",
        "n_valid":                len(snapshots),
        "n_dropped_no_activity":  len(drop_qids),
        "dropped_qids":           drop_qids,
    }
    manifest["artifacts"]["phase2_questions_json"] = {
        "path":      "data/interim/phase2_questions.json",
        "n_records": len(records),
        "sha256":    phase2_q_hash,
        "classifier_version": CLASSIFIER_VERSION_V11,
    }
    manifest["artifacts"]["classifier_audit_sample_v11_json"] = {
        "path":      "data/interim/classifier_audit_sample_v11.json",
        "n_kept":    len([r for r in audit_records if r["audit_stratum"] == "kept"]),
        "n_dropped": len([r for r in audit_records if r["audit_stratum"] == "dropped"]),
    }
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()

    with open(PHASE2_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"  Manifest updated: {PHASE2_MANIFEST_PATH}", flush=True)

    # ------------------------------------------------------------------ #
    # 7. EXPERIMENTS.md
    # ------------------------------------------------------------------ #
    print("\n[7] Updating EXPERIMENTS.md...", flush=True)
    running_total = _read_running_total()
    new_total = _append_experiments_v11(classifier_results, running_total)
    print(f"  Running total: ${running_total:.4f} → ${new_total:.4f}", flush=True)

    # ------------------------------------------------------------------ #
    # 8. Summary + 10 recovered titles inline
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60, flush=True)
    print("Phase-2 v1.1 COMPLETE", flush=True)
    print(f"  v1.0 keep: {len(v10_keep)} | v1.1 keep: {len(v11_keep)}", flush=True)
    print(f"  Recovered (v1.0-drop→v1.1-keep): {len(recovered)}", flush=True)
    print(f"  Newly dropped (v1.0-keep→v1.1-drop): {len(newly_dropped)}", flush=True)
    print(f"  haiku-clean:      {n_haiku_final}", flush=True)
    print(f"  pre-cutoff probe: {n_probe_final}", flush=True)
    print(f"  jan-2026-clean:   {n_jan26_final}", flush=True)
    print(f"  dropped (no bets at T): {len(drop_qids)}", flush=True)
    print(f"  total records:    {len(records)}", flush=True)
    print(f"  Classifier cost:  ${classifier_results.get('cost_usd', 0):.4f}", flush=True)
    print(f"  EXPERIMENTS total: ${new_total:.4f}", flush=True)

    # 10 recovered titles for inline reporting
    if recovered:
        qid_map = {q["qid"]: q for q in all_questions}
        print("\n  10 titles from RECOVERED set (v1.0-drop → v1.1-keep):", flush=True)
        for qid in sorted(list(recovered))[:10]:
            title = (qid_map.get(qid, {}).get("title") or "").strip()
            justification = decisions_v11.get(qid, {}).get("justification", "")[:80]
            print(f"    - {title[:70]}", flush=True)
            print(f"      [{justification}]", flush=True)

    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
