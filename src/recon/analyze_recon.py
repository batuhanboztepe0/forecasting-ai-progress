"""
analyze_recon.py — Offline analysis over normalised question lists.

Works from in-memory lists (or JSON files); does NOT hit APIs.
Produces:
  - Resolution-date distribution table (per source, per year/quarter)
  - Clean post-cutoff N per candidate cutoff (raw + snapshot-feasible)
  - Manifold liquidity summary stats
  - Classifier precision estimate (seeded random sample + manual-label proxy)
"""

import json
import os
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np

from config import (
    CANDIDATE_CUTOFFS,
    SNAPSHOT_LEAD_DAYS,
    MANIFOLD_MIN_UNIQUE_BETTORS,
    MANIFOLD_MIN_VOLUME_MANA,
    RANDOM_SEED,
    INTERIM_DIR,
    KEYWORD_LIST_VERSION,
)


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

def _parse_iso(s: str) -> datetime | None:
    """Parse an ISO-8601 datetime string (UTC); return None on failure."""
    if not s:
        return None
    # Normalise trailing Z
    s = s.replace("Z", "+00:00")
    # Try full datetime first, then date-only
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:26], fmt[:len(s[:26])])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    # Fallback: strip microseconds beyond 6 digits
    trimmed = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        return datetime.fromisoformat(trimmed)
    except Exception:
        return None


def _cutoff_dt(date_str: str) -> datetime:
    """Return a timezone-aware UTC datetime from a date string like '2023-04-01'."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. Resolution-date distribution
# ---------------------------------------------------------------------------

def resolution_distribution(questions: list[dict]) -> dict:
    """
    Count questions by year and quarter of resolved_at, per source.

    Args:
        questions: Combined list from Metaculus + Manifold.

    Returns:
        Dict with keys 'by_year' and 'by_quarter', each a nested dict
        {source: {period: count}}, plus 'combined'.
    """
    by_year: dict[str, dict[str, int]] = {}
    by_quarter: dict[str, dict[str, int]] = {}

    for q in questions:
        src = q["source"]
        dt = _parse_iso(q.get("resolved_at", ""))
        if dt is None:
            continue

        year = str(dt.year)
        quarter = f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"

        # by_year
        by_year.setdefault(src, {})
        by_year[src][year] = by_year[src].get(year, 0) + 1

        by_quarter.setdefault(src, {})
        by_quarter[src][quarter] = by_quarter[src].get(quarter, 0) + 1

    # Combined
    by_year["combined"] = {}
    by_quarter["combined"] = {}
    for src, counts in by_year.items():
        if src == "combined":
            continue
        for period, cnt in counts.items():
            by_year["combined"][period] = by_year["combined"].get(period, 0) + cnt
    for src, counts in by_quarter.items():
        if src == "combined":
            continue
        for period, cnt in counts.items():
            by_quarter["combined"][period] = by_quarter["combined"].get(period, 0) + cnt

    return {"by_year": by_year, "by_quarter": by_quarter}


# ---------------------------------------------------------------------------
# 2. Clean post-cutoff N per candidate cutoff
# ---------------------------------------------------------------------------

def _has_snapshot_history(q: dict, snapshot_dt: datetime) -> bool:
    """
    Heuristic check whether a crowd snapshot is feasible at snapshot_dt.

    For Metaculus: check prediction_count > 0 AND created_at < snapshot_dt.
    For Manifold: check unique_bettors > 0 AND created_at < snapshot_dt.
    (We can't query the actual history in recon; this is the necessary condition.)

    Args:
        q: Normalised question dict.
        snapshot_dt: The T = resolved_at - 30d datetime.

    Returns:
        True if the question likely had at least one forecast/bet by snapshot_dt.
    """
    created = _parse_iso(q.get("created_at", ""))
    if created is None or created >= snapshot_dt:
        return False

    if q["source"] == "metaculus":
        return (q.get("prediction_count") or 0) > 0 or (q.get("nr_forecasters") or 0) > 0
    elif q["source"] == "manifold":
        return (q.get("unique_bettors") or 0) > 0 or (q.get("num_traders") or 0) > 0
    return True


def clean_n_per_cutoff(questions: list[dict]) -> list[dict]:
    """
    For each candidate cutoff C in CANDIDATE_CUTOFFS, count:
      - raw_n: questions with resolved_at >= C + SNAPSHOT_LEAD_DAYS (D-006 rule)
      - snapshot_feasible_n: subset where a crowd snapshot at T=resolved_at-30d
        is plausibly available.

    Per source and combined.

    Args:
        questions: Combined normalised list.

    Returns:
        List of dicts, one per cutoff, with counts per source and combined.
    """
    rows = []
    for cutoff in CANDIDATE_CUTOFFS:
        c_dt = _cutoff_dt(cutoff["date"])
        cutoff_plus_lead = c_dt + timedelta(days=SNAPSHOT_LEAD_DAYS)

        raw_meta = 0
        raw_manifold = 0
        snap_meta = 0
        snap_manifold = 0

        for q in questions:
            dt = _parse_iso(q.get("resolved_at", ""))
            if dt is None:
                continue
            if dt < cutoff_plus_lead:
                continue

            snapshot_dt = dt - timedelta(days=SNAPSHOT_LEAD_DAYS)

            src = q["source"]
            if src == "metaculus":
                raw_meta += 1
                if _has_snapshot_history(q, snapshot_dt):
                    snap_meta += 1
            elif src == "manifold":
                raw_manifold += 1
                if _has_snapshot_history(q, snapshot_dt):
                    snap_manifold += 1

        rows.append({
            "cutoff_label": cutoff["label"],
            "cutoff_date": cutoff["date"],
            "raw_metaculus": raw_meta,
            "raw_manifold": raw_manifold,
            "raw_combined": raw_meta + raw_manifold,
            "snap_feasible_metaculus": snap_meta,
            "snap_feasible_manifold": snap_manifold,
            "snap_feasible_combined": snap_meta + snap_manifold,
        })

    return rows


# ---------------------------------------------------------------------------
# 3. Manifold liquidity stats
# ---------------------------------------------------------------------------

def manifold_liquidity_stats(questions: list[dict]) -> dict:
    """
    Compute summary statistics for Manifold liquidity fields.

    Args:
        questions: All normalised questions (Manifold + Metaculus; filters to Manifold).

    Returns:
        Dict of summary stats and viability counts.
    """
    mf = [q for q in questions if q["source"] == "manifold"]
    if not mf:
        return {"n": 0, "note": "no Manifold questions found"}

    volumes = np.array([q.get("volume") or 0.0 for q in mf], dtype=float)
    bettors = np.array([q.get("unique_bettors") or 0 for q in mf], dtype=float)
    liquidity = np.array([q.get("total_liquidity") or 0.0 for q in mf], dtype=float)
    trades = np.array([q.get("num_traders") or 0 for q in mf], dtype=float)

    def pct(arr: np.ndarray, thres: float) -> float:
        return float(np.mean(arr >= thres) * 100) if len(arr) > 0 else 0.0

    return {
        "n": len(mf),
        "volume": {
            "median": float(np.median(volumes)),
            "p25": float(np.percentile(volumes, 25)),
            "p75": float(np.percentile(volumes, 75)),
            "p90": float(np.percentile(volumes, 90)),
            "mean": float(np.mean(volumes)),
            "pct_above_1000": pct(volumes, 1000),
            "pct_above_500": pct(volumes, 500),
        },
        "unique_bettors": {
            "median": float(np.median(bettors)),
            "p25": float(np.percentile(bettors, 25)),
            "p75": float(np.percentile(bettors, 75)),
            "p90": float(np.percentile(bettors, 90)),
            "mean": float(np.mean(bettors)),
            "pct_above_20": pct(bettors, 20),
            "pct_above_10": pct(bettors, 10),
        },
        "total_liquidity": {
            "median": float(np.median(liquidity)),
            "p25": float(np.percentile(liquidity, 25)),
            "p75": float(np.percentile(liquidity, 75)),
            "p90": float(np.percentile(liquidity, 90)),
            "mean": float(np.mean(liquidity)),
        },
        "num_trades": {
            "median": float(np.median(trades)),
            "p25": float(np.percentile(trades, 25)),
            "p75": float(np.percentile(trades, 75)),
            "p90": float(np.percentile(trades, 90)),
            "mean": float(np.mean(trades)),
        },
        "viability": {
            "n_above_20_bettors_and_1000_vol": int(
                np.sum((bettors >= MANIFOLD_MIN_UNIQUE_BETTORS) & (volumes >= MANIFOLD_MIN_VOLUME_MANA))
            ),
            "pct_above_20_bettors_and_1000_vol": pct(
                (bettors >= MANIFOLD_MIN_UNIQUE_BETTORS) & (volumes >= MANIFOLD_MIN_VOLUME_MANA).astype(float),
                0.5,  # at least one threshold met — recompute below
            ),
        },
    }


def manifold_liquidity_stats_v2(questions: list[dict]) -> dict:
    """
    Version 2 — fixed viability computation.
    Uses the same inputs as manifold_liquidity_stats but corrects the
    pct calculation for joint threshold.
    """
    mf = [q for q in questions if q["source"] == "manifold"]
    if not mf:
        return {"n": 0, "note": "no Manifold questions found"}

    volumes = np.array([q.get("volume") or 0.0 for q in mf], dtype=float)
    bettors = np.array([q.get("unique_bettors") or 0 for q in mf], dtype=float)
    liquidity = np.array([q.get("total_liquidity") or 0.0 for q in mf], dtype=float)
    trades = np.array([q.get("num_traders") or 0 for q in mf], dtype=float)

    n = len(mf)

    def _stats(arr: np.ndarray) -> dict:
        return {
            "median": round(float(np.median(arr)), 1),
            "p25": round(float(np.percentile(arr, 25)), 1),
            "p75": round(float(np.percentile(arr, 75)), 1),
            "p90": round(float(np.percentile(arr, 90)), 1),
            "mean": round(float(np.mean(arr)), 1),
        }

    mask_viable = (bettors >= MANIFOLD_MIN_UNIQUE_BETTORS) & (volumes >= MANIFOLD_MIN_VOLUME_MANA)
    n_viable = int(np.sum(mask_viable))

    return {
        "n": n,
        "volume_mana": _stats(volumes),
        "unique_bettors": _stats(bettors),
        "total_liquidity_mana": _stats(liquidity),
        "num_trades": _stats(trades),
        "viability": {
            "thresholds": f">={MANIFOLD_MIN_UNIQUE_BETTORS} bettors AND >={MANIFOLD_MIN_VOLUME_MANA} mana volume",
            "n_viable": n_viable,
            "pct_viable": round(n_viable / n * 100, 1) if n > 0 else 0.0,
            "n_above_20_bettors": int(np.sum(bettors >= 20)),
            "n_above_1000_vol": int(np.sum(volumes >= 1000)),
            "n_above_10_bettors": int(np.sum(bettors >= 10)),
        },
    }


# ---------------------------------------------------------------------------
# 4. Classifier precision estimate (seeded random sample)
# ---------------------------------------------------------------------------

def classifier_precision_sample(
    questions: list[dict],
    n_sample: int = 30,
    seed: int = RANDOM_SEED,
) -> dict:
    """
    Draw a seeded random sample of matched questions and apply a
    tighter rule-based heuristic that approximates what a human reviewer
    would call "genuinely AI-progress".

    Since we have no LLM here, we use a stricter sub-keyword set as a proxy
    for what the LLM classifier would flag as correct.  This gives a *lower
    bound* on precision (false positives are likely in edge cases).

    The sample titles are returned verbatim so the report can include them
    for human inspection.

    Args:
        questions: Combined normalised list.
        n_sample: Sample size.
        seed: RNG seed.

    Returns:
        Dict with sample list, estimated precision, and methodology note.
    """
    rng = random.Random(seed)
    pool = questions.copy()
    rng.shuffle(pool)
    sample = pool[:min(n_sample, len(pool))]

    # Stricter "core AI-progress" keywords that are almost never false positives
    CORE_KEYWORDS = [
        "gpt", "llm", "language model", "benchmark", "chatgpt", "claude",
        "gemini", "deepmind", "openai", "anthropic", "llama", "mistral",
        "deep learning", "neural network", "agi", "alignment", "fine-tun",
        "training run", "compute", "model release", "capabilities",
        "ai safety", "scaling", "parameter", "transformer", "diffusion",
        "code generation", "reasoning model", "multimodal",
    ]

    # Borderline keywords that can also match non-AI-progress contexts
    BORDERLINE_KEYWORDS = [
        " ai ", "artificial intelligence", "machine learning", "automation",
        "robots", "autonomous", "agent",
    ]

    def _classify_strictly(title: str, desc: str) -> str:
        """Return 'core', 'borderline', or 'likely_fp' for a sample question."""
        t = (title + " " + desc).lower()
        for kw in CORE_KEYWORDS:
            if kw in t:
                return "core"
        for kw in BORDERLINE_KEYWORDS:
            if kw in t:
                return "borderline"
        return "likely_fp"

    results = []
    n_core = 0
    n_borderline = 0
    n_likely_fp = 0
    for q in sample:
        cat = _classify_strictly(q["title"], q.get("description", ""))
        results.append({
            "qid": q["qid"],
            "source": q["source"],
            "title": q["title"][:120],
            "category": cat,
        })
        if cat == "core":
            n_core += 1
        elif cat == "borderline":
            n_borderline += 1
        else:
            n_likely_fp += 1

    n = len(sample)
    # Precision estimate: core = definitely correct; borderline = probably correct (weight 0.6)
    est_precision = (n_core + 0.6 * n_borderline) / n if n > 0 else 0.0

    return {
        "sample_size": n,
        "seed": seed,
        "n_core": n_core,
        "n_borderline": n_borderline,
        "n_likely_fp": n_likely_fp,
        "estimated_precision": round(est_precision, 3),
        "methodology": (
            "Seeded random sample; strict sub-keyword set ('core') vs borderline heuristic. "
            "Precision = (core + 0.6 * borderline) / n. "
            f"Keyword list version: {KEYWORD_LIST_VERSION}. "
            "Note: this is a lower-bound proxy; human review or LLM classifier (Phase 2) will be more accurate."
        ),
        "sample": results,
    }


# ---------------------------------------------------------------------------
# 5. Save interim outputs
# ---------------------------------------------------------------------------

def save_interim(data: Any, filename: str) -> str:
    """Save data as JSON to data/interim/; return path."""
    os.makedirs(INTERIM_DIR, exist_ok=True)
    path = os.path.join(INTERIM_DIR, filename)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path
