"""
config.py — D-011 locked parameters for the Phase-1 MVP thin slice.

All constants here are FROZEN per D-011 (2026-07-16).  Do not change
them without logging a new decision in docs/DECISIONS.md.
"""

import os

# ------------------------------------------------------------------ #
# Reproducibility
# ------------------------------------------------------------------ #

RANDOM_SEED: int = 42

# ------------------------------------------------------------------ #
# D-011 §2 — Training-data cutoffs (end-of-month, conservative, UTC)
# ------------------------------------------------------------------ #

# Format: ISO date string (YYYY-MM-DD); treated as midnight UTC on that date.
TRAINING_CUTOFFS: dict = {
    "claude-haiku-4-5-20251001": "2025-07-31",
    "claude-sonnet-5":           "2026-01-31",
    "claude-opus-4-8":           "2026-01-31",
}

# D-006 contamination rule: resolved_at >= C + SNAPSHOT_LEAD_DAYS
SNAPSHOT_LEAD_DAYS: int = 30

# Derived D-006 min_resolved per model (resolved_at must be > this date)
# 2025-07-31 + 30d = 2025-08-30
# 2026-01-31 + 30d = 2026-03-02
MODEL_MIN_RESOLVED: dict = {
    "claude-haiku-4-5-20251001": "2025-08-30",
    "claude-sonnet-5":           "2026-03-02",
    "claude-opus-4-8":           "2026-03-02",
}

# ------------------------------------------------------------------ #
# D-011 §3 — Model panel
# ------------------------------------------------------------------ #

PANEL_MODELS: list = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-4-8",
]

# Models where temperature=0 is accepted
TEMPERATURE_SUPPORTED_MODELS: frozenset = frozenset([
    "claude-haiku-4-5-20251001",
])

# Pricing USD per 1M tokens (in/out), per D-011 §6 (2026-07-16 rates)
# sonnet-5 uses intro pricing valid through 2026-08-31
MODEL_PRICING: dict = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5":           {"input": 2.00, "output": 10.00},
    "claude-opus-4-8":           {"input": 5.00, "output": 25.00},
}

# Hard stop: escalate if a single run is projected to exceed this
COST_HARD_STOP_USD: float = 25.0

# ------------------------------------------------------------------ #
# D-011 §4 — Thin slice question sample spec
# ------------------------------------------------------------------ #

# Total thin-slice N
THIN_SLICE_N: int = 50

# Minimum unique bettors to prefer a question
MIN_UNIQUE_BETTORS_PREFERRED: int = 20

# Post-cutoff bucket (haiku-clean): resolved_at >= this date
POST_CUTOFF_MIN_RESOLVED: str = "2025-08-30"

# All-three-models-clean: resolved_at >= this date
ALL3_CLEAN_MIN_RESOLVED: str = "2026-03-02"

# Required minimum questions in all-3-models-clean stratum
ALL3_CLEAN_MIN_N: int = 8

# ------------------------------------------------------------------ #
# D-011 §4 — Elicitation protocol v1
# ------------------------------------------------------------------ #

ELICITATION_PROTOCOL_VERSION: str = "v1"

# D-012 — Protocol v2 version tag (do not rename v1; provenance)
ELICITATION_PROTOCOL_VERSION_V2: str = "v2"

# max_tokens cap (D-011: ≤ 1000)
MAX_TOKENS: int = 1000

# Output probability clamp
PROB_MIN: float = 0.01
PROB_MAX: float = 0.99

# ------------------------------------------------------------------ #
# API
# ------------------------------------------------------------------ #

ANTHROPIC_MESSAGES_URL: str = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION: str = "2023-06-01"

MANIFOLD_BETS_URL: str = "https://api.manifold.markets/v0/bets"
MANIFOLD_BETS_PAGE_SIZE: int = 1000
MANIFOLD_RATE_SLEEP: float = 0.4

# ------------------------------------------------------------------ #
# Paths (relative to repo root, resolved at runtime)
# ------------------------------------------------------------------ #

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

RAW_DIR          = os.path.join(_REPO_ROOT, "data", "raw", "recon")
LLM_CACHE_DIR    = os.path.join(_REPO_ROOT, "data", "llm_cache")
INTERIM_DIR      = os.path.join(_REPO_ROOT, "data", "interim")
EXPERIMENTS_PATH = os.path.join(_REPO_ROOT, "docs", "EXPERIMENTS.md")
MVP_MANIFEST_PATH = os.path.join(_REPO_ROOT, "data", "mvp_manifest.json")

# Input data (produced by recon)
QUESTIONS_COMBINED_PATH = os.path.join(INTERIM_DIR, "questions_combined.json")
PILOT_QUESTIONS_PATH    = os.path.join(INTERIM_DIR, "pilot_questions.json")
PILOT_CROWD_PROBS_PATH  = os.path.join(INTERIM_DIR, "pilot_crowd_probs.json")

# Thin-slice outputs
MVP_SAMPLE_PATH      = os.path.join(INTERIM_DIR, "mvp_sample.json")
MVP_CROWD_PATH       = os.path.join(INTERIM_DIR, "mvp_crowd_probs.json")
MVP_FORECASTS_PATH   = os.path.join(INTERIM_DIR, "mvp_forecasts.csv")
# D-012 — protocol v2 output (same schema + protocol column)
MVP_FORECASTS_V2_PATH = os.path.join(INTERIM_DIR, "mvp_forecasts_v2.csv")
