"""
elicit_v2.py — Elicitation protocol v2 for the Phase-1 plumbing-check re-run (D-012).

Protocol v2 (frozen per D-012 2026-07-16):
  System: calibrated forecaster; writes 1–2 sentences of key considerations
          (base-rate anchor where natural; no Bayesian jargon), then JSON.
  User: same structure as v1 — title + description (≤600 chars) + "Assume today is T,
        use no information after T." + instruction to write reasoning then JSON.
  Same JSON output contract as v1: {"prob": float} in [0.01, 0.99].
  temperature=0 where accepted (haiku); omitted elsewhere (sonnet-5, opus-4-8).
  No thinking parameter.
  max_tokens=1000 (same as v1).
  Probability clamp [0.01, 0.99] (same as v1).

Cache key: sha256(qid|model|v2|seed)[:32]
Cache files: data/llm_cache/mvp_v2_{model}_{key}.json  (NEVER overwrites v1 files)
"""

import json
import os
import hashlib
import time
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mvp_config import (
    ELICITATION_PROTOCOL_VERSION_V2,
    SNAPSHOT_LEAD_DAYS,
    PANEL_MODELS,
    TEMPERATURE_SUPPORTED_MODELS,
    MODEL_PRICING,
    COST_HARD_STOP_USD,
    MAX_TOKENS,
    PROB_MIN,
    PROB_MAX,
    RANDOM_SEED,
    LLM_CACHE_DIR,
    ANTHROPIC_MESSAGES_URL,
    ANTHROPIC_API_VERSION,
)
from env_loader import require_key


# ------------------------------------------------------------------ #
# Protocol v2 prompts (frozen; do NOT modify — provenance)
# ------------------------------------------------------------------ #

# D-012 spec: "1–2 sentences of key considerations (base-rate anchor where natural);
# no Bayesian reasoning framing, no superforecaster persona, no other additions;
# then same JSON output contract as v1."
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


def _build_user_message_v2(question: dict) -> str:
    """
    Build the protocol-v2 user message for a question.

    Same structure as v1 (title + description + snapshot date + no-leakage instruction)
    with the final line updated to request reasoning before JSON.

    Args:
        question: Normalised question dict with resolved_at field.

    Returns:
        User message string.
    """
    title = (question.get("title") or "").strip()
    description = (question.get("description") or "").strip()[:600]

    # Snapshot date T = resolved_at - 30d  (same as v1)
    resolved_str = question.get("resolved_at", "")
    T_str = ""
    if resolved_str:
        try:
            s = resolved_str
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            resolved_dt = datetime.fromisoformat(s)
            if resolved_dt.tzinfo is None:
                resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
            T_dt = resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)
            T_str = T_dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    lines = [f"Question: {title}"]
    if description:
        lines.append(f"\nContext / Resolution criteria:\n{description}")
    if T_str:
        # Identical to v1: "Assume today is T. Use no information after this date."
        lines.append(
            f"\nAssume today is {T_str}. "
            "Use no information after this date."
        )
    lines.append(
        "\nWrite 1–2 sentences of key considerations "
        "(a base-rate anchor where natural), "
        "then output the JSON object {\"prob\": <float>} where <float> is in [0.01, 0.99]."
    )
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Cache helpers (v2-specific; never touches v1 files)
# ------------------------------------------------------------------ #

def _cache_key_v2(qid: str, model: str, seed: int) -> str:
    """Deterministic cache key for (qid, model, 'v2', seed)."""
    raw = f"{qid}|{model}|{ELICITATION_PROTOCOL_VERSION_V2}|{seed}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path_v2(qid: str, model: str) -> str:
    """Filesystem path for a v2 cached response (prefix mvp_v2_)."""
    os.makedirs(LLM_CACHE_DIR, exist_ok=True)
    key = _cache_key_v2(qid, model, RANDOM_SEED)
    safe_model = model.replace("/", "_").replace(":", "_")
    return os.path.join(LLM_CACHE_DIR, f"mvp_v2_{safe_model}_{key}.json")


def _load_cache_v2(qid: str, model: str) -> Optional[dict]:
    """Return cached v2 response dict or None."""
    path = _cache_path_v2(qid, model)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save_cache_v2(qid: str, model: str, record: dict) -> None:
    """Persist a v2 elicitation record to the cache."""
    with open(_cache_path_v2(qid, model), "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ #
# API call (v2 system prompt)
# ------------------------------------------------------------------ #

def _call_anthropic_v2(model: str, user_message: str) -> dict:
    """
    POST to Anthropic Messages API with protocol-v2 parameters.

    Uses _SYSTEM_PROMPT_V2. Auth via x-api-key; key never logged.

    Args:
        model: Anthropic model ID.
        user_message: User turn content.

    Returns:
        Raw API response dict.

    Raises:
        RuntimeError: On unrecoverable HTTP errors.
    """
    import urllib.request as _req
    import urllib.error as _err

    api_key = require_key("ANTHROPIC_API_KEY")

    body: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM_PROMPT_V2,
        "messages": [{"role": "user", "content": user_message}],
    }
    if model in TEMPERATURE_SUPPORTED_MODELS:
        body["temperature"] = 0
    # thinking OMITTED for all models (same as v1)

    payload = json.dumps(body).encode("utf-8")
    request = _req.Request(
        ANTHROPIC_MESSAGES_URL,
        data=payload,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type":      "application/json",
            "accept":            "application/json",
        },
        method="POST",
    )

    for attempt in range(4):
        try:
            with _req.urlopen(request, timeout=90) as resp:
                return json.load(resp)
        except _err.HTTPError as exc:
            body_txt = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in (429, 500, 502, 503, 529) and attempt < 3:
                wait = 8 * (2 ** attempt)
                print(f"    [retry {attempt+1}] HTTP {exc.code}, wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic HTTP {exc.code}: {body_txt}") from exc
    raise RuntimeError("Max retries exceeded")


# ------------------------------------------------------------------ #
# Response parsing (v2: JSON may be preceded by reasoning text)
# ------------------------------------------------------------------ #

def _parse_response_v2(response: dict) -> tuple:
    """
    Extract probability, reasoning text, stop_reason, and raw text from a v2 response.

    v2 responses contain 1–2 sentences of reasoning before the JSON object.
    We scan left-to-right for the first '{' that yields a valid {"prob": float}.

    Args:
        response: Raw Anthropic API response dict.

    Returns:
        (prob: Optional[float], reasoning_text: str, stop_reason: str, raw_text: str)
    """
    stop_reason = response.get("stop_reason", "unknown")
    raw_text = ""

    for block in response.get("content", []):
        if block.get("type") == "text":
            raw_text = block.get("text", "").strip()
            break

    if not raw_text:
        return None, "", stop_reason, ""

    # Strip markdown fences if present
    text = raw_text
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].strip()
        if text.startswith("json"):
            text = text[4:].strip()

    # Scan for JSON object — try each '{' left-to-right
    prob = None
    json_start = -1
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj = json.loads(text[i:])
            val = obj.get("prob")
            if val is not None:
                prob = float(val)
                prob = max(PROB_MIN, min(PROB_MAX, prob))
                json_start = i
                break
        except (json.JSONDecodeError, TypeError, ValueError):
            # Try to find closing brace for a partial parse
            close = text.find("}", i)
            if close == -1:
                continue
            try:
                obj = json.loads(text[i : close + 1])
                val = obj.get("prob")
                if val is not None:
                    prob = float(val)
                    prob = max(PROB_MIN, min(PROB_MAX, prob))
                    json_start = i
                    break
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    reasoning_text = text[:json_start].strip() if json_start >= 0 else text.strip()
    return prob, reasoning_text, stop_reason, raw_text


# ------------------------------------------------------------------ #
# Pricing (same formula as v1)
# ------------------------------------------------------------------ #

def _cost_usd_v2(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost from token counts using D-011 pricing."""
    prices = MODEL_PRICING.get(model, {"input": 5.0, "output": 25.0})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


# ------------------------------------------------------------------ #
# Cost estimation
# ------------------------------------------------------------------ #

def estimate_cost_v2(n_questions: int) -> float:
    """
    Estimate total USD cost for v2 elicitation over n_questions × all 3 models.

    v2 output is larger than v1 (reasoning + JSON); uses 300 input + 80 output.

    Args:
        n_questions: Number of questions.

    Returns:
        Estimated USD total.
    """
    est_in, est_out = 300, 80  # conservative: reasoning adds ~60 output tokens vs v1
    total = 0.0
    for model in PANEL_MODELS:
        total += _cost_usd_v2(model, n_questions * est_in, n_questions * est_out)
    return total


# ------------------------------------------------------------------ #
# Main elicitation loop
# ------------------------------------------------------------------ #

def run_elicitation_v2(
    questions: list,
    offline: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run protocol-v2 elicitation on all questions × all panel models.

    Cache keys and file names differ from v1; v1 cache is never touched.

    Args:
        questions: List of thin-slice question dicts.
        offline: If True, only use cached responses (no API calls).
        verbose: Print per-question progress.

    Returns:
        Dict with keys:
          'records': list of per-(qid, model) result dicts (include reasoning_text)
          'total_usd': float
          'total_input_tokens': int
          'total_output_tokens': int
          'n_cache_hits': int
          'n_api_calls': int
          'n_parse_errors': int
          'n_refusals': int
    """
    records = []
    total_usd = 0.0
    total_in = total_out = 0
    n_cache_hits = n_api_calls = n_parse_errors = n_refusals = 0

    n_q = len(questions)

    for model in PANEL_MODELS:
        if verbose:
            print(f"\n  === {model} ===", flush=True)
        model_usd = 0.0

        for i, q in enumerate(questions, 1):
            qid = q["qid"]

            # Cache-first
            cached = _load_cache_v2(qid, model)
            if cached:
                n_cache_hits += 1
                records.append(cached)
                total_usd += cached.get("usd", 0.0)
                total_in  += cached.get("input_tokens", 0)
                total_out += cached.get("output_tokens", 0)
                model_usd += cached.get("usd", 0.0)
                if verbose:
                    print(f"    [{i:3d}/{n_q}] {qid[:28]} CACHE prob={cached.get('model_prob')}",
                          flush=True)
                continue

            if offline:
                records.append({
                    "qid": qid, "model": model,
                    "protocol_version": ELICITATION_PROTOCOL_VERSION_V2,
                    "model_prob": None,
                    "reasoning_text": "",
                    "reasoning_chars": 0,
                    "stop_reason": "offline_no_cache",
                    "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                    "cache_hit": False, "parse_error": True,
                    "elicited_at_utc": None,
                })
                n_parse_errors += 1
                continue

            # Live API call
            user_msg = _build_user_message_v2(q)
            if verbose:
                print(f"    [{i:3d}/{n_q}] {qid[:28]} calling...", flush=True)

            try:
                response = _call_anthropic_v2(model, user_msg)
            except RuntimeError as exc:
                print(f"    [ERROR] {qid} {model}: {exc}", flush=True)
                records.append({
                    "qid": qid, "model": model,
                    "protocol_version": ELICITATION_PROTOCOL_VERSION_V2,
                    "model_prob": None,
                    "reasoning_text": "",
                    "reasoning_chars": 0,
                    "stop_reason": "api_error",
                    "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                    "cache_hit": False, "parse_error": True,
                    "error": str(exc)[:200],
                    "elicited_at_utc": datetime.now(timezone.utc).isoformat(),
                })
                n_parse_errors += 1
                continue

            n_api_calls += 1
            prob, reasoning_text, stop_reason, raw_text = _parse_response_v2(response)

            usage = response.get("usage", {})
            in_tok  = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            usd = _cost_usd_v2(model, in_tok, out_tok)
            total_in  += in_tok
            total_out += out_tok
            total_usd += usd
            model_usd += usd

            is_refusal  = (stop_reason == "refusal")
            is_parse_err = (prob is None and not is_refusal)

            if is_refusal:
                n_refusals += 1
            if is_parse_err:
                n_parse_errors += 1

            record = {
                "qid":              qid,
                "model":            model,
                "protocol_version": ELICITATION_PROTOCOL_VERSION_V2,
                "seed":             RANDOM_SEED,
                "model_prob":       prob,
                "reasoning_text":   reasoning_text[:400] if reasoning_text else "",
                "reasoning_chars":  len(reasoning_text),
                "stop_reason":      stop_reason,
                "raw_text":         raw_text[:600] if raw_text else "",
                "input_tokens":     in_tok,
                "output_tokens":    out_tok,
                "usd":              usd,
                "cache_hit":        False,
                "parse_error":      is_parse_err,
                "is_refusal":       is_refusal,
                "elicited_at_utc":  datetime.now(timezone.utc).isoformat(),
            }
            _save_cache_v2(qid, model, record)
            records.append(record)

            if verbose:
                status = (
                    "REFUSAL" if is_refusal
                    else ("PARSE_ERR" if is_parse_err else f"prob={prob:.4f}")
                )
                print(f"    [{i:3d}/{n_q}] {qid[:28]} {status} "
                      f"in={in_tok} out={out_tok} usd=${usd:.5f} "
                      f"reasoning_chars={len(reasoning_text)}", flush=True)

            time.sleep(0.8 if "opus" in model else 0.4)

        if verbose:
            print(f"  {model}: usd=${model_usd:.4f}", flush=True)

    if verbose:
        print(f"\n  Totals: in={total_in} out={total_out} usd=${total_usd:.4f} "
              f"cache={n_cache_hits} api={n_api_calls} "
              f"parse_err={n_parse_errors} refusals={n_refusals}", flush=True)

    return {
        "records":              records,
        "total_usd":            total_usd,
        "total_input_tokens":   total_in,
        "total_output_tokens":  total_out,
        "n_cache_hits":         n_cache_hits,
        "n_api_calls":          n_api_calls,
        "n_parse_errors":       n_parse_errors,
        "n_refusals":           n_refusals,
    }


# ------------------------------------------------------------------ #
# Public prompt hash (for manifest provenance)
# ------------------------------------------------------------------ #

def system_prompt_hash_v2() -> str:
    """SHA-256 of the frozen protocol-v2 system prompt."""
    return hashlib.sha256(_SYSTEM_PROMPT_V2.encode()).hexdigest()
