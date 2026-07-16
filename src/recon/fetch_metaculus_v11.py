"""
fetch_metaculus_v11.py — Fetch resolved binary AI-progress questions from Metaculus
using auth token (v1.1, 2026-07-16).

Endpoint: GET /api/posts/?statuses=resolved&question_type=binary&topic=ai
Auth: Token scheme in Authorization header (never in query params).
Pagination: cursor-based via 'next' URL field.

Key API findings (documented here for reproducibility):
  - The new /api/posts/ endpoint (auth required as of 2026-07-15) returns:
      resolved=True, status=resolved, actual_resolve_time (ISO-8601)
  - The question.resolution field is null for ALL resolved questions in this endpoint.
    This is a current Metaculus API limitation (version as of 2026-07-16).
  - The aggregation history (community prediction at time T) is also null/empty.
    Snapshot feasibility is heuristic only: question open ≥ 30d before resolution
    with nr_forecasters > 0.
  - For Phase 2, the resolution outcome will need to be retrieved via the website
    or a different endpoint when the API exposes it.

Auth: load from env_loader (never printed or written to tracked files).
"""

import json
import os
import hashlib
import re
from datetime import datetime, timezone

import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import (
    AI_PROGRESS_KEYWORDS,
    EXCLUSION_KEYWORDS,
    RAW_DIR,
    METACULUS_RATE_SLEEP,
    METACULUS_MAX_PAGES,
    KEYWORD_LIST_VERSION,
)
from http_utils import get_json_with_retry
from env_loader import require_key

# Metaculus new API base
METACULUS_NEW_API_BASE = "https://www.metaculus.com/api/posts/"

# Page size for the new API (100 is safe)
PAGE_SIZE = 100

# Topic slug that Metaculus uses for "Artificial Intelligence"
AI_TOPIC_SLUG = "ai"


def _is_ai_progress(title: str, description: str = "") -> bool:
    """Keyword-based AI-progress filter (v1.0) — same as other modules."""
    combined = (title + " " + description).lower()
    title_lower = title.lower()
    for excl in EXCLUSION_KEYWORDS:
        if excl.lower() in title_lower:
            return False
    for kw in AI_PROGRESS_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False


def _save_raw_page(page_data: dict, label: str) -> str:
    """Save a raw API response page to disk. Returns file path."""
    os.makedirs(RAW_DIR, exist_ok=True)
    safe_label = re.sub(r"[^a-zA-Z0-9_\-]", "_", label)[:80]
    path = os.path.join(RAW_DIR, f"metaculus_v11_{safe_label}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(page_data, fh, ensure_ascii=False, indent=2)
    return path


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalise(r: dict) -> dict:
    """
    Normalise a /api/posts/ result into the core schema.

    Note: resolution (yes/no) is null in the current API; we can only confirm
    the question is resolved (resolved=True) and binary (question.type=binary).
    Resolution outcome must be obtained separately in Phase 2.

    Args:
        r: Raw post dict from /api/posts/.

    Returns:
        Normalised flat dict.
    """
    q = r.get("question", {}) or {}
    post_id = str(r.get("id", ""))
    title = q.get("title", "") or r.get("title", "") or ""
    description = (q.get("description") or q.get("resolution_criteria") or "")
    if not isinstance(description, str):
        description = json.dumps(description)[:500]
    description = str(description)[:500]

    created_at = r.get("created_at") or q.get("created_at") or ""
    open_time = q.get("open_time") or r.get("open_time") or created_at
    actual_close_time = q.get("actual_close_time") or ""
    actual_resolve_time = q.get("actual_resolve_time") or ""

    # resolution field is null in the new API — documented limitation
    resolution_raw = q.get("resolution")  # will be None
    nr_forecasters = r.get("nr_forecasters") or 0

    # Projects: check for AI topic
    projects = r.get("projects", {}) or {}
    topics = projects.get("topic", []) or []
    topic_slugs = [t.get("slug", "") for t in topics if isinstance(t, dict)]

    return {
        "qid": f"metaculus_{post_id}",
        "source": "metaculus",
        "title": title,
        "description": description,
        "created_at": created_at,
        "open_time": open_time,
        "close_at": actual_close_time,
        "resolved_at": actual_resolve_time,
        "resolution_raw": resolution_raw,  # null — API limitation
        "outcome": None,  # null — API limitation; populate in Phase 2
        "url": f"https://www.metaculus.com/questions/{post_id}/",
        "nr_forecasters": nr_forecasters,
        "prediction_count": nr_forecasters,  # best proxy available
        "topic_slugs": topic_slugs,
        "resolved": r.get("resolved", False),
    }


def fetch_metaculus_questions_v11(
    verbose: bool = True,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Fetch all resolved binary AI-progress questions from Metaculus via the new /api/posts/ endpoint.

    Strategy:
      1. GET /api/posts/?statuses=resolved&question_type=binary&topic=ai (pre-filter on AI topic)
      2. Paginate with cursor from 'next' field.
      3. Apply keyword filter on title + description as a second pass.
      4. Note: resolution (yes/no) is null in current API; outcome=None for all records.

    Auth: Authorization: Token <METACULUS_API_TOKEN> (from env_loader; never logged).

    Args:
        verbose: Print progress to stdout.

    Returns:
        Tuple of (questions list, dropped list, manifest entries list).
    """
    token = require_key("METACULUS_API_TOKEN")
    auth_header = f"Token {token}"

    all_questions: list[dict] = []
    dropped: list[dict] = []
    manifest_entries: list[dict] = []
    truncated = False

    n_not_ai = 0
    n_non_binary = 0
    n_not_resolved = 0
    total_raw = 0

    # Initial URL
    next_url = (
        f"{METACULUS_NEW_API_BASE}"
        f"?limit={PAGE_SIZE}&statuses=resolved&question_type=binary&topic={AI_TOPIC_SLUG}"
        f"&order_by=-actual_resolve_time"
    )
    page = 1

    while next_url and page <= METACULUS_MAX_PAGES:
        if verbose:
            print(f"  Metaculus v1.1: page {page} ...", flush=True)

        import time as _time
        if page > 1:
            _time.sleep(METACULUS_RATE_SLEEP)

        import urllib.request as _urllib_req
        import urllib.error as _urllib_err

        try:
            req = _urllib_req.Request(
                next_url,
                headers={
                    "Authorization": auth_header,
                    "Accept": "application/json",
                    "User-Agent": "forecasting-ai-progress-recon/1.1",
                },
            )
            with _urllib_req.urlopen(req, timeout=30) as resp:
                raw_bytes = resp.read()
            data = json.loads(raw_bytes)
        except _urllib_err.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and page < METACULUS_MAX_PAGES:
                wait = 8.0 * (2 ** min(page - 1, 3))
                print(f"  [retry] HTTP {exc.code}, waiting {wait:.0f}s", flush=True)
                _time.sleep(wait)
                continue
            else:
                print(f"  [ERROR] Metaculus v1.1 page {page}: HTTP {exc.code}", flush=True)
                break
        except Exception as exc:
            print(f"  [ERROR] Metaculus v1.1 page {page}: {exc}", flush=True)
            break

        results = data.get("results", [])
        fetched_at = datetime.now(timezone.utc).isoformat()

        # Save raw page (auth header is NOT saved — only params and counts)
        page_record = {
            "page": page,
            "url_params": next_url.split("?")[1] if "?" in next_url else "",
            "items": results,  # raw results
            "fetched_at": fetched_at,
        }
        raw_path = _save_raw_page(page_record, f"resolved_binary_ai_page_{page:04d}")
        content_hash = _sha256_file(raw_path)

        manifest_entries.append({
            "source": "metaculus_v11",
            "page": page,
            "endpoint": METACULUS_NEW_API_BASE,
            "params": {
                "statuses": "resolved",
                "question_type": "binary",
                "topic": AI_TOPIC_SLUG,
                "limit": PAGE_SIZE,
                "order_by": "-actual_resolve_time",
            },
            "items_in_page": len(results),
            "fetched_at_utc": fetched_at,
            "raw_file": raw_path,
            "content_hash_sha256": content_hash,
            "auth_scheme": "Token (header only; value not recorded)",
        })

        total_raw += len(results)

        for r in results:
            q = r.get("question", {}) or {}
            qtype = q.get("type", "")
            is_resolved = r.get("resolved", False)

            if not is_resolved:
                n_not_resolved += 1
                continue
            if qtype != "binary":
                n_non_binary += 1
                continue

            norm = _normalise(r)

            if not _is_ai_progress(norm["title"], norm["description"]):
                n_not_ai += 1
                continue

            all_questions.append(norm)

        # Break if page is empty (API returns next=non-null even past end)
        if len(results) == 0:
            if verbose:
                print(f"  Metaculus v1.1: empty page at {page}, stopping.", flush=True)
            break

        next_url = data.get("next")
        if not next_url:
            if verbose:
                print(f"  Metaculus v1.1: reached last page at {page}.", flush=True)
            break

        # Safety: if next_url loops or is malformed, break
        if page > 1 and not next_url.startswith("http"):
            print(f"  [WARN] Metaculus v1.1: malformed next URL: {next_url[:80]}", flush=True)
            break

        page += 1
    else:
        truncated = True
        print(f"  [WARNING] Metaculus v1.1: hit MAX_PAGES={METACULUS_MAX_PAGES}. Results may be truncated.", flush=True)

    if verbose:
        print(
            f"  Metaculus v1.1 summary: raw_fetched={total_raw}, "
            f"not_resolved_dropped={n_not_resolved}, non_binary_dropped={n_non_binary}, "
            f"not_ai_filtered={n_not_ai}, ai_progress_binary={len(all_questions)}, "
            f"truncated={truncated}",
            flush=True,
        )
        print(
            "  NOTE: question.resolution is null for ALL records (Metaculus API v2026-07-16 limitation). "
            "YES/NO outcomes must be retrieved separately in Phase 2.",
            flush=True,
        )

    manifest_entries.append({
        "source": "metaculus_v11",
        "type": "summary",
        "total_raw_fetched": total_raw,
        "n_not_resolved_dropped": n_not_resolved,
        "n_non_binary_dropped": n_non_binary,
        "n_not_ai_filtered": n_not_ai,
        "n_ai_progress_binary": len(all_questions),
        "truncated": truncated,
        "api_limitation": "question.resolution=null for all records; aggregation history=null for all records",
    })

    return all_questions, dropped, manifest_entries
