#!/usr/bin/env python3
"""
scoring.py — Reusable metric library for Phase-2/3 analyses.

All functions are pure (no I/O, no global state). Arrays-in, stats-out.
Seeds must be passed explicitly. Fail loud: no silent NaN swallowing.

Functions
---------
brier_score(probs, outcomes) -> float
base_rate_brier(outcomes) -> float
brier_skill_score(bs, bs_ref) -> float
log_loss(probs, outcomes, clamp_eps) -> float
calibration_in_the_large(probs, outcomes) -> float
logistic_recalibration(probs, outcomes, ...) -> (intercept, slope)
reliability_bins(probs, outcomes, bins) -> list[(mean_f, obs_f, n)]
bootstrap_ci(fn, probs, outcomes, n_boot, seed, alpha) -> (lo, hi)
bootstrap_score_diff_ci(fn, probs_a, probs_b, outcomes, n_boot, seed, alpha) -> (lo, hi)
"""

from __future__ import annotations

import math
import random
from typing import Callable, List, Sequence, Tuple

import numpy as np  # used only in logistic_recalibration (matrix ops)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default clamping epsilon for log-loss.  1e-7 matches sklearn's convention.
LOG_LOSS_CLAMP_DEFAULT: float = 1e-7

# Bootstrap defaults
N_BOOT_DEFAULT: int = 2000
BOOTSTRAP_SEED: int = 42
BOOTSTRAP_ALPHA: float = 0.05

# IRLS defaults
IRLS_MAX_ITER: int = 200
IRLS_TOL: float = 1e-8
IRLS_ETA_CLIP: float = 50.0  # clip eta before sigmoid to prevent overflow
IRLS_W_MIN: float = 1e-10    # floor on IRLS weights (numerical stability)


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------

def brier_score(probs: Sequence[float], outcomes: Sequence[int]) -> float:
    """
    Mean squared error between probabilistic forecast and binary outcome.

    BS = (1/N) sum_i (p_i - y_i)^2.  Lower is better.  Proper scoring rule.

    Args:
        probs:    sequence of float in [0, 1]
        outcomes: sequence of int in {0, 1}, same length as probs

    Returns:
        float, or NaN for empty input.
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n


def base_rate_brier(outcomes: Sequence[int]) -> float:
    """
    Brier score of the climatology (base-rate) forecaster.

    The climatology forecaster always predicts p_bar = mean(outcomes).
    Its BS equals p_bar * (1 - p_bar), which is also the Uncertainty term
    in the Murphy/Brier decomposition.

    Args:
        outcomes: sequence of int in {0, 1}

    Returns:
        float, or NaN for empty input.
    """
    n = len(outcomes)
    if n == 0:
        return float("nan")
    p_bar = sum(outcomes) / n
    # Algebraically: p_bar*(1-p_bar), but computed from the definition to
    # stay consistent with brier_score's formula.
    return sum((p_bar - y) ** 2 for y in outcomes) / n


def brier_skill_score(bs: float, bs_ref: float) -> float:
    """
    Brier skill score vs a reference forecaster: BSS = 1 - BS / BS_ref.

    BSS > 0: beats the reference.
    BSS = 0: ties the reference.
    BSS < 0: worse than the reference.

    Args:
        bs:     Brier score of the forecaster under evaluation
        bs_ref: Brier score of the reference (e.g., climatology)

    Returns:
        float, or NaN if bs_ref is 0 or NaN (undefined).
    """
    if math.isnan(bs_ref) or bs_ref == 0.0:
        return float("nan")
    return 1.0 - bs / bs_ref


# ---------------------------------------------------------------------------
# Log-loss
# ---------------------------------------------------------------------------

def log_loss(
    probs: Sequence[float],
    outcomes: Sequence[int],
    clamp_eps: float = LOG_LOSS_CLAMP_DEFAULT,
) -> float:
    """
    Binary log-loss (negative mean log-likelihood).

    = -(1/N) sum_i [ y_i * log(p_i) + (1 - y_i) * log(1 - p_i) ]

    Lower is better.  Proper scoring rule.

    Clamping policy: p is clipped to [clamp_eps, 1 - clamp_eps] before log.
    Pass clamp_eps=0 to disable clamping; raises ValueError if any p is at
    the boundary (log undefined).  The policy is explicit here, not hidden.

    Args:
        probs:     sequence of float in [0, 1]
        outcomes:  sequence of int in {0, 1}
        clamp_eps: clamping floor/ceiling (default 1e-7)

    Returns:
        float, or NaN for empty input.

    Raises:
        ValueError: if clamp_eps == 0 and any p is 0 or 1.
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    total = 0.0
    for p, y in zip(probs, outcomes):
        if clamp_eps == 0.0:
            if p <= 0.0 or p >= 1.0:
                raise ValueError(
                    f"clamp_eps=0 but p={p} is at boundary; log undefined. "
                    "Pass clamp_eps > 0 to enable clamping."
                )
            pc = p
        else:
            pc = min(1.0 - clamp_eps, max(clamp_eps, p))
        total += y * math.log(pc) + (1 - y) * math.log(1.0 - pc)
    return -total / n


# ---------------------------------------------------------------------------
# Calibration-in-the-large
# ---------------------------------------------------------------------------

def calibration_in_the_large(
    probs: Sequence[float],
    outcomes: Sequence[int],
) -> float:
    """
    Mean forecast minus mean outcome (= mean(p) - mean(y)).

    Positive => systematic over-prediction.
    Negative => systematic under-prediction.
    Zero     => unbiased in the large.

    Args:
        probs:    sequence of float in [0, 1]
        outcomes: sequence of int in {0, 1}

    Returns:
        float, or NaN for empty input.
    """
    n = len(probs)
    if n == 0:
        return float("nan")
    return sum(probs) / n - sum(outcomes) / n


# ---------------------------------------------------------------------------
# Logistic recalibration (IRLS / Newton-Raphson)
# ---------------------------------------------------------------------------

def logistic_recalibration(
    probs: Sequence[float],
    outcomes: Sequence[int],
    clamp_eps: float = LOG_LOSS_CLAMP_DEFAULT,
    max_iter: int = IRLS_MAX_ITER,
    tol: float = IRLS_TOL,
) -> Tuple[float, float]:
    """
    Fit logistic regression on logit-scale forecasts:

        outcome ~ Bernoulli(sigmoid(intercept + slope * logit(p)))

    via Newton-Raphson / IRLS, implemented from scratch (no sklearn).
    Returns (intercept, slope).

    Interpretation:
        slope = 1, intercept = 0  =>  perfectly calibrated on logit scale
        slope < 1                 =>  overconfident (predictions too extreme)
        slope > 1                 =>  underconfident
        intercept > 0             =>  systematic over-prediction in logit space
        intercept < 0             =>  systematic under-prediction in logit space

    Design matrix: X = [[1, logit(p_1)], ..., [1, logit(p_N)]]
    Initial beta: [0.0, 1.0]  (identity calibration)

    Args:
        probs:     sequence of float; clamped to [clamp_eps, 1-clamp_eps] before logit
        outcomes:  sequence of int in {0, 1}
        clamp_eps: probability clamping for logit (default 1e-7)
        max_iter:  maximum IRLS iterations
        tol:       convergence threshold on max |delta_beta|

    Returns:
        (intercept, slope) as floats; (nan, nan) if fitting is undefined
        (fewer than 3 observations, or all outcomes identical).

    Raises:
        ValueError: if probs and outcomes have different lengths.
    """
    n = len(probs)
    if n != len(outcomes):
        raise ValueError(f"probs length {n} != outcomes length {len(outcomes)}")

    # Degenerate cases where MLE is undefined
    s = sum(outcomes)
    if n < 3 or s == 0 or s == n:
        return float("nan"), float("nan")

    # Build design matrix: column 0 = intercept, column 1 = logit(p)
    probs_c = [min(1.0 - clamp_eps, max(clamp_eps, p)) for p in probs]
    x_vals = [math.log(p / (1.0 - p)) for p in probs_c]

    X = np.column_stack([np.ones(n), np.array(x_vals)])
    y = np.array(outcomes, dtype=float)

    # Initialize at identity calibration
    beta = np.array([0.0, 1.0])

    for _ in range(max_iter):
        eta = X @ beta
        # clip eta to prevent exp overflow in sigmoid
        eta_c = np.clip(eta, -IRLS_ETA_CLIP, IRLS_ETA_CLIP)
        mu = 1.0 / (1.0 + np.exp(-eta_c))

        # IRLS working weights W = mu * (1 - mu); floor for numerical stability
        W = np.maximum(mu * (1.0 - mu), IRLS_W_MIN)

        # Newton-Raphson update: delta = (X^T W X)^{-1} X^T (y - mu)
        XtW = X.T * W          # (2, n)
        XtWX = XtW @ X         # (2, 2)  — observed Fisher information
        grad = X.T @ (y - mu)  # (2,)   — gradient of log-likelihood

        try:
            delta = np.linalg.solve(XtWX, grad)
        except np.linalg.LinAlgError:
            # Singular information matrix; return current estimate
            break

        beta = beta + delta
        if np.max(np.abs(delta)) < tol:
            break

    return float(beta[0]), float(beta[1])  # (intercept, slope)


# ---------------------------------------------------------------------------
# Reliability-diagram binning
# ---------------------------------------------------------------------------

def reliability_bins(
    probs: Sequence[float],
    outcomes: Sequence[int],
    bins: Sequence[float],
) -> List[Tuple[float, float, int]]:
    """
    Bin forecasts into fixed-width bins and compute per-bin statistics.

    Bin assignment: idx = min(floor(p * n_bins), n_bins - 1), so p=1.0
    falls in the last bin (no out-of-range index).

    Args:
        probs:    sequence of float in [0, 1]
        outcomes: sequence of int in {0, 1}
        bins:     sorted bin edges, e.g. [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    Returns:
        list of (mean_forecast, observed_freq, n) for each non-empty bin,
        in bin order.
    """
    n_bins = len(bins) - 1
    if n_bins < 1:
        raise ValueError(f"bins must have at least 2 edges; got {len(bins)}")

    bin_preds: List[List[float]] = [[] for _ in range(n_bins)]
    bin_outs:  List[List[int]]   = [[] for _ in range(n_bins)]

    for p, y in zip(probs, outcomes):
        idx = min(int(p * n_bins), n_bins - 1)
        bin_preds[idx].append(p)
        bin_outs[idx].append(y)

    result = []
    for i in range(n_bins):
        cnt = len(bin_preds[i])
        if cnt == 0:
            continue
        mean_f = sum(bin_preds[i]) / cnt
        obs_f  = sum(bin_outs[i])  / cnt
        result.append((mean_f, obs_f, cnt))

    return result


# ---------------------------------------------------------------------------
# Bootstrap CI machinery
# ---------------------------------------------------------------------------

def bootstrap_ci(
    fn: Callable[[List[float], List[int]], float],
    probs: Sequence[float],
    outcomes: Sequence[int],
    n_boot: int = N_BOOT_DEFAULT,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = BOOTSTRAP_ALPHA,
) -> Tuple[float, float]:
    """
    Percentile bootstrap CI for a scalar score computed by fn(probs, outcomes).

    Resamples question indices with replacement N_boot times.

    Args:
        fn:       pure function (probs, outcomes) -> float (e.g. brier_score)
        probs:    sequence of float
        outcomes: sequence of int in {0, 1}
        n_boot:   number of bootstrap replicates
        seed:     RNG seed (explicit; never default to system entropy)
        alpha:    two-sided significance level; CI = [alpha/2, 1-alpha/2]

    Returns:
        (lower, upper) percentile CI bounds.
    """
    n = len(probs)
    rng = random.Random(seed)
    boot_stats: List[float] = []

    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        p_b = [probs[i] for i in idx]
        o_b = [outcomes[i] for i in idx]
        boot_stats.append(fn(p_b, o_b))

    boot_stats.sort()
    lo_idx = int(alpha / 2 * n_boot)
    hi_idx = min(int((1.0 - alpha / 2) * n_boot), n_boot - 1)
    return boot_stats[lo_idx], boot_stats[hi_idx]


def bootstrap_score_diff_ci(
    fn: Callable[[List[float], List[int]], float],
    probs_a: Sequence[float],
    probs_b: Sequence[float],
    outcomes: Sequence[int],
    n_boot: int = N_BOOT_DEFAULT,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = BOOTSTRAP_ALPHA,
) -> Tuple[float, float]:
    """
    Paired percentile bootstrap CI for fn(probs_a, outcomes) - fn(probs_b, outcomes).

    "Paired" means probs_a, probs_b, and outcomes share the same question index.
    Each bootstrap replicate draws the SAME set of question indices for both
    forecasters, preserving the pairing and removing between-question variance
    from the CI on the difference.

    Args:
        fn:       pure function (probs, outcomes) -> float
        probs_a:  sequence of float for forecaster A
        probs_b:  sequence of float for forecaster B (same length as probs_a)
        outcomes: sequence of int in {0, 1}
        n_boot:   number of bootstrap replicates
        seed:     RNG seed (explicit)
        alpha:    two-sided significance level

    Returns:
        (lower, upper) percentile CI bounds on (score_A - score_B).

    Raises:
        ValueError: if probs_a, probs_b, outcomes have different lengths.
    """
    n = len(probs_a)
    if len(probs_b) != n or len(outcomes) != n:
        raise ValueError(
            f"probs_a ({n}), probs_b ({len(probs_b)}), outcomes ({len(outcomes)}) "
            "must have equal length."
        )

    rng = random.Random(seed)
    boot_diffs: List[float] = []

    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        pa_b = [probs_a[i] for i in idx]
        pb_b = [probs_b[i] for i in idx]
        o_b  = [outcomes[i] for i in idx]
        boot_diffs.append(fn(pa_b, o_b) - fn(pb_b, o_b))

    boot_diffs.sort()
    lo_idx = int(alpha / 2 * n_boot)
    hi_idx = min(int((1.0 - alpha / 2) * n_boot), n_boot - 1)
    return boot_diffs[lo_idx], boot_diffs[hi_idx]
