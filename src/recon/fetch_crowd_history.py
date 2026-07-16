"""
fetch_crowd_history.py — Fetch Manifold bet history and compute crowd_prob_at_T.

For each question, T = resolved_at - 30 days (D-007 snapshot rule).
We walk the bet history in ascending time order and take the probAfter of the
last bet placed at or before T.  If no bets exist before T we fall back to
the market's initial AMM probability (field `p` from the market listing, or 0.5
if absent).

All raw bet pages are saved to RAW_DIR (git-ignored); only the summary dict is
committed via the manifest.
"""

import json
import os
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Optional

import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import RAW_DIR, MANIFOLD_MIN_UNIQUE_BETTORS, SNAPSHOT_LEAD_DAYS

MANIFOLD_BETS_URL = "https://api.manifold.markets/v0/bets"
BETS_PAGE_SIZE = 1000  # Manifold max
RATE_SLEEP = 0.4       # stay well under Manifold rate limits


def _market_id_from_qid(qid: str) -> str:
    """Strip 'manifold_' prefix to get Manifold contract ID."""
    return qid.replace("manifold_", "", 1)


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _save_raw_bets(market_id: str, bets: list) -> str:
    """Save raw bet list to RAW_DIR. Returns file path."""
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"bets_{market_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bets, fh, ensure_ascii=False, separators=(",", ":"))
    return path


def _fetch_all_bets(market_id: str) -> list:
    """
    Fetch all bets for a Manifold market using cursor pagination.

    Args:
        market_id: Manifold market ID (short alphanumeric string).

    Returns:
        List of bet dicts, in any order (will be sorted by caller).

    Raises:
        RuntimeError: On HTTP errors that are not retryable.
    """
    all_bets: list = []
    before_id: Optional[str] = None
    page = 0

    while True:
        params = f"contractId={market_id}&limit={BETS_PAGE_SIZE}"
        if before_id:
            params += f"&before={before_id}"
        url = f"{MANIFOLD_BETS_URL}?{params}"

        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url, headers={"Accept": "application/json",
                                  "User-Agent": "forecasting-ai-progress-recon/1.1"}
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    page_bets = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    time.sleep(4 ** (attempt + 1))
                    continue
                raise RuntimeError(f"Manifold bets HTTP {exc.code} for {market_id}") from exc
        else:
            raise RuntimeError(f"Max retries exceeded for bets/{market_id}")

        if not page_bets:
            break

        all_bets.extend(page_bets)
        page += 1

        if len(page_bets) < BETS_PAGE_SIZE:
            break  # last page

        # Cursor: use the id of the last bet in this page
        before_id = page_bets[-1].get("id")
        if not before_id:
            break

        time.sleep(RATE_SLEEP)

    return all_bets


def crowd_prob_at_snapshot(
    question: dict,
    verbose: bool = False,
) -> Optional[float]:
    """
    Compute the Manifold crowd probability at T = resolved_at - SNAPSHOT_LEAD_DAYS.

    Strategy:
      1. Sort all bets by createdTime ascending.
      2. Find last bet with createdTime <= T_ms.
      3. Return that bet's probAfter.
      4. Fallback: if no bets before T, return market initial prob (field 'p', default 0.5).

    Args:
        question: Normalised question dict with fields qid, resolved_at, unique_bettors.
        verbose: Print progress.

    Returns:
        Probability float in (0, 1), or None if fetch fails or data insufficient.
    """
    qid = question["qid"]
    market_id = _market_id_from_qid(qid)

    resolved_at_str = question.get("resolved_at", "")
    if not resolved_at_str:
        return None

    try:
        if resolved_at_str.endswith("Z"):
            resolved_at_str = resolved_at_str[:-1] + "+00:00"
        resolved_dt = datetime.fromisoformat(resolved_at_str)
        if resolved_dt.tzinfo is None:
            resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    T_dt = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
    T_ms = int(T_dt.timestamp() * 1000)

    if verbose:
        print(f"  [{qid}] T={T_dt.date()}, fetching bets...", flush=True)

    try:
        bets = _fetch_all_bets(market_id)
    except RuntimeError as exc:
        if verbose:
            print(f"  [{qid}] WARN: {exc}", flush=True)
        return None

    # Save raw bets
    _save_raw_bets(market_id, bets)

    # Sort ascending by createdTime
    bets_sorted = sorted(bets, key=lambda b: b.get("createdTime", 0))

    # Find last bet at or before T
    # Skip redemption bets (isRedemption=True) as they don't reflect trader belief
    eligible = [
        b for b in bets_sorted
        if not b.get("isRedemption", False)
        and b.get("createdTime", 0) <= T_ms
        and b.get("probAfter") is not None
    ]

    if eligible:
        prob = float(eligible[-1]["probAfter"])
        if verbose:
            n_before = len(eligible)
            print(f"  [{qid}] crowd_prob_at_T={prob:.4f} ({n_before} eligible bets before T)", flush=True)
        return prob

    # Fallback: use initial AMM prob
    initial_p = question.get("p")
    if initial_p is not None:
        prob = float(initial_p)
        if verbose:
            print(f"  [{qid}] No bets before T; fallback to initial p={prob:.4f}", flush=True)
        return prob

    if verbose:
        print(f"  [{qid}] No bets before T and no initial p — skipping", flush=True)
    return None


def fetch_crowd_probs_for_pilot(
    pilot_questions: list,
    verbose: bool = True,
) -> dict:
    """
    Fetch crowd_prob_at_T for all pilot questions.

    Args:
        pilot_questions: List of normalised question dicts.
        verbose: Print per-question progress.

    Returns:
        Dict mapping qid -> crowd_prob_at_T (None if unavailable).
    """
    results: dict = {}
    n = len(pilot_questions)
    for i, q in enumerate(pilot_questions, 1):
        qid = q["qid"]
        if verbose:
            print(f"  [{i}/{n}] Fetching bets for {qid}...", flush=True)
        prob = crowd_prob_at_snapshot(q, verbose=verbose)
        results[qid] = prob
        time.sleep(RATE_SLEEP)

    n_ok = sum(1 for v in results.values() if v is not None)
    if verbose:
        print(f"  Crowd history: {n_ok}/{n} questions with valid crowd_prob_at_T", flush=True)

    return results
