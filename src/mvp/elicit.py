"""
elicit.py — Elicitation protocol v1 for the Phase-1 MVP thin slice (D-011).

Protocol v1 (frozen):
  System: structured JSON forecaster persona.
  User: title + description (truncated) + resolution criteria + "Assume today is <T>.
        Use no information after <T>." + single probability in [0.01, 0.99] as JSON.
  temperature=0 where accepted (haiku); omitted where rejected (sonnet-5, opus-4-8).
  No thinking parameter for opus-4-8.
  max_tokens <= 1000.

Cache key: sha256(qid|model|protocol_version|seed)[:32].
Responses cached in data/llm_cache/ (git-ignored).

Handles stop_reason == "end_turn" normally; "refusal" and parse failures logged as
missing values, not retried.
"""

import json
import os
import hashlib
import time
import math
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

# mvp_config.py (unique name) avoids shadowing src/recon/config.py.
_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mvp_config import (
    ELICITATION_PROTOCOL_VERSION,
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
# Protocol v1 prompt (frozen; do NOT modify — version in config)
# ------------------------------------------------------------------ #

_SYSTEM_PROMPT_V1 = (
    "You are a calibrated probabilistic forecaster. "
    "Output ONLY a JSON object with a single key \"prob\" (float). "
    "The value must be in the range [0.01, 0.99]. "
    "Example: {\"prob\": 0.73}\n"
    "Do not include any other text, reasoning, or explanation outside the JSON object."
)


def _build_user_message_v1(question: dict) -> str:
    """
    Build the protocol-v1 user message for a question.

    Includes title, description (≤600 chars), snapshot date T with explicit
    instruction to use no information after T.

    Args:
        question: Normalised question dict with resolved_at field.

    Returns:
        User message string.
    """
    title = (question.get("title") or "").strip()
    description = (question.get("description") or "").strip()[:600]

    # Compute snapshot date T = resolved_at - 30d
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
        lines.append(
            f"\nAssume today is {T_str}. "
            "Use no information after this date."
        )
    lines.append(
        "\nWhat probability (in [0.01, 0.99]) do you assign to this resolving YES? "
        "Output only the JSON object."
    )
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Cache helpers
# ------------------------------------------------------------------ #

def _cache_key(qid: str, model: str, protocol_version: str, seed: int) -> str:
    """Deterministic cache key for a (qid, model, protocol_version, seed) tuple."""
    raw = f"{qid}|{model}|{protocol_version}|{seed}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path(qid: str, model: str) -> str:
    """Filesystem path for cached response."""
    os.makedirs(LLM_CACHE_DIR, exist_ok=True)
    key = _cache_key(qid, model, ELICITATION_PROTOCOL_VERSION, RANDOM_SEED)
    safe_model = model.replace("/", "_").replace(":", "_")
    return os.path.join(LLM_CACHE_DIR, f"mvp_v1_{safe_model}_{key}.json")


def _load_cache(qid: str, model: str) -> Optional[dict]:
    path = _cache_path(qid, model)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save_cache(qid: str, model: str, record: dict) -> None:
    with open(_cache_path(qid, model), "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ #
# API call
# ------------------------------------------------------------------ #

def _call_anthropic(model: str, user_message: str) -> dict:
    """
    POST to Anthropic Messages API with protocol-v1 parameters.

    Auth via x-api-key header; key never logged, never written to
    tracked files.

    Args:
        model: Anthropic model ID.
        user_message: User turn content.

    Returns:
        Raw API response dict.

    Raises:
        RuntimeError: On unrecoverable HTTP errors.
    """
    import urllib.request as _req
    import urllib.error  as _err

    api_key = require_key("ANTHROPIC_API_KEY")

    body: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM_PROMPT_V1,
        "messages": [{"role": "user", "content": user_message}],
    }
    # temperature=0 only where accepted
    if model in TEMPERATURE_SUPPORTED_MODELS:
        body["temperature"] = 0
    # thinking OMITTED entirely for opus-4-8 (D-011 §4: cheaper, more deterministic)

    payload = json.dumps(body).encode("utf-8")
    request = _req.Request(
        ANTHROPIC_MESSAGES_URL,
        data=payload,
        headers={
            "x-api-key":           api_key,
            "anthropic-version":   ANTHROPIC_API_VERSION,
            "content-type":        "application/json",
            "accept":              "application/json",
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
# Response parsing
# ------------------------------------------------------------------ #

def _parse_response(response: dict) -> tuple:
    """
    Extract probability and stop_reason from API response.

    Args:
        response: Raw Anthropic API response dict.

    Returns:
        (prob: Optional[float], stop_reason: str, raw_text: str)
    """
    stop_reason = response.get("stop_reason", "unknown")
    raw_text = ""

    for block in response.get("content", []):
        if block.get("type") == "text":
            raw_text = block.get("text", "").strip()
            break

    if not raw_text:
        return None, stop_reason, ""

    # Strip markdown fences if present
    text = raw_text
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].strip()
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        obj = json.loads(text)
        val = obj.get("prob")
        if val is not None:
            p = float(val)
            # Clamp to [PROB_MIN, PROB_MAX]
            p = max(PROB_MIN, min(PROB_MAX, p))
            return p, stop_reason, raw_text
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return None, stop_reason, raw_text


# ------------------------------------------------------------------ #
# Pricing
# ------------------------------------------------------------------ #

def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost from token counts using D-011 pricing."""
    prices = MODEL_PRICING.get(model, {"input": 5.0, "output": 25.0})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


# ------------------------------------------------------------------ #
# Main elicitation loop
# ------------------------------------------------------------------ #

def estimate_cost(n_questions: int) -> float:
    """
    Estimate total USD cost for eliciting n_questions × all 3 models.

    Uses conservative per-call estimates (300 input + 20 output tokens).

    Args:
        n_questions: Number of questions to elicit.

    Returns:
        Estimated USD total.
    """
    est_in, est_out = 300, 20
    total = 0.0
    for model in PANEL_MODELS:
        total += _cost_usd(model, n_questions * est_in, n_questions * est_out)
    return total


def run_elicitation(
    questions: list,
    offline: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Run protocol-v1 elicitation on all questions × all panel models.

    Args:
        questions: List of thin-slice question dicts.
        offline: If True, only use cached responses (no API calls).
        verbose: Print per-question progress.

    Returns:
        Dict with keys:
          'records': list of per-(qid, model) result dicts
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

            # Check cache first
            cached = _load_cache(qid, model)
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
                # In offline mode, record as missing
                records.append({
                    "qid": qid, "model": model,
                    "model_prob": None,
                    "stop_reason": "offline_no_cache",
                    "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                    "cache_hit": False, "parse_error": True,
                    "elicited_at_utc": None,
                })
                n_parse_errors += 1
                continue

            # Live API call
            user_msg = _build_user_message_v1(q)
            if verbose:
                print(f"    [{i:3d}/{n_q}] {qid[:28]} calling...", flush=True)

            try:
                response = _call_anthropic(model, user_msg)
            except RuntimeError as exc:
                print(f"    [ERROR] {qid} {model}: {exc}", flush=True)
                records.append({
                    "qid": qid, "model": model,
                    "model_prob": None,
                    "stop_reason": "api_error",
                    "input_tokens": 0, "output_tokens": 0, "usd": 0.0,
                    "cache_hit": False, "parse_error": True,
                    "error": str(exc)[:200],
                    "elicited_at_utc": datetime.now(timezone.utc).isoformat(),
                })
                n_parse_errors += 1
                continue

            n_api_calls += 1
            prob, stop_reason, raw_text = _parse_response(response)

            usage = response.get("usage", {})
            in_tok  = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)
            usd = _cost_usd(model, in_tok, out_tok)
            total_in  += in_tok
            total_out += out_tok
            total_usd += usd
            model_usd += usd

            is_refusal = (stop_reason == "refusal")
            is_parse_err = (prob is None and not is_refusal)

            if is_refusal:
                n_refusals += 1
            if is_parse_err:
                n_parse_errors += 1

            record = {
                "qid": qid,
                "model": model,
                "protocol_version": ELICITATION_PROTOCOL_VERSION,
                "seed": RANDOM_SEED,
                "model_prob": prob,
                "stop_reason": stop_reason,
                "raw_text": raw_text[:500] if raw_text else "",
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "usd": usd,
                "cache_hit": False,
                "parse_error": is_parse_err,
                "is_refusal": is_refusal,
                "elicited_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            _save_cache(qid, model, record)
            records.append(record)

            if verbose:
                status = "REFUSAL" if is_refusal else ("PARSE_ERR" if is_parse_err else f"prob={prob}")
                print(f"    [{i:3d}/{n_q}] {qid[:28]} {status} "
                      f"in={in_tok} out={out_tok} usd=${usd:.5f}", flush=True)

            # Polite rate limiting
            time.sleep(0.8 if "opus" in model else 0.4)

        if verbose:
            print(f"  {model}: usd=${model_usd:.4f}", flush=True)

    if verbose:
        print(f"\n  Totals: in={total_in} out={total_out} usd=${total_usd:.4f} "
              f"cache={n_cache_hits} api={n_api_calls} "
              f"parse_err={n_parse_errors} refusals={n_refusals}", flush=True)

    return {
        "records": records,
        "total_usd": total_usd,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "n_cache_hits": n_cache_hits,
        "n_api_calls": n_api_calls,
        "n_parse_errors": n_parse_errors,
        "n_refusals": n_refusals,
    }


# ------------------------------------------------------------------ #
# Public system prompt hash (for manifest)
# ------------------------------------------------------------------ #

def system_prompt_hash() -> str:
    """SHA-256 of the frozen protocol-v1 system prompt."""
    return hashlib.sha256(_SYSTEM_PROMPT_V1.encode()).hexdigest()
