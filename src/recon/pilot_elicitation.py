"""
pilot_elicitation.py — LLM pilot elicitation for Phase-0 recon.

Queries 2 Anthropic models on 30 seeded pilot questions.  Each call uses:
  temperature=0, max_tokens=1000, structured JSON output.
Keys from env_loader only — never printed or written to tracked files.
Responses cached in data/llm_cache/ (git-ignored) keyed by (qid, model, seed).

Models used in this pilot (chosen for training-cutoff span):
  - claude-haiku-4-5-20251001  (reliable cutoff: Feb 2025)
  - claude-sonnet-5             (reliable cutoff: Jan 2026)

Cost estimate (before run):
  Each question prompt ≈ 400 input tokens, response ≈ 80 output tokens
  Haiku: 30 × (400×$1 + 80×$5) / 1e6 ≈ $0.024
  Sonnet 5: 30 × (400×$3 + 80×$15) / 1e6 ≈ $0.072
  Total pilot ≈ $0.10 (well within $25 guardrail)
"""

import json
import os
import hashlib
import time
import sys
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from env_loader import require_key
from config import RAW_DIR, RANDOM_SEED, SNAPSHOT_LEAD_DAYS

# Cache directory (git-ignored)
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
LLM_CACHE_DIR = os.path.join(_REPO_ROOT, "data", "llm_cache")

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# Pilot model panel: (model_id, reliable_cutoff_str)
PILOT_MODELS = [
    ("claude-haiku-4-5-20251001", "Feb 2025"),
    ("claude-sonnet-5", "Jan 2026"),
]

# ------------------------------------------------------------------ #
# Prompt construction
# ------------------------------------------------------------------ #

_SYSTEM_PROMPT = (
    "You are a calibrated probabilistic forecaster. "
    "You will be given a binary question that was open for public prediction. "
    "Provide your probability estimate that the question resolves YES. "
    "Output ONLY a JSON object with a single key \"prob\" (float, 0.0–1.0). "
    "Example: {\"prob\": 0.73}\n"
    "Do not include any other text, explanation, or reasoning outside the JSON."
)


def _build_user_message(question: dict, cutoff_str: str) -> str:
    """
    Build the user message for a forecasting question.

    Args:
        question: Normalised question dict.
        cutoff_str: Model's knowledge cutoff (e.g. 'Jan 2026'), used as context boundary.

    Returns:
        User message string.
    """
    title = question.get("title", "").strip()
    description = (question.get("description") or "").strip()

    # T = resolved_at - 30d is the effective snapshot date
    resolved_at_str = question.get("resolved_at", "")
    snapshot_date_str = ""
    if resolved_at_str:
        try:
            if resolved_at_str.endswith("Z"):
                resolved_at_str = resolved_at_str[:-1] + "+00:00"
            rd = datetime.fromisoformat(resolved_at_str)
            if rd.tzinfo is None:
                rd = rd.replace(tzinfo=timezone.utc)
            T = rd - timedelta(days=SNAPSHOT_LEAD_DAYS)
            snapshot_date_str = T.strftime("%Y-%m-%d")
        except ValueError:
            pass

    lines = [f"Question: {title}"]
    if description:
        lines.append(f"\nContext / Resolution criteria:\n{description[:600]}")
    if snapshot_date_str:
        lines.append(
            f"\nYour forecast is as of {snapshot_date_str} "
            f"(your knowledge cutoff is approximately {cutoff_str}). "
            "Do not speculate beyond your knowledge cutoff."
        )
    lines.append(
        "\nWhat probability (0.0–1.0) do you assign to this resolving YES? "
        "Output only the JSON object."
    )
    return "\n".join(lines)


# ------------------------------------------------------------------ #
# Cache helpers
# ------------------------------------------------------------------ #

def _cache_key(qid: str, model: str, seed: int) -> str:
    raw = f"{qid}|{model}|{seed}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_path(qid: str, model: str, seed: int) -> str:
    os.makedirs(LLM_CACHE_DIR, exist_ok=True)
    key = _cache_key(qid, model, seed)
    safe_model = model.replace("/", "_").replace(":", "_")
    return os.path.join(LLM_CACHE_DIR, f"{safe_model}_{key}.json")


def _load_cache(qid: str, model: str, seed: int) -> Optional[dict]:
    path = _cache_path(qid, model, seed)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save_cache(qid: str, model: str, seed: int, record: dict) -> None:
    path = _cache_path(qid, model, seed)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ #
# API call
# ------------------------------------------------------------------ #

# Models that do NOT support the temperature parameter (deprecated as of their release).
# For these, we omit temperature and rely on default sampling; reproducibility is achieved
# by caching all responses keyed by (qid, model, seed).
_TEMPERATURE_DEPRECATED_MODELS = frozenset([
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
])


def _call_anthropic(
    model: str,
    system_prompt: str,
    user_message: str,
    seed: int,
    max_tokens: int = 1000,
) -> dict:
    """
    Call Anthropic Messages API.  Returns raw response dict.
    Auth via x-api-key header; key never logged or written to tracked files.

    Note: temperature=0 is omitted for newer models where it is deprecated
    (e.g. claude-sonnet-5).  Reproducibility for those models is achieved via
    response caching keyed by (qid, model, seed).

    Args:
        model: Anthropic model ID.
        system_prompt: System prompt string.
        user_message: User turn content.
        seed: Reserved for logging (Anthropic API does not support seed param).
        max_tokens: Max output tokens.

    Returns:
        Parsed JSON response dict.

    Raises:
        RuntimeError: On HTTP errors.
    """
    import urllib.request as _req
    import urllib.error as _err

    api_key = require_key("ANTHROPIC_API_KEY")

    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    # Include temperature only for models that support it
    if model not in _TEMPERATURE_DEPRECATED_MODELS:
        body["temperature"] = 0

    payload = json.dumps(body).encode("utf-8")

    request = _req.Request(
        ANTHROPIC_MESSAGES_URL,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )

    for attempt in range(4):
        try:
            with _req.urlopen(request, timeout=60) as resp:
                return json.load(resp)
        except _err.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code in (429, 500, 502, 503, 529) and attempt < 3:
                wait = 8 * (2 ** attempt)
                print(f"    [retry] HTTP {exc.code}, waiting {wait}s: {body_text[:100]}", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic API HTTP {exc.code}: {body_text}") from exc
    raise RuntimeError("Max retries exceeded for Anthropic API call")


def _parse_prob(response: dict) -> Optional[float]:
    """
    Extract probability from Anthropic response content.

    Args:
        response: Raw Anthropic Messages API response dict.

    Returns:
        Float probability, or None if parsing fails.
    """
    try:
        content = response.get("content", [])
        for block in content:
            if block.get("type") == "text":
                text = block["text"].strip()
                # Remove markdown code fences if present
                if text.startswith("```"):
                    text = text.split("```")[1].strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                obj = json.loads(text)
                val = obj.get("prob")
                if val is not None:
                    p = float(val)
                    # Clip to avoid infinite logits
                    return max(0.001, min(0.999, p))
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        pass
    return None


def _extract_usage(response: dict) -> dict:
    """Extract token usage from response."""
    usage = response.get("usage", {})
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
    }


# ------------------------------------------------------------------ #
# Pricing (as of 2026-07-16, from Anthropic docs)
# ------------------------------------------------------------------ #

# USD per 1M tokens
_PRICES = {
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "claude-sonnet-5": {"input": 3.0, "output": 15.0},  # intro pricing through Aug 2026
}


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for given token counts."""
    prices = _PRICES.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1e6


# ------------------------------------------------------------------ #
# Main elicitation loop
# ------------------------------------------------------------------ #

def run_pilot_elicitation(
    pilot_questions: list,
    verbose: bool = True,
) -> dict:
    """
    Run elicitation on pilot_questions with both pilot models.

    Args:
        pilot_questions: List of 30 normalised question dicts.
        verbose: Print progress.

    Returns:
        Dict with keys:
          'results': list of {qid, model, prob, input_tokens, output_tokens, usd, cache_hit}
          'total_input_tokens': int (per model breakdown in results)
          'total_output_tokens': int
          'total_usd': float
          'n_parse_errors': int
          'model_cutoffs': dict model_id -> cutoff_str
    """
    all_results = []
    total_usd = 0.0
    n_parse_errors = 0
    n_cache_hits = 0
    total_in = 0
    total_out = 0

    for model_id, cutoff_str in PILOT_MODELS:
        if verbose:
            print(f"\n  === Model: {model_id} (cutoff: {cutoff_str}) ===", flush=True)

        model_in = 0
        model_out = 0

        for i, q in enumerate(pilot_questions, 1):
            qid = q["qid"]
            user_msg = _build_user_message(q, cutoff_str)

            # Check cache first
            cached = _load_cache(qid, model_id, RANDOM_SEED)
            if cached:
                n_cache_hits += 1
                if verbose:
                    print(f"    [{i:2d}/{len(pilot_questions)}] {qid[:30]} CACHE HIT prob={cached.get('prob')}", flush=True)
                all_results.append(cached)
                model_in += cached.get("input_tokens", 0)
                model_out += cached.get("output_tokens", 0)
                total_usd += cached.get("usd", 0.0)
                continue

            # Live call
            if verbose:
                print(f"    [{i:2d}/{len(pilot_questions)}] {qid[:30]} calling API...", flush=True)

            try:
                response = _call_anthropic(
                    model=model_id,
                    system_prompt=_SYSTEM_PROMPT,
                    user_message=user_msg,
                    seed=RANDOM_SEED,
                    max_tokens=1000,
                )
            except RuntimeError as exc:
                print(f"    [ERROR] {qid} {model_id}: {exc}", flush=True)
                n_parse_errors += 1
                all_results.append({
                    "qid": qid,
                    "model": model_id,
                    "prob": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "usd": 0.0,
                    "cache_hit": False,
                    "error": str(exc),
                })
                continue

            prob = _parse_prob(response)
            if prob is None:
                n_parse_errors += 1
                if verbose:
                    content_preview = str(response.get("content", ""))[:100]
                    print(f"    [PARSE ERROR] {qid}: {content_preview}", flush=True)

            usage = _extract_usage(response)
            in_tok = usage["input_tokens"]
            out_tok = usage["output_tokens"]
            usd = _estimate_cost_usd(model_id, in_tok, out_tok)

            record = {
                "qid": qid,
                "model": model_id,
                "model_cutoff": cutoff_str,
                "variant": "zero_shot",
                "repeat": 0,
                "seed": RANDOM_SEED,
                "prob": prob,
                "raw_content": [b.get("text", "") for b in response.get("content", []) if b.get("type") == "text"],
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                "usd": usd,
                "cache_hit": False,
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            _save_cache(qid, model_id, RANDOM_SEED, record)
            all_results.append(record)

            model_in += in_tok
            model_out += out_tok
            total_usd += usd

            if verbose:
                print(f"    [{i:2d}/{len(pilot_questions)}] {qid[:30]} prob={prob} "
                      f"in={in_tok} out={out_tok} usd=${usd:.4f}", flush=True)

            # Polite rate limit: 1 request/sec for sonnet, faster for haiku
            time.sleep(1.0 if "sonnet" in model_id else 0.5)

        total_in += model_in
        total_out += model_out
        if verbose:
            model_usd = _estimate_cost_usd(model_id, model_in, model_out)
            print(f"  {model_id}: in={model_in} out={model_out} usd=${model_usd:.4f}", flush=True)

    if verbose:
        print(f"\n  Pilot totals: in={total_in} out={total_out} usd=${total_usd:.4f} "
              f"cache_hits={n_cache_hits} parse_errors={n_parse_errors}", flush=True)

    return {
        "results": all_results,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_usd": total_usd,
        "n_cache_hits": n_cache_hits,
        "n_parse_errors": n_parse_errors,
        "model_cutoffs": {m: c for m, c in PILOT_MODELS},
    }


# ------------------------------------------------------------------ #
# Correlation analysis
# ------------------------------------------------------------------ #

def _logit(p: float) -> float:
    """Log-odds of p. Clips to avoid ±inf."""
    p = max(1e-6, min(1 - 1e-6, p))
    return math.log(p / (1 - p))


def compute_pilot_correlation(
    elicitation_results: list,
    crowd_probs: dict,
) -> dict:
    """
    Compute logit-scale Pearson correlation between market and model probabilities
    for each model, plus Fisher-z 95% CI.

    Args:
        elicitation_results: List of elicitation result dicts.
        crowd_probs: Dict qid -> crowd_prob_at_T (from fetch_crowd_history).

    Returns:
        Dict mapping model_id -> {'r', 'n', 'ci_low', 'ci_high', 'z', 'brier_model',
                                   'brier_crowd', 'n_used', 'n_skipped'}
    """
    import math

    # Group by model
    by_model: dict = {}
    for rec in elicitation_results:
        m = rec["model"]
        if m not in by_model:
            by_model[m] = []
        by_model[m].append(rec)

    analysis: dict = {}

    for model_id, recs in by_model.items():
        pairs = []  # (crowd_logit, model_logit, outcome)
        n_skipped = 0

        for rec in recs:
            qid = rec["qid"]
            model_prob = rec.get("prob")
            crowd_prob = crowd_probs.get(qid)

            if model_prob is None or crowd_prob is None:
                n_skipped += 1
                continue

            # Find outcome from pilot_questions (outcome=1 for YES, 0 for NO)
            pairs.append((crowd_prob, model_prob))

        n = len(pairs)
        if n < 3:
            analysis[model_id] = {"r": None, "n": n, "n_skipped": n_skipped,
                                   "error": "insufficient pairs"}
            continue

        crowd_logits = [_logit(p[0]) for p in pairs]
        model_logits = [_logit(p[1]) for p in pairs]

        # Pearson r on logit scale
        def _pearson(xs: list, ys: list) -> float:
            n = len(xs)
            mx = sum(xs) / n
            my = sum(ys) / n
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
            dy = math.sqrt(sum((y - my) ** 2 for y in ys))
            if dx == 0 or dy == 0:
                return 0.0
            return num / (dx * dy)

        r = _pearson(crowd_logits, model_logits)

        # Fisher-z 95% CI
        # z = atanh(r); SE = 1/sqrt(n-3)
        r_clipped = max(-0.9999, min(0.9999, r))
        z = math.atanh(r_clipped)
        se = 1.0 / math.sqrt(max(n - 3, 1))
        z_low = z - 1.96 * se
        z_high = z + 1.96 * se
        r_low = math.tanh(z_low)
        r_high = math.tanh(z_high)

        analysis[model_id] = {
            "r": round(r, 4),
            "n": n,
            "n_skipped": n_skipped,
            "ci_low": round(r_low, 4),
            "ci_high": round(r_high, 4),
            "fisher_z": round(z, 4),
            "fisher_z_se": round(se, 4),
        }

    return analysis
