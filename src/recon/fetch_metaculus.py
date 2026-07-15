"""
fetch_metaculus.py — Pull resolved binary AI-progress questions from Metaculus.

Endpoint used: GET /api2/questions/
  Filter params: type=forecast, status=resolved, resolution__in=yes,no,
                 tags (or project filters for AI)

Raw responses saved to data/raw/recon/metaculus_raw_<page>.json (git-ignored).
Returns a list of normalised question dicts.

Rate limiting: METACULUS_RATE_SLEEP seconds between page requests.
Respects METACULUS_MAX_PAGES hard cap; logs truncation if hit.
"""

import json
import os
import hashlib
import time
from datetime import datetime, timezone

from config import (
    METACULUS_API_BASE,
    METACULUS_PAGE_SIZE,
    METACULUS_RATE_SLEEP,
    METACULUS_MAX_PAGES,
    AI_PROGRESS_KEYWORDS,
    EXCLUSION_KEYWORDS,
    RAW_DIR,
)
from http_utils import get_json_with_retry


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_ai_progress(title: str, description: str = "") -> bool:
    """
    Keyword-based AI-progress filter (v1.0).
    Returns True if the title (or description) contains at least one AI keyword
    and no exclusion keyword matches the title.

    Args:
        title: Question title string.
        description: Optional description for extra signal.

    Returns:
        True if classified as AI-progress.
    """
    combined = (title + " " + description).lower()
    title_lower = title.lower()

    for excl in EXCLUSION_KEYWORDS:
        if excl.lower() in title_lower:
            return False

    for kw in AI_PROGRESS_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False


def _save_raw_page(page_data: dict, page_num: int) -> str:
    """Save a raw page response to disk and return the file path."""
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"metaculus_raw_page_{page_num:04d}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(page_data, fh, ensure_ascii=False, indent=2)
    return path


def _sha256_file(path: str) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalise(q: dict) -> dict:
    """
    Extract and normalise fields we care about from a raw Metaculus question record.

    Returns a flat dict with the core schema fields.
    """
    qid = str(q.get("id", ""))
    title = q.get("title", "") or ""
    description = q.get("description", "") or ""

    created = q.get("created_time") or q.get("publish_time") or ""
    close_at = q.get("close_time") or ""
    resolved_at = q.get("resolve_time") or q.get("resolution_time") or ""

    resolution = q.get("resolution")  # "yes", "no", "ambiguous", "annulled", etc.
    if resolution is not None:
        resolution = str(resolution).lower()

    # Binary outcome mapping
    if resolution == "yes":
        outcome = 1
    elif resolution == "no":
        outcome = 0
    else:
        outcome = None  # ambiguous/annulled — will be flagged

    return {
        "qid": f"metaculus_{qid}",
        "source": "metaculus",
        "title": title,
        "description": description[:500],  # truncate for storage
        "created_at": created,
        "close_at": close_at,
        "resolved_at": resolved_at,
        "resolution_raw": resolution,
        "outcome": outcome,
        "url": f"https://www.metaculus.com/questions/{qid}/",
        "community_prediction": q.get("community_prediction"),
        "nr_forecasters": q.get("nr_forecasters") or 0,
        "prediction_count": q.get("prediction_count") or 0,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_metaculus_questions(
    verbose: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    """
    Fetch all resolved binary AI-progress questions from Metaculus.

    Strategy:
      1. Query /api2/questions/ with type=forecast, status=resolved,
         guessed_outcome_time__isnull=False, order_by=-resolve_time.
      2. Paginate until no more results or MAX_PAGES hit.
      3. Apply binary filter: only questions where resolution in {yes, no}.
      4. Apply keyword-based AI-progress filter on title+description.
      5. Save raw pages to disk; return normalised list + manifest entries.

    Args:
        verbose: Print progress to stdout.

    Returns:
        Tuple of:
          - all_questions: List of normalised question dicts (AI-progress, binary).
          - dropped: List of dicts with qid + reason for dropped questions.
          - manifest_entries: List of dicts for the run manifest.
    """
    base_url = METACULUS_API_BASE + "questions/"
    params_base = {
        "type": "forecast",
        "status": "resolved",
        "limit": METACULUS_PAGE_SIZE,
        "format": "json",
        "order_by": "-resolve_time",
        # Only questions with a definitive resolution
        "resolution": "yes,no",  # comma-separated values — Metaculus supports this
    }

    all_questions: list[dict] = []
    dropped: list[dict] = []
    manifest_entries: list[dict] = []
    truncated = False

    page = 1
    offset = 0
    total_raw_fetched = 0

    # Counts for logging
    n_non_binary = 0
    n_ambiguous = 0
    n_not_ai = 0

    while page <= METACULUS_MAX_PAGES:
        if verbose:
            print(f"  Metaculus: fetching page {page} (offset={offset})...", flush=True)

        params = {**params_base, "offset": offset}

        try:
            data = get_json_with_retry(
                base_url,
                params=params,
                sleep_before=METACULUS_RATE_SLEEP if page > 1 else 0.2,
            )
        except Exception as exc:
            print(f"  [ERROR] Metaculus page {page} failed: {exc}", flush=True)
            break

        # Save raw page
        raw_path = _save_raw_page({"page": page, "params": params, "data": data}, page)
        content_hash = _sha256_file(raw_path)
        fetched_at = datetime.now(timezone.utc).isoformat()

        results = data.get("results", []) if isinstance(data, dict) else []
        total_count = data.get("count", 0) if isinstance(data, dict) else 0

        manifest_entries.append({
            "source": "metaculus",
            "page": page,
            "offset": offset,
            "endpoint": base_url,
            "params": params,
            "fetched_at_utc": fetched_at,
            "items_in_page": len(results),
            "total_reported_by_api": total_count,
            "raw_file": raw_path,
            "content_hash_sha256": content_hash,
        })

        if not results:
            if verbose:
                print(f"  Metaculus: no more results at page {page}. Done.", flush=True)
            break

        total_raw_fetched += len(results)

        for q in results:
            raw_res = str(q.get("resolution", "") or "").lower()

            # Non-binary resolution (annulled, ambiguous, numeric, etc.)
            if raw_res not in ("yes", "no"):
                n_non_binary += 1
                continue

            norm = _normalise(q)

            # Double-check outcome is clean
            if norm["outcome"] is None:
                n_ambiguous += 1
                dropped.append({"qid": norm["qid"], "reason": "ambiguous_resolution"})
                continue

            # AI-progress keyword filter
            if not _is_ai_progress(norm["title"], norm["description"]):
                n_not_ai += 1
                continue

            all_questions.append(norm)

        # Pagination: Metaculus uses offset-based pagination
        next_offset = data.get("next") if isinstance(data, dict) else None
        # If `next` is a URL, parse the offset from it; otherwise increment manually
        if next_offset is None:
            offset += METACULUS_PAGE_SIZE
        else:
            # next is a full URL; extract offset param
            import urllib.parse as _up
            parsed = _up.urlparse(str(next_offset))
            qs = _up.parse_qs(parsed.query)
            offset = int(qs.get("offset", [offset + METACULUS_PAGE_SIZE])[0])

        # Check if we've consumed everything
        if total_count and offset >= total_count:
            if verbose:
                print(f"  Metaculus: reached end (total={total_count}). Done.", flush=True)
            break

        # No next link and we got fewer than page_size results
        if len(results) < METACULUS_PAGE_SIZE:
            if verbose:
                print(f"  Metaculus: last page (got {len(results)} < {METACULUS_PAGE_SIZE}). Done.", flush=True)
            break

        page += 1

    else:
        truncated = True
        print(f"  [WARNING] Metaculus: hit MAX_PAGES={METACULUS_MAX_PAGES}. Results may be truncated.", flush=True)

    if verbose:
        print(
            f"  Metaculus summary: raw_fetched={total_raw_fetched}, "
            f"non_binary_dropped={n_non_binary}, ambiguous_dropped={n_ambiguous}, "
            f"not_ai_filtered={n_not_ai}, ai_progress_binary={len(all_questions)}, "
            f"truncated={truncated}",
            flush=True,
        )

    # Attach summary to last manifest entry
    manifest_entries.append({
        "source": "metaculus",
        "type": "summary",
        "total_raw_fetched": total_raw_fetched,
        "n_non_binary_dropped": n_non_binary,
        "n_ambiguous_dropped": n_ambiguous,
        "n_not_ai_filtered": n_not_ai,
        "n_ai_progress_binary": len(all_questions),
        "truncated": truncated,
        "pages_fetched": page,
    })

    return all_questions, dropped, manifest_entries
