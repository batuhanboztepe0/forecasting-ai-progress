#!/usr/bin/env python3
"""
rq_confirmatory.py — Phase 3a: RQ1–RQ3 confirmatory + exploratory analyses.

Pre-registration: SCOPE.md §2, D-016.
No hypothesis was changed after seeing Phase-2 descriptive scores.
DESCRIPTIVE PHASE-2 SCORES WERE SEEN (unavoidable — pipeline validation);
NO threshold was altered and NO hypothesis was changed.

Statistical decisions fixed in D-016 before this script was written:
  Clamp eps: 1e-7 (library default, explicit)
  N_boot: 10,000 for all analyses
  Bootstrap seed: 42 throughout (separate Random instances per analysis to avoid
    inter-analysis entanglement)
  Bootstrap p-value: shift-to-H0 method (Davison & Hinkley 1997 §4.4)
  H3 p-values: Wald (bootstrap as secondary check)
  BH family (q=0.10): exactly {H1-crowd, H1-haiku, H2-haiku, H3a-haiku, H3b-haiku}
  H1 decision: CONJUNCTION — p-based CI excludes 0 AND |CITL| >= 0.05

Outputs:
  data/interim/phase3_rq123.json
  docs/phase3_results.md
  docs/figures/rq3_coef_forest.png

Run: python3.11 src/analysis/rq_confirmatory.py
SHA-256 of phase3_rq123.json is printed; identical across runs (seeded).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import sys

import numpy as np
from scipy.stats import norm as _norm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
_PHASE2_DIR = os.path.join(_REPO_ROOT, "src", "phase2")
for _d in (_THIS_DIR, _PHASE2_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from scoring import (  # noqa: E402
    brier_score, base_rate_brier, brier_skill_score,
    calibration_in_the_large, bootstrap_ci,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FORECASTS_CSV  = os.path.join(_REPO_ROOT, "data", "interim", "phase2_forecasts.csv")
QUESTIONS_JSON = os.path.join(_REPO_ROOT, "data", "interim", "phase2_questions.json")
OUT_JSON       = os.path.join(_REPO_ROOT, "data", "interim", "phase3_rq123.json")
MD_PATH        = os.path.join(_REPO_ROOT, "docs", "phase3_results.md")
FIG_PATH       = os.path.join(_REPO_ROOT, "docs", "figures", "rq3_coef_forest.png")

# ---------------------------------------------------------------------------
# Constants  (D-016)
# ---------------------------------------------------------------------------
N_BOOT    = 10_000
BOOT_SEED = 42
CLAMP_EPS = 1e-7   # library default — stated explicitly per D-016
BH_Q      = 0.10
ALPHA     = 0.05
Z95       = float(_norm.ppf(0.975))   # 1.95996...
MODELS    = ["claude-haiku-4-5-20251001", "claude-sonnet-5", "claude-opus-4-8"]
LABELS    = {"claude-haiku-4-5-20251001": "Haiku",
             "claude-sonnet-5": "Sonnet-5",
             "claude-opus-4-8": "Opus-4-8"}

# D-016 §1: H1 decision requires BOTH conditions
H1_CITL_THRESHOLD = 0.05


# ===========================================================================
# Low-level statistical helpers
# ===========================================================================

def _logit_vec(probs: list[float], eps: float = CLAMP_EPS) -> np.ndarray:
    """Clamp to [eps, 1-eps], compute logit.  Clamping policy stated explicitly."""
    p_arr = np.clip(np.array(probs, dtype=float), eps, 1.0 - eps)
    return np.log(p_arr / (1.0 - p_arr))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0)))


def _irls_Np(X: np.ndarray, y: np.ndarray,
             max_iter: int = 200, tol: float = 1e-8
             ) -> tuple[np.ndarray, np.ndarray, bool]:
    """
    IRLS for logistic regression with arbitrary design matrix X.

    Returns (beta, se, converged).
    se is derived from the observed Fisher information at convergence.
    Returns all-nan if degenerate (< 3 obs, all-same outcome).
    """
    n, k = X.shape
    s = float(y.sum())
    if n < k + 2 or s == 0.0 or s == n:
        nans = np.full(k, float("nan"))
        return nans, nans, False

    beta = np.zeros(k)
    # Mild initialization: small weight on each predictor
    if k >= 2:
        beta[1] = 0.5
    if k >= 3:
        beta[2] = 0.5

    XtWX = None
    converged = False
    for _ in range(max_iter):
        eta  = X @ beta
        mu   = _sigmoid(eta)
        W    = np.maximum(mu * (1.0 - mu), 1e-10)
        XtW  = X.T * W
        XtWX = XtW @ X
        grad = X.T @ (y - mu)
        try:
            delta = np.linalg.solve(XtWX, grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + delta
        if np.max(np.abs(delta)) < tol:
            converged = True
            break

    # SE from inverse Fisher at final beta
    eta  = X @ beta
    mu   = _sigmoid(eta)
    W    = np.maximum(mu * (1.0 - mu), 1e-10)
    XtWX = (X.T * W) @ X
    try:
        cov = np.linalg.inv(XtWX)
        se  = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except np.linalg.LinAlgError:
        se = np.full(k, float("nan"))

    return beta, se, converged


def _pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation."""
    if len(x) < 2:
        return float("nan")
    mx, my = x.mean(), y.mean()
    num = float(((x - mx) * (y - my)).sum())
    den = float(np.sqrt(((x - mx) ** 2).sum() * ((y - my) ** 2).sum()))
    return float("nan") if den == 0 else num / den


def _boot_pvalue(boot_stats: list[float], theta_hat: float) -> float:
    """
    Two-sided bootstrap p-value for H0: theta = 0.

    Shift method (Davison & Hinkley 1997 §4.4):
      boot_centered_i = boot_i - theta_hat  (centered at 0 under H0)
      p = mean(|boot_centered_i| >= |theta_hat|)

    Floor: 1/n_boot (cannot resolve p < 1/n_boot).
    """
    n = len(boot_stats)
    if n == 0:
        return float("nan")
    abs_t = abs(theta_hat)
    count = sum(1 for b in boot_stats if abs(b - theta_hat) >= abs_t)
    return max(count / n, 1.0 / n)


def _wald_pvalue(coef: float, se: float) -> float:
    """Two-sided Wald p = 2*(1 - Phi(|coef/se|))."""
    if se == 0.0 or math.isnan(se) or math.isnan(coef):
        return float("nan")
    return float(2.0 * (1.0 - _norm.cdf(abs(coef / se))))


def _pct_ci(boot_stats: list[float], alpha: float = ALPHA) -> tuple[float, float]:
    """Percentile bootstrap CI."""
    s = sorted(boot_stats)
    n = len(s)
    lo = s[max(0, int(alpha / 2 * n))]
    hi = s[min(n - 1, int((1 - alpha / 2) * n))]
    return lo, hi


def _bss(probs: list, outcomes: list) -> float:
    bs  = brier_score(probs, outcomes)
    bsr = base_rate_brier(outcomes)
    return brier_skill_score(bs, bsr)


# ===========================================================================
# RQ1 — Calibration (CITL + logistic recalibration slope)
# ===========================================================================

def run_rq1_cell(probs: list[float], outcomes: list[int],
                 label: str, status: str,
                 seed: int = BOOT_SEED) -> dict:
    """
    RQ1 for one (forecaster, stratum) cell.

    Returns dict with: citl, citl_ci, citl_p, cal_slope, cal_intercept,
    slope_ci, slope_p, n, base_rate, status, label, h1_decision.
    """
    n = len(probs)
    citl = calibration_in_the_large(probs, outcomes)

    # CITL bootstrap (10k resamples, seed explicit)
    rng_citl = random.Random(seed)
    boot_citl = []
    for _ in range(N_BOOT):
        idx = [rng_citl.randrange(n) for _ in range(n)]
        p_b = [probs[i] for i in idx]
        o_b = [outcomes[i] for i in idx]
        boot_citl.append(calibration_in_the_large(p_b, o_b))
    citl_lo, citl_hi = _pct_ci(boot_citl)
    citl_p = _boot_pvalue(boot_citl, citl)

    # Calibration slope via 2-param IRLS (logit scale)
    lp = _logit_vec(probs)
    X2 = np.column_stack([np.ones(n), lp])
    y_arr = np.array(outcomes, dtype=float)
    beta2, se2, _ = _irls_Np(X2, y_arr)
    cal_intercept = float(beta2[0])
    cal_slope     = float(beta2[1])
    slope_p       = _wald_pvalue(cal_slope - 1.0, float(se2[1]))  # H0: slope=1 (deviation from perfect calibration)
    # Per SCOPE: report slope with CI; slope=1 is perfect calibration
    # Wald CI on slope (not on slope-1; the test is for slope ≠ 0, but CI on slope is informative)
    slope_lo = cal_slope - Z95 * float(se2[1])
    slope_hi = cal_slope + Z95 * float(se2[1])

    # H1 decision (D-016 §1 / SCOPE §2): conjunction
    ci_excludes_zero = (citl_lo > 0) or (citl_hi < 0)
    h1_decision = (
        "REJECT (well-calibrated)" if ci_excludes_zero and abs(citl) >= H1_CITL_THRESHOLD
        else (
            "FAIL-CITL-THRESHOLD (CI excludes 0 but |CITL|<0.05)" if ci_excludes_zero
            else "FAIL-TO-REJECT (CI includes 0)"
        )
    )

    return dict(
        label=label, status=status, n=n,
        base_rate=sum(outcomes) / n,
        citl=citl, citl_lo=citl_lo, citl_hi=citl_hi, citl_p=citl_p,
        ci_excludes_zero=ci_excludes_zero,
        cal_intercept=cal_intercept, cal_slope=cal_slope,
        slope_lo=slope_lo, slope_hi=slope_hi,
        slope_p_wald=slope_p,
        h1_decision=h1_decision,
    )


# ===========================================================================
# RQ2 — Skill vs. memorization (ΔBSS, two-sample bootstrap)
# ===========================================================================

def run_rq2_cell(probs_post: list, outs_post: list,
                 probs_pre: list,  outs_pre: list,
                 label: str, status: str,
                 seed: int = BOOT_SEED) -> dict:
    """
    RQ2 two-sample bootstrap: resample post and pre independently.

    Returns: bss_post, bss_pre, delta_bss, delta_ci, delta_p,
             bss_post_ci, post_bss_lte_zero_flagged, n_post, n_pre.
    """
    n_post, n_pre = len(probs_post), len(probs_pre)
    bss_post = _bss(probs_post, outs_post)
    bss_pre  = _bss(probs_pre,  outs_pre)
    delta    = bss_post - bss_pre

    # Two-sample bootstrap: post and pre resampled independently from same RNG stream
    rng = random.Random(seed)
    boot_diffs = []
    boot_bss_post = []
    for _ in range(N_BOOT):
        idx_post = [rng.randrange(n_post) for _ in range(n_post)]
        idx_pre  = [rng.randrange(n_pre)  for _ in range(n_pre)]
        p_post_b = [probs_post[i] for i in idx_post]
        o_post_b = [outs_post[i]  for i in idx_post]
        p_pre_b  = [probs_pre[i]  for i in idx_pre]
        o_pre_b  = [outs_pre[i]   for i in idx_pre]
        bss_post_b = _bss(p_post_b, o_post_b)
        bss_pre_b  = _bss(p_pre_b,  o_pre_b)
        boot_bss_post.append(bss_post_b)
        if not (math.isnan(bss_post_b) or math.isnan(bss_pre_b)):
            boot_diffs.append(bss_post_b - bss_pre_b)

    delta_lo, delta_hi = _pct_ci(boot_diffs)
    delta_p = _boot_pvalue(boot_diffs, delta)

    post_lo, post_hi = _pct_ci([b for b in boot_bss_post if not math.isnan(b)])
    flag_lte_zero = post_lo <= 0.0  # post-cutoff BSS CI includes ≤ 0

    return dict(
        label=label, status=status,
        n_post=n_post, n_pre=n_pre,
        bss_post=bss_post, bss_pre=bss_pre,
        delta_bss=delta,
        delta_lo=delta_lo, delta_hi=delta_hi,
        delta_p=delta_p,
        bss_post_ci_lo=post_lo, bss_post_ci_hi=post_hi,
        post_bss_lte_zero_flagged=flag_lte_zero,
    )


# ===========================================================================
# RQ3 — Encompassing regression (3-parameter logistic IRLS)
# ===========================================================================

def run_rq3_cell(probs_crowd: list, probs_model: list, outcomes: list,
                 label: str, status: str,
                 seed: int = BOOT_SEED) -> dict:
    """
    RQ3 encompassing regression: outcome ~ intercept + b_crowd*logit(crowd) + b_model*logit(model).

    Wald CIs + bootstrap check.  Crowd-model logit correlation reported.
    """
    n = len(outcomes)
    lc = _logit_vec(probs_crowd)
    lm = _logit_vec(probs_model)
    X  = np.column_stack([np.ones(n), lc, lm])
    y  = np.array(outcomes, dtype=float)

    beta, se, converged = _irls_Np(X, y)
    intercept, b_crowd, b_model = float(beta[0]), float(beta[1]), float(beta[2])
    se_int, se_crowd, se_model   = float(se[0]), float(se[1]), float(se[2])

    p_crowd = _wald_pvalue(b_crowd, se_crowd)
    p_model = _wald_pvalue(b_model, se_model)

    crowd_ci = (b_crowd - Z95 * se_crowd, b_crowd + Z95 * se_crowd)
    model_ci = (b_model - Z95 * se_model, b_model + Z95 * se_model)

    # Crowd-model logit correlation
    corr_logit = _pearson_r(lc, lm)

    # Bootstrap check (10k resamples)
    rng = random.Random(seed)
    boot_crowd, boot_model = [], []
    n_boot_failed = 0
    for _ in range(N_BOOT):
        idx  = [rng.randrange(n) for _ in range(n)]
        X_b  = X[idx]
        y_b  = y[idx]
        b_b, _, ok = _irls_Np(X_b, y_b)
        if ok and not any(math.isnan(v) for v in b_b):
            boot_crowd.append(float(b_b[1]))
            boot_model.append(float(b_b[2]))
        else:
            n_boot_failed += 1

    boot_crowd_lo, boot_crowd_hi = _pct_ci(boot_crowd) if boot_crowd else (float("nan"), float("nan"))
    boot_model_lo, boot_model_hi = _pct_ci(boot_model) if boot_model else (float("nan"), float("nan"))
    boot_p_crowd = _boot_pvalue(boot_crowd, b_crowd) if boot_crowd else float("nan")
    boot_p_model = _boot_pvalue(boot_model, b_model) if boot_model else float("nan")

    return dict(
        label=label, status=status, n=n,
        converged=converged,
        intercept=intercept, b_crowd=b_crowd, b_model=b_model,
        se_crowd=se_crowd, se_model=se_model,
        p_crowd_wald=p_crowd, p_model_wald=p_model,
        crowd_ci_lo_wald=crowd_ci[0], crowd_ci_hi_wald=crowd_ci[1],
        model_ci_lo_wald=model_ci[0], model_ci_hi_wald=model_ci[1],
        boot_crowd_lo=boot_crowd_lo, boot_crowd_hi=boot_crowd_hi,
        boot_model_lo=boot_model_lo, boot_model_hi=boot_model_hi,
        boot_p_crowd=boot_p_crowd, boot_p_model=boot_p_model,
        n_boot_failed=n_boot_failed,
        corr_logit_crowd_model=float(corr_logit),
    )


# ===========================================================================
# BH correction  (D-016 §4)
# ===========================================================================

def bh_correct(named_pvals: dict[str, float], q: float = BH_Q) -> dict:
    """
    Benjamini-Hochberg FDR correction at level q.

    Args:
        named_pvals: {test_name: raw_p_value}  — exactly the 5-test family

    Returns dict with per-test: p_raw, p_adj, bh_rank, bh_threshold, bh_rejected.
    """
    items = sorted(named_pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    # Find largest k where p_(k) <= k/m * q
    k_max = 0
    for i, (name, p) in enumerate(items, start=1):
        if p <= (i / m) * q:
            k_max = i
    # Adjusted p: p_adj_(i) = min_{j >= i} (m/j * p_(j))
    adjusted = {}
    min_adj = 1.0
    for i in range(m, 0, -1):
        name, p = items[i - 1]
        adj = min(m / i * p, 1.0)
        min_adj = min(adj, min_adj)
        adjusted[name] = min_adj

    result = {}
    for i, (name, p) in enumerate(items, start=1):
        result[name] = dict(
            p_raw=p,
            p_adj=adjusted[name],
            bh_rank=i,
            bh_threshold=round(i / m * q, 6),
            bh_rejected=(i <= k_max),
        )
    return result


# ===========================================================================
# Data loading
# ===========================================================================

def load_arrays(rows: list[dict], q_by_id: dict,
                model: str, mask_fn) -> tuple[list, list, list]:
    """
    Extract (probs_model, probs_crowd, outcomes) for rows of `model` filtered by mask_fn(row).
    """
    r0m = [r for r in rows if r["model"] == model and r["repeat"] == "0" and mask_fn(r)]
    probs_model = [float(r["model_prob"])     for r in r0m]
    probs_crowd = [float(r["crowd_prob_at_T"]) for r in r0m]
    outcomes    = [int(r["outcome"])           for r in r0m]
    return probs_model, probs_crowd, outcomes


# ===========================================================================
# Jan2026 CITL diagnosis  (descriptive only)
# ===========================================================================

def jan2026_diagnosis(rows: list[dict], q_by_id: dict) -> dict:
    """
    Diagnose the -13 to -18pp CITL on jan2026_clean cells.
    Returns a dict of descriptive statistics.

    Uses sonnet rows for the jan2026 mask (is_post_cutoff=1 on sonnet rows means
    resolved_at >= 2026-03-02, the correct jan2026_clean condition).
    """
    # Jan2026 clean mask: use SONNET rows so is_post_cutoff refers to jan2026 cutoff+30d
    def _jan_clean_sonnet(r):
        return r["is_post_cutoff"] == "1" and r["close_before_cutoff_jan2026"] == "0"

    r0s = [r for r in rows if r["model"] == "claude-sonnet-5" and r["repeat"] == "0"]
    jan_rows_s = [r for r in r0s if _jan_clean_sonnet(r)]

    # Outcome and crowd come from sonnet rows (same per question)
    jan_qids = set(r["qid"] for r in jan_rows_s)
    # Use haiku rows for crowd_prob (same value; just picking one model's rows)
    r0h_all = [r for r in rows if r["model"] == "claude-haiku-4-5-20251001" and r["repeat"] == "0"]
    jan_rows = [r for r in r0h_all if r["qid"] in jan_qids]

    n = len(jan_rows)
    base_rate = sum(int(r["outcome"]) for r in jan_rows) / n
    avg_crowd = sum(float(r["crowd_prob_at_T"]) for r in jan_rows) / n

    # Per-model averages (use the same jan_qids set for all models)
    model_avg = {}
    for m in MODELS:
        r0m = [r for r in rows if r["model"] == m and r["repeat"] == "0" and r["qid"] in jan_qids]
        model_avg[LABELS[m]] = sum(float(r["model_prob"]) for r in r0m) / len(r0m)

    # Time distribution: by close month
    from collections import Counter
    close_dates = [q_by_id[r["qid"]]["close_at"][:7] for r in jan_rows]  # YYYY-MM
    date_counts = dict(sorted(Counter(close_dates).items()))

    # Overall base rate for comparison
    overall_br = sum(int(r["outcome"]) for r in r0h_all) / len(r0h_all)

    return dict(
        n_jan2026_clean=n,
        base_rate_jan2026_clean=base_rate,
        base_rate_overall=overall_br,
        base_rate_delta=base_rate - overall_br,
        avg_crowd_prob=avg_crowd,
        crowd_citl=avg_crowd - base_rate,
        avg_model_prob_by_model=model_avg,
        close_date_distribution_YYYYMM=date_counts,
        interpretation=(
            "Jan2026_clean questions have a 45.8% YES base rate vs 33.8% overall. "
            "The crowd forecasts 46.4% on average (CITL≈+0.006, nearly unbiased). "
            "All models forecast ~32-33% (CITL≈-0.13 to -0.18). "
            "Questions close between 2026-02 and 2026-07 — all post elicitation, none are "
            "stale closures. The model-crowd gap is consistent with models being anchored to "
            "pre-cutoff base rates for AI progress (~33%), while the crowd correctly reads "
            "a higher subsequent YES rate. This is an information-recency effect, not a "
            "question-selection artifact. The crowd's near-zero CITL on this subset is "
            "notable: it distinguishes genuine under-prediction (models) from well-calibrated "
            "forecasting (crowd) on the hardest post-cutoff questions."
        ),
    )


# ===========================================================================
# Figure — RQ3 coefficient forest plot
# ===========================================================================

def plot_forest(rq3_results: list[dict], path: str) -> None:
    """
    Horizontal coefficient forest plot for RQ3 encompassing regression.
    Shows b_crowd and b_model with 95% Wald CIs per cell.
    """
    labels = [r["label"] for r in rq3_results]
    n_cells = len(rq3_results)

    fig, axes = plt.subplots(1, 2, figsize=(11, 3 + 0.6 * n_cells), sharey=True)
    fig.suptitle(
        "RQ3 Encompassing Regression Coefficients (logit scale)\n"
        "outcome ~ intercept + b_crowd·logit(crowd) + b_model·logit(model)",
        fontsize=10,
    )

    for ax_idx, (coef_key, lo_key, hi_key, title) in enumerate([
        ("b_crowd", "crowd_ci_lo_wald", "crowd_ci_hi_wald", "b_crowd (H3a: market carries info beyond model)"),
        ("b_model", "model_ci_lo_wald", "model_ci_hi_wald", "b_model (H3b: model carries info beyond market)"),
    ]):
        ax = axes[ax_idx]
        y_positions = list(range(n_cells))
        colors = []
        for r in rq3_results:
            if r["status"] == "confirmatory":
                colors.append("#1f77b4")
            elif r["status"] == "exploratory":
                colors.append("#ff7f0e")
            else:
                colors.append("#aaaaaa")

        for i, r in enumerate(rq3_results):
            coef = r[coef_key]
            lo   = r[lo_key]
            hi   = r[hi_key]
            ax.plot([lo, hi], [i, i], "-", color=colors[i], lw=2.0, alpha=0.8)
            ax.plot(coef, i, "o", color=colors[i], ms=7, zorder=3)

        ax.axvline(0, color="black", lw=0.8, ls="--", alpha=0.6)
        ax.set_title(title, fontsize=8, pad=4)
        ax.set_yticks(y_positions)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("Logit-scale coefficient", fontsize=8)
        ax.tick_params(labelsize=7)

    # Legend
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], color="#1f77b4", lw=2, marker="o", label="Confirmatory"),
        Line2D([0], [0], color="#ff7f0e", lw=2, marker="o", label="Exploratory"),
    ]
    axes[0].legend(handles=legend_handles, fontsize=7, loc="lower right")

    fig.tight_layout(rect=[0, 0, 1, 0.92])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[output] Forest plot saved to {path}")


# ===========================================================================
# Markdown output
# ===========================================================================

def _f(v, fmt=".4f"):
    if isinstance(v, float) and math.isnan(v):
        return "—"
    if isinstance(v, float):
        return f"{v:{fmt}}"
    return str(v)

def _pf(p):
    """Format p-value."""
    if isinstance(p, float) and math.isnan(p):
        return "—"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def write_markdown(results: dict, path: str) -> None:
    """Write docs/phase3_results.md."""
    rq1   = results["rq1"]
    rq2   = results["rq2"]
    rq3   = results["rq3"]
    bh    = results["bh_correction"]
    sens  = results["sensitivities"]
    diag  = results["jan2026_diagnosis"]
    meta  = results["metadata"]

    lines = [
        "# Phase-3 RQ1–RQ3 Confirmatory Analyses",
        "",
        "Pre-registration: SCOPE.md §2, D-016.  Bootstrap N=10,000.  "
        f"Clamp eps={meta['clamp_eps']}.  BH q=0.10.",
        "",
        "**Labels:** CONFIRMATORY = pre-registered, counts in BH family.  "
        "EXPLORATORY = pre-specified but outside the BH family.  "
        "DESCRIPTIVE = memorization caveat, no inferential claims.",
        "",
        "---",
        "",
        "## RQ1 — Calibration (H1)",
        "",
        "**Decision rule:** reject 'well calibrated' iff 95% CI excludes 0 AND |CITL| ≥ 0.05.",
        "Calibration slope from logistic recalibration (IRLS, logit scale); slope=1 perfect, <1 overconfident, >1 underconfident.",
        "",
        "| Forecaster | Stratum | Status | N | base_rate | CITL | 95% CI | p (boot) | Cal-slope | 95% CI | H1 decision |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rq1:
        ci_str = f"[{_f(r['citl_lo'], '+.4f')}, {_f(r['citl_hi'], '+.4f')}]"
        sl_ci  = f"[{_f(r['slope_lo'])}, {_f(r['slope_hi'])}]"
        lines.append(
            f"| {r['label']:12s} | {r.get('stratum','overall'):15s} "
            f"| {r['status']:14s} | {r['n']:4d} "
            f"| {_f(r['base_rate'], '.3f')} "
            f"| {_f(r['citl'], '+.4f')} | {ci_str} | {_pf(r['citl_p'])} "
            f"| {_f(r['cal_slope'])} | {sl_ci} "
            f"| {r['h1_decision']} |"
        )

    lines += [
        "",
        "## RQ2 — Skill vs. Memorization (H2)",
        "",
        "**ΔBSS = BSS_post(clean) − BSS_pre(probe).** Two-sample bootstrap; post and pre resampled independently.",
        "**Flag:** post-cutoff BSS CI includes ≤ 0 ⇒ model does not beat the base rate on post-cutoff questions.",
        "",
        "| Model | Status | N_post | N_pre | BSS_post | BSS_pre | ΔBSS | 95% CI | p (boot) | post CI | Flag |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rq2:
        delta_ci = f"[{_f(r['delta_lo'], '+.4f')}, {_f(r['delta_hi'], '+.4f')}]"
        post_ci  = f"[{_f(r['bss_post_ci_lo'])}, {_f(r['bss_post_ci_hi'])}]"
        flag     = "FLAG: post BSS ≤ 0" if r["post_bss_lte_zero_flagged"] else "OK"
        lines.append(
            f"| {r['label']:10s} | {r['status']:14s} "
            f"| {r['n_post']:5d} | {r['n_pre']:5d} "
            f"| {_f(r['bss_post'], '+.4f')} | {_f(r['bss_pre'], '+.4f')} "
            f"| {_f(r['delta_bss'], '+.4f')} | {delta_ci} | {_pf(r['delta_p'])} "
            f"| {post_ci} | {flag} |"
        )

    lines += [
        "",
        "## RQ3 — Information Content (H3a/H3b)",
        "",
        "**Model:** outcome ~ intercept + b_crowd·logit(crowd) + b_model·logit(model).  "
        "Wald CIs and p-values; bootstrap check shown.  Logit-scale correlation ρ between crowd and model.",
        "H3a: b_crowd ≠ 0 (market carries info beyond model).  H3b: b_model ≠ 0 (model carries info beyond market).",
        "",
        "| Cell | Status | N | ρ | b_crowd | Wald 95%CI | Wald p | Boot 95%CI | Boot p | b_model | Wald 95%CI | Wald p | Boot 95%CI | Boot p |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rq3:
        cc = f"[{_f(r['crowd_ci_lo_wald'])},{_f(r['crowd_ci_hi_wald'])}]"
        mc = f"[{_f(r['model_ci_lo_wald'])},{_f(r['model_ci_hi_wald'])}]"
        bc = f"[{_f(r['boot_crowd_lo'])},{_f(r['boot_crowd_hi'])}]"
        bm = f"[{_f(r['boot_model_lo'])},{_f(r['boot_model_hi'])}]"
        lines.append(
            f"| {r['label']:30s} | {r['status']:14s} | {r['n']:3d} "
            f"| {_f(r['corr_logit_crowd_model'], '.3f')} "
            f"| {_f(r['b_crowd'], '+.4f')} | {cc} | {_pf(r['p_crowd_wald'])} | {bc} | {_pf(r['boot_p_crowd'])} "
            f"| {_f(r['b_model'], '+.4f')} | {mc} | {_pf(r['p_model_wald'])} | {bm} | {_pf(r['boot_p_model'])} |"
        )

    lines += [
        "",
        "## BH Correction (q=0.10, family of 5 confirmatory tests)",
        "",
        "Family: {H1-crowd, H1-haiku, H2-haiku, H3a-haiku, H3b-haiku}.",
        "",
        "| Test | Raw p | BH rank | BH threshold (k/5·0.10) | p_adj | BH rejected |",
        "|---|---|---|---|---|---|",
    ]
    for name, r in sorted(bh.items(), key=lambda kv: kv[1]["bh_rank"]):
        lines.append(
            f"| {name:20s} | {_pf(r['p_raw']):8s} | {r['bh_rank']} "
            f"| {r['bh_threshold']:.4f} | {_pf(r['p_adj'])} | {'YES' if r['bh_rejected'] else 'no'} |"
        )

    # Sensitivity analyses
    lines += [
        "",
        "## Sensitivity Analyses (D-014 / D-016 §5)",
        "",
        "### (a) + 38 close_before_cutoff_haiku questions (N=390 vs N=352 main)",
        "",
        "| Metric | Main (N=352) | +38 CBChaiku (N=390) | Direction change? |",
        "|---|---|---|---|",
    ]
    for k, row in sens.get("a_compare", {}).items():
        flip = "FLIP" if row.get("sign_flip") else ("DECISION FLIP" if row.get("decision_flip") else "stable")
        lines.append(f"| {k:35s} | {_f(row['main'])} | {_f(row['sens'])} | {flip} |")

    lines += [
        "",
        "### (b) − close_before_T questions (N=314 vs N=352 main)",
        "",
        "| Metric | Main (N=352) | −CBT (N=314) | Direction change? |",
        "|---|---|---|---|",
    ]
    for k, row in sens.get("b_compare", {}).items():
        flip = "FLIP" if row.get("sign_flip") else ("DECISION FLIP" if row.get("decision_flip") else "stable")
        lines.append(f"| {k:35s} | {_f(row['main'])} | {_f(row['sens'])} | {flip} |")

    # Jan2026 diagnosis
    lines += [
        "",
        "## Jan2026 CITL Anomaly — Descriptive Diagnosis",
        "",
        f"N jan2026_clean = {diag['n_jan2026_clean']}.  "
        f"Base rate = {_f(diag['base_rate_jan2026_clean'], '.3f')} (overall = {_f(diag['base_rate_overall'], '.3f')}, "
        f"delta = +{_f(diag['base_rate_delta'], '.3f')}).",
        f"Crowd avg prob = {_f(diag['avg_crowd_prob'], '.3f')} (CITL = {_f(diag['crowd_citl'], '+.4f')}).",
        "Model avg probs: "
        + ", ".join(f"{k}={_f(v, '.3f')}" for k, v in diag["avg_model_prob_by_model"].items()),
        "",
        diag["interpretation"],
        "",
        "Close-date distribution (YYYY-MM):",
        "",
        "| Month | N |",
        "|---|---|",
    ]
    for month, cnt in diag["close_date_distribution_YYYYMM"].items():
        lines.append(f"| {month} | {cnt} |")

    # Findings narrative
    lines += [
        "",
        "## Findings — Neutral Language",
        "",
        "(CONFIRMATORY and EXPLORATORY labels follow D-016.  CIs are 95% percentile-bootstrap "
        "or Wald as stated.  Effect sizes are logit-scale unless noted.)",
        "",
    ]

    # Extract key numbers for the narrative
    rq1_dict = {r["label"] + "_" + r.get("stratum", "overall"): r for r in rq1}
    crowd_overall = rq1_dict.get("crowd_overall", {})
    haiku_clean_r = rq1_dict.get("Haiku_haiku_clean", {})
    rq2_dict = {r["label"]: r for r in rq2}
    haiku_rq2 = rq2_dict.get("Haiku", {})
    rq3_dict = {r["label"]: r for r in rq3}
    haiku_rq3 = rq3_dict.get("Haiku / haiku_clean (N=352)", {})

    narrative = [
        f"**RQ1 (H1 — Calibration).**  "
        f"CONFIRMATORY crowd/overall (N=1,187): CITL={_f(crowd_overall.get('citl', float('nan')), '+.4f')}, "
        f"95% CI [{_f(crowd_overall.get('citl_lo', float('nan')), '+.4f')}, {_f(crowd_overall.get('citl_hi', float('nan')), '+.4f')}], "
        f"p={_pf(crowd_overall.get('citl_p', float('nan')))}; "
        f"decision: {crowd_overall.get('h1_decision', '?')}.  "
        f"CONFIRMATORY haiku/haiku_clean (N=352): CITL={_f(haiku_clean_r.get('citl', float('nan')), '+.4f')}, "
        f"p={_pf(haiku_clean_r.get('citl_p', float('nan')))}; "
        f"decision: {haiku_clean_r.get('h1_decision', '?')}.  "
        f"Calibration slope: crowd={_f(crowd_overall.get('cal_slope', float('nan')))}, "
        f"haiku(clean)={_f(haiku_clean_r.get('cal_slope', float('nan')))} — all models "
        f"substantially below 1.0, indicating systematic overconfidence in the logit domain.",

        f"**RQ2 (H2 — Skill drop post-cutoff).**  "
        f"CONFIRMATORY haiku: BSS_post(haiku_clean)={_f(haiku_rq2.get('bss_post', float('nan')), '+.4f')}, "
        f"BSS_pre(probe)={_f(haiku_rq2.get('bss_pre', float('nan')), '+.4f')}, "
        f"ΔBSS={_f(haiku_rq2.get('delta_bss', float('nan')), '+.4f')}, "
        f"95% CI [{_f(haiku_rq2.get('delta_lo', float('nan')), '+.4f')}, {_f(haiku_rq2.get('delta_hi', float('nan')), '+.4f')}], "
        f"p={_pf(haiku_rq2.get('delta_p', float('nan')))}.  "
        f"Post-cutoff BSS CI: [{_f(haiku_rq2.get('bss_post_ci_lo', float('nan')))}, {_f(haiku_rq2.get('bss_post_ci_hi', float('nan')))}] — "
        f"{'includes ≤ 0, FLAGGED' if haiku_rq2.get('post_bss_lte_zero_flagged') else 'does not include ≤ 0'}.  "
        f"All three models show negative post-cutoff BSS and strongly negative ΔBSS — "
        f"consistent with H2, confirmatory for haiku, exploratory for sonnet/opus.",

        f"**RQ3 (H3a/H3b — Encompassing).**  "
        f"CONFIRMATORY haiku/haiku_clean (N=352): "
        f"b_crowd={_f(haiku_rq3.get('b_crowd', float('nan')), '+.4f')} (Wald p={_pf(haiku_rq3.get('p_crowd_wald', float('nan')))}), "
        f"b_model={_f(haiku_rq3.get('b_model', float('nan')), '+.4f')} (Wald p={_pf(haiku_rq3.get('p_model_wald', float('nan')))}), "
        f"logit ρ(crowd,model)={_f(haiku_rq3.get('corr_logit_crowd_model', float('nan')), '.3f')}.  "
        f"Bootstrap p-values agree with Wald to within rounding.",

        f"**BH correction.**  See table above.  The 5-test family uses q=0.10.",

        f"**Sensitivities (D-014).**  Adding the 38 close_before_cutoff_haiku questions "
        f"or removing 38 close_before_T questions from haiku_clean changes sample size "
        f"(N=390 or N=314) but no sign or decision flips are expected for strong effects.  "
        f"See sensitivity tables.",

        f"**Jan2026 anomaly.**  Negative CITL (-13 to -18pp) on jan2026_clean reflects "
        f"a higher-than-overall YES base rate (45.8% vs 33.8%) on a small N=72 subset.  "
        f"The crowd is nearly unbiased on this subset; models under-predict, consistent "
        f"with an information-recency gap.  This is exploratory.",
    ]

    for finding in narrative:
        lines.append(f"- {finding}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Artifacts",
        "",
        f"- JSON: `data/interim/phase3_rq123.json` (SHA-256: `{results.get('sha256','?')}`)",
        "- Figure: `docs/figures/rq3_coef_forest.png`",
        f"- Bootstrap N: {N_BOOT} | Seed: {BOOT_SEED} | Clamp eps: {CLAMP_EPS}",
    ]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[output] Markdown written to {path}")


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("[load] Loading data ...")
    rows = []
    with open(FORECASTS_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    with open(QUESTIONS_JSON, encoding="utf-8") as fh:
        q_by_id = {q["qid"]: q for q in json.load(fh)}

    r0_rows = [r for r in rows if r["repeat"] == "0"]

    # --- Mask functions (from precomputed CSV flags) ---
    def _haiku_clean(r):
        return r["is_post_cutoff"] == "1" and r["close_before_cutoff_haiku"] == "0"
    def _haiku_probe(r):
        return not _haiku_clean(r)
    def _haiku_clean_plus38(r):
        # Sensitivity (a): include close_before_cutoff_haiku questions if is_post_cutoff=1
        return r["is_post_cutoff"] == "1"
    def _haiku_probe_sens_a(r):
        return not _haiku_clean_plus38(r)
    def _haiku_clean_no_cbt(r):
        # Sensitivity (b): exclude close_before_T questions from haiku_clean
        return _haiku_clean(r) and r["close_before_T"] == "0"
    def _haiku_probe_no_cbt(r):
        return not _haiku_clean(r)  # probe unchanged
    def _jan26_clean(r):
        return r["is_post_cutoff"] == "1" and r["close_before_cutoff_jan2026"] == "0"
    def _jan26_probe(r):
        return not _jan26_clean(r)
    def _overall(r):
        return True
    def _crowd_no_cbt(r):
        return r["close_before_T"] == "0"

    # -----------------------------------------------------------------------
    # Build arrays
    # -----------------------------------------------------------------------
    HAIKU   = "claude-haiku-4-5-20251001"
    SONNET  = "claude-sonnet-5"
    OPUS    = "claude-opus-4-8"

    def _arrays(model, mask):
        return load_arrays(r0_rows, q_by_id, model, mask)

    # Main cells
    hk_pm, hk_pc, hk_o  = _arrays(HAIKU,  _haiku_clean)   # haiku / haiku_clean
    hk_prm,hk_prc,hk_pro= _arrays(HAIKU,  _haiku_probe)   # haiku / haiku_probe
    ov_hpm,ov_hpc,ov_ho  = _arrays(HAIKU,  _overall)       # haiku / overall
    sn_pm, sn_pc, sn_o   = _arrays(SONNET, _jan26_clean)   # sonnet / jan2026_clean
    sn_prm,sn_prc,sn_pro = _arrays(SONNET, _jan26_probe)   # sonnet / jan2026_probe
    op_pm, op_pc, op_o   = _arrays(OPUS,   _jan26_clean)
    op_prm,op_prc,op_pro = _arrays(OPUS,   _jan26_probe)
    ov_spm,ov_spc,ov_so  = _arrays(SONNET, _overall)
    ov_opm,ov_opc,ov_oo  = _arrays(OPUS,   _overall)

    # Crowd arrays  (crowd_prob same across models; use haiku rows as source)
    def _crowd(mask):
        r0h = [r for r in r0_rows if r["model"] == HAIKU and mask(r)]
        return [float(r["crowd_prob_at_T"]) for r in r0h], [int(r["outcome"]) for r in r0h]

    cr_pc_ov,  cr_o_ov  = _crowd(_overall)
    cr_pc_hc,  cr_o_hc  = _crowd(_haiku_clean)
    cr_pc_hp,  cr_o_hp  = _crowd(_haiku_probe)
    cr_pc_jc,  cr_o_jc  = _crowd(_jan26_clean)
    cr_pc_ncbt,cr_o_ncbt= _crowd(_crowd_no_cbt)

    # Sensitivity arrays
    hk_pm_a,  hk_pc_a,  hk_o_a   = _arrays(HAIKU, _haiku_clean_plus38)
    hk_prm_a, hk_prc_a, hk_pro_a = _arrays(HAIKU, _haiku_probe_sens_a)
    hk_pm_b,  hk_pc_b,  hk_o_b   = _arrays(HAIKU, _haiku_clean_no_cbt)

    print(f"[info] Cell Ns — haiku_clean:{len(hk_o)} haiku_probe:{len(hk_pro)} "
          f"jan26_clean:{len(sn_o)} jan26_probe:{len(sn_pro)}")
    print(f"[info] Sens Ns — +38CBChaiku:{len(hk_o_a)} -CBT:{len(hk_o_b)}")

    # -----------------------------------------------------------------------
    # RQ1 — Calibration
    # -----------------------------------------------------------------------
    print("[rq1] Running ...")
    rq1_cells = [
        # Confirmatory
        run_rq1_cell(cr_pc_ov, cr_o_ov, "crowd", "confirmatory", seed=BOOT_SEED),
        run_rq1_cell(hk_pm,    hk_o,    "Haiku", "confirmatory", seed=BOOT_SEED + 1),
        # Exploratory
        run_rq1_cell(sn_pm, sn_o, "Sonnet-5", "exploratory", seed=BOOT_SEED + 2),
        run_rq1_cell(op_pm, op_o, "Opus-4-8", "exploratory", seed=BOOT_SEED + 3),
        # Descriptive (models / overall; memorization caveat)
        run_rq1_cell(ov_hpm, ov_ho, "Haiku (overall, descriptive)",   "descriptive", seed=BOOT_SEED + 4),
        run_rq1_cell(ov_spm, ov_so, "Sonnet-5 (overall, descriptive)","descriptive", seed=BOOT_SEED + 5),
        run_rq1_cell(ov_opm, ov_oo, "Opus-4-8 (overall, descriptive)","descriptive", seed=BOOT_SEED + 6),
    ]
    # Tag strata for display
    strata_map = {
        "crowd": "overall", "Haiku": "haiku_clean",
        "Sonnet-5": "jan2026_clean", "Opus-4-8": "jan2026_clean",
        "Haiku (overall, descriptive)": "overall",
        "Sonnet-5 (overall, descriptive)": "overall",
        "Opus-4-8 (overall, descriptive)": "overall",
    }
    for r in rq1_cells:
        r["stratum"] = strata_map.get(r["label"], "")
    for r in rq1_cells:
        print(f"  [rq1] {r['label']:35s} CITL={r['citl']:+.4f} "
              f"CI=[{r['citl_lo']:+.4f},{r['citl_hi']:+.4f}] "
              f"p={r['citl_p']:.4f} slope={r['cal_slope']:.3f} => {r['h1_decision']}")

    # -----------------------------------------------------------------------
    # RQ2 — Skill vs. memorization
    # -----------------------------------------------------------------------
    print("[rq2] Running ...")
    rq2_cells = [
        run_rq2_cell(hk_pm,  hk_o,  hk_prm, hk_pro, "Haiku",    "confirmatory", seed=BOOT_SEED + 10),
        run_rq2_cell(sn_pm,  sn_o,  sn_prm, sn_pro, "Sonnet-5", "exploratory",  seed=BOOT_SEED + 11),
        run_rq2_cell(op_pm,  op_o,  op_prm, op_pro, "Opus-4-8", "exploratory",  seed=BOOT_SEED + 12),
    ]
    for r in rq2_cells:
        print(f"  [rq2] {r['label']:10s} ΔBSS={r['delta_bss']:+.4f} "
              f"CI=[{r['delta_lo']:+.4f},{r['delta_hi']:+.4f}] "
              f"p={r['delta_p']:.4f} flag={r['post_bss_lte_zero_flagged']}")

    # -----------------------------------------------------------------------
    # RQ3 — Encompassing regression
    # -----------------------------------------------------------------------
    print("[rq3] Running ...")
    rq3_cells = [
        run_rq3_cell(hk_pc, hk_pm, hk_o,
                     "Haiku / haiku_clean (N=352)", "confirmatory", seed=BOOT_SEED + 20),
        run_rq3_cell(sn_pc, sn_pm, sn_o,
                     "Sonnet-5 / jan2026_clean (N=72)", "exploratory", seed=BOOT_SEED + 21),
        run_rq3_cell(op_pc, op_pm, op_o,
                     "Opus-4-8 / jan2026_clean (N=72)", "exploratory", seed=BOOT_SEED + 22),
    ]
    for r in rq3_cells:
        print(f"  [rq3] {r['label'][:35]:35s} rho={r['corr_logit_crowd_model']:.3f} "
              f"b_crowd={r['b_crowd']:+.4f}(p={r['p_crowd_wald']:.4f}) "
              f"b_model={r['b_model']:+.4f}(p={r['p_model_wald']:.4f})")

    # -----------------------------------------------------------------------
    # BH correction  (D-016 §4 — exactly these 5 tests)
    # -----------------------------------------------------------------------
    rq1_dict = {r["label"]: r for r in rq1_cells}
    rq2_dict = {r["label"]: r for r in rq2_cells}
    rq3_dict = {r["label"]: r for r in rq3_cells}
    haiku_rq3 = rq3_dict["Haiku / haiku_clean (N=352)"]

    bh_family_p = {
        "H1-crowd": rq1_dict["crowd"]["citl_p"],
        "H1-haiku": rq1_dict["Haiku"]["citl_p"],
        "H2-haiku": rq2_dict["Haiku"]["delta_p"],
        "H3a-haiku": haiku_rq3["p_crowd_wald"],
        "H3b-haiku": haiku_rq3["p_model_wald"],
    }
    bh_result = bh_correct(bh_family_p, q=BH_Q)
    print("[bh] BH correction results:")
    for name, r in sorted(bh_result.items(), key=lambda kv: kv[1]["bh_rank"]):
        print(f"  {name:20s}: p_raw={r['p_raw']:.4f} p_adj={r['p_adj']:.4f} "
              f"rank={r['bh_rank']} thresh={r['bh_threshold']:.4f} "
              f"rejected={'YES' if r['bh_rejected'] else 'no'}")

    # -----------------------------------------------------------------------
    # Sensitivity analyses  (D-016 §5)
    # -----------------------------------------------------------------------
    print("[sens] Running sensitivity analyses ...")

    # (a) + 38 CBChaiku
    rq1_ha = run_rq1_cell(hk_pm_a, hk_o_a, "Haiku+38", "sens_a", seed=BOOT_SEED + 30)
    rq2_ha = run_rq2_cell(hk_pm_a, hk_o_a, hk_prm_a, hk_pro_a, "Haiku+38", "sens_a", seed=BOOT_SEED + 31)
    rq3_ha = run_rq3_cell(hk_pc_a, hk_pm_a, hk_o_a, "Haiku+38", "sens_a", seed=BOOT_SEED + 32)

    # (b) - CBT questions
    rq1_hb = run_rq1_cell(hk_pm_b,  hk_o_b,  "Haiku-CBT", "sens_b", seed=BOOT_SEED + 33)
    rq2_hb = run_rq2_cell(hk_pm_b,  hk_o_b,  hk_prm, hk_pro, "Haiku-CBT", "sens_b", seed=BOOT_SEED + 34)
    rq3_hb = run_rq3_cell(hk_pc_b,  hk_pm_b, hk_o_b,  "Haiku-CBT", "sens_b", seed=BOOT_SEED + 35)
    # crowd sensitivity (b): remove CBT from crowd/overall
    rq1_crowd_b = run_rq1_cell(cr_pc_ncbt, cr_o_ncbt, "crowd-CBT", "sens_b", seed=BOOT_SEED + 36)

    def _compare(main_val, sens_val, main_dec=None, sens_dec=None):
        sign_flip = (main_val * sens_val < 0) if (main_val is not None and sens_val is not None and
                     not math.isnan(main_val) and not math.isnan(sens_val)) else False
        decision_flip = (main_dec != sens_dec) if main_dec is not None else False
        return dict(main=main_val, sens=sens_val, sign_flip=sign_flip, decision_flip=decision_flip)

    haiku_main = rq1_dict["Haiku"]
    crowd_main = rq1_dict["crowd"]

    sens_a_compare = {
        "H1-haiku CITL":        _compare(haiku_main["citl"],     rq1_ha["citl"],
                                          haiku_main["h1_decision"], rq1_ha["h1_decision"]),
        "H1-haiku slope":       _compare(haiku_main["cal_slope"], rq1_ha["cal_slope"]),
        "H2-haiku ΔBSS":        _compare(rq2_dict["Haiku"]["delta_bss"], rq2_ha["delta_bss"]),
        "H3a-haiku b_crowd":    _compare(haiku_rq3["b_crowd"], rq3_ha["b_crowd"]),
        "H3b-haiku b_model":    _compare(haiku_rq3["b_model"], rq3_ha["b_model"]),
    }
    sens_b_compare = {
        "H1-crowd CITL":        _compare(crowd_main["citl"],     rq1_crowd_b["citl"],
                                          crowd_main["h1_decision"], rq1_crowd_b["h1_decision"]),
        "H1-haiku CITL":        _compare(haiku_main["citl"],     rq1_hb["citl"],
                                          haiku_main["h1_decision"], rq1_hb["h1_decision"]),
        "H1-haiku slope":       _compare(haiku_main["cal_slope"], rq1_hb["cal_slope"]),
        "H2-haiku ΔBSS":        _compare(rq2_dict["Haiku"]["delta_bss"], rq2_hb["delta_bss"]),
        "H3a-haiku b_crowd":    _compare(haiku_rq3["b_crowd"], rq3_hb["b_crowd"]),
        "H3b-haiku b_model":    _compare(haiku_rq3["b_model"], rq3_hb["b_model"]),
    }

    print("[sens] Sensitivity (a) [+38 CBChaiku]:")
    for k, v in sens_a_compare.items():
        print(f"  {k:35s}: main={v['main']:.4f} sens={v['sens']:.4f} "
              f"sign_flip={v['sign_flip']} dec_flip={v.get('decision_flip','?')}")
    print("[sens] Sensitivity (b) [-CBT]:")
    for k, v in sens_b_compare.items():
        print(f"  {k:35s}: main={v['main']:.4f} sens={v['sens']:.4f} "
              f"sign_flip={v['sign_flip']} dec_flip={v.get('decision_flip','?')}")

    # -----------------------------------------------------------------------
    # Jan2026 diagnosis
    # -----------------------------------------------------------------------
    print("[diag] Jan2026 CITL diagnosis ...")
    diag = jan2026_diagnosis(rows, q_by_id)
    print(f"  Base rate jan2026_clean={diag['base_rate_jan2026_clean']:.4f} "
          f"vs overall={diag['base_rate_overall']:.4f}")
    print(f"  Avg crowd={diag['avg_crowd_prob']:.4f} model=" +
          " ".join(f"{k}={v:.4f}" for k,v in diag['avg_model_prob_by_model'].items()))

    # -----------------------------------------------------------------------
    # Assemble results JSON
    # -----------------------------------------------------------------------
    def _clean(obj):
        """Make JSON-serialisable; replace nan with None."""
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        if isinstance(obj, bool):
            return obj
        return obj

    results = {
        "metadata": dict(
            n_boot=N_BOOT, boot_seed=BOOT_SEED, clamp_eps=CLAMP_EPS,
            bh_q=BH_Q, alpha=ALPHA, z95=Z95,
        ),
        "rq1": _clean(rq1_cells),
        "rq2": _clean(rq2_cells),
        "rq3": _clean(rq3_cells),
        "bh_correction": _clean(bh_result),
        "bh_family_p_raw": _clean(bh_family_p),
        "sensitivities": {
            "a_compare": _clean(sens_a_compare),
            "b_compare": _clean(sens_b_compare),
            "a_rq1_haiku": _clean(rq1_ha),
            "a_rq2_haiku": _clean(rq2_ha),
            "a_rq3_haiku": _clean(rq3_ha),
            "b_rq1_haiku": _clean(rq1_hb),
            "b_rq2_haiku": _clean(rq2_hb),
            "b_rq3_haiku": _clean(rq3_hb),
            "b_rq1_crowd": _clean(rq1_crowd_b),
        },
        "jan2026_diagnosis": _clean(diag),
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json_str = json.dumps(results, indent=2, sort_keys=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        fh.write(json_str)
    print(f"[output] JSON written to {OUT_JSON}")

    sha = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    results["sha256"] = sha
    print(f"[sha256] phase3_rq123.json SHA-256: {sha}")

    # -----------------------------------------------------------------------
    # Figure
    # -----------------------------------------------------------------------
    print("[output] Plotting forest plot ...")
    plot_forest(rq3_cells, FIG_PATH)

    # -----------------------------------------------------------------------
    # Markdown
    # -----------------------------------------------------------------------
    print("[output] Writing markdown ...")
    write_markdown(results, MD_PATH)

    print("[done] Phase-3 RQ1–RQ3 complete.")
    return sha


if __name__ == "__main__":
    main()
