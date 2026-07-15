"""
http_utils.py — Thin wrapper around urllib for polite, retrying HTTP GET.
Uses only stdlib (urllib); no requests dependency.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Any


def get_json(url: str, params: dict | None = None, sleep_before: float = 0.0) -> Any:
    """
    Fetch a JSON endpoint via HTTP GET.

    Args:
        url: The base URL.
        params: Optional query-string parameters (will be URL-encoded).
        sleep_before: Seconds to sleep before the request (rate-limiting).

    Returns:
        Parsed JSON (dict or list).

    Raises:
        urllib.error.HTTPError: On 4xx/5xx responses.
        ValueError: If the response body is not valid JSON.
    """
    if sleep_before > 0:
        time.sleep(sleep_before)

    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "forecasting-ai-progress-recon/0.1 (research; contact boztepe.batuhan12363@gmail.com)",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()

    return json.loads(raw)


def get_json_with_retry(
    url: str,
    params: dict | None = None,
    sleep_before: float = 0.0,
    max_retries: int = 3,
    backoff_base: float = 4.0,
) -> Any:
    """
    Like get_json but retries on 429 / 5xx with exponential back-off.

    Args:
        url: Base URL.
        params: Query parameters.
        sleep_before: Polite sleep before first attempt.
        max_retries: Maximum retry attempts after the first failure.
        backoff_base: Base for exponential back-off (seconds * 2^attempt).

    Returns:
        Parsed JSON.

    Raises:
        urllib.error.HTTPError: If retries are exhausted.
    """
    attempt = 0
    while True:
        try:
            return get_json(url, params=params, sleep_before=sleep_before if attempt == 0 else 0)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = backoff_base * (2 ** attempt)
                print(f"  [retry] HTTP {exc.code} on {url[:80]}... — waiting {wait:.0f}s (attempt {attempt+1}/{max_retries})", flush=True)
                time.sleep(wait)
                attempt += 1
            else:
                raise
