"""
config.py — Named constants for Phase-0 reconnaissance.
All magic numbers live here; imported by every other recon module.
"""

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED: int = 42

# ---------------------------------------------------------------------------
# Candidate model knowledge-cutoff grid (ISO-8601 date strings, UTC midnight)
# These represent published / widely-agreed knowledge cutoffs for models
# we may include in the panel.  Verify / update if official dates change.
# Sources consulted: model release papers, official docs, LMSys Arena notes.
#
#  GPT-4 (0314)         — cutoff Jan 2022  (conservative; OpenAI paper)
#  GPT-4o (0513)        — cutoff Oct 2023  (OpenAI system card, May 2024)
#  Claude-3.5-Sonnet    — cutoff Apr 2024  (Anthropic docs, June 2024 release)
#  GPT-4o-mini / o3     — cutoff Oct 2024  (approx; OpenAI docs)
#  Claude-3.7-Sonnet    — cutoff Feb 2025  (Anthropic docs, Feb 2025 release)
#  Gemini-2.5-Pro       — cutoff Jan 2025  (Google DeepMind docs)
# ---------------------------------------------------------------------------
CANDIDATE_CUTOFFS: list[dict] = [
    {"label": "2022-01 (GPT-4 class)",        "date": "2022-01-01"},
    {"label": "2023-04 (approx GPT-4-class)",  "date": "2023-04-01"},
    {"label": "2023-10 (GPT-4o train cutoff)", "date": "2023-10-01"},
    {"label": "2024-04 (Claude-3.5-Sonnet)",   "date": "2024-04-01"},
    {"label": "2024-10 (GPT-4o-mini / o3 approx)", "date": "2024-10-01"},
    {"label": "2025-01 (Gemini-2.5-Pro / Claude-3.7)", "date": "2025-01-01"},
    {"label": "2025-04 (mid-2025 class)",      "date": "2025-04-01"},
]

# Under D-006 the clean rule is resolved_at >= C + SNAPSHOT_LEAD_DAYS
SNAPSHOT_LEAD_DAYS: int = 30

# ---------------------------------------------------------------------------
# Keyword filter — v1.0
# Purpose: coarse first pass to identify AI-progress questions from titles.
# Matches are case-insensitive substring checks.
# This list is versioned (see manifest); the LLM-assisted phase-2 classifier
# will supersede it.
# ---------------------------------------------------------------------------
KEYWORD_LIST_VERSION: str = "v1.0"

AI_PROGRESS_KEYWORDS: list[str] = [
    # Benchmark / evaluation
    "benchmark", "agi", "performance", "accuracy", "score",
    "superhuman", "human-level", "human level", "pass@",
    "mmlu", "humaneval", "swe-bench", "gpqa", "arc-agi",
    "frontier eval", "eval",
    # Model releases / capabilities
    "gpt-", "gpt4", "gpt 4", "gpt-5", "claude", "gemini", "llama",
    "mistral", "deepseek", "qwen", "phi-", "falcon",
    "language model", "llm", "large language", "foundation model",
    "generative ai", "multimodal", "vision model", "text-to-image",
    "diffusion model", "stable diffusion", "dall-e", "sora",
    # Compute / scaling
    "parameter", "trillion", "billion param", "compute", "flop",
    "training run", "gpu cluster", "h100", "a100", "tpu",
    "scaling law", "chinchilla", "pretraining",
    # Capabilities / milestones
    "reasoning", "coding", "code generation", "agent", "autonomous",
    "alignment", "safety", "jailbreak", "hallucination",
    "context window", "retrieval", "rag",
    # Adoption / impact
    "chatgpt", "copilot", "users", "revenue", "valuation",
    "sam altman", "openai", "anthropic", "deepmind", "google ai",
    "meta ai", "microsoft ai",
    # Generic AI-progress
    "artificial intelligence", " ai ", "machine learning", "deep learning",
    "neural network", "transformer",
]

# Additional title-level exclusion patterns (to filter out non-AI topics that
# might match the above by accident, e.g. "AI" as a country code in sports).
EXCLUSION_KEYWORDS: list[str] = [
    "arsenal",   # "AI" in name but not about AI progress
]

# ---------------------------------------------------------------------------
# Metaculus API
# ---------------------------------------------------------------------------
METACULUS_API_BASE: str = "https://www.metaculus.com/api2/"
METACULUS_PAGE_SIZE: int = 100    # max allowed per page
METACULUS_RATE_SLEEP: float = 1.0  # seconds between page requests (polite)
METACULUS_MAX_PAGES: int = 50      # hard cap — logs if truncated

# Tag IDs / slugs for AI on Metaculus — discovered empirically.
# We query with project/category filter "ai" and also tag-based.
METACULUS_AI_TAGS: list[str] = ["ai", "artificial-intelligence", "machine-learning"]

# ---------------------------------------------------------------------------
# Manifold API
# ---------------------------------------------------------------------------
MANIFOLD_API_BASE: str = "https://api.manifold.markets/v0"
MANIFOLD_PAGE_SIZE: int = 100
MANIFOLD_RATE_SLEEP: float = 1.0   # seconds between requests
MANIFOLD_MAX_PAGES: int = 200      # hard cap — logs if truncated

# Group slugs to search — discovered by hitting /v0/groups?availableToGroupType=public
# and filtering for AI-related names.  Record exactly what we used.
MANIFOLD_AI_GROUP_SLUGS: list[str] = [
    "ai",
    "artificial-intelligence",
    "ai-progress",
    "ai-safety",
    "openai",
    "machine-learning",
    "ai-forecasting",
    "llms",
    "large-language-models",
    "ai-capabilities",
    "ai-alignment",
    "google-deepmind",
    "anthropic",
]

# Liquidity thresholds for RQ4 viability assessment
MANIFOLD_MIN_UNIQUE_BETTORS: int = 20
MANIFOLD_MIN_VOLUME_MANA: float = 1000.0

# ---------------------------------------------------------------------------
# Power-sketch simulation
# ---------------------------------------------------------------------------
POWER_SIM_N_MONTE_CARLO: int = 5000
POWER_SIM_RHO_GRID: list[float] = [0.4, 0.6, 0.75, 0.9]
POWER_SIM_N_GRID: list[int] = [50, 100, 200, 400]
POWER_SIM_ALPHA: float = 0.05
POWER_SIM_INFORMATION_WEIGHT: float = 0.25  # "weaker source carries 25% of info weight"

# ---------------------------------------------------------------------------
# Paths (absolute; set relative to repo root)
# ---------------------------------------------------------------------------
import os as _os
REPO_ROOT: str = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", "..")
)
RAW_DIR: str = _os.path.join(REPO_ROOT, "data", "raw", "recon")
INTERIM_DIR: str = _os.path.join(REPO_ROOT, "data", "interim")
MANIFEST_PATH: str = _os.path.join(REPO_ROOT, "data", "recon_manifest.json")
REPORT_PATH: str = _os.path.join(REPO_ROOT, "docs", "recon_report.md")
EXPERIMENTS_PATH: str = _os.path.join(REPO_ROOT, "docs", "EXPERIMENTS.md")
