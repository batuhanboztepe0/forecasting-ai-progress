"""
sample_questions.py — Seeded thin-slice question selection per D-011 spec.

Bucket strategy (seed=42, N=50):
  Post-cutoff (25): reuse pilot questions (ub>=20) first; fill remainder
    from post-cutoff pool not in pilot.  Include >=8 from the all-3-models
    clean stratum (resolved_at >= 2026-03-02).
  Pre-cutoff (25): sample from resolved_at < 2025-08-30, ub>=20.

All selection is deterministic given the input dataset and seed.
"""

import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import os as _os, sys as _sys
_HERE_SQ = _os.path.dirname(_os.path.abspath(__file__))
for _p in [_HERE_SQ]:
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from mvp_config import (
    RANDOM_SEED,
    SNAPSHOT_LEAD_DAYS,
    POST_CUTOFF_MIN_RESOLVED,
    ALL3_CLEAN_MIN_RESOLVED,
    ALL3_CLEAN_MIN_N,
    MIN_UNIQUE_BETTORS_PREFERRED,
    THIN_SLICE_N,
    QUESTIONS_COMBINED_PATH,
    PILOT_QUESTIONS_PATH,
    MVP_SAMPLE_PATH,
)


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO datetime string to UTC-aware datetime."""
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


def _is_snapshot_feasible(q: dict) -> tuple:
    """
    Check if a question has a valid snapshot point.

    Returns:
        (is_feasible: bool, resolved_dt: Optional[datetime])
    """
    ra_str = q.get("resolved_at", "")
    resolved_dt = _parse_dt(ra_str)
    if resolved_dt is None:
        return False, None

    T = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
    created_dt = _parse_dt(q.get("created_at", ""))

    ub = q.get("unique_bettors", 0) or 0
    if created_dt is not None and created_dt < T and ub > 0:
        return True, resolved_dt
    return False, resolved_dt


def select_thin_slice(
    all_questions: list,
    pilot_questions: list,
    verbose: bool = True,
) -> list:
    """
    Select the 50-question thin-slice per D-011 §4.

    Args:
        all_questions: Full combined question list from QUESTIONS_COMBINED_PATH.
        pilot_questions: 30 pilot questions (responses already cached).
        verbose: Print selection summary.

    Returns:
        Sorted list of 50 question dicts with added field 'thin_slice_stratum'
        ('post_cutoff' or 'pre_cutoff').
    """
    rng = random.Random(RANDOM_SEED)

    post_min_dt = _parse_dt(POST_CUTOFF_MIN_RESOLVED)
    all3_min_dt = _parse_dt(ALL3_CLEAN_MIN_RESOLVED)
    pilot_qids = {q["qid"] for q in pilot_questions}

    # Partition all snapshot-feasible questions by stratum
    post_pool = []   # resolved_at >= 2025-08-30
    pre_pool  = []   # resolved_at <  2025-08-30

    for q in all_questions:
        if q.get("source") != "manifold":
            continue
        ok, resolved_dt = _is_snapshot_feasible(q)
        if not ok or resolved_dt is None:
            continue
        if resolved_dt >= post_min_dt:
            post_pool.append((resolved_dt, q))
        else:
            pre_pool.append((resolved_dt, q))

    # ------------------------------------------------------------------ #
    # Post-cutoff bucket (25 questions)
    # Priority 1: pilot questions with ub >= preferred threshold
    # Priority 2: remaining pilot questions (ub < threshold)
    # Priority 3: non-pilot post-cutoff questions (sorted by qid, seeded sample)
    # ------------------------------------------------------------------ #
    n_post = THIN_SLICE_N // 2   # 25

    pilot_post_hi = []
    pilot_post_lo = []
    for q in pilot_questions:
        ok, resolved_dt = _is_snapshot_feasible(q)
        if not ok or resolved_dt is None:
            continue
        if resolved_dt >= post_min_dt:
            ub = q.get("unique_bettors", 0) or 0
            if ub >= MIN_UNIQUE_BETTORS_PREFERRED:
                pilot_post_hi.append((resolved_dt, q))
            else:
                pilot_post_lo.append((resolved_dt, q))

    selected_post = list(pilot_post_hi)
    slots_remaining = n_post - len(selected_post)

    if slots_remaining > 0 and pilot_post_lo:
        selected_post += pilot_post_lo[:slots_remaining]
        slots_remaining = n_post - len(selected_post)

    if slots_remaining > 0:
        # Non-pilot pool, prefer ub >= threshold
        non_pilot_post = [
            (dt, q) for dt, q in post_pool
            if q["qid"] not in pilot_qids
        ]
        non_pilot_hi = sorted(
            [(dt, q) for dt, q in non_pilot_post
             if (q.get("unique_bettors", 0) or 0) >= MIN_UNIQUE_BETTORS_PREFERRED],
            key=lambda x: x[1]["qid"]
        )
        sample_size = min(slots_remaining, len(non_pilot_hi))
        if sample_size > 0:
            fill = rng.sample(non_pilot_hi, sample_size)
            selected_post += fill
            slots_remaining = n_post - len(selected_post)

        # If still short, dip into lower-ub non-pilot questions
        if slots_remaining > 0:
            non_pilot_lo = sorted(
                [(dt, q) for dt, q in non_pilot_post
                 if (q.get("unique_bettors", 0) or 0) < MIN_UNIQUE_BETTORS_PREFERRED],
                key=lambda x: x[1]["qid"]
            )
            fill2 = rng.sample(non_pilot_lo, min(slots_remaining, len(non_pilot_lo)))
            selected_post += fill2

    # Verify >=8 all-3-models-clean questions
    n_all3 = sum(
        1 for _, q in selected_post
        if (_parse_dt(q.get("resolved_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= all3_min_dt
    )
    if n_all3 < ALL3_CLEAN_MIN_N:
        raise ValueError(
            f"Post-cutoff selection has only {n_all3} all-3-models-clean questions; "
            f"need >= {ALL3_CLEAN_MIN_N}."
        )

    # ------------------------------------------------------------------ #
    # Pre-cutoff bucket (25 questions)
    # Prefer ub >= threshold; seeded sample
    # ------------------------------------------------------------------ #
    n_pre = THIN_SLICE_N - len(selected_post)

    pre_hi = sorted(
        [(dt, q) for dt, q in pre_pool
         if (q.get("unique_bettors", 0) or 0) >= MIN_UNIQUE_BETTORS_PREFERRED],
        key=lambda x: x[1]["qid"]
    )
    pre_lo = sorted(
        [(dt, q) for dt, q in pre_pool
         if (q.get("unique_bettors", 0) or 0) < MIN_UNIQUE_BETTORS_PREFERRED],
        key=lambda x: x[1]["qid"]
    )

    sample_pre = rng.sample(pre_hi, min(n_pre, len(pre_hi)))
    if len(sample_pre) < n_pre:
        shortfall = n_pre - len(sample_pre)
        sample_pre += rng.sample(pre_lo, min(shortfall, len(pre_lo)))

    selected_pre = sample_pre[:n_pre]

    # ------------------------------------------------------------------ #
    # Combine and annotate
    # ------------------------------------------------------------------ #
    result = []
    for _, q in selected_post:
        qc = dict(q)
        qc["thin_slice_stratum"] = "post_cutoff"
        qc["_resolved_dt_str"] = q.get("resolved_at", "")
        result.append(qc)

    for _, q in selected_pre:
        qc = dict(q)
        qc["thin_slice_stratum"] = "pre_cutoff"
        qc["_resolved_dt_str"] = q.get("resolved_at", "")
        result.append(qc)

    result.sort(key=lambda q: q.get("resolved_at", ""))

    # De-duplicate (should not be needed but guard)
    seen = set()
    deduped = []
    for q in result:
        if q["qid"] not in seen:
            seen.add(q["qid"])
            deduped.append(q)

    if verbose:
        n_post_sel = sum(1 for q in deduped if q["thin_slice_stratum"] == "post_cutoff")
        n_pre_sel  = sum(1 for q in deduped if q["thin_slice_stratum"] == "pre_cutoff")
        n_all3_sel = sum(
            1 for q in deduped
            if q["thin_slice_stratum"] == "post_cutoff"
            and (_parse_dt(q.get("resolved_at", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= all3_min_dt
        )
        n_pilot    = sum(1 for q in deduped if q["qid"] in pilot_qids)
        print(f"  Thin slice: {len(deduped)} total | "
              f"post={n_post_sel} (all3-clean={n_all3_sel}) | "
              f"pre={n_pre_sel} | pilot reuse={n_pilot}", flush=True)

    return deduped


def load_or_build_sample(verbose: bool = True) -> list:
    """
    Load the thin-slice sample from disk, or build and save it.

    Args:
        verbose: Print progress.

    Returns:
        List of 50 annotated question dicts.
    """
    if os.path.exists(MVP_SAMPLE_PATH):
        with open(MVP_SAMPLE_PATH, encoding="utf-8") as fh:
            sample = json.load(fh)
        if verbose:
            print(f"  Loaded existing sample ({len(sample)} questions) from {MVP_SAMPLE_PATH}",
                  flush=True)
        return sample

    with open(QUESTIONS_COMBINED_PATH, encoding="utf-8") as fh:
        all_questions = json.load(fh)

    pilot_questions: list = []
    if os.path.exists(PILOT_QUESTIONS_PATH):
        with open(PILOT_QUESTIONS_PATH, encoding="utf-8") as fh:
            pilot_questions = json.load(fh)

    sample = select_thin_slice(all_questions, pilot_questions, verbose=verbose)

    os.makedirs(os.path.dirname(MVP_SAMPLE_PATH), exist_ok=True)
    with open(MVP_SAMPLE_PATH, "w", encoding="utf-8") as fh:
        json.dump(sample, fh, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  Saved sample to {MVP_SAMPLE_PATH}", flush=True)

    return sample
