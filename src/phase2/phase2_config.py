"""
config.py — Named constants for Phase-2 Step A.

Frozen per D-011 (2026-07-16).  All magic numbers live here.
"""

import os

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED: int = 42

# ---------------------------------------------------------------------------
# D-011 §2 — Training-data cutoffs (end-of-month, conservative, UTC)
# ---------------------------------------------------------------------------
TRAINING_CUTOFFS: dict = {
    "claude-haiku-4-5-20251001": "2025-07-31",
    "claude-sonnet-5":           "2026-01-31",
    "claude-opus-4-8":           "2026-01-31",
}

# D-006 contamination rule: resolved_at >= C + SNAPSHOT_LEAD_DAYS
SNAPSHOT_LEAD_DAYS: int = 30

# D-011 §4 — Elicitation set boundaries (derived from training cutoffs)
# 2025-07-31 + 30d = 2025-08-30
HAIKU_CLEAN_MIN_RESOLVED: str = "2025-08-30"
# 2026-01-31 + 30d = 2026-03-02
JAN2026_CLEAN_MIN_RESOLVED: str = "2026-03-02"

# Target sizes per D-011 §4
HAIKU_CLEAN_TARGET: int = 791      # "take all available" up to this
PRE_CUTOFF_PROBE_TARGET: int = 800  # seeded sample

# ---------------------------------------------------------------------------
# D-011 §3 — Model panel (classifier uses haiku; elicitation uses all)
# ---------------------------------------------------------------------------
CLASSIFIER_MODEL: str = "claude-haiku-4-5-20251001"
PANEL_MODELS: list = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-4-8",
]

# ---------------------------------------------------------------------------
# Classifier versions (v1.0 frozen; v1.1 frozen per D-013)
# ---------------------------------------------------------------------------
CLASSIFIER_VERSION:     str = "v1.0"   # step A — narrow capabilities/benchmarks
CLASSIFIER_VERSION_V11: str = "v1.1"   # D-013 realignment — all five DATA.md categories

# Binary decision labels
DECISION_KEEP: str = "RELEVANT"
DECISION_DROP: str = "NOT_RELEVANT"

# Max tokens for classifier output (brief justification + JSON)
CLASSIFIER_MAX_TOKENS: int = 120

# Audit sample size and seed (both KEPT and DROPPED for v1.1)
AUDIT_SAMPLE_N: int = 40
AUDIT_SAMPLE_SEED: int = 42

# ---------------------------------------------------------------------------
# Pricing (D-011 §6 rates, 2026-07-16)
# Batch = 50% discount on both input and output
# ---------------------------------------------------------------------------
MODEL_PRICING: dict = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5":           {"input": 2.00, "output": 10.00},
    "claude-opus-4-8":           {"input": 5.00, "output": 25.00},
}
BATCH_DISCOUNT: float = 0.50   # 50% off for Message Batches API

COST_HARD_STOP_USD: float = 5.0   # classifier-specific stop (task spec)
COST_STUDY_HARD_STOP_USD: float = 25.0  # single-run study stop (SCOPE §6)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
ANTHROPIC_API_BASE: str = "https://api.anthropic.com/v1"
ANTHROPIC_API_VERSION: str = "2023-06-01"
ANTHROPIC_BATCH_BETA: str = "message-batches-2024-09-24"

MANIFOLD_BETS_URL: str = "https://api.manifold.markets/v0/bets"
MANIFOLD_BETS_PAGE_SIZE: int = 1000
MANIFOLD_RATE_SLEEP: float = 0.4   # seconds between Manifold requests

# Max requests per batch (Anthropic limit)
BATCH_MAX_REQUESTS: int = 10_000

# Poll interval for batch status (seconds)
BATCH_POLL_INTERVAL_S: int = 15

# ---------------------------------------------------------------------------
# Paths (resolved from repo root)
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

INTERIM_DIR         = os.path.join(_REPO_ROOT, "data", "interim")
RAW_DIR             = os.path.join(_REPO_ROOT, "data", "raw", "phase2")
RECON_RAW_DIR       = os.path.join(_REPO_ROOT, "data", "raw", "recon")
LLM_CACHE_DIR       = os.path.join(_REPO_ROOT, "data", "llm_cache")
EXPERIMENTS_PATH    = os.path.join(_REPO_ROOT, "docs", "EXPERIMENTS.md")

# Input (from recon)
QUESTIONS_COMBINED_PATH = os.path.join(INTERIM_DIR, "questions_combined.json")

# Phase-2 outputs (interim, git-ignored)
# v1.0 paths (step A, kept for audit)
CLASSIFIER_CACHE_DIR        = os.path.join(_REPO_ROOT, "data", "llm_cache", "classifier_v1")
CLASSIFIER_BATCH_CHECKPOINT = os.path.join(INTERIM_DIR, "phase2_classifier_batch.json")
CLASSIFIER_RESULTS_PATH     = os.path.join(INTERIM_DIR, "phase2_classifier_results.json")
CROWD_SNAPSHOT_CHECKPOINT   = os.path.join(INTERIM_DIR, "phase2_crowd_checkpoint.json")

# v1.1 paths (D-013 re-run)
CLASSIFIER_CACHE_DIR_V11        = os.path.join(_REPO_ROOT, "data", "llm_cache", "classifier_v11")
CLASSIFIER_BATCH_CHECKPOINT_V11 = os.path.join(INTERIM_DIR, "phase2_classifier_batch_v11.json")
CLASSIFIER_RESULTS_PATH_V11     = os.path.join(INTERIM_DIR, "phase2_classifier_results_v11.json")
CROWD_SNAPSHOT_CHECKPOINT_V11   = os.path.join(INTERIM_DIR, "phase2_crowd_checkpoint_v11.json")

# Phase-2 committed outputs (v1.1 rewrites phase2_questions.json; manifest appends v1.1 section)
PHASE2_QUESTIONS_PATH  = os.path.join(INTERIM_DIR, "phase2_questions.json")
AUDIT_SAMPLE_PATH      = os.path.join(INTERIM_DIR, "classifier_audit_sample.json")
AUDIT_SAMPLE_V11_PATH  = os.path.join(INTERIM_DIR, "classifier_audit_sample_v11.json")
PHASE2_MANIFEST_PATH   = os.path.join(_REPO_ROOT, "data", "phase2_manifest.json")
