"""
classify.py — LLM-assisted AI-progress classifier (Phase-2).

Supports prompt v1.0 (step A, frozen) and v1.1 (D-013 realignment, frozen).
Uses claude-haiku-4-5 via the Anthropic Message Batches API (50% discount).
Each version uses a separate cache directory; neither overwrites the other.

Both prompts:
  - Never include resolution/outcome information (leakage prevention).
  - Decision: RELEVANT | NOT_RELEVANT
  - Output: strict JSON {"decision": "...", "justification": "..."}
"""

import json
import os
import sys
import hashlib
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from phase2_config import (  # noqa: E402 — local config
    CLASSIFIER_MODEL, CLASSIFIER_VERSION, CLASSIFIER_VERSION_V11,
    CLASSIFIER_MAX_TOKENS,
    DECISION_KEEP, DECISION_DROP,
    MODEL_PRICING, BATCH_DISCOUNT, COST_HARD_STOP_USD,
    ANTHROPIC_API_BASE, ANTHROPIC_API_VERSION, ANTHROPIC_BATCH_BETA,
    BATCH_MAX_REQUESTS, BATCH_POLL_INTERVAL_S,
    CLASSIFIER_CACHE_DIR, CLASSIFIER_BATCH_CHECKPOINT, CLASSIFIER_RESULTS_PATH,
    CLASSIFIER_CACHE_DIR_V11, CLASSIFIER_BATCH_CHECKPOINT_V11,
    CLASSIFIER_RESULTS_PATH_V11,
    RAW_DIR,
)
from env_loader import require_key  # noqa: E402

# ---------------------------------------------------------------------------
# Classifier prompt v1.0 — FROZEN (step A).
# No resolution/outcome information (leakage rule).
# ---------------------------------------------------------------------------
_CLASSIFIER_SYSTEM_V10 = (
    "You are an expert research assistant helping to identify AI-progress questions "
    "from a prediction market dataset. "
    "Your job is to classify whether a market question is about the trajectory of "
    "AI itself: this includes benchmark results or saturation, model releases and "
    "capabilities, compute or scaling milestones, adoption or impact claims about AI, "
    "or AI-lab or company outcomes related to AI progress. "
    "Respond with ONLY a JSON object with two keys: "
    '"decision" (string: exactly "RELEVANT" or "NOT_RELEVANT") and '
    '"justification" (string: one sentence explaining your decision). '
    "Example: "
    '{"decision": "RELEVANT", "justification": "Asks about GPT-5 benchmark scores."}'
)

# ---------------------------------------------------------------------------
# Classifier prompt v1.1 — FROZEN (D-013 realignment).
# Aligned verbatim to DATA.md's five pre-registered categories.
# No resolution/outcome information (leakage rule).
# ---------------------------------------------------------------------------
_CLASSIFIER_SYSTEM_V11 = (
    "You are an expert research assistant classifying prediction-market questions "
    "for an AI-progress forecasting study. "
    "Mark a question RELEVANT if it is primarily about ANY of the following five "
    "categories:\n"
    "(a) BENCHMARK RESULTS OR SATURATION — scores, rankings, or saturation on AI "
    "evaluation benchmarks (MMLU, HumanEval, ARC-AGI, GPQA, SWE-bench, Chatbot Arena, "
    "IMO, FrontierMath, etc.).\n"
    "(b) MODEL RELEASES AND CAPABILITIES — release of new AI models or versions; "
    "capability milestones ACHIEVED BY an AI system, including mathematical proofs or "
    "discoveries made by AI, creative firsts (first AI film/novel/song reaching a "
    "threshold), game-playing achievements, or autonomous-agent milestones.\n"
    "(c) COMPUTE / SCALING MILESTONES — training run compute, parameter count, "
    "data-center or GPU/TPU cluster capacity tied to AI, AI-chip or fab capacity "
    "relevant to AI training, or scaling-law findings.\n"
    "(d) ADOPTION / IMPACT CLAIMS ABOUT AI — user counts or growth, AI content "
    "reaching view/usage thresholds, AI-attributed writing/art credits, "
    "AI-generated content in mainstream distribution, broad economic or labor-market "
    "impact of AI adoption.\n"
    "(e) AI-LAB / COMPANY OUTCOMES — fundraising rounds, revenue or ARR, valuation, "
    "mergers and acquisitions, new AI-lab formation, major AI-company partnerships "
    "with material AI-capability implications.\n\n"
    "Mark a question NOT_RELEVANT if it is PRIMARILY about:\n"
    "- Personal or joke questions, or questions about the prediction market itself "
    '("will this market resolve YES", Manifold profit, market mechanics).\n'
    "- Individual personnel moves or gossip (a specific person's hiring, firing, or "
    "departure), unless the question is directly about an AI-capability consequence.\n"
    "- Product naming, branding, or UI trivia with no capability content.\n"
    "- Governance or regulation ONLY (EU AI Act passage, executive orders, policy "
    "votes) with no capability or adoption claim — regulatory questions that "
    "explicitly link to a capability threshold (e.g., 'if GPT-5 passes X, will "
    "the EU ban it?') are RELEVANT.\n\n"
    "When in doubt, prefer RELEVANT — err on the side of inclusion if the question "
    "has any plausible connection to AI capability, adoption, or lab outcomes.\n\n"
    "Respond with ONLY a JSON object with two keys: "
    '"decision" (string: exactly "RELEVANT" or "NOT_RELEVANT") and '
    '"justification" (string: one sentence explaining which category applies or why '
    "it is excluded). "
    'Example: {"decision": "RELEVANT", "justification": "Asks about an AI math '
    'proof milestone (category b)."}'
)

# Version → (system_prompt, cache_dir, batch_checkpoint, results_path)
_VERSION_CONFIG: dict = {
    CLASSIFIER_VERSION: (
        _CLASSIFIER_SYSTEM_V10,
        CLASSIFIER_CACHE_DIR,
        CLASSIFIER_BATCH_CHECKPOINT,
        CLASSIFIER_RESULTS_PATH,
    ),
    CLASSIFIER_VERSION_V11: (
        _CLASSIFIER_SYSTEM_V11,
        CLASSIFIER_CACHE_DIR_V11,
        CLASSIFIER_BATCH_CHECKPOINT_V11,
        CLASSIFIER_RESULTS_PATH_V11,
    ),
}


def _classifier_user_message(question: dict) -> str:
    """
    Build classifier user message from question title and description only.

    Outcome/resolution fields are deliberately excluded (leakage prevention).

    Args:
        question: Normalised question dict.

    Returns:
        User message string.
    """
    title = (question.get("title") or "").strip()
    desc = (question.get("description") or "").strip()[:400]

    lines = [f"Question title: {title}"]
    if desc:
        lines.append(f"Question description: {desc}")
    lines.append("Is this question about AI progress? Respond with the JSON object.")
    return "\n".join(lines)


def _cache_path(qid: str, version: str) -> str:
    """Filesystem path for a cached classifier decision (version-scoped)."""
    _, cache_dir, _, _ = _VERSION_CONFIG[version]
    os.makedirs(cache_dir, exist_ok=True)
    key = hashlib.sha256(f"{qid}|{version}".encode()).hexdigest()[:32]
    return os.path.join(cache_dir, f"cls_{key}.json")


def _load_cached_decision(qid: str, version: str) -> Optional[dict]:
    """Load cached decision for this version; return None if not cached."""
    path = _cache_path(qid, version)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def _save_cached_decision(qid: str, version: str, record: dict) -> None:
    """Save decision record to version-scoped cache."""
    with open(_cache_path(qid, version), "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False)


def _parse_classifier_text(text: str, qid: str) -> tuple:
    """
    Parse classifier JSON output.

    Args:
        text: Raw model text output.
        qid: Question ID (for error logging).

    Returns:
        (decision: str|None, justification: str)
        decision is DECISION_KEEP, DECISION_DROP, or None on parse failure.
    """
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        obj = json.loads(text)
        decision = obj.get("decision", "").strip().upper()
        justification = obj.get("justification", "").strip()
        if decision in (DECISION_KEEP, DECISION_DROP):
            return decision, justification
        print(f"  [PARSE_WARN] {qid}: unexpected decision '{decision}'", flush=True)
        return None, justification
    except (json.JSONDecodeError, AttributeError) as exc:
        print(f"  [PARSE_ERR] {qid}: {exc} | text={text[:80]}", flush=True)
        return None, text[:120]


def _cost_usd(input_tokens: int, output_tokens: int, batch: bool = True) -> float:
    """Compute USD cost using haiku pricing, with optional batch discount."""
    prices = MODEL_PRICING[CLASSIFIER_MODEL]
    factor = BATCH_DISCOUNT if batch else 1.0
    return factor * (
        input_tokens * prices["input"] + output_tokens * prices["output"]
    ) / 1_000_000


def _headers(api_key: str) -> dict:
    """Shared Anthropic API request headers."""
    return {
        "x-api-key":           api_key,
        "anthropic-version":   ANTHROPIC_API_VERSION,
        "anthropic-beta":      ANTHROPIC_BATCH_BETA,
        "content-type":        "application/json",
        "accept":              "application/json",
    }


def _post_json(url: str, body: dict, api_key: str) -> dict:
    """POST JSON body to url; return parsed response dict."""
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
                print(f"  [retry {attempt+1}] HTTP {exc.code} wait {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic POST {url} HTTP {exc.code}: {body_txt}") from exc
    raise RuntimeError(f"Max retries exceeded for {url}")


def _get_json(url: str, api_key: str) -> dict:
    """GET url; return parsed response dict."""
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
            raise RuntimeError(f"Anthropic GET {url} HTTP {exc.code}: {body_txt}") from exc
    raise RuntimeError(f"Max retries exceeded for GET {url}")


def _submit_batch(questions_to_classify: list, system_prompt: str, api_key: str) -> str:
    """
    Submit a Message Batches job for all uncached questions.

    Args:
        questions_to_classify: List of question dicts without cached decisions.
        system_prompt: Classifier system prompt (version-specific).
        api_key: Anthropic API key.

    Returns:
        Batch ID string.

    Raises:
        RuntimeError: On API failure.
    """
    requests_payload = []
    for q in questions_to_classify:
        qid = q["qid"]
        user_msg = _classifier_user_message(q)
        requests_payload.append({
            "custom_id": qid,
            "params": {
                "model":      CLASSIFIER_MODEL,
                "max_tokens": CLASSIFIER_MAX_TOKENS,
                "system":     system_prompt,
                "messages":   [{"role": "user", "content": user_msg}],
            },
        })

    # Split into chunks if over BATCH_MAX_REQUESTS (safety valve)
    if len(requests_payload) > BATCH_MAX_REQUESTS:
        raise RuntimeError(
            f"Batch size {len(requests_payload)} exceeds limit {BATCH_MAX_REQUESTS}"
        )

    print(f"  Submitting batch with {len(requests_payload)} requests...", flush=True)
    url = f"{ANTHROPIC_API_BASE}/messages/batches"
    resp = _post_json(url, {"requests": requests_payload}, api_key)
    batch_id = resp["id"]
    print(f"  Batch submitted: {batch_id} status={resp.get('processing_status')}", flush=True)
    return batch_id


def _poll_batch(batch_id: str, api_key: str) -> dict:
    """
    Poll until batch processing_status == 'ended'.

    Args:
        batch_id: Batch ID from _submit_batch.
        api_key: Anthropic API key.

    Returns:
        Final batch status dict.
    """
    url = f"{ANTHROPIC_API_BASE}/messages/batches/{batch_id}"
    poll_n = 0
    while True:
        status = _get_json(url, api_key)
        ps = status.get("processing_status", "unknown")
        counts = status.get("request_counts", {})
        print(
            f"  [poll {poll_n}] batch={batch_id} status={ps} "
            f"succeeded={counts.get('succeeded', '?')} "
            f"errored={counts.get('errored', '?')} "
            f"processing={counts.get('processing', '?')}",
            flush=True,
        )
        if ps == "ended":
            return status
        if ps not in ("in_progress", "canceling"):
            raise RuntimeError(f"Unexpected batch status: {ps}")
        poll_n += 1
        time.sleep(BATCH_POLL_INTERVAL_S)


def _retrieve_batch_results(batch_id: str, api_key: str) -> list:
    """
    Retrieve JSONL results from a completed batch.

    Args:
        batch_id: Completed batch ID.
        api_key: Anthropic API key.

    Returns:
        List of result dicts (one per request).
    """
    url = f"{ANTHROPIC_API_BASE}/messages/batches/{batch_id}/results"
    req = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    results = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line = line.decode("utf-8").strip()
            if line:
                results.append(json.loads(line))
    return results


def _fallback_sequential(
    questions: list, system_prompt: str, api_key: str, verbose: bool = True
) -> list:
    """
    Sequential fallback if Batch API is unavailable.

    Uses the standard Messages API (no batch discount).
    Returns list of raw result dicts matching the batch result format.
    """
    url = f"{ANTHROPIC_API_BASE}/messages"
    results = []
    n = len(questions)
    for i, q in enumerate(questions, 1):
        qid = q["qid"]
        user_msg = _classifier_user_message(q)
        body = {
            "model":      CLASSIFIER_MODEL,
            "max_tokens": CLASSIFIER_MAX_TOKENS,
            "system":     system_prompt,
            "messages":   [{"role": "user", "content": user_msg}],
        }
        if verbose:
            print(f"  [{i:4d}/{n}] {qid[:32]}...", flush=True)
        payload = json.dumps(body).encode("utf-8")

        # Remove beta header for standard endpoint
        hdrs = {k: v for k, v in _headers(api_key).items() if k != "anthropic-beta"}
        req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")

        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_dict = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                err_txt = exc.read().decode("utf-8", errors="replace")[:200]
                if exc.code in (429, 500, 502, 503, 529) and attempt < 3:
                    time.sleep(8 * (2 ** attempt))
                    continue
                print(f"  [ERROR] {qid} HTTP {exc.code}: {err_txt}", flush=True)
                resp_dict = {"error": {"type": "http_error", "message": err_txt}}
                break
        else:
            resp_dict = {"error": {"type": "max_retries", "message": "max retries"}}

        results.append({"custom_id": qid, "result": {"type": "succeeded", "message": resp_dict}
                        if "error" not in resp_dict
                        else {"type": "errored", "error": resp_dict["error"]}})
        time.sleep(0.3)

    return results


def run_classifier(
    questions: list,
    version: str = CLASSIFIER_VERSION,
    verbose: bool = True,
) -> dict:
    """
    Run the LLM-assisted AI-progress classifier on all candidate questions.

    Steps:
      1. Load per-question cached decisions for this version (skip already-decided).
      2. Estimate and check cost vs hard stop.
      3. Try Message Batches API; fall back to sequential if unavailable.
      4. Parse and cache each decision (version-scoped cache, never overwrites other version).
      5. Return aggregate result dict.

    Args:
        questions: Full list of candidate question dicts.
        version: Classifier prompt version — CLASSIFIER_VERSION ("v1.0") or
                 CLASSIFIER_VERSION_V11 ("v1.1").
        verbose: Print progress.

    Returns:
        Dict with keys:
          'decisions': {qid: {"decision": str, "justification": str}}
          'n_candidates': int
          'n_keep': int
          'n_drop': int
          'n_parse_error': int
          'input_tokens': int
          'output_tokens': int
          'cost_usd': float
          'used_batch_api': bool
          'classifier_version': str
          'classifier_model': str
          'classifier_system_hash': str
          'run_timestamp_utc': str
    """
    if version not in _VERSION_CONFIG:
        raise ValueError(f"Unknown classifier version '{version}'; "
                         f"must be one of {list(_VERSION_CONFIG)}")

    system_prompt, cache_dir, batch_ckpt, results_path = _VERSION_CONFIG[version]

    api_key = require_key("ANTHROPIC_API_KEY")

    n_total = len(questions)
    decisions: dict = {}
    parse_errors: list = []

    # --- Step 1: load from version-scoped cache ---
    to_classify = []
    n_cache_hits = 0
    for q in questions:
        qid = q["qid"]
        cached = _load_cached_decision(qid, version)
        if cached and cached.get("decision") in (DECISION_KEEP, DECISION_DROP):
            decisions[qid] = cached
            n_cache_hits += 1
        else:
            to_classify.append(q)

    if verbose:
        print(f"  Classifier {version}: {n_total} candidates; "
              f"{n_cache_hits} from cache; {len(to_classify)} to classify.", flush=True)

    # --- Step 2: cost estimate (v1.1 system prompt is longer ~450 tokens) ---
    est_in_per_q = 600 if version == CLASSIFIER_VERSION_V11 else 370
    est_out_per_q = 60
    est_total_in  = len(to_classify) * est_in_per_q
    est_total_out = len(to_classify) * est_out_per_q
    est_cost_batch = _cost_usd(est_total_in, est_total_out, batch=True)
    est_cost_seq   = _cost_usd(est_total_in, est_total_out, batch=False)

    if verbose:
        print(f"  Cost estimate: batch=${est_cost_batch:.2f} | "
              f"sequential=${est_cost_seq:.2f} | "
              f"hard stop=${COST_HARD_STOP_USD:.2f}", flush=True)

    if est_cost_batch > COST_HARD_STOP_USD:
        raise RuntimeError(
            f"Projected classifier cost ${est_cost_batch:.2f} exceeds "
            f"hard stop ${COST_HARD_STOP_USD:.2f}. "
            f"STOP — escalate to orchestrator."
        )

    # --- Step 3: classify uncached questions ---
    total_input_tokens = 0
    total_output_tokens = 0
    used_batch_api = False

    if to_classify:
        # Try Batch API first; fall back to sequential on error
        raw_results = None
        try:
            # Check for existing in-progress batch checkpoint (version-scoped)
            batch_id = None
            if os.path.exists(batch_ckpt):
                with open(batch_ckpt, encoding="utf-8") as fh:
                    ckpt = json.load(fh)
                batch_id = ckpt.get("batch_id")
                if verbose:
                    print(f"  Resuming batch {batch_id} from checkpoint.", flush=True)

            if batch_id is None:
                batch_id = _submit_batch(to_classify, system_prompt, api_key)
                # Save checkpoint
                os.makedirs(os.path.dirname(batch_ckpt), exist_ok=True)
                with open(batch_ckpt, "w", encoding="utf-8") as fh:
                    json.dump({
                        "batch_id": batch_id,
                        "version": version,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                        "n_requests": len(to_classify),
                    }, fh)

            _poll_batch(batch_id, api_key)
            if verbose:
                print(f"  Batch ended. Retrieving results...", flush=True)

            raw_results = _retrieve_batch_results(batch_id, api_key)
            used_batch_api = True

            # Save raw JSONL to raw dir for provenance
            os.makedirs(RAW_DIR, exist_ok=True)
            raw_path = os.path.join(
                RAW_DIR, f"classifier_batch_{batch_id}_{version}_results.jsonl"
            )
            with open(raw_path, "w", encoding="utf-8") as fh:
                for r in raw_results:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            if verbose:
                print(f"  Raw results saved to {raw_path}", flush=True)

            # Remove checkpoint after successful retrieval
            if os.path.exists(batch_ckpt):
                os.remove(batch_ckpt)

        except (RuntimeError, urllib.error.URLError) as exc:
            print(f"  [WARN] Batch API failed ({exc}); falling back to sequential.", flush=True)
            used_batch_api = False
            raw_results = _fallback_sequential(
                to_classify, system_prompt, api_key, verbose=verbose
            )

        # --- Step 4: parse results and cache ---
        for result_entry in raw_results:
            qid = result_entry.get("custom_id", "")
            result = result_entry.get("result", {})
            rtype = result.get("type", "unknown")

            if rtype == "errored":
                error = result.get("error", {})
                print(f"  [BATCH_ERR] {qid}: {error}", flush=True)
                record = {
                    "qid": qid,
                    "decision": DECISION_DROP,  # conservative: drop on error
                    "justification": f"batch_error: {error.get('type', 'unknown')}",
                    "parse_error": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "classifier_version": version,
                    "classifier_model": CLASSIFIER_MODEL,
                }
                parse_errors.append(qid)
                _save_cached_decision(qid, version, record)
                decisions[qid] = record
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
            total_input_tokens  += in_tok
            total_output_tokens += out_tok

            decision, justification = _parse_classifier_text(raw_text, qid)
            is_parse_err = decision is None
            if is_parse_err:
                decision = DECISION_DROP  # conservative
                parse_errors.append(qid)

            record = {
                "qid": qid,
                "decision": decision,
                "justification": justification,
                "parse_error": is_parse_err,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "classifier_version": version,
                "classifier_model": CLASSIFIER_MODEL,
                "raw_text": raw_text[:200],
            }
            _save_cached_decision(qid, version, record)
            decisions[qid] = record

    # Accumulate token counts from cached hits (already spent tokens, just log)
    if raw_results:
        new_qids = {r["custom_id"] for r in raw_results}
    else:
        new_qids = set()
    for qid, dec in decisions.items():
        if qid not in new_qids:
            total_input_tokens  += dec.get("input_tokens", 0)
            total_output_tokens += dec.get("output_tokens", 0)

    # Summarise
    n_keep  = sum(1 for d in decisions.values() if d["decision"] == DECISION_KEEP)
    n_drop  = sum(1 for d in decisions.values() if d["decision"] == DECISION_DROP)
    n_perr  = len(parse_errors)
    actual_cost = _cost_usd(total_input_tokens, total_output_tokens, batch=used_batch_api)

    sys_hash = hashlib.sha256(system_prompt.encode()).hexdigest()

    result_summary = {
        "decisions":              decisions,
        "n_candidates":           n_total,
        "n_keep":                 n_keep,
        "n_drop":                 n_drop,
        "n_parse_error":          n_perr,
        "input_tokens":           total_input_tokens,
        "output_tokens":          total_output_tokens,
        "cost_usd":               actual_cost,
        "used_batch_api":         used_batch_api,
        "n_cache_hits":           n_cache_hits,
        "classifier_version":     version,
        "classifier_model":       CLASSIFIER_MODEL,
        "classifier_system_hash": sys_hash,
        "run_timestamp_utc":      datetime.now(timezone.utc).isoformat(),
    }

    if verbose:
        print(
            f"\n  Classifier done: N={n_total} → keep={n_keep} drop={n_drop} "
            f"parse_err={n_perr} cost=${actual_cost:.4f} "
            f"batch={used_batch_api}",
            flush=True,
        )

    return result_summary
