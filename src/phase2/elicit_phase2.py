"""
elicit_phase2.py — Step B: batched full-scale Phase-2 elicitation.

Runs protocol v2 (D-012, frozen) over all 1,187 questions × 3 panel models via
the Message Batches API.  Also runs a seeded 100-question variance probe on
sonnet-5 for repeats 1 and 2 (repeat 0 is from the main run).

Hard rules:
  - outcome and resolved_at NEVER interpolated into prompt text (asserted).
  - No silent failures: parse errors recorded, counted, reported.
  - Determinism: CSV rebuild from cache must be bit-identical (SHA-256 verified).
  - Cost estimate first; stop if projected > $25.
  - All model/token/USD costs appended to EXPERIMENTS.md.

Output:
  data/interim/phase2_forecasts.csv  — main dataset
  data/raw/phase2/elicit_batch_*.jsonl — raw batch results (provenance)
  manifest: step_b_elicitation section
"""

import csv
import hashlib
import io
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from phase2_config import (  # noqa
    PHASE2_QUESTIONS_PATH,
    PHASE2_MANIFEST_PATH,
    EXPERIMENTS_PATH,
    INTERIM_DIR,
    RAW_DIR,
    LLM_CACHE_DIR,
    PANEL_MODELS,
    TRAINING_CUTOFFS,
    MODEL_PRICING,
    BATCH_DISCOUNT,
    COST_STUDY_HARD_STOP_USD,
    SNAPSHOT_LEAD_DAYS,
    ANTHROPIC_API_BASE,
    ANTHROPIC_API_VERSION,
    ANTHROPIC_BATCH_BETA,
    BATCH_MAX_REQUESTS,
    BATCH_POLL_INTERVAL_S,
)
from env_loader import require_key  # noqa

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = "v2"
MAX_TOKENS       = 1000
PROB_MIN         = 0.01
PROB_MAX         = 0.99
VARIANCE_PROBE_N = 100
VARIANCE_SEED    = 42
VARIANCE_REPEATS = [1, 2]     # repeat 0 = main run
MAIN_REPEAT      = 0
TEMPERATURE_SUPPORTED = frozenset(["claude-haiku-4-5-20251001"])

PHASE2_FORECASTS_PATH = os.path.join(INTERIM_DIR, "phase2_forecasts.csv")
ELICIT_CACHE_DIR      = os.path.join(LLM_CACHE_DIR, "phase2_v2")
ELICIT_CHECKPOINT_DIR = os.path.join(INTERIM_DIR, "phase2_elicit_checkpoints")

# Model min_resolved thresholds for is_post_cutoff
_MIN_RESOLVED = {
    "claude-haiku-4-5-20251001": "2025-08-30",
    "claude-sonnet-5":           "2026-03-02",
    "claude-opus-4-8":           "2026-03-02",
}

# Frozen protocol v2 system prompt (verbatim from elicit_v2.py / D-012)
_SYSTEM_PROMPT_V2 = (
    "You are a calibrated probabilistic forecaster. "
    "For each question, first write 1–2 sentences of key considerations "
    "(include a base-rate anchor where it is natural; avoid Bayesian jargon). "
    "Then output a JSON object with a single key \"prob\" (float in [0.01, 0.99]). "
    "Example:\n"
    "Similar milestones have been reached roughly 35% of the time in comparable windows; "
    "current signals are mixed. "
    "{\"prob\": 0.32}"
)
_SYSTEM_PROMPT_HASH = hashlib.sha256(_SYSTEM_PROMPT_V2.encode()).hexdigest()


# ---------------------------------------------------------------------------
# User message builder (HARD RULE: never interpolates outcome or resolved_at)
# ---------------------------------------------------------------------------

def _build_user_message(title: str, description: str, T_str: str) -> str:
    """
    Build protocol-v2 user message from SAFE fields only.

    Args:
        title:       Question title (safe).
        description: Truncated description ≤600 chars (safe).
        T_str:       Snapshot date string YYYY-MM-DD = resolved_at - 30d (safe).
                     This is NOT resolved_at; it is 30 days earlier.

    Returns:
        User message string.
    """
    lines = [f"Question: {title}"]
    if description:
        lines.append(f"\nContext / Resolution criteria:\n{description}")
    if T_str:
        lines.append(
            f"\nAssume today is {T_str}. Use no information after this date."
        )
    lines.append(
        "\nWrite 1–2 sentences of key considerations "
        "(a base-rate anchor where natural), "
        "then output the JSON object {\"prob\": <float>} where <float> is in [0.01, 0.99]."
    )
    return "\n".join(lines)


def _extract_safe_fields(q: dict) -> dict:
    """
    Extract only the fields needed to build a user message.

    Deliberately excludes outcome and resolved_at from the returned dict
    so they cannot accidentally reach the prompt.

    Args:
        q: Question record with all fields.

    Returns:
        Dict with only title, description, and T_str.
        T_str is resolved_at - 30d formatted as YYYY-MM-DD.
        resolved_at is consumed here; it does not appear in the returned dict.
    """
    title = (q.get("title") or "").strip()
    description = (q.get("description") or "").strip()[:600]
    resolved_str = q.get("resolved_at", "")

    T_str = ""
    if resolved_str:
        try:
            s = resolved_str.replace("Z", "+00:00")
            resolved_dt = datetime.fromisoformat(s)
            if resolved_dt.tzinfo is None:
                resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
            T_dt = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
            T_str = T_dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # HARD ASSERTION: T_str must differ from resolved_at date (never leaks resolution date)
    if resolved_str and T_str:
        resolved_date = resolved_str[:10]
        assert T_str != resolved_date, (
            f"T_str equals resolved_at date — logic error for {q.get('qid')}"
        )

    return {"title": title, "description": description, "T_str": T_str}


def _make_user_message(q: dict) -> str:
    """Build protocol-v2 user message for question q, with leakage assertion."""
    safe = _extract_safe_fields(q)

    msg = _build_user_message(**safe)

    # HARD ASSERTION: neither 'outcome' nor 'resolved_at' raw string appears in prompt
    outcome = q.get("outcome")
    resolved_str = q.get("resolved_at", "")

    # outcome is 0 or 1 (int); check it doesn't appear as a resolution statement
    if outcome is not None:
        for leak in [f"resolved to {outcome}", f"outcome: {outcome}",
                     f'"outcome": {outcome}']:
            assert leak not in msg, (
                f"Outcome leakage detected in prompt for {q.get('qid')}: {leak!r}"
            )

    # resolved_at date must not appear literally (only T = resolved - 30d appears)
    if resolved_str and len(resolved_str) >= 10:
        resolved_date = resolved_str[:10]
        # Note: title/description may contain dates — we check only that resolved_date
        # is NOT equal to T_str (structural) and is not present as a "resolves on" phrase
        for leak in [f"resolves on {resolved_date}", f"resolved on {resolved_date}",
                     f"resolution date: {resolved_date}"]:
            assert leak not in msg, (
                f"resolved_at leakage in prompt for {q.get('qid')}: {leak!r}"
            )

    return msg


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(qid: str, model: str, repeat: int) -> str:
    """Deterministic cache key for (qid, model, phase2_v2, repeat)."""
    raw = f"{qid}|{model}|phase2_v2|{repeat}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path(qid: str, model: str, repeat: int) -> str:
    """Filesystem path for a phase2_v2 cached response."""
    os.makedirs(ELICIT_CACHE_DIR, exist_ok=True)
    key = _cache_key(qid, model, repeat)
    safe_model = model.replace("/", "_").replace(":", "_")
    return os.path.join(ELICIT_CACHE_DIR, f"p2v2_{safe_model}_{key}.json")


def _load_cache(qid: str, model: str, repeat: int) -> Optional[dict]:
    """Load cached elicitation record; return None if not cached."""
    path = _cache_path(qid, model, repeat)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save_cache(qid: str, model: str, repeat: int, record: dict) -> None:
    """Persist elicitation record to phase2_v2 cache."""
    with open(_cache_path(qid, model, repeat), "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False)


def _check_mvp_v2_cache(qid: str, model: str) -> Optional[dict]:
    """
    Check the MVP v2 cache for a possible cache hit (slice overlap reuse).

    The MVP v2 cache key uses seed=42 instead of repeat.
    """
    raw = f"{qid}|{model}|v2|42"
    key = hashlib.sha256(raw.encode()).hexdigest()[:32]
    safe_model = model.replace("/", "_").replace(":", "_")
    path = os.path.join(LLM_CACHE_DIR, f"mvp_v2_{safe_model}_{key}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


# ---------------------------------------------------------------------------
# Probability parsing
# ---------------------------------------------------------------------------

def _parse_prob(raw_text: str) -> Optional[float]:
    """
    Extract probability from protocol-v2 response text (reasoning + JSON).

    Scans left-to-right for first '{' that yields a valid {"prob": float}.

    Args:
        raw_text: Raw model output.

    Returns:
        Clamped float in [0.01, 0.99], or None on parse failure.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    for i, ch in enumerate(text):
        if ch != "{":
            continue
        for end in range(len(text), i, -1):
            try:
                obj = json.loads(text[i:end])
                val = obj.get("prob")
                if val is not None:
                    return float(max(PROB_MIN, min(PROB_MAX, float(val))))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def _cost_usd(model: str, in_tok: int, out_tok: int, batch: bool = True) -> float:
    """USD cost for given token counts, with optional batch discount."""
    prices = MODEL_PRICING.get(model, {"input": 5.0, "output": 25.0})
    factor = BATCH_DISCOUNT if batch else 1.0
    return factor * (
        in_tok * prices["input"] + out_tok * prices["output"]
    ) / 1_000_000


def estimate_total_cost(n_q: int) -> dict:
    """
    Estimate total USD cost for Phase-2 elicitation.

    Conservative estimate: 450 input tokens, 120 output tokens per question per model.
    Variance probe adds 100q × sonnet × 2 extra repeats.

    Args:
        n_q: Number of questions (1187).

    Returns:
        Dict with per-model and total estimates.
    """
    est_in, est_out = 450, 120
    costs = {}
    total = 0.0
    for model in PANEL_MODELS:
        c = _cost_usd(model, n_q * est_in, n_q * est_out, batch=True)
        costs[model] = c
        total += c
    # variance probe: 100q × sonnet × 2 extra repeats
    probe_c = _cost_usd("claude-sonnet-5",
                        VARIANCE_PROBE_N * est_in * len(VARIANCE_REPEATS),
                        VARIANCE_PROBE_N * est_out * len(VARIANCE_REPEATS),
                        batch=True)
    costs["variance_probe_sonnet"] = probe_c
    total += probe_c
    costs["total"] = total
    return costs


# ---------------------------------------------------------------------------
# Anthropic Batch API helpers
# ---------------------------------------------------------------------------

def _headers(api_key: str) -> dict:
    return {
        "x-api-key":         api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "anthropic-beta":    ANTHROPIC_BATCH_BETA,
        "content-type":      "application/json",
        "accept":            "application/json",
    }


def _post_json(url: str, body: dict, api_key: str) -> dict:
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers=_headers(api_key), method="POST"
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body_txt = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in (429, 500, 502, 503, 529) and attempt < 3:
                wait = 10 * (2 ** attempt)
                print(f"  [retry {attempt+1}] HTTP {exc.code}, wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"POST {url} HTTP {exc.code}: {body_txt}") from exc
    raise RuntimeError(f"Max retries exceeded for {url}")


def _get_json(url: str, api_key: str) -> dict:
    req = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body_txt = exc.read().decode("utf-8", errors="replace")[:200]
            if exc.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(10 * (2 ** attempt))
                continue
            raise RuntimeError(f"GET {url} HTTP {exc.code}: {body_txt}") from exc
    raise RuntimeError(f"Max retries exceeded for GET {url}")


def _submit_batch(questions: list, model: str, repeat: int, api_key: str) -> str:
    """Submit a Message Batches job. Returns batch_id."""
    requests_payload = []
    for q in questions:
        qid = q["qid"]
        user_msg = _make_user_message(q)  # hard assertion inside
        params: dict = {
            "model":      model,
            "max_tokens": MAX_TOKENS,
            "system":     _SYSTEM_PROMPT_V2,
            "messages":   [{"role": "user", "content": user_msg}],
        }
        if model in TEMPERATURE_SUPPORTED:
            params["temperature"] = 0
        requests_payload.append({
            "custom_id": f"{qid}__r{repeat}",
            "params":    params,
        })

    if len(requests_payload) > BATCH_MAX_REQUESTS:
        raise RuntimeError(
            f"Batch size {len(requests_payload)} exceeds limit {BATCH_MAX_REQUESTS}"
        )

    print(f"  Submitting {len(requests_payload)} requests for {model} repeat={repeat}...",
          flush=True)
    url = f"{ANTHROPIC_API_BASE}/messages/batches"
    resp = _post_json(url, {"requests": requests_payload}, api_key)
    batch_id = resp["id"]
    print(f"  Batch submitted: {batch_id} status={resp.get('processing_status')}",
          flush=True)
    return batch_id


def _poll_batch(batch_id: str, api_key: str) -> None:
    """Poll batch until processing_status == 'ended'.

    Retries up to 5 times on transient network errors (OSError/URLError)
    with a 30-second backoff before raising.
    """
    import urllib.error as _ue
    url = f"{ANTHROPIC_API_BASE}/messages/batches/{batch_id}"
    poll_n = 0
    while True:
        net_retries = 0
        while True:
            try:
                status = _get_json(url, api_key)
                break
            except (_ue.URLError, OSError) as exc:
                net_retries += 1
                if net_retries > 5:
                    raise RuntimeError(
                        f"Network unreachable after 5 retries polling {batch_id}"
                    ) from exc
                print(
                    f"  [poll {poll_n}] network error ({exc}); retry {net_retries}/5 in 30s",
                    flush=True,
                )
                time.sleep(30)
        ps = status.get("processing_status", "unknown")
        counts = status.get("request_counts", {})
        print(
            f"  [poll {poll_n}] {batch_id[:20]} status={ps} "
            f"succeeded={counts.get('succeeded','?')} "
            f"errored={counts.get('errored','?')} "
            f"processing={counts.get('processing','?')}",
            flush=True,
        )
        if ps == "ended":
            return
        if ps not in ("in_progress", "canceling"):
            raise RuntimeError(f"Unexpected batch status: {ps}")
        poll_n += 1
        time.sleep(BATCH_POLL_INTERVAL_S)


def _retrieve_batch_results(batch_id: str, api_key: str) -> list:
    """Retrieve JSONL results from completed batch."""
    url = f"{ANTHROPIC_API_BASE}/messages/batches/{batch_id}/results"
    req = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    results = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line = line.decode("utf-8").strip()
            if line:
                results.append(json.loads(line))
    return results


def _save_raw_jsonl(batch_id: str, model: str, repeat: int, results: list) -> None:
    """Save raw batch results to data/raw/phase2/ for provenance."""
    os.makedirs(RAW_DIR, exist_ok=True)
    safe_model = model.replace("/", "_").replace(":", "_").replace("-", "_")
    path = os.path.join(
        RAW_DIR, f"elicit_batch_{batch_id}_{safe_model}_r{repeat}_results.jsonl"
    )
    with open(path, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Raw results saved: {path}", flush=True)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _ckpt_path(model: str, repeat: int) -> str:
    os.makedirs(ELICIT_CHECKPOINT_DIR, exist_ok=True)
    safe = model.replace("/", "_").replace(":", "_").replace("-", "_")
    return os.path.join(ELICIT_CHECKPOINT_DIR, f"batch_{safe}_r{repeat}.json")


def _load_ckpt(model: str, repeat: int) -> Optional[str]:
    path = _ckpt_path(model, repeat)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("batch_id")
    return None


def _save_ckpt(model: str, repeat: int, batch_id: str) -> None:
    with open(_ckpt_path(model, repeat), "w", encoding="utf-8") as fh:
        json.dump({"batch_id": batch_id, "model": model, "repeat": repeat,
                   "submitted_at": datetime.now(timezone.utc).isoformat()}, fh)


def _delete_ckpt(model: str, repeat: int) -> None:
    path = _ckpt_path(model, repeat)
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Single batch run (one model × one repeat)
# ---------------------------------------------------------------------------

def run_one_batch(
    questions: list,
    model: str,
    repeat: int,
    api_key: str,
) -> dict:
    """
    Run Batch API elicitation for one model × one repeat value.

    Checks phase2_v2 cache first, then MVP v2 cache (repeat=0 only).
    Submits uncached questions to Batch API.
    Parses results, caches each, returns aggregate stats.

    Args:
        questions: List of question dicts.
        model: Anthropic model ID.
        repeat: 0 for main run; 1+ for variance probe.
        api_key: Anthropic API key.

    Returns:
        Dict: input_tokens, output_tokens, cost_usd, n_cache, n_new, n_parse_err, batch_id
    """
    print(f"\n  --- {model} repeat={repeat} ({len(questions)} questions) ---", flush=True)

    # --- Step 1: load phase2_v2 cache ---
    to_classify = []
    n_cache = 0
    n_mvp_reuse = 0
    for q in questions:
        qid = q["qid"]
        if _load_cache(qid, model, repeat) is not None:
            n_cache += 1
            continue

        # Repeat=0 only: check MVP v2 cache for slice-overlap reuse
        if repeat == MAIN_REPEAT:
            mvp = _check_mvp_v2_cache(qid, model)
            if mvp is not None and mvp.get("model_prob") is not None:
                # Translate MVP v2 record into phase2 cache format
                record = {
                    "qid":              qid,
                    "model":            model,
                    "repeat":           repeat,
                    "protocol_version": PROTOCOL_VERSION,
                    "model_prob":       mvp.get("model_prob"),
                    "parse_error":      mvp.get("parse_error", False),
                    "is_refusal":       mvp.get("is_refusal", False),
                    "stop_reason":      mvp.get("stop_reason", ""),
                    "raw_text":         mvp.get("raw_text", "")[:600],
                    "input_tokens":     mvp.get("input_tokens", 0),
                    "output_tokens":    mvp.get("output_tokens", 0),
                    "usd":              mvp.get("usd", 0.0),
                    "cache_hit":        True,
                    "mvp_v2_reuse":     True,
                    "elicited_at_utc":  mvp.get("elicited_at_utc"),
                }
                _save_cache(qid, model, repeat, record)
                n_mvp_reuse += 1
                continue

        to_classify.append(q)

    print(f"    cache={n_cache} mvp_reuse={n_mvp_reuse} to_classify={len(to_classify)}",
          flush=True)

    if not to_classify:
        return {
            "batch_id": None, "input_tokens": 0, "output_tokens": 0,
            "cost_usd": 0.0, "n_cache": n_cache + n_mvp_reuse,
            "n_new": 0, "n_parse_err": 0,
        }

    # --- Step 2: submit/resume batch ---
    batch_id = _load_ckpt(model, repeat)
    if batch_id:
        print(f"    Resuming batch {batch_id} from checkpoint.", flush=True)
    else:
        batch_id = _submit_batch(to_classify, model, repeat, api_key)
        _save_ckpt(model, repeat, batch_id)

    _poll_batch(batch_id, api_key)
    print(f"    Batch ended. Retrieving results...", flush=True)
    raw_results = _retrieve_batch_results(batch_id, api_key)
    _save_raw_jsonl(batch_id, model, repeat, raw_results)
    _delete_ckpt(model, repeat)

    # --- Step 3: parse and cache ---
    total_in = total_out = n_new = n_parse_err = 0
    ts = datetime.now(timezone.utc).isoformat()

    for entry in raw_results:
        custom_id = entry.get("custom_id", "")
        qid = custom_id.rsplit("__r", 1)[0]  # strip "__rN" repeat suffix
        result = entry.get("result", {})
        rtype = result.get("type", "unknown")

        if rtype == "errored":
            error = result.get("error", {})
            print(f"    [BATCH_ERR] {qid}: {error}", flush=True)
            record = {
                "qid": qid, "model": model, "repeat": repeat,
                "protocol_version": PROTOCOL_VERSION,
                "model_prob": None, "parse_error": True, "is_refusal": False,
                "stop_reason": "batch_error",
                "raw_text": f"batch_error: {error.get('type', 'unknown')}",
                "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                "cache_hit": False, "elicited_at_utc": ts,
            }
            n_parse_err += 1
            _save_cache(qid, model, repeat, record)
            continue

        message = result.get("message", {})
        raw_text = ""
        for block in message.get("content", []):
            if block.get("type") == "text":
                raw_text = block.get("text", "")
                break

        usage = message.get("usage", {})
        in_tok  = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        total_in  += in_tok
        total_out += out_tok

        stop_reason = message.get("stop_reason", "unknown")
        is_refusal  = (stop_reason == "refusal")
        prob = None if is_refusal else _parse_prob(raw_text)
        is_parse_err = (prob is None and not is_refusal)

        if is_parse_err:
            n_parse_err += 1
            print(f"    [PARSE_ERR] {qid}: raw={raw_text[:60]!r}", flush=True)

        record = {
            "qid":              qid,
            "model":            model,
            "repeat":           repeat,
            "protocol_version": PROTOCOL_VERSION,
            "model_prob":       prob,
            "parse_error":      is_parse_err,
            "is_refusal":       is_refusal,
            "stop_reason":      stop_reason,
            "raw_text":         raw_text[:600],
            "input_tokens":     in_tok,
            "output_tokens":    out_tok,
            "usd":              _cost_usd(model, in_tok, out_tok, batch=True),
            "cache_hit":        False,
            "mvp_v2_reuse":     False,
            "elicited_at_utc":  ts,
        }
        _save_cache(qid, model, repeat, record)
        n_new += 1

    actual_cost = _cost_usd(model, total_in, total_out, batch=True)
    print(
        f"    Done: new={n_new} parse_err={n_parse_err} "
        f"in={total_in} out={total_out} cost=${actual_cost:.4f}",
        flush=True,
    )
    return {
        "batch_id":     batch_id,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cost_usd":     actual_cost,
        "n_cache":      n_cache + n_mvp_reuse,
        "n_new":        n_new,
        "n_parse_err":  n_parse_err,
    }


# ---------------------------------------------------------------------------
# CSV builder
# ---------------------------------------------------------------------------

def _is_post_cutoff(resolved_at: str, model: str) -> int:
    """Return 1 if resolved_at >= model's min_resolved threshold."""
    min_res = _MIN_RESOLVED.get(model, "9999-01-01")
    return 1 if resolved_at >= min_res else 0


def build_csv(questions: list, all_records: list, path: str) -> str:
    """
    Build phase2_forecasts.csv from question records and elicitation records.

    Args:
        questions: List of all question dicts (with D-014 flags).
        all_records: Flat list of elicitation result dicts.
        path: Output CSV path.

    Returns:
        SHA-256 of the written file bytes.
    """
    qid_map = {q["qid"]: q for q in questions}

    fieldnames = [
        "qid", "source", "title_hash", "resolved_at", "outcome",
        "crowd_prob_at_T", "model", "model_prob", "repeat",
        "close_before_cutoff_haiku", "close_before_cutoff_jan2026",
        "close_before_T", "is_post_cutoff",
        "elicited_at", "cache_hit", "parse_error", "protocol",
    ]

    rows = []
    for rec in all_records:
        qid = rec["qid"]
        q = qid_map.get(qid, {})
        title = (q.get("title") or "").strip()
        title_hash = hashlib.sha256(title.encode()).hexdigest()[:16]
        model = rec["model"]
        row = {
            "qid":                         qid,
            "source":                      q.get("source", "manifold"),
            "title_hash":                  title_hash,
            "resolved_at":                 q.get("resolved_at", ""),
            "outcome":                     q.get("outcome", ""),
            "crowd_prob_at_T":             q.get("crowd_prob_at_T", ""),
            "model":                       model,
            "model_prob":                  rec.get("model_prob", ""),
            "repeat":                      rec.get("repeat", 0),
            "close_before_cutoff_haiku":   int(q.get("close_before_cutoff_haiku", False)),
            "close_before_cutoff_jan2026": int(q.get("close_before_cutoff_jan2026", False)),
            "close_before_T":              int(q.get("close_before_T", False)),
            "is_post_cutoff":              _is_post_cutoff(q.get("resolved_at", ""), model),
            "elicited_at":                 rec.get("elicited_at_utc", ""),
            "cache_hit":                   int(rec.get("cache_hit", False)
                                               or rec.get("mvp_v2_reuse", False)),
            "parse_error":                 int(rec.get("parse_error", False)),
            "protocol":                    PROTOCOL_VERSION,
        }
        rows.append(row)

    # Sort deterministically: qid, model, repeat
    rows.sort(key=lambda r: (r["qid"], r["model"], r["repeat"]))

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_text = buf.getvalue()

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(csv_text)

    return hashlib.sha256(csv_text.encode("utf-8")).hexdigest()


def rebuild_csv_from_cache(questions: list, probe_questions: list, path: str) -> str:
    """
    Rebuild CSV from cache only (no API calls) — determinism check.

    Returns SHA-256 of rebuilt CSV text.
    """
    all_records = []
    for q in questions:
        for model in PANEL_MODELS:
            rec = _load_cache(q["qid"], model, MAIN_REPEAT)
            if rec:
                all_records.append(rec)
    # Variance probe repeats
    for q in probe_questions:
        for repeat in VARIANCE_REPEATS:
            rec = _load_cache(q["qid"], "claude-sonnet-5", repeat)
            if rec:
                all_records.append(rec)

    return build_csv(questions, all_records, path)


# ---------------------------------------------------------------------------
# EXPERIMENTS.md update
# ---------------------------------------------------------------------------

def _append_experiments(model_stats: dict, probe_stats: dict,
                        running_total: float) -> float:
    """Append per-model elicitation rows to EXPERIMENTS.md."""
    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    reg_marker  = "| _example_ | 2026-01-01"
    cost_marker = "| _example_ | claude-sonnet"

    def _cost_block_suffix(content: str) -> str:
        return content.split("## Cost ledger")[1] if "## Cost ledger" in content else content

    new_total = running_total
    run_rows = []
    cost_rows = []

    for model, stats in model_stats.items():
        usd = stats.get("cost_usd", 0.0)
        new_total += usd
        rid = f"phase2-elicit-{model.split('-')[1][:6]}-2026-07-16"
        run_rows.append(
            f"| {rid} | 2026-07-16 | 2 | elicitation | src/phase2/elicit_phase2.py@HEAD "
            f"| 42 | {model} | 1187 | data/interim/phase2_forecasts.csv "
            f"| Phase-2 v2 elicitation: n_new={stats.get('n_new',0)} "
            f"cache={stats.get('n_cache',0)} parse_err={stats.get('n_parse_err',0)} |"
        )
        cost_rows.append(
            f"| {rid} | {model} "
            f"| {stats.get('input_tokens',0):,} | {stats.get('output_tokens',0):,} "
            f"| yes | no | {usd:.4f} | {new_total:.4f} |"
        )

    # Variance probe
    if probe_stats:
        usd = probe_stats.get("cost_usd", 0.0)
        new_total += usd
        rid = "phase2-elicit-probe-2026-07-16"
        run_rows.append(
            f"| {rid} | 2026-07-16 | 2 | elicitation | src/phase2/elicit_phase2.py@HEAD "
            f"| 42 | claude-sonnet-5 | {VARIANCE_PROBE_N * len(VARIANCE_REPEATS)} "
            f"| data/interim/phase2_forecasts.csv "
            f"| Variance probe 100q sonnet-5 repeats 1+2 |"
        )
        cost_rows.append(
            f"| {rid} | claude-sonnet-5 "
            f"| {probe_stats.get('input_tokens',0):,} | {probe_stats.get('output_tokens',0):,} "
            f"| yes | no | {usd:.4f} | {new_total:.4f} |"
        )

    if reg_marker in content:
        insert = "\n".join(run_rows) + "\n" + reg_marker
        content = content.replace(reg_marker, insert)

    cost_suffix = _cost_block_suffix(content)
    if cost_marker in cost_suffix:
        insert = "\n".join(cost_rows) + "\n" + cost_marker
        content = content.replace(cost_marker, insert)

    old_total_str = f"**Running total: USD {running_total:.4f}**"
    new_total_str = f"**Running total: USD {new_total:.4f}**"
    content = content.replace(old_total_str, new_total_str)

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
    print("Phase-2 Step B — batched elicitation (protocol v2)", flush=True)
    print(f"  timestamp={datetime.now(timezone.utc).isoformat()}", flush=True)
    print("=" * 60, flush=True)

    api_key = require_key("ANTHROPIC_API_KEY")

    # --- Load questions ---
    with open(PHASE2_QUESTIONS_PATH, encoding="utf-8") as fh:
        questions = json.load(fh)
    print(f"\n[0] Loaded {len(questions)} questions", flush=True)

    # --- Cost estimate ---
    print("\n[1] Cost estimate...", flush=True)
    est = estimate_total_cost(len(questions))
    for k, v in est.items():
        print(f"    {k}: ${v:.3f}", flush=True)
    if est["total"] > COST_STUDY_HARD_STOP_USD:
        raise RuntimeError(
            f"STOP: projected cost ${est['total']:.2f} exceeds "
            f"guardrail ${COST_STUDY_HARD_STOP_USD:.2f}"
        )
    print(f"  Projected total: ${est['total']:.3f} — within guardrail", flush=True)

    # --- Main elicitation: 1187q × 3 models ---
    print("\n[2] Main elicitation (1187q × 3 models, repeat=0)...", flush=True)
    model_stats = {}
    batch_ids = {}

    for model in PANEL_MODELS:
        stats = run_one_batch(questions, model, MAIN_REPEAT, api_key)
        model_stats[model] = stats
        if stats["batch_id"]:
            batch_ids[f"{model}|r0"] = stats["batch_id"]

    # --- Variance probe: 100q × sonnet-5 × repeats 1, 2 ---
    print("\n[3] Variance probe (100q × sonnet-5 × repeats 1+2)...", flush=True)
    rng = random.Random(VARIANCE_SEED)
    probe_questions = rng.sample(questions, VARIANCE_PROBE_N)
    probe_questions.sort(key=lambda q: q["qid"])  # deterministic order

    probe_combined = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                      "n_cache": 0, "n_new": 0, "n_parse_err": 0}
    for repeat in VARIANCE_REPEATS:
        stats = run_one_batch(probe_questions, "claude-sonnet-5", repeat, api_key)
        for k in ("input_tokens", "output_tokens", "cost_usd", "n_cache",
                  "n_new", "n_parse_err"):
            probe_combined[k] += stats.get(k, 0)
        if stats["batch_id"]:
            batch_ids[f"claude-sonnet-5|r{repeat}"] = stats["batch_id"]

    # --- Collect all records from cache ---
    print("\n[4] Collecting all cached records...", flush=True)
    all_records = []
    n_missing = 0
    for q in questions:
        for model in PANEL_MODELS:
            rec = _load_cache(q["qid"], model, MAIN_REPEAT)
            if rec:
                all_records.append(rec)
            else:
                n_missing += 1
                print(f"  [WARN] missing cache: {q['qid']} {model} r=0", flush=True)

    for q in probe_questions:
        for repeat in VARIANCE_REPEATS:
            rec = _load_cache(q["qid"], "claude-sonnet-5", repeat)
            if rec:
                all_records.append(rec)
            else:
                n_missing += 1
                print(f"  [WARN] missing cache: {q['qid']} sonnet-5 r={repeat}", flush=True)

    print(f"  Total records collected: {len(all_records)} | missing: {n_missing}", flush=True)

    # --- Build CSV ---
    print("\n[5] Building phase2_forecasts.csv...", flush=True)
    csv_sha256 = build_csv(questions, all_records, PHASE2_FORECASTS_PATH)
    print(f"  CSV written: {PHASE2_FORECASTS_PATH}", flush=True)
    print(f"  CSV SHA-256: {csv_sha256}", flush=True)

    # --- Determinism check: rebuild from cache ---
    print("\n[6] Determinism check — rebuilding CSV from cache...", flush=True)
    rebuild_path = PHASE2_FORECASTS_PATH + ".rebuild"
    rebuild_sha256 = rebuild_csv_from_cache(questions, probe_questions, rebuild_path)
    if rebuild_sha256 == csv_sha256:
        print(f"  [PASS] rebuild SHA-256 matches: {rebuild_sha256[:16]}...", flush=True)
        os.remove(rebuild_path)
    else:
        raise AssertionError(
            f"Determinism FAIL: original={csv_sha256[:16]} rebuild={rebuild_sha256[:16]}"
        )

    # --- Update manifest ---
    print("\n[7] Updating manifest...", flush=True)
    with open(PHASE2_MANIFEST_PATH, encoding="utf-8") as fh:
        manifest = json.load(fh)

    total_main_cost = sum(s.get("cost_usd", 0) for s in model_stats.values())
    total_main_in   = sum(s.get("input_tokens", 0) for s in model_stats.values())
    total_main_out  = sum(s.get("output_tokens", 0) for s in model_stats.values())

    manifest["step_b_elicitation"] = {
        "protocol_version":    PROTOCOL_VERSION,
        "system_prompt_hash":  _SYSTEM_PROMPT_HASH,
        "n_questions":         len(questions),
        "panel_models":        PANEL_MODELS,
        "batch_ids":           batch_ids,
        "timestamp_utc":       datetime.now(timezone.utc).isoformat(),
        "main_run": {
            "n_questions": len(questions),
            "total_input_tokens":  total_main_in,
            "total_output_tokens": total_main_out,
            "total_cost_usd":      total_main_cost,
            "per_model":           {
                m: {
                    "n_new":      s.get("n_new", 0),
                    "n_cache":    s.get("n_cache", 0),
                    "n_parse_err": s.get("n_parse_err", 0),
                    "cost_usd":   s.get("cost_usd", 0.0),
                }
                for m, s in model_stats.items()
            },
        },
        "variance_probe": {
            "n_questions":    VARIANCE_PROBE_N,
            "model":          "claude-sonnet-5",
            "repeats":        VARIANCE_REPEATS,
            "seed":           VARIANCE_SEED,
            "n_new":          probe_combined["n_new"],
            "n_parse_err":    probe_combined["n_parse_err"],
            "cost_usd":       probe_combined["cost_usd"],
        },
        "artifacts": {
            "phase2_forecasts_csv": {
                "path":         "data/interim/phase2_forecasts.csv",
                "n_rows":       len(all_records),
                "sha256_text":  csv_sha256,
                "determinism":  "PASS — rebuild from cache bit-identical",
            }
        },
    }
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()

    with open(PHASE2_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f"  Manifest updated.", flush=True)

    # --- EXPERIMENTS.md ---
    print("\n[8] Updating EXPERIMENTS.md...", flush=True)
    running_total = _read_running_total()
    new_total = _append_experiments(model_stats, probe_combined, running_total)
    print(f"  Running total: ${running_total:.4f} → ${new_total:.4f}", flush=True)

    # --- Summary ---
    print("\n" + "=" * 60, flush=True)
    print("Phase-2 Step B COMPLETE", flush=True)
    n_success = n_parse_err = n_refusal = 0
    for rec in all_records:
        if rec.get("is_refusal"):
            n_refusal += 1
        elif rec.get("parse_error"):
            n_parse_err += 1
        elif rec.get("model_prob") is not None:
            n_success += 1

    print(f"  Total records: {len(all_records)}", flush=True)
    print(f"  n_success:     {n_success}", flush=True)
    print(f"  n_parse_err:   {n_parse_err}", flush=True)
    print(f"  n_refusal:     {n_refusal}", flush=True)
    for model, stats in model_stats.items():
        print(f"  {model[:30]}: cost=${stats.get('cost_usd',0):.4f} "
              f"parse_err={stats.get('n_parse_err',0)}", flush=True)
    print(f"  Probe sonnet-5 r1+r2: cost=${probe_combined['cost_usd']:.4f} "
          f"parse_err={probe_combined['n_parse_err']}", flush=True)
    print(f"  CSV SHA-256: {csv_sha256}", flush=True)
    print(f"  Determinism: PASS", flush=True)
    print(f"  EXPERIMENTS total: ${new_total:.4f}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
