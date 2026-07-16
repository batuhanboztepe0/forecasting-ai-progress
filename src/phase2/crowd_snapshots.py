"""
crowd_snapshots.py — Fetch Manifold bet history and compute crowd_prob_at_T
for all Phase-2 selected questions.

T = resolved_at - 30 days (D-007).  crowd_prob_at_T is the probAfter of the
last non-redemption bet placed at or before T.  Fallback: market initial AMM
probability (field 'p') if no bets precede T.  Drop questions with no bet
activity at/before T AND no fallback p — log count, refill if possible.

Reuses existing raw bet files from data/raw/recon/ and data/raw/phase2/
to avoid redundant API calls.

Checkpoints progress to CROWD_SNAPSHOT_CHECKPOINT so interrupted runs resume.

Microstructure captured at T (DATA.md schema):
  - trade_count_at_T: non-redemption bets at/before T
  - unique_bettors_at_T: distinct userId values at/before T
  - volume_mana_at_T: sum of |amount| for bets at/before T
  - total_liquidity: market-level addedLiquidity (static, from listing)
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import urllib.request
import urllib.error

from phase2_config import (  # noqa: E402
    SNAPSHOT_LEAD_DAYS,
    MANIFOLD_BETS_URL,
    MANIFOLD_BETS_PAGE_SIZE,
    MANIFOLD_RATE_SLEEP,
    CROWD_SNAPSHOT_CHECKPOINT,
    RAW_DIR,
    RECON_RAW_DIR,
    INTERIM_DIR,
)


def _market_id(qid: str) -> str:
    """Strip 'manifold_' prefix to get Manifold contract ID."""
    return qid.replace("manifold_", "", 1)


def _raw_bet_path(market_id: str) -> str:
    """Canonical path for raw bet JSON in Phase-2 raw dir."""
    return os.path.join(RAW_DIR, f"bets_{market_id}.json")


def _recon_bet_path(market_id: str) -> str:
    """Path in recon raw dir (from Phase-0/1 pulls)."""
    return os.path.join(RECON_RAW_DIR, f"bets_{market_id}.json")


def _sha256_file(path: str) -> str:
    """Compute SHA-256 hex of file at path."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_raw_bets(market_id: str) -> Optional[list]:
    """
    Load raw bets from disk cache (Phase-2 dir first, then recon dir).

    Returns:
        List of bet dicts, or None if not cached.
    """
    for path in [_raw_bet_path(market_id), _recon_bet_path(market_id)]:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
    return None


def _save_raw_bets(market_id: str, bets: list) -> str:
    """Save raw bet list to Phase-2 raw dir. Returns path."""
    os.makedirs(RAW_DIR, exist_ok=True)
    path = _raw_bet_path(market_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(bets, fh, ensure_ascii=False, separators=(",", ":"))
    return path


def _fetch_all_bets_api(market_id: str) -> list:
    """
    Fetch all bets for a Manifold market via paginated API.

    Args:
        market_id: Manifold contract ID.

    Returns:
        List of bet dicts (unsorted).

    Raises:
        RuntimeError: On HTTP errors.
    """
    all_bets: list = []
    before_id: Optional[str] = None

    while True:
        params = f"contractId={market_id}&limit={MANIFOLD_BETS_PAGE_SIZE}"
        if before_id:
            params += f"&before={before_id}"
        url = f"{MANIFOLD_BETS_URL}?{params}"

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "forecasting-ai-progress-phase2/1.0",
            },
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    page_bets = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    time.sleep(4 ** (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Manifold bets HTTP {exc.code} for {market_id}"
                ) from exc
        else:
            raise RuntimeError(f"Max retries for bets/{market_id}")

        if not page_bets:
            break
        all_bets.extend(page_bets)
        if len(page_bets) < MANIFOLD_BETS_PAGE_SIZE:
            break
        before_id = page_bets[-1].get("id")
        if not before_id:
            break
        time.sleep(MANIFOLD_RATE_SLEEP)

    return all_bets


def _compute_snapshot(q: dict, bets: list) -> dict:
    """
    Compute crowd_prob_at_T and microstructure at T from bet history.

    Args:
        q: Question dict (for resolved_at and fallback p).
        bets: Full bet list for this market.

    Returns:
        Dict with crowd_prob_at_T and microstructure fields, or error info.
    """
    resolved_str = q.get("resolved_at", "")
    if not resolved_str:
        return {"crowd_prob_at_T": None, "snapshot_error": "no_resolved_at"}

    try:
        s = resolved_str.replace("Z", "+00:00")
        resolved_dt = datetime.fromisoformat(s)
        if resolved_dt.tzinfo is None:
            resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return {"crowd_prob_at_T": None, "snapshot_error": "bad_resolved_at"}

    T_dt = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
    T_ms = int(T_dt.timestamp() * 1000)

    # Sort bets ascending by createdTime
    bets_sorted = sorted(bets, key=lambda b: b.get("createdTime", 0))

    # Non-redemption bets at or before T
    eligible = [
        b for b in bets_sorted
        if not b.get("isRedemption", False)
        and b.get("createdTime", 0) <= T_ms
        and b.get("probAfter") is not None
    ]

    if eligible:
        crowd_prob = float(eligible[-1]["probAfter"])
        used_fallback = False
    else:
        # Fallback to initial AMM prob
        # D-013 inclusion rule: hard drop for 0-trade questions.
        # The AMM initial price (p) is NOT a crowd forecast — never use it as one.
        return {
            "crowd_prob_at_T": None,
            "snapshot_error": "no_bets_before_T_hard_drop",
            "trade_count_at_T": 0,
            "unique_bettors_at_T": 0,
            "volume_mana_at_T": 0.0,
            "total_liquidity": q.get("total_liquidity"),
        }

    # Microstructure at T
    unique_bettor_ids = {b.get("userId", "") for b in eligible}
    volume_mana = sum(abs(b.get("amount", 0)) for b in eligible)

    return {
        "crowd_prob_at_T":     crowd_prob,
        "snapshot_T_date":     T_dt.strftime("%Y-%m-%d"),
        "used_fallback_p":     False,        # D-013: fallback never used
        "snapshot_error":      None,
        "trade_count_at_T":    len(eligible),
        "unique_bettors_at_T": len(unique_bettor_ids),
        "volume_mana_at_T":    round(volume_mana, 4),
        "total_liquidity":     q.get("total_liquidity"),
    }


def _load_checkpoint(checkpoint_path: str) -> dict:
    """Load snapshot checkpoint; return empty dict if missing."""
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_checkpoint(checkpoint: dict, checkpoint_path: str) -> None:
    """Save snapshot checkpoint atomically."""
    os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
    tmp = checkpoint_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(checkpoint, fh, ensure_ascii=False)
    os.replace(tmp, checkpoint_path)


def fetch_all_snapshots(
    questions: list,
    checkpoint_path: str = None,
    verbose: bool = True,
) -> tuple:
    """
    Fetch crowd_prob_at_T and microstructure for all questions.

    Skips questions with a valid cached snapshot in the checkpoint.
    Rate-sleeps 0.4s between API calls.  Saves raw bets for new fetches.

    D-013 inclusion rule: a question must have ≥1 bet at/before T.  The
    AMM initial price (p) is NOT a valid crowd forecast; 0-trade questions
    are hard-dropped.  No refill.

    Args:
        questions: Combined haiku-clean + pre-cutoff probe list.
        checkpoint_path: Path to checkpoint JSON (default: CROWD_SNAPSHOT_CHECKPOINT).
        verbose: Print per-question progress.

    Returns:
        (snapshots: dict, drop_qids: list, content_hashes: dict)
        snapshots[qid] = snapshot dict (crowd_prob_at_T + microstructure)
        drop_qids = qids hard-dropped for 0 bets at T
        content_hashes[qid] = SHA-256 of "{title}\n{description}"
    """
    if checkpoint_path is None:
        checkpoint_path = CROWD_SNAPSHOT_CHECKPOINT
    checkpoint = _load_checkpoint(checkpoint_path)
    snapshots: dict = {}
    drop_qids: list = []
    content_hashes: dict = {}
    n = len(questions)
    n_api = 0
    n_cache = 0
    n_reused_raw = 0

    for i, q in enumerate(questions, 1):
        qid = q["qid"]
        mid = _market_id(qid)

        # Content hash (title + description)
        text_for_hash = (q.get("title") or "") + "\n" + (q.get("description") or "")
        content_hashes[qid] = hashlib.sha256(text_for_hash.encode()).hexdigest()

        # Checkpoint resume
        if qid in checkpoint and checkpoint[qid].get("crowd_prob_at_T") is not None:
            snapshots[qid] = checkpoint[qid]
            n_cache += 1
            if verbose and i % 200 == 0:
                print(f"  [{i:4d}/{n}] {qid[:28]} CACHED crowd={checkpoint[qid]['crowd_prob_at_T']:.4f}",
                      flush=True)
            continue

        # Try loading raw bets from disk first
        bets = _load_raw_bets(mid)
        if bets is not None:
            n_reused_raw += 1
        else:
            # Fetch from API
            if verbose:
                print(f"  [{i:4d}/{n}] {qid[:28]} fetching bets...", flush=True)
            try:
                bets = _fetch_all_bets_api(mid)
                _save_raw_bets(mid, bets)
                n_api += 1
            except RuntimeError as exc:
                if verbose:
                    print(f"  [{i:4d}/{n}] {qid[:28]} FETCH_ERR: {exc}", flush=True)
                snap = {
                    "crowd_prob_at_T": None,
                    "snapshot_error": f"fetch_error: {exc}",
                }
                checkpoint[qid] = snap
                _save_checkpoint(checkpoint, checkpoint_path)
                drop_qids.append(qid)
                continue
            time.sleep(MANIFOLD_RATE_SLEEP)

        snap = _compute_snapshot(q, bets)
        if snap.get("crowd_prob_at_T") is None:
            if verbose:
                print(f"  [{i:4d}/{n}] {qid[:28]} DROP: {snap.get('snapshot_error')}", flush=True)
            drop_qids.append(qid)
        else:
            snapshots[qid] = snap
            if verbose:
                print(
                    f"  [{i:4d}/{n}] {qid[:28]} crowd={snap['crowd_prob_at_T']:.4f} "
                    f"trades={snap.get('trade_count_at_T', '?')}",
                    flush=True,
                )

        checkpoint[qid] = snap
        # Save checkpoint every 50 questions
        if i % 50 == 0:
            _save_checkpoint(checkpoint, checkpoint_path)

    _save_checkpoint(checkpoint, checkpoint_path)

    if verbose:
        print(
            f"\n  Snapshots: {len(snapshots)} valid | {len(drop_qids)} dropped"
            f" | api={n_api} reused_raw={n_reused_raw} cached={n_cache}",
            flush=True,
        )

    return snapshots, drop_qids, content_hashes
