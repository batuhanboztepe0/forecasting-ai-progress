"""
fetch_manifold.py — Pull resolved binary AI-progress markets from Manifold Markets.

Strategy:
  1. For each AI-related group slug, fetch group ID via GET /v0/group/{slug}.
  2. Fetch all markets in that group via GET /v0/markets?groupId=... (paginated with `before`).
  3. Filter: outcomeType=BINARY, isResolved=true, resolution in {YES, NO}.
  4. Apply keyword-based AI-progress filter on question text.
  5. De-duplicate across groups.
  6. Save raw pages to disk; return normalised list + manifest entries.

Rate limit: MANIFOLD_RATE_SLEEP seconds between requests.
"""

import json
import os
import hashlib
import re
from datetime import datetime, timezone

from config import (
    MANIFOLD_API_BASE,
    MANIFOLD_PAGE_SIZE,
    MANIFOLD_RATE_SLEEP,
    MANIFOLD_MAX_PAGES,
    MANIFOLD_AI_GROUP_SLUGS,
    AI_PROGRESS_KEYWORDS,
    EXCLUSION_KEYWORDS,
    RAW_DIR,
)
from http_utils import get_json_with_retry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_ai_progress(title: str, description: str = "") -> bool:
    """
    Keyword-based AI-progress filter (v1.0) — same logic as Metaculus version.

    Args:
        title: Market question text.
        description: Optional description.

    Returns:
        True if at least one AI keyword matches and no exclusion keyword matches.
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


def _save_raw(data: dict | list, label: str) -> str:
    """Save raw JSON to disk; return path."""
    os.makedirs(RAW_DIR, exist_ok=True)
    safe_label = re.sub(r"[^a-zA-Z0-9_\-]", "_", label)[:80]
    path = os.path.join(RAW_DIR, f"manifold_raw_{safe_label}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def _sha256_file(path: str) -> str:
    """SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ts_to_iso(ts_ms: int | None) -> str:
    """Convert a Manifold millisecond epoch timestamp to ISO-8601 string."""
    if ts_ms is None:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()


def _normalise(m: dict) -> dict:
    """
    Normalise a raw Manifold market record into the core schema.

    Returns a flat dict.
    """
    mid = m.get("id", "")
    title = m.get("question", "") or ""
    description_raw = m.get("textDescription", "") or m.get("description", "") or ""
    # textDescription may be a complex slate.js object; convert to string if needed
    if isinstance(description_raw, dict):
        description_raw = json.dumps(description_raw)[:500]
    description = str(description_raw)[:500]

    created_at = _ts_to_iso(m.get("createdTime"))
    close_at = _ts_to_iso(m.get("closeTime"))
    resolved_at = _ts_to_iso(m.get("resolutionTime"))

    resolution = str(m.get("resolution", "") or "").upper()
    if resolution == "YES":
        outcome = 1
    elif resolution == "NO":
        outcome = 0
    else:
        outcome = None

    return {
        "qid": f"manifold_{mid}",
        "source": "manifold",
        "title": title,
        "description": description,
        "created_at": created_at,
        "close_at": close_at,
        "resolved_at": resolved_at,
        "resolution_raw": resolution,
        "outcome": outcome,
        "url": m.get("url", f"https://manifold.markets/{mid}"),
        "probability": m.get("probability"),
        "total_liquidity": m.get("totalLiquidity") or 0.0,
        "volume": m.get("volume") or 0.0,
        "unique_bettors": m.get("uniqueBettorCount") or m.get("uniqueBettors") or 0,
        # Note: numberOfBets / tradesCount are not returned by the /v0/markets listing endpoint;
        # this field will be 0 for all records from this endpoint.
        "num_traders": m.get("numberOfBets") or m.get("tradesCount") or 0,
        "pool": m.get("pool"),
        "p": m.get("p"),  # AMM p parameter
        "slug": m.get("slug", ""),
    }


def _fetch_group_id(slug: str, manifest_entries: list[dict], verbose: bool) -> str | None:
    """
    Fetch the group object for a given slug and return its id.
    Returns None if the slug does not exist (404).
    """
    url = f"{MANIFOLD_API_BASE}/group/{slug}"
    try:
        data = get_json_with_retry(url, sleep_before=MANIFOLD_RATE_SLEEP)
        raw_path = _save_raw(data, f"group_{slug}")
        content_hash = _sha256_file(raw_path)
        manifest_entries.append({
            "source": "manifold",
            "type": "group_lookup",
            "slug": slug,
            "group_id": data.get("id"),
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_file": raw_path,
            "content_hash_sha256": content_hash,
        })
        if verbose:
            print(f"  Manifold group '{slug}' → id={data.get('id')}", flush=True)
        return data.get("id")
    except Exception as exc:
        if "404" in str(exc) or "HTTP Error 404" in str(exc):
            if verbose:
                print(f"  Manifold group '{slug}' → 404 (not found), skipping.", flush=True)
        else:
            print(f"  [WARN] Manifold group '{slug}' fetch error: {exc}", flush=True)
        return None


def _fetch_markets_for_group(
    group_id: str,
    group_slug: str,
    manifest_entries: list[dict],
    verbose: bool,
) -> tuple[list[dict], bool]:
    """
    Paginate through all markets for a group using the `before` cursor.

    Args:
        group_id: Manifold group id.
        group_slug: Human-readable slug for logging/filenames.
        manifest_entries: Mutable list to append manifest records to.
        verbose: Print progress.

    Returns:
        Tuple of (list of raw market dicts, truncated_flag).
    """
    url = f"{MANIFOLD_API_BASE}/markets"
    all_markets: list[dict] = []
    before: str | None = None
    page = 1
    truncated = False

    while page <= MANIFOLD_MAX_PAGES:
        params: dict = {
            "groupId": group_id,
            "limit": MANIFOLD_PAGE_SIZE,
        }
        if before:
            params["before"] = before

        if verbose:
            print(f"    Manifold group={group_slug}: page {page} (before={before})...", flush=True)

        try:
            data = get_json_with_retry(url, params=params, sleep_before=MANIFOLD_RATE_SLEEP)
        except Exception as exc:
            print(f"  [ERROR] Manifold markets for group {group_slug} page {page}: {exc}", flush=True)
            break

        if not isinstance(data, list):
            print(f"  [WARN] Manifold markets response not a list for group {group_slug}: {type(data)}", flush=True)
            break

        label = f"markets_{group_slug}_page_{page:04d}"
        raw_path = _save_raw({"group_id": group_id, "group_slug": group_slug, "page": page, "before": before, "data": data}, label)
        content_hash = _sha256_file(raw_path)

        manifest_entries.append({
            "source": "manifold",
            "type": "markets_page",
            "group_id": group_id,
            "group_slug": group_slug,
            "page": page,
            "before_cursor": before,
            "items_in_page": len(data),
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_file": raw_path,
            "content_hash_sha256": content_hash,
        })

        all_markets.extend(data)

        if len(data) < MANIFOLD_PAGE_SIZE:
            # Last page
            break

        # Next cursor is the id of the last item
        before = data[-1].get("id")
        if not before:
            break

        page += 1
    else:
        truncated = True
        print(f"  [WARNING] Manifold group {group_slug}: hit MAX_PAGES={MANIFOLD_MAX_PAGES}. Results may be truncated.", flush=True)

    return all_markets, truncated


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_manifold_questions(
    verbose: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    """
    Fetch all resolved binary AI-progress markets from Manifold.

    For each AI group slug:
      - Look up group id.
      - Paginate through markets.
      - Filter for BINARY + resolved YES/NO + keyword match.
    De-duplicate by market id.

    Args:
        verbose: Print progress.

    Returns:
        Tuple of:
          - all_questions: List of normalised market dicts.
          - dropped: List of {qid, reason} for dropped markets.
          - manifest_entries: List of manifest dicts for the run manifest.
    """
    manifest_entries: list[dict] = []
    seen_ids: set[str] = set()
    all_questions: list[dict] = []
    dropped: list[dict] = []

    n_non_binary = 0
    n_ambiguous = 0
    n_not_ai = 0
    n_dedup = 0
    any_truncated = False

    for slug in MANIFOLD_AI_GROUP_SLUGS:
        group_id = _fetch_group_id(slug, manifest_entries, verbose)
        if group_id is None:
            continue

        raw_markets, truncated = _fetch_markets_for_group(group_id, slug, manifest_entries, verbose)
        if truncated:
            any_truncated = True

        if verbose:
            print(f"    Manifold group={slug}: {len(raw_markets)} raw markets fetched.", flush=True)

        for m in raw_markets:
            mid = m.get("id", "")

            # De-duplicate across groups
            if mid in seen_ids:
                n_dedup += 1
                continue
            seen_ids.add(mid)

            # Binary only
            if m.get("outcomeType") != "BINARY":
                n_non_binary += 1
                continue

            # Resolved only
            if not m.get("isResolved"):
                continue

            resolution = str(m.get("resolution", "") or "").upper()
            if resolution not in ("YES", "NO"):
                n_ambiguous += 1
                dropped.append({"qid": f"manifold_{mid}", "reason": f"resolution_{resolution.lower() or 'unknown'}"})
                continue

            norm = _normalise(m)

            # Keyword filter
            if not _is_ai_progress(norm["title"], norm["description"]):
                n_not_ai += 1
                continue

            all_questions.append(norm)

    if verbose:
        print(
            f"  Manifold summary: groups_tried={len(MANIFOLD_AI_GROUP_SLUGS)}, "
            f"dedup_dropped={n_dedup}, non_binary_dropped={n_non_binary}, "
            f"ambiguous_dropped={n_ambiguous}, not_ai_filtered={n_not_ai}, "
            f"ai_progress_binary={len(all_questions)}, truncated={any_truncated}",
            flush=True,
        )

    manifest_entries.append({
        "source": "manifold",
        "type": "summary",
        "groups_tried": len(MANIFOLD_AI_GROUP_SLUGS),
        "n_dedup_dropped": n_dedup,
        "n_non_binary_dropped": n_non_binary,
        "n_ambiguous_dropped": n_ambiguous,
        "n_not_ai_filtered": n_not_ai,
        "n_ai_progress_binary": len(all_questions),
        "truncated": any_truncated,
    })

    return all_questions, dropped, manifest_entries
