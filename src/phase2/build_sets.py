"""
build_sets.py — Build the final Phase-2 elicitation strata from LLM-kept questions.

Strata (D-011 §4):
  (a) haiku-clean — resolved_at >= 2025-08-30 and snapshot-feasible; take all kept.
  (b) pre-cutoff memorization probe — resolved_at < 2025-08-30; seeded sample of ~800.

Snapshot-feasible definition (Phase-2 version):
  created_at < T  AND  unique_bettors > 0
  where T = resolved_at - 30 days.

Binary resolved YES/NO only (outcome 0 or 1); ambiguous/annulled/cancelled already
dropped in recon (only YES/NO in questions_combined.json — log counts anyway).

Also computes the Jan-2026-clean subset (resolved_at >= 2026-03-02).
"""

import json
import os
import random
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from phase2_config import (  # noqa: E402
    RANDOM_SEED,
    SNAPSHOT_LEAD_DAYS,
    HAIKU_CLEAN_MIN_RESOLVED,
    JAN2026_CLEAN_MIN_RESOLVED,
    HAIKU_CLEAN_TARGET,
    PRE_CUTOFF_PROBE_TARGET,
    DECISION_KEEP,
    AUDIT_SAMPLE_N,
    AUDIT_SAMPLE_SEED,
    AUDIT_SAMPLE_PATH,
    INTERIM_DIR,
)


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO datetime string to UTC-aware datetime; return None on failure."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        return None


def _is_snapshot_feasible(q: dict) -> tuple:
    """
    Check snapshot feasibility: created_at < T and unique_bettors > 0.

    Args:
        q: Question dict.

    Returns:
        (feasible: bool, resolved_dt: Optional[datetime])
    """
    resolved_dt = _parse_dt(q.get("resolved_at", ""))
    if resolved_dt is None:
        return False, None
    T = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
    created_dt = _parse_dt(q.get("created_at", ""))
    ub = q.get("unique_bettors", 0) or 0
    if created_dt is not None and created_dt < T and ub > 0:
        return True, resolved_dt
    return False, resolved_dt


def build_elicitation_sets(
    all_questions: list,
    decisions: dict,
    verbose: bool = True,
) -> dict:
    """
    Build haiku-clean and pre-cutoff probe strata from LLM-kept questions.

    Args:
        all_questions: Full list of question dicts from questions_combined.json.
        decisions: {qid: {"decision": str, ...}} from run_classifier.
        verbose: Print progress summary.

    Returns:
        Dict with keys:
          'haiku_clean': list of question dicts (stratum a)
          'pre_cutoff_probe': list of question dicts (stratum b)
          'jan2026_clean_subset': list (haiku_clean subset for Jan-2026 models)
          'n_ambiguous_dropped': int  (outcome not 0 or 1 — logged, not used)
          'n_no_snapshot_dropped': int
          'n_total_kept_questions': int  (LLM RELEVANT)
    """
    haiku_min_dt = _parse_dt(HAIKU_CLEAN_MIN_RESOLVED)
    jan26_min_dt = _parse_dt(JAN2026_CLEAN_MIN_RESOLVED)

    n_ambiguous_dropped = 0
    n_no_snapshot = 0

    haiku_clean_pool = []
    pre_cutoff_pool  = []

    for q in all_questions:
        qid = q["qid"]

        # Only LLM-kept questions
        if decisions.get(qid, {}).get("decision") != DECISION_KEEP:
            continue

        # Binary resolved only (should always be 0 or 1 per recon, but log)
        outcome = q.get("outcome")
        if outcome not in (0, 1):
            n_ambiguous_dropped += 1
            continue

        feasible, resolved_dt = _is_snapshot_feasible(q)
        if not feasible or resolved_dt is None:
            n_no_snapshot += 1
            continue

        if resolved_dt >= haiku_min_dt:
            haiku_clean_pool.append((resolved_dt, q))
        else:
            pre_cutoff_pool.append((resolved_dt, q))

    # Stratum (a): haiku-clean — take all (sorted by resolved_at for determinism)
    haiku_clean = [q for _, q in sorted(haiku_clean_pool, key=lambda x: x[0])]

    # Stratum (b): pre-cutoff probe — seeded sample of min(target, available)
    rng = random.Random(RANDOM_SEED)
    pre_pool_sorted = sorted(pre_cutoff_pool, key=lambda x: x[1]["qid"])
    n_probe = min(PRE_CUTOFF_PROBE_TARGET, len(pre_pool_sorted))
    pre_cutoff_probe = [
        q for _, q in rng.sample(pre_pool_sorted, n_probe)
    ]
    # Sort by resolved_at for output consistency
    pre_cutoff_probe.sort(key=lambda q: q.get("resolved_at", ""))

    # Jan-2026-clean subset (resolved_at >= 2026-03-02)
    jan2026_subset = [
        q for q in haiku_clean
        if (_parse_dt(q.get("resolved_at", "")) or datetime.min.replace(tzinfo=timezone.utc))
        >= jan26_min_dt
    ]

    n_total_kept = len(haiku_clean) + len(pre_cutoff_probe)

    if verbose:
        print(
            f"\n  Strata built:"
            f"\n    haiku-clean (resolved >= {HAIKU_CLEAN_MIN_RESOLVED}): "
            f"{len(haiku_clean)} questions"
            f"\n    pre-cutoff probe (resolved < {HAIKU_CLEAN_MIN_RESOLVED}): "
            f"{len(pre_cutoff_probe)} questions (sampled from {len(pre_pool_sorted)})"
            f"\n    jan-2026-clean subset (resolved >= {JAN2026_CLEAN_MIN_RESOLVED}): "
            f"{len(jan2026_subset)} questions"
            f"\n    ambiguous/non-binary dropped: {n_ambiguous_dropped}"
            f"\n    no-snapshot dropped: {n_no_snapshot}",
            flush=True,
        )

    return {
        "haiku_clean":          haiku_clean,
        "pre_cutoff_probe":     pre_cutoff_probe,
        "jan2026_clean_subset": jan2026_subset,
        "n_ambiguous_dropped":  n_ambiguous_dropped,
        "n_no_snapshot_dropped": n_no_snapshot,
        "n_total_kept_questions": n_total_kept,
    }


def build_audit_sample(
    decisions: dict,
    all_questions: list,
    verbose: bool = True,
) -> list:
    """
    Draw a seeded 40-question audit sample from KEPT questions.

    Args:
        decisions: {qid: decision_record} from classifier.
        all_questions: Full question list for title lookup.
        verbose: Print summary.

    Returns:
        List of 40 audit record dicts: {qid, title, decision, justification}.
    """
    # Build qid -> title map
    qid_to_q = {q["qid"]: q for q in all_questions}

    kept_qids = sorted([
        qid for qid, rec in decisions.items()
        if rec.get("decision") == DECISION_KEEP
    ])

    rng = random.Random(AUDIT_SAMPLE_SEED)
    n_sample = min(AUDIT_SAMPLE_N, len(kept_qids))
    sampled_qids = rng.sample(kept_qids, n_sample)

    audit_records = []
    for qid in sorted(sampled_qids):  # sort for determinism in output
        rec = decisions[qid]
        q = qid_to_q.get(qid, {})
        audit_records.append({
            "qid":           qid,
            "title":         (q.get("title") or "").strip(),
            "resolved_at":   q.get("resolved_at", ""),
            "decision":      rec["decision"],
            "justification": rec.get("justification", ""),
            "parse_error":   rec.get("parse_error", False),
        })

    if verbose:
        print(f"\n  Audit sample: {len(audit_records)} questions drawn "
              f"(seed={AUDIT_SAMPLE_SEED}) from {len(kept_qids)} kept.", flush=True)

    # Save to committed path
    os.makedirs(INTERIM_DIR, exist_ok=True)
    with open(AUDIT_SAMPLE_PATH, "w", encoding="utf-8") as fh:
        json.dump(audit_records, fh, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  Audit sample saved to {AUDIT_SAMPLE_PATH}", flush=True)

    return audit_records
