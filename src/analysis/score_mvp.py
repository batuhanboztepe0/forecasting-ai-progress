#!/usr/bin/env python3
"""
score_mvp.py — Phase-1 MVP calibration scoring.

Reads  : data/interim/mvp_forecasts.csv  (150 rows = 50 questions × 3 models)
Writes :
  data/interim/mvp_scores.csv       — per-forecaster metrics table
  docs/figures/mvp_calibration.png  — 2×2 reliability diagram
  docs/mvp_results.md               — half-page human-readable summary

No network calls, no LLM calls, no seeds needed (pure computation — no randomness).
Entrypoint: python3 src/analysis/score_mvp.py

Matplotlib note: if matplotlib is not available under the active python3, the script
first tries /opt/homebrew/opt/python@3.11 site-packages (Homebrew default on macOS),
then falls back to `pip install --user matplotlib`. On a clean install run
    python3.11 src/analysis/score_mvp.py
if the fallback path is not present on your machine.

Known-input self-test executes at startup; failure raises AssertionError (loud, no suppression).
"""

import csv
import os
import sys

# ── matplotlib: try import, then fallback locations, then pip --user ──────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    _BREW_311 = (
        "/opt/homebrew/opt/python@3.11/Frameworks/Python.framework/"
        "Versions/3.11/lib/python3.11/site-packages"
    )
    if os.path.isdir(_BREW_311) and _BREW_311 not in sys.path:
        sys.path.insert(0, _BREW_311)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(
            "[setup] matplotlib not found — attempting `pip install --user matplotlib`.\n"
            "        If this fails (PEP 668), run: python3.11 src/analysis/score_mvp.py"
        )
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "matplotlib"])
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

import numpy as np   # confirmed available under python3 and python3.11

# ── paths (absolute, derived from this file's location) ──────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))

CSV_IN  = os.path.join(REPO_ROOT, "data", "interim", "mvp_forecasts.csv")
CSV_OUT = os.path.join(REPO_ROOT, "data", "interim", "mvp_scores.csv")
FIG_OUT = os.path.join(REPO_ROOT, "docs", "figures", "mvp_calibration.png")
MD_OUT  = os.path.join(REPO_ROOT, "docs", "mvp_results.md")

# v2 paths (protocol v2 = reasoning-first elicitation; D-012)
CSV_IN_V2  = os.path.join(REPO_ROOT, "data", "interim", "mvp_forecasts_v2.csv")
CSV_OUT_V2 = os.path.join(REPO_ROOT, "data", "interim", "mvp_scores_v2.csv")
FIG_OUT_V2 = os.path.join(REPO_ROOT, "docs", "figures", "mvp_calibration_v2.png")

# ── constants ─────────────────────────────────────────────────────────────────
MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-5",
    "claude-opus-4-8",
]
MODEL_LABELS = {
    "claude-haiku-4-5-20251001": "Haiku",
    "claude-sonnet-5":           "Sonnet-5",
    "claude-opus-4-8":           "Opus-4-8",
}
# 5 fixed-width bins; n=50 makes finer bins unreliable
BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

# Model cutoffs per D-011 (informational — used only for label text in the summary)
CUTOFFS = {
    "claude-haiku-4-5-20251001": "2025-07-31",
    "claude-sonnet-5":           "2026-01-31",
    "claude-opus-4-8":           "2026-01-31",
}

# ── pure metric functions ─────────────────────────────────────────────────────

def brier_score(probs, outcomes):
    """
    Brier score: mean of (p − y)^2. Lower is better. Proper scoring rule.

    Args:
        probs:    list of float in [0,1]
        outcomes: list of int in {0,1}

    Returns:
        float, or NaN for empty input.
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n


def base_rate_brier(outcomes):
    """
    Brier score of the climatology forecaster (always predicts overall base rate).
    Equals p̄(1−p̄) = Uncertainty term in the Brier decomposition.

    Args:
        outcomes: list of int in {0,1}

    Returns:
        float, or NaN for empty input.
    """
    n = len(outcomes)
    if n == 0:
        return float("nan")
    p_bar = sum(outcomes) / n
    return sum((p_bar - y) ** 2 for y in outcomes) / n


def brier_skill_score(bs, bs_ref):
    """
    Skill score vs the base-rate (climatology) reference: 1 − BS / BS_ref.
    >0 beats the reference; 0 = equal; <0 = worse.

    Args:
        bs:     Brier score of the forecaster
        bs_ref: Brier score of the reference (base-rate) forecaster

    Returns:
        float, or NaN if bs_ref is 0 or NaN.
    """
    if bs_ref == 0 or (bs_ref != bs_ref):  # second condition catches NaN
        return float("nan")
    return 1.0 - bs / bs_ref


def calibration_in_the_large(probs, outcomes):
    """
    mean(forecasts) − mean(outcomes).
    Positive = systematic over-prediction; negative = under-prediction.

    Args:
        probs:    list of float in [0,1]
        outcomes: list of int in {0,1}

    Returns:
        float, or NaN for empty input.
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    return sum(probs) / n - sum(outcomes) / n


def reliability_bins(probs, outcomes, bins):
    """
    Assign forecasts to fixed-width bins and compute per-bin statistics.

    Uses idx = min(floor(p * n_bins), n_bins−1) so that p=1.0 falls in the last bin.

    Args:
        probs:    list of float in [0,1]
        outcomes: list of int in {0,1}
        bins:     sorted list of bin edges (e.g. [0, 0.2, 0.4, 0.6, 0.8, 1.0])

    Returns:
        list of (mean_forecast, obs_freq, n) for each non-empty bin.
    """
    n_bins = len(bins) - 1
    bin_preds = [[] for _ in range(n_bins)]
    bin_outs  = [[] for _ in range(n_bins)]
    for p, y in zip(probs, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        bin_preds[idx].append(p)
        bin_outs[idx].append(y)
    result = []
    for i in range(n_bins):
        n = len(bin_preds[i])
        if n == 0:
            continue
        mean_f = sum(bin_preds[i]) / n
        obs_f  = sum(bin_outs[i]) / n
        result.append((mean_f, obs_f, n))
    return result


# ── known-input self-test ─────────────────────────────────────────────────────

def run_self_test():
    """
    Hand-computed Brier check. Runs at startup; raises AssertionError on failure.

    Test vectors:
      preds=[0.9, 0.1, 0.5], outcomes=[1, 0, 1]
      BS = ((0.9−1)² + (0.1−0)² + (0.5−1)²) / 3
         = (0.01 + 0.01 + 0.25) / 3 = 0.27 / 3 = 0.09  (exact)
    """
    preds    = [0.9, 0.1, 0.5]
    outcomes = [1,   0,   1  ]
    expected = 0.09

    got = brier_score(preds, outcomes)
    assert abs(got - expected) < 1e-9, (
        f"SELF-TEST FAILED: brier_score([0.9,0.1,0.5],[1,0,1]) "
        f"expected {expected}, got {got}"
    )

    # BSS boundary cases
    assert brier_skill_score(0.25, 0.25) == 0.0, "BSS(bs==bs_ref) should be 0.0"
    assert brier_skill_score(0.1, 0.25) > 0.0,   "BSS should be >0 when bs < bs_ref"
    assert brier_skill_score(0.3, 0.25) < 0.0,   "BSS should be <0 when bs > bs_ref"
    # NaN propagation
    import math
    assert math.isnan(brier_skill_score(0.1, 0.0)), "BSS(bs_ref=0) should be NaN"

    print("[self-test] PASS — Brier=0.09 confirmed; BSS boundary cases OK")


# ── data loading ──────────────────────────────────────────────────────────────

def load_data(path):
    """
    Parse mvp_forecasts.csv.

    Returns:
        questions (dict): qid → {outcome, crowd_prob, haiku_post_cutoff}
            crowd_prob: Manifold price at T = resolved_at − 30d
            haiku_post_cutoff: is_post_cutoff flag from the haiku row (0 or 1),
                used for the crowd's pre/post split per task specification.
        model_data (dict): model → list of {qid, prob, is_post_cutoff, outcome}
    """
    questions  = {}
    model_data = {m: [] for m in MODELS}

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            qid     = row["qid"]
            model   = row["model"]
            outcome = int(row["outcome"])
            crowd   = float(row["crowd_prob_at_T"])
            prob    = float(row["model_prob"])
            post    = int(row["is_post_cutoff"])

            if qid not in questions:
                questions[qid] = {
                    "outcome":           outcome,
                    "crowd_prob":        crowd,
                    "haiku_post_cutoff": None,
                }

            # Haiku row carries the haiku-cutoff flag used for the crowd's split
            if model == MODELS[0]:   # "claude-haiku-4-5-20251001"
                questions[qid]["haiku_post_cutoff"] = post

            if model in model_data:
                model_data[model].append({
                    "qid":            qid,
                    "prob":           prob,
                    "is_post_cutoff": post,
                    "outcome":        outcome,
                })

    return questions, model_data


# ── sanity checks ─────────────────────────────────────────────────────────────

def sanity_check(questions, model_data):
    """
    Structural integrity checks. Raises ValueError on hard failures.

    Returns:
        list of str — one 'PASS' message confirming the checks, or error details.
    """
    nq = len(questions)
    if nq != 50:
        raise ValueError(f"Expected 50 unique questions, found {nq}")

    for m in MODELS:
        nm = len(model_data[m])
        if nm != 50:
            raise ValueError(f"Model {m}: expected 50 rows, found {nm}")

    for qid, q in questions.items():
        y = q["outcome"]
        if y not in (0, 1):
            raise ValueError(f"qid {qid}: outcome={y} not in {{0,1}}")
        cp = q["crowd_prob"]
        if not (0.0 <= cp <= 1.0):
            raise ValueError(f"qid {qid}: crowd_prob={cp} outside [0,1]")
        if q["haiku_post_cutoff"] is None:
            raise ValueError(f"qid {qid}: haiku_post_cutoff missing (no haiku row?)")

    for m in MODELS:
        for row in model_data[m]:
            p = row["prob"]
            if not (0.0 <= p <= 1.0):
                raise ValueError(
                    f"Model {m}, qid {row['qid']}: prob={p} outside [0,1]"
                )

    return [
        "PASS — 50 questions, 3×50 model rows, outcomes in {0,1}, "
        "crowd probs and model probs all in [0,1]"
    ]


# ── per-forecaster scoring ────────────────────────────────────────────────────

def score_forecaster(probs_all, outs_all, probs_pre, outs_pre, probs_post, outs_post):
    """
    Compute the full metrics dict for one forecaster.

    BSS reference (climatology) is computed on the same question subset as the forecaster,
    so pre-cutoff BSS uses the pre-cutoff base rate, and post-cutoff BSS uses the
    post-cutoff base rate.

    Args:
        probs_all / outs_all  : full set (all 50 questions for this forecaster)
        probs_pre / outs_pre  : pre-cutoff subset
        probs_post / outs_post: post-cutoff subset

    Returns:
        dict with keys:
          brier_overall, brier_pre, brier_post,
          bss_overall, bss_pre, bss_post,
          citl_overall, n_all, n_pre, n_post
    """
    bs_all  = brier_score(probs_all,  outs_all)
    bs_pre  = brier_score(probs_pre,  outs_pre)
    bs_post = brier_score(probs_post, outs_post)

    br_all  = base_rate_brier(outs_all)
    br_pre  = base_rate_brier(outs_pre)
    br_post = base_rate_brier(outs_post)

    return {
        "brier_overall": bs_all,
        "brier_pre":     bs_pre,
        "brier_post":    bs_post,
        "bss_overall":   brier_skill_score(bs_all,  br_all),
        "bss_pre":       brier_skill_score(bs_pre,  br_pre),
        "bss_post":      brier_skill_score(bs_post, br_post),
        "citl_overall":  calibration_in_the_large(probs_all, outs_all),
        "n_all":         len(probs_all),
        "n_pre":         len(probs_pre),
        "n_post":        len(probs_post),
    }


def compute_all_scores(questions, model_data):
    """
    Score all 4 forecasters: crowd + 3 models.

    Crowd pre/post split uses haiku's is_post_cutoff flag (D-011 table symmetry rule),
    labeled explicitly in the returned dict key.

    Returns:
        OrderedDict-like dict: forecaster_name → metrics dict
    """
    qids = sorted(questions.keys())

    # ── crowd ─────────────────────────────────────────────────────────────────
    crowd_all  = [(questions[q]["crowd_prob"], questions[q]["outcome"]) for q in qids]
    crowd_pre  = [(questions[q]["crowd_prob"], questions[q]["outcome"]) for q in qids
                  if questions[q]["haiku_post_cutoff"] == 0]
    crowd_post = [(questions[q]["crowd_prob"], questions[q]["outcome"]) for q in qids
                  if questions[q]["haiku_post_cutoff"] == 1]

    def _unzip(pairs):
        if not pairs:
            return [], []
        ps, ys = zip(*pairs)
        return list(ps), list(ys)

    cp_all,  co_all  = _unzip(crowd_all)
    cp_pre,  co_pre  = _unzip(crowd_pre)
    cp_post, co_post = _unzip(crowd_post)

    results = {}
    results["crowd (haiku split)"] = score_forecaster(
        cp_all, co_all, cp_pre, co_pre, cp_post, co_post,
    )

    # ── models ────────────────────────────────────────────────────────────────
    for m in MODELS:
        rows = model_data[m]
        all_  = [(r["prob"], r["outcome"]) for r in rows]
        pre   = [(r["prob"], r["outcome"]) for r in rows if r["is_post_cutoff"] == 0]
        post  = [(r["prob"], r["outcome"]) for r in rows if r["is_post_cutoff"] == 1]

        pa, oa = _unzip(all_)
        pp, op = _unzip(pre)
        pq, oq = _unzip(post)

        results[MODEL_LABELS[m]] = score_forecaster(pa, oa, pp, op, pq, oq)

    return results


# ── anomaly detection ─────────────────────────────────────────────────────────

def detect_anomalies(results):
    """
    Flag values that warrant explicit attention. Does NOT suppress anything.

    Thresholds (exploratory for MVP; n=50 is pre-confirmatory):
      - Brier overall > 0.30: abnormally bad for a calibrated forecaster.
      - Post-cutoff BSS ≤ 0: no better than the naive base-rate forecaster post-cutoff.
      - |CITL| > 0.15: large systematic bias (over- or under-prediction).

    Returns:
        list of str — anomaly messages, or one 'sane' message if nothing flagged.
    """
    import math
    flags = []
    for name, m in results.items():
        bs = m["brier_overall"]
        if bs > 0.30:
            flags.append(
                f"ANOMALY: {name} — overall Brier={bs:.4f} > 0.30; "
                "worse than expected for a forecasting-capable source."
            )
        bss_post = m["bss_post"]
        if not math.isnan(bss_post) and bss_post <= 0.0:
            flags.append(
                f"FLAG (H2-relevant): {name} — post-cutoff BSS={bss_post:+.4f} ≤ 0 "
                f"(n_post={m['n_post']}); no better than the naive base-rate on post-cutoff questions. "
                "N=50 — do not treat as confirmatory."
            )
        citl = m["citl_overall"]
        if abs(citl) > 0.15:
            flags.append(
                f"FLAG: {name} — |CITL|={abs(citl):.4f} > 0.15; "
                f"large {'over' if citl > 0 else 'under'}-prediction bias."
            )
    if not flags:
        flags.append("All anomaly checks passed — numbers appear plausible for n=50.")
    return flags


# ── reliability diagram (2×2 grid) ───────────────────────────────────────────

def plot_reliability(questions, model_data, out_path, title_suffix=""):
    """
    2×2 reliability diagram: crowd (top-left), Haiku (top-right),
    Sonnet-5 (bottom-left), Opus-4-8 (bottom-right).

    5 fixed-width bins [0,0.2), [0.2,0.4), ..., [0.8,1.0].
    Per-bin counts annotated. N=50 noted. Saves PNG to out_path.
    """
    qids = sorted(questions.keys())

    panel_sources = [
        ("Crowd\n(Manifold T=res−30d)",
         [questions[q]["crowd_prob"] for q in qids],
         [questions[q]["outcome"]    for q in qids]),
    ]
    for m in MODELS:
        rows_sorted = sorted(model_data[m], key=lambda r: r["qid"])
        probs    = [r["prob"]    for r in rows_sorted]
        outcomes = [r["outcome"] for r in rows_sorted]
        panel_sources.append((MODEL_LABELS[m], probs, outcomes))

    fig, axes = plt.subplots(2, 2, figsize=(9, 8))
    axes_flat = axes.flatten()

    fig.suptitle(
        f"MVP Reliability Diagrams  —  n = 50 questions, 5 fixed-width bins{title_suffix}\n"
        "(small n → high per-bin variance; interpret cautiously)",
        fontsize=10,
        y=0.98,
    )

    for ax, (title, probs, outcomes) in zip(axes_flat, panel_sources):
        bins_result = reliability_bins(probs, outcomes, BINS)

        if not bins_result:
            ax.set_title(title, fontsize=9)
            ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
            continue

        x_pts  = [mf for mf, _,  _ in bins_result]
        y_pts  = [of for _,  of, _ in bins_result]
        ns     = [n  for _,  _,  n in bins_result]

        # perfect calibration diagonal
        ax.plot([0, 1], [0, 1], "--", color="#888888", lw=0.9, label="Perfect calibration")

        # shaded region to guide the eye (over- vs under-confidence)
        ax.fill_between([0, 1], [0, 1], [0, 0], alpha=0.04, color="red",   label="Over-confident")
        ax.fill_between([0, 1], [0, 1], [1, 1], alpha=0.04, color="green", label="Under-confident")

        # dots sized proportional to bin count
        dot_sizes = [max(60, n * 20) for n in ns]
        ax.scatter(x_pts, y_pts, s=dot_sizes, color="steelblue", alpha=0.85, zorder=3)

        # line connecting points
        if len(x_pts) > 1:
            ax.plot(x_pts, y_pts, "-", color="steelblue", alpha=0.5, lw=1.0)

        # annotate bin counts
        for xp, yp, n in zip(x_pts, y_pts, ns):
            ax.annotate(
                f"n={n}", (xp, yp),
                textcoords="offset points", xytext=(5, 4),
                fontsize=7, color="#333333",
            )

        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.07, 1.07)
        ax.set_xlabel("Mean forecast probability", fontsize=8)
        ax.set_ylabel("Observed frequency",        fontsize=8)
        ax.set_title(title, fontsize=9, pad=4)
        ax.tick_params(labelsize=7)
        ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] Reliability diagram saved to {out_path}")


# ── CSV output ────────────────────────────────────────────────────────────────

SCORE_FIELDS = [
    "forecaster", "n_all", "n_pre", "n_post",
    "brier_overall", "brier_pre", "brier_post",
    "bss_overall",   "bss_pre",   "bss_post",
    "citl_overall",
]


def write_scores_csv(results, path):
    """Write per-forecaster metrics to CSV."""

    def _fmt(v):
        if isinstance(v, float):
            import math
            return "nan" if math.isnan(v) else f"{v:.6f}"
        return str(v)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        for name, m in results.items():
            row = {"forecaster": name}
            for field in SCORE_FIELDS:
                if field == "forecaster":
                    continue
                row[field] = _fmt(m[field])
            writer.writerow(row)
    print(f"[output] Scores CSV written to {path}")


# ── markdown summary ──────────────────────────────────────────────────────────

def write_md_summary(results, anomalies, path):
    """
    Write a half-page human-readable summary to docs/mvp_results.md.
    Descriptive only — n=50 is pre-confirmatory; no p-values, no CI.
    """
    import math

    def _f(v, fmt=".4f"):
        if math.isnan(v):
            return "—"
        return f"{v:{fmt}}"

    lines = [
        "# MVP Scoring Results — Phase 1 Thin Slice",
        "",
        "**N = 50 questions × 3 models (Haiku, Sonnet-5, Opus-4-8) + Manifold crowd.**  ",
        "All figures are descriptive; n = 50 is too small for confirmatory tests or confidence intervals.",
        "Crowd pre/post split uses the Haiku cutoff (2025-07-31) for table symmetry; labeled accordingly.",
        "BSS = Brier Skill Score vs. the climatology (base-rate) forecaster; positive = beats base rate.",
        "CITL = Calibration-in-the-Large (mean forecast − base rate); positive = systematic over-prediction.",
        "",
        "## Scores table",
        "",
        "| Forecaster | N (pre/post) | Brier overall | Brier pre | Brier post | BSS overall | BSS pre | BSS post | CITL overall |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for name, m in results.items():
        row = (
            f"| {name} "
            f"| {m['n_pre']}/{m['n_post']} "
            f"| {_f(m['brier_overall'])} "
            f"| {_f(m['brier_pre'])} "
            f"| {_f(m['brier_post'])} "
            f"| {_f(m['bss_overall'], '+.4f')} "
            f"| {_f(m['bss_pre'],     '+.4f')} "
            f"| {_f(m['bss_post'],    '+.4f')} "
            f"| {_f(m['citl_overall'],'+.4f')} |"
        )
        lines.append(row)

    crowd_m  = results["crowd (haiku split)"]
    haiku_m  = results["Haiku"]
    sonnet_m = results["Sonnet-5"]
    opus_m   = results["Opus-4-8"]

    lines += [
        "",
        "## Observations (descriptive, n = 50, no hypothesis tests)",
        "",
        (
            f"The Manifold crowd achieves an overall Brier score of {_f(crowd_m['brier_overall'])} "
            f"(BSS {_f(crowd_m['bss_overall'], '+.4f')} vs. base rate, "
            f"CITL {_f(crowd_m['citl_overall'], '+.4f')}), "
            "suggesting it extracts meaningful signal from the question set while remaining close to "
            "the base rate on average."
        ),
        (
            f"Among the three models, Haiku scores Brier {_f(haiku_m['brier_overall'])} overall "
            f"(BSS {_f(haiku_m['bss_overall'], '+.4f')}, "
            f"CITL {_f(haiku_m['citl_overall'], '+.4f')}); "
            f"Sonnet-5 scores {_f(sonnet_m['brier_overall'])} "
            f"(BSS {_f(sonnet_m['bss_overall'], '+.4f')}, "
            f"CITL {_f(sonnet_m['citl_overall'], '+.4f')}); "
            f"Opus-4-8 scores {_f(opus_m['brier_overall'])} "
            f"(BSS {_f(opus_m['bss_overall'], '+.4f')}, "
            f"CITL {_f(opus_m['citl_overall'], '+.4f')})."
        ),
        (
            "Post-cutoff n is 25 for Haiku and only 15 for Sonnet-5 and Opus-4-8; "
            "pre/post Brier differences at this sample size are highly variable and should not be "
            "interpreted as evidence for or against H2 (RQ2 is Phase-2 confirmatory)."
        ),
        (
            "The reliability diagram (docs/figures/mvp_calibration.png) shows that the crowd "
            "tracks the diagonal well in the low- and high-probability regions. "
            "All three models show non-trivial deviation from perfect calibration at n=50, "
            "but with ≤ 12 points per bin, individual bin estimates are noisy."
        ),
        "",
        "## Anomaly flags",
        "",
    ]
    for a in anomalies:
        lines.append(f"- {a}")

    lines += [
        "",
        "## Limitations",
        "",
        "- n = 50 is the MVP thin slice — diagnostic only.",
        "- No bootstrap CIs at this stage (Phase-2 gate: n ≥ 175 clean post-cutoff questions).",
        "- Single 30-day snapshot horizon per D-007; no multi-horizon robustness.",
        "- Sonnet-5 and Opus-4-8 share the same training cutoff (2026-01-31), so their "
          "post-cutoff N is only 15, limiting pre/post contrast for those models.",
        "- Reliability diagram uses 5 fixed-width bins; with n ≤ 12 per bin, "
          "calibration estimates are unstable.",
        "- Crowd CITL could reflect prediction-market microstructure (thin markets, "
          "fee pressure) as well as forecaster bias.",
        "- Single-provider model panel (Anthropic only); no cross-provider generalization (D-011).",
        "",
        "## Artifacts",
        "",
        "- Figure: `docs/figures/mvp_calibration.png`",
        "- Scores: `data/interim/mvp_scores.csv`",
    ]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[output] Markdown summary written to {path}")


# ── main ──────────────────────────────────────────────────────────────────────

def run_pipeline(csv_in, csv_out, fig_out, md_out, title_suffix=""):
    """
    Full scoring pipeline parameterized by I/O paths.

    Args:
        csv_in:       Path to input forecasts CSV.
        csv_out:      Path to write per-forecaster scores CSV.
        fig_out:      Path to write reliability diagram PNG.
        md_out:       Path to write markdown summary, or None to skip.
        title_suffix: String appended to the reliability diagram title
                      (e.g. ' — Protocol v2').
    """
    run_self_test()

    print(f"[data] Loading {csv_in}")
    questions, model_data = load_data(csv_in)

    sanity_msgs = sanity_check(questions, model_data)
    for msg in sanity_msgs:
        print(f"[sanity] {msg}")

    results   = compute_all_scores(questions, model_data)
    anomalies = detect_anomalies(results)

    for name, m in results.items():
        import math
        bss_post_str = "nan" if math.isnan(m["bss_post"]) else f"{m['bss_post']:+.4f}"
        print(
            f"[score] {name:30s}  "
            f"BS={m['brier_overall']:.4f}  "
            f"BSS={m['bss_overall']:+.4f}  "
            f"CITL={m['citl_overall']:+.4f}  "
            f"(pre n={m['n_pre']}  post n={m['n_post']}  BSS_post={bss_post_str})"
        )

    for a in anomalies:
        print(f"[check] {a}")

    write_scores_csv(results, csv_out)
    plot_reliability(questions, model_data, fig_out, title_suffix=title_suffix)
    if md_out is not None:
        write_md_summary(results, anomalies, md_out)

    print("[done] MVP scoring complete.")


def main():
    """Run the v1 scoring pipeline (default paths, no title suffix)."""
    run_pipeline(CSV_IN, CSV_OUT, FIG_OUT, MD_OUT)


if __name__ == "__main__":
    if "--protocol" in sys.argv:
        _idx = sys.argv.index("--protocol")
        if _idx + 1 >= len(sys.argv):
            raise ValueError("--protocol requires a value (e.g. v2)")
        _proto = sys.argv[_idx + 1]
        if _proto == "v2":
            run_pipeline(CSV_IN_V2, CSV_OUT_V2, FIG_OUT_V2, None,
                         title_suffix=" — Protocol v2")
        else:
            raise ValueError(f"Unknown --protocol value: {_proto!r}  (expected 'v2')")
    else:
        main()
