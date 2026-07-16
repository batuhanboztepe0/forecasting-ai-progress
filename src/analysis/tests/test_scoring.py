"""
test_scoring.py — Known-input unit tests for scoring.py and splits.py.

Hand-computed expected values are documented inline.
All seeds are fixed; tests are deterministic.

Run:
    python3.11 -m pytest src/analysis/tests/ -q
"""

import math
import os
import sys

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Path setup: allow `python -m pytest` from repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ANALYSIS_DIR = os.path.join(_REPO_ROOT, "src", "analysis")
_PHASE2_DIR   = os.path.join(_REPO_ROOT, "src", "phase2")

for _d in (_REPO_ROOT, _ANALYSIS_DIR, _PHASE2_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from scoring import (  # noqa: E402
    base_rate_brier,
    bootstrap_ci,
    bootstrap_score_diff_ci,
    brier_score,
    brier_skill_score,
    calibration_in_the_large,
    log_loss,
    logistic_recalibration,
    reliability_bins,
)
from splits import (  # noqa: E402
    assign_splits,
    clean_mask,
    close_before_cutoff_mask,
    close_before_T_mask,
    is_clean,
)


# ===========================================================================
# brier_score
# ===========================================================================

class TestBrierScore:
    def test_hand_computed_three_point(self):
        """
        probs = [0.9, 0.1, 0.5], outcomes = [1, 0, 1]

        BS = ((0.9-1)^2 + (0.1-0)^2 + (0.5-1)^2) / 3
           = (  0.01    +   0.01    +   0.25    ) / 3
           = 0.27 / 3
           = 0.09  (exact)
        """
        assert abs(brier_score([0.9, 0.1, 0.5], [1, 0, 1]) - 0.09) < 1e-9

    def test_perfect_forecast_is_zero(self):
        """
        probs = outcomes => each (p-y)^2 = 0.
        """
        assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0

    def test_all_yes_outcomes(self):
        """
        probs = [0.8, 0.7, 0.9], outcomes = [1, 1, 1]

        BS = ((0.8-1)^2 + (0.7-1)^2 + (0.9-1)^2) / 3
           = (  0.04    +   0.09    +   0.01    ) / 3
           = 0.14 / 3
           ≈ 0.046667
        """
        expected = 0.14 / 3
        assert abs(brier_score([0.8, 0.7, 0.9], [1, 1, 1]) - expected) < 1e-9

    def test_all_no_outcomes(self):
        """
        probs = [0.1, 0.2, 0.3], outcomes = [0, 0, 0]

        BS = (0.1^2 + 0.2^2 + 0.3^2) / 3
           = (0.01 + 0.04 + 0.09) / 3
           = 0.14 / 3
           ≈ 0.046667
        """
        expected = 0.14 / 3
        assert abs(brier_score([0.1, 0.2, 0.3], [0, 0, 0]) - expected) < 1e-9

    def test_empty_input_returns_nan(self):
        assert math.isnan(brier_score([], []))

    def test_single_correct_forecast(self):
        """
        probs = [0.8], outcomes = [1]
        BS = (0.8 - 1)^2 / 1 = 0.04
        """
        assert abs(brier_score([0.8], [1]) - 0.04) < 1e-9

    def test_single_wrong_forecast(self):
        """
        probs = [0.8], outcomes = [0]
        BS = (0.8 - 0)^2 = 0.64
        """
        assert abs(brier_score([0.8], [0]) - 0.64) < 1e-9


# ===========================================================================
# base_rate_brier
# ===========================================================================

class TestBaseRateBrier:
    def test_hand_computed(self):
        """
        outcomes = [1, 0, 1]; base_rate = 2/3.
        BS_ref = ((2/3-1)^2 + (2/3-0)^2 + (2/3-1)^2) / 3
               = ( 1/9     +  4/9      +  1/9     ) / 3
               = (6/9) / 3 = 2/9
        """
        expected = 2.0 / 9.0
        assert abs(base_rate_brier([1, 0, 1]) - expected) < 1e-9

    def test_all_yes_base_rate_is_zero(self):
        """
        All outcomes = 1 => base_rate = 1.0 => climatology predicts 1.0
        BS_ref = ((1-1)^2 * 3) / 3 = 0
        """
        assert base_rate_brier([1, 1, 1]) == 0.0

    def test_all_no_base_rate_is_zero(self):
        """
        All outcomes = 0 => base_rate = 0.0 => climatology predicts 0.0
        BS_ref = ((0-0)^2 * 3) / 3 = 0
        """
        assert base_rate_brier([0, 0, 0]) == 0.0

    def test_empty_returns_nan(self):
        assert math.isnan(base_rate_brier([]))

    def test_equal_split_equals_quarter(self):
        """
        [1, 1, 0, 0] => base_rate = 0.5
        BS_ref = 4 * (0.5 - 0/1)^2 / 4 = 0.5 * 0.5 = 0.25
        """
        assert abs(base_rate_brier([1, 1, 0, 0]) - 0.25) < 1e-9


# ===========================================================================
# brier_skill_score (BSS) — boundary cases
# ===========================================================================

class TestBrierSkillScore:
    """
    Hand-computed reference: outcomes = [1, 0, 1], base_rate = 2/3, BS_ref = 2/9.
    """

    def test_perfect_forecaster_bss_is_1(self):
        """
        Perfect: probs = [1, 0, 1], outcomes = [1, 0, 1] => BS = 0.
        BSS = 1 - 0 / (2/9) = 1.0
        """
        bs = brier_score([1.0, 0.0, 1.0], [1, 0, 1])
        bs_ref = base_rate_brier([1, 0, 1])
        assert brier_skill_score(bs, bs_ref) == 1.0

    def test_climatology_bss_is_0(self):
        """
        Climatology: probs = [2/3, 2/3, 2/3], outcomes = [1, 0, 1].
        BS = ((2/3-1)^2 + (2/3-0)^2 + (2/3-1)^2) / 3
           = (1/9 + 4/9 + 1/9) / 3 = 2/9
        BS_ref = 2/9
        BSS = 1 - (2/9)/(2/9) = 0.0
        """
        p_bar = 2.0 / 3.0
        bs = brier_score([p_bar, p_bar, p_bar], [1, 0, 1])
        bs_ref = base_rate_brier([1, 0, 1])
        assert abs(brier_skill_score(bs, bs_ref)) < 1e-9

    def test_anti_forecaster_bss_negative(self):
        """
        Anti-forecaster: probs = [0.1, 0.9, 0.1], outcomes = [1, 0, 1].
        BS = ((0.1-1)^2 + (0.9-0)^2 + (0.1-1)^2) / 3
           = (0.81 + 0.81 + 0.81) / 3 = 0.81
        BS_ref = 2/9 ≈ 0.2222
        BSS = 1 - 0.81 / (2/9) = 1 - 0.81 * 4.5 = 1 - 3.645 = -2.645 < 0
        """
        bs = brier_score([0.1, 0.9, 0.1], [1, 0, 1])
        bs_ref = base_rate_brier([1, 0, 1])
        bss = brier_skill_score(bs, bs_ref)
        assert bss < 0.0

    def test_bs_ref_zero_returns_nan(self):
        """
        All outcomes identical => BS_ref = 0 => BSS undefined => NaN.
        """
        assert math.isnan(brier_skill_score(0.1, 0.0))

    def test_bs_ref_nan_returns_nan(self):
        assert math.isnan(brier_skill_score(0.1, float("nan")))

    def test_equal_bs_returns_zero(self):
        """bs == bs_ref => BSS = 0."""
        assert brier_skill_score(0.25, 0.25) == 0.0

    def test_better_than_ref_positive(self):
        """bs < bs_ref => BSS > 0."""
        assert brier_skill_score(0.1, 0.25) > 0.0

    def test_worse_than_ref_negative(self):
        """bs > bs_ref => BSS < 0."""
        assert brier_skill_score(0.3, 0.25) < 0.0

    def test_all_yes_outcomes_bss_nan(self):
        """
        outcomes = [1, 1, 1] => base_rate = 1 => BS_ref = 0 => BSS = NaN.
        """
        bs_ref = base_rate_brier([1, 1, 1])
        assert math.isnan(brier_skill_score(0.05, bs_ref))

    def test_all_no_outcomes_bss_nan(self):
        """
        outcomes = [0, 0, 0] => base_rate = 0 => BS_ref = 0 => BSS = NaN.
        """
        bs_ref = base_rate_brier([0, 0, 0])
        assert math.isnan(brier_skill_score(0.05, bs_ref))


# ===========================================================================
# log_loss
# ===========================================================================

class TestLogLoss:
    def test_hand_computed_two_point(self):
        """
        probs = [0.9, 0.1], outcomes = [1, 0]
        Contribution 1: 1 * log(0.9) + 0 * log(0.1) = log(0.9)
        Contribution 2: 0 * log(0.1) + 1 * log(1-0.1) = log(0.9)
        log_loss = -(log(0.9) + log(0.9)) / 2 = -log(0.9) ≈ 0.10536052
        """
        expected = -math.log(0.9)
        assert abs(log_loss([0.9, 0.1], [1, 0]) - expected) < 1e-9

    def test_clamping_p_zero(self):
        """
        p = 0.0, outcome = 1, clamp_eps = 1e-7
        p_clamp = 1e-7
        log_loss = -(1 * log(1e-7)) = 7 * log(10) ≈ 16.11810

        7 * log(10) = 7 * 2.302585... = 16.118095...
        """
        expected = 7.0 * math.log(10)
        result = log_loss([0.0], [1], clamp_eps=1e-7)
        assert abs(result - expected) < 1e-6

    def test_clamping_p_one(self):
        """
        p = 1.0, outcome = 0, clamp_eps = 1e-7
        (1-y) * log(1 - p_clamp) = 1 * log(1e-7) = -7 * log(10)
        log_loss = 7 * log(10) ≈ 16.11810
        """
        expected = 7.0 * math.log(10)
        result = log_loss([1.0], [0], clamp_eps=1e-7)
        assert abs(result - expected) < 1e-6

    def test_clamping_with_mix(self):
        """
        probs = [0.0, 0.5], outcomes = [1, 0], clamp_eps = 1e-7

        Contribution 1: p_clamp = 1e-7  => 1*log(1e-7) = -7*log(10) ≈ -16.11810
        Contribution 2: p_clamp = 0.5   => 0*log(0.5) + 1*log(0.5) = log(0.5) ≈ -0.69315

        log_loss = -((-16.11810) + (-0.69315)) / 2
                 = (7*log(10) + log(2)) / 2

        7*log(10) = 16.118095650958322
        log(2)    = 0.6931471805599453
        Sum       = 16.811242831518268
        / 2       = 8.405621415759134
        """
        expected = (7 * math.log(10) + math.log(2)) / 2
        result = log_loss([0.0, 0.5], [1, 0], clamp_eps=1e-7)
        assert abs(result - expected) < 1e-9

    def test_explicit_clamp_eps(self):
        """
        p = 0.0, outcome = 1, clamp_eps = 0.01
        p_clamp = 0.01
        log_loss = -log(0.01) = -log(10^-2) = 2*log(10) ≈ 4.60517
        """
        expected = -math.log(0.01)
        assert abs(log_loss([0.0], [1], clamp_eps=0.01) - expected) < 1e-9

    def test_clamp_disabled_raises_on_boundary(self):
        """clamp_eps=0 + p=0 => ValueError."""
        with pytest.raises(ValueError, match="clamp_eps=0"):
            log_loss([0.0], [1], clamp_eps=0.0)

    def test_empty_returns_nan(self):
        assert math.isnan(log_loss([], []))

    def test_perfect_forecast_low_loss(self):
        """
        probs = [0.99, 0.01], outcomes = [1, 0], clamp_eps = 1e-7
        Both terms contribute log(0.99) ≈ -0.01005.
        log_loss = -log(0.99) ≈ 0.01005  (very low, near-perfect forecast).
        """
        result = log_loss([0.99, 0.01], [1, 0])
        assert result < 0.015  # should be very low


# ===========================================================================
# calibration_in_the_large
# ===========================================================================

class TestCalibrationInTheLarge:
    def test_over_prediction_is_positive(self):
        """
        probs = [0.8, 0.8, 0.8], outcomes = [0, 0, 0]
        mean_f = 0.8, mean_y = 0.0
        CITL = 0.8 - 0.0 = +0.8 (positive = over-prediction)
        """
        assert abs(calibration_in_the_large([0.8, 0.8, 0.8], [0, 0, 0]) - 0.8) < 1e-9

    def test_under_prediction_is_negative(self):
        """
        probs = [0.2, 0.2, 0.2], outcomes = [1, 1, 1]
        mean_f = 0.2, mean_y = 1.0
        CITL = 0.2 - 1.0 = -0.8 (negative = under-prediction)
        """
        assert abs(calibration_in_the_large([0.2, 0.2, 0.2], [1, 1, 1]) - (-0.8)) < 1e-9

    def test_unbiased_is_zero(self):
        """
        probs = [0.5, 0.5, 0.5], outcomes = [1, 0, 1]
        Wait: mean_f = 0.5, mean_y = 2/3
        CITL = 0.5 - 2/3 = -1/6  (not zero — pick a balanced example)

        Better: probs = [2/3, 2/3, 2/3], outcomes = [1, 0, 1]
        mean_f = 2/3, mean_y = 2/3
        CITL = 0.0
        """
        p_bar = 2.0 / 3.0
        assert abs(
            calibration_in_the_large([p_bar, p_bar, p_bar], [1, 0, 1])
        ) < 1e-9

    def test_empty_returns_nan(self):
        assert math.isnan(calibration_in_the_large([], []))

    def test_mixed_sign(self):
        """
        probs = [0.6, 0.4, 0.7], outcomes = [1, 0, 1]
        mean_f = (0.6 + 0.4 + 0.7) / 3 = 1.7 / 3
        mean_y = 2/3
        CITL = 1.7/3 - 2/3 = (1.7 - 2) / 3 = -0.3 / 3 = -0.1
        """
        expected = -0.1
        result = calibration_in_the_large([0.6, 0.4, 0.7], [1, 0, 1])
        assert abs(result - expected) < 1e-9


# ===========================================================================
# logistic_recalibration (slope recovery)
# ===========================================================================

def _synthetic_calib_data(
    n: int = 1000,
    true_intercept: float = 0.1,
    true_slope: float = 0.5,
    seed: int = 42,
):
    """
    Generate synthetic calibration data.

    raw_probs = sigmoid(x), x ~ Uniform(-2, 2), seed fixed.
    outcomes  ~ Bernoulli( sigmoid(true_intercept + true_slope * x) )

    Since logit(raw_probs) = x, fitting logistic_recalibration(raw_probs, outcomes)
    is equivalent to fitting:
        outcome ~ logit_link(a + b * x)
    where the true parameters are (a=true_intercept, b=true_slope).

    With N=1000 and a well-spread design, the MLE should be close to truth.
    """
    rng = np.random.default_rng(seed)
    x = rng.uniform(-2.0, 2.0, size=n)
    raw_probs = 1.0 / (1.0 + np.exp(-x))
    true_p    = 1.0 / (1.0 + np.exp(-(true_intercept + true_slope * x)))
    outcomes  = (rng.uniform(size=n) < true_p).astype(int).tolist()
    return raw_probs.tolist(), outcomes


class TestLogisticRecalibration:
    def test_slope_recovery_within_tolerance(self):
        """
        Synthetic data: true_intercept=0.1, true_slope=0.5, N=1000, seed=42.
        The IRLS MLE should converge to parameters close to the truth.
        Tolerance: |slope - 0.5| < 0.12  and  |intercept - 0.1| < 0.12
        (Conservative for finite N; tighter would need N >> 1000.)
        """
        raw_probs, outcomes = _synthetic_calib_data(
            n=1000, true_intercept=0.1, true_slope=0.5, seed=42
        )
        intercept, slope = logistic_recalibration(raw_probs, outcomes)
        assert abs(slope - 0.5) < 0.12, (
            f"Slope recovery failed: got {slope:.4f}, expected ≈ 0.5"
        )
        assert abs(intercept - 0.1) < 0.12, (
            f"Intercept recovery failed: got {intercept:.4f}, expected ≈ 0.1"
        )

    def test_identity_calibration_slope_near_one(self):
        """
        Generate data from sigmoid(x) directly (true_intercept=0, true_slope=1).
        Raw probs ARE the true probs => recalibration should find slope≈1, intercept≈0.
        """
        raw_probs, outcomes = _synthetic_calib_data(
            n=1000, true_intercept=0.0, true_slope=1.0, seed=7
        )
        intercept, slope = logistic_recalibration(raw_probs, outcomes)
        assert abs(slope - 1.0) < 0.15, (
            f"Identity slope: got {slope:.4f}, expected ≈ 1.0"
        )
        assert abs(intercept - 0.0) < 0.15, (
            f"Identity intercept: got {intercept:.4f}, expected ≈ 0.0"
        )

    def test_all_yes_returns_nan(self):
        """
        All outcomes = 1 => MLE undefined => (nan, nan).
        """
        intercept, slope = logistic_recalibration([0.7, 0.8, 0.9], [1, 1, 1])
        assert math.isnan(intercept)
        assert math.isnan(slope)

    def test_all_no_returns_nan(self):
        """
        All outcomes = 0 => MLE undefined => (nan, nan).
        """
        intercept, slope = logistic_recalibration([0.1, 0.2, 0.3], [0, 0, 0])
        assert math.isnan(intercept)
        assert math.isnan(slope)

    def test_too_few_observations_returns_nan(self):
        """
        n < 3 => (nan, nan).
        """
        intercept, slope = logistic_recalibration([0.6, 0.4], [1, 0])
        assert math.isnan(intercept)
        assert math.isnan(slope)

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            logistic_recalibration([0.5, 0.6], [1, 0, 1])


# ===========================================================================
# reliability_bins
# ===========================================================================

class TestReliabilityBins:
    def test_hand_computed_five_bins(self):
        """
        bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        outcomes = [0, 1, 1, 0, 1]

        Bin assignment: idx = min(int(p * 5), 4)
          p=0.1 => int(0.5)=0  => bin 0  [0, 0.2)
          p=0.3 => int(1.5)=1  => bin 1  [0.2, 0.4)
          p=0.5 => int(2.5)=2  => bin 2  [0.4, 0.6)
          p=0.7 => int(3.5)=3  => bin 3  [0.6, 0.8)
          p=0.9 => int(4.5)=4  => bin 4  [0.8, 1.0]

        Per bin: mean_f = single value, obs_f = outcome, n = 1
          bin 0: mean_f=0.1, obs_f=0.0, n=1
          bin 1: mean_f=0.3, obs_f=1.0, n=1
          bin 2: mean_f=0.5, obs_f=1.0, n=1
          bin 3: mean_f=0.7, obs_f=0.0, n=1
          bin 4: mean_f=0.9, obs_f=1.0, n=1
        """
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = reliability_bins([0.1, 0.3, 0.5, 0.7, 0.9], [0, 1, 1, 0, 1], bins)

        assert len(result) == 5
        mf0, of0, n0 = result[0]
        assert abs(mf0 - 0.1) < 1e-9 and of0 == 0.0 and n0 == 1
        mf4, of4, n4 = result[4]
        assert abs(mf4 - 0.9) < 1e-9 and of4 == 1.0 and n4 == 1

    def test_p_one_falls_in_last_bin(self):
        """
        p = 1.0 => idx = min(int(1.0 * 5), 4) = min(5, 4) = 4 => last bin.
        """
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = reliability_bins([1.0], [1], bins)
        assert len(result) == 1
        mf, of, n = result[0]
        assert mf == 1.0 and of == 1.0 and n == 1

    def test_empty_bin_skipped(self):
        """
        probs = [0.1, 0.9], outcomes = [0, 1]  => bins 0 and 4 populated; bins 1-3 empty.
        """
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = reliability_bins([0.1, 0.9], [0, 1], bins)
        assert len(result) == 2

    def test_empty_input(self):
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        assert reliability_bins([], [], bins) == []

    def test_two_points_same_bin(self):
        """
        probs = [0.15, 0.18], outcomes = [0, 1]  => both in bin 0.
        mean_f = (0.15 + 0.18) / 2 = 0.165
        obs_f  = (0 + 1) / 2 = 0.5
        n      = 2
        """
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = reliability_bins([0.15, 0.18], [0, 1], bins)
        assert len(result) == 1
        mf, of, n = result[0]
        assert abs(mf - 0.165) < 1e-9
        assert abs(of - 0.5) < 1e-9
        assert n == 2


# ===========================================================================
# bootstrap_ci and bootstrap_score_diff_ci
# ===========================================================================

class TestBootstrap:
    def test_identical_forecasters_diff_ci_is_zero(self):
        """
        probs_a = probs_b => fn(probs_a, outcomes) - fn(probs_b, outcomes) = 0 for any resample.
        Bootstrap CI must be [0, 0].
        """
        probs = [0.7, 0.3, 0.6, 0.8, 0.2]
        outcomes = [1, 0, 1, 1, 0]

        lo, hi = bootstrap_score_diff_ci(
            brier_score, probs, probs, outcomes,
            n_boot=200, seed=42
        )
        assert lo == 0.0
        assert hi == 0.0

    def test_score_diff_ci_is_non_degenerate(self):
        """
        Two different forecasters => bootstrap CI should have lo < hi
        (some variance across resamples).
        Seeded for reproducibility.
        """
        rng = np.random.default_rng(7)
        n = 60
        outcomes = rng.integers(0, 2, size=n).tolist()
        probs_a = rng.uniform(0.3, 0.9, size=n).tolist()
        probs_b = rng.uniform(0.1, 0.5, size=n).tolist()

        lo, hi = bootstrap_score_diff_ci(
            brier_score, probs_a, probs_b, outcomes,
            n_boot=500, seed=99
        )
        assert lo < hi, f"Expected lo < hi but got [{lo:.4f}, {hi:.4f}]"

    def test_bootstrap_ci_single_forecaster_non_degenerate(self):
        """
        Single-forecaster bootstrap CI should have lo < hi for non-trivial data.
        """
        rng = np.random.default_rng(3)
        n = 50
        outcomes = rng.integers(0, 2, size=n).tolist()
        probs = rng.uniform(0.2, 0.8, size=n).tolist()

        lo, hi = bootstrap_ci(brier_score, probs, outcomes, n_boot=500, seed=11)
        assert lo < hi

    def test_bootstrap_seed_reproducibility(self):
        """Same seed => identical CI."""
        probs = [0.6, 0.4, 0.7, 0.3, 0.8]
        outcomes = [1, 0, 1, 0, 1]

        lo1, hi1 = bootstrap_ci(brier_score, probs, outcomes, n_boot=100, seed=42)
        lo2, hi2 = bootstrap_ci(brier_score, probs, outcomes, n_boot=100, seed=42)
        assert lo1 == lo2
        assert hi1 == hi2

    def test_bootstrap_different_seeds_differ(self):
        """Different seeds => generally different CIs (extremely unlikely to be identical)."""
        probs = [0.6, 0.4, 0.7, 0.3, 0.8]
        outcomes = [1, 0, 1, 0, 1]

        lo1, hi1 = bootstrap_ci(brier_score, probs, outcomes, n_boot=200, seed=42)
        lo2, hi2 = bootstrap_ci(brier_score, probs, outcomes, n_boot=200, seed=99)
        # Different seeds should produce at least some difference
        assert (lo1, hi1) != (lo2, hi2)

    def test_bootstrap_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            bootstrap_score_diff_ci(
                brier_score, [0.5, 0.6], [0.5], [1, 0],
                n_boot=10, seed=42
            )


# ===========================================================================
# splits.py — is_clean boundary cases
# ===========================================================================

# Use haiku as the test model throughout; its cutoff is "2025-07-31".
# C + 30d = 2025-07-31 + 30d = 2025-08-30 (August has 30 days after the 31st)
# Verify: datetime.date(2025, 7, 31) + timedelta(30) = datetime.date(2025, 8, 30)
# This matches phase2_config.HAIKU_CLEAN_MIN_RESOLVED = "2025-08-30".

HAIKU = "claude-haiku-4-5-20251001"
HAIKU_CUTOFF = "2025-07-31"   # C
HAIKU_MIN_RES = "2025-08-30"  # C + 30d = minimum clean resolved_at (inclusive)


class TestIsClean:
    """
    D-014 clean rule: resolved_at >= C + 30d  AND  close_at >= C.
    Both comparisons are INCLUSIVE (>= not >).
    """

    def test_boundary_inclusive_resolved_at_exact(self):
        """
        resolved_at = C + 30d exactly (2025-08-30) => INCLUDED (clean).
        close_at = C exactly (2025-07-31) => INCLUDED.
        Matches phase2_config.HAIKU_CLEAN_MIN_RESOLVED = "2025-08-30".
        """
        assert is_clean(
            resolved_at="2025-08-30",
            close_at="2025-07-31",
            model=HAIKU,
        ) is True

    def test_resolved_at_one_day_before_boundary_is_not_clean(self):
        """
        resolved_at = C + 29d (2025-08-29) < C + 30d => NOT clean.
        """
        assert is_clean(
            resolved_at="2025-08-29",
            close_at="2025-07-31",
            model=HAIKU,
        ) is False

    def test_close_at_one_day_before_cutoff_is_not_clean(self):
        """
        resolved_at is fine (C + 30d), but close_at = C - 1d = 2025-07-30 < C => NOT clean.
        """
        assert is_clean(
            resolved_at="2025-08-30",
            close_at="2025-07-30",
            model=HAIKU,
        ) is False

    def test_close_at_exactly_cutoff_is_clean(self):
        """
        close_at = C = 2025-07-31 => INCLUDED (>= is satisfied by equality).
        """
        assert is_clean(
            resolved_at="2025-09-01",
            close_at="2025-07-31",
            model=HAIKU,
        ) is True

    def test_both_well_above_boundary(self):
        """Well after all boundaries => clean."""
        assert is_clean(
            resolved_at="2025-12-01",
            close_at="2025-10-01",
            model=HAIKU,
        ) is True

    def test_resolved_at_too_early_even_with_good_close_at(self):
        """resolved_at < C + 30d fails the first condition; not clean regardless of close_at."""
        assert is_clean(
            resolved_at="2025-07-31",  # = C exactly; C < C + 30d => not clean
            close_at="2025-07-31",
            model=HAIKU,
        ) is False

    def test_sonnet_model_uses_its_own_cutoff(self):
        """
        claude-sonnet-5 has cutoff 2026-01-31; C + 30d = 2026-03-02.
        resolved_at = 2026-03-02 => INCLUDED for sonnet, but would be clean for haiku too
        since haiku cutoff is earlier.
        """
        assert is_clean(
            resolved_at="2026-03-02",
            close_at="2026-01-31",
            model="claude-sonnet-5",
        ) is True

    def test_sonnet_boundary_one_day_early(self):
        """
        For sonnet C + 30d = 2026-03-02; resolved_at = 2026-03-01 => NOT clean.
        """
        assert is_clean(
            resolved_at="2026-03-01",
            close_at="2026-01-31",
            model="claude-sonnet-5",
        ) is False


class TestCleanMask:
    def test_mixed_clean_not_clean(self):
        """
        Three questions for haiku:
          [0] res=2025-08-30, close=2025-07-31 => clean (boundary inclusive)
          [1] res=2025-08-29, close=2025-07-31 => not clean (res too early)
          [2] res=2025-09-01, close=2025-07-30 => not clean (close too early)
        """
        mask = clean_mask(
            resolved_at_list=["2025-08-30", "2025-08-29", "2025-09-01"],
            close_at_list=   ["2025-07-31", "2025-07-31", "2025-07-30"],
            model=HAIKU,
        )
        assert mask == [True, False, False]

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            clean_mask(["2025-09-01", "2025-09-02"], ["2025-07-31"], HAIKU)


# ===========================================================================
# Sensitivity masks
# ===========================================================================

class TestCloseBeforeCutoffMask:
    """
    close_before_cutoff_<model>: True if close_at < C.
    """

    def test_close_at_before_cutoff_is_flagged(self):
        """close_at = 2025-07-30 < 2025-07-31 => True."""
        mask = close_before_cutoff_mask(["2025-07-30"], HAIKU)
        assert mask == [True]

    def test_close_at_equals_cutoff_not_flagged(self):
        """close_at = 2025-07-31 = C => False (close_at >= C, not flagged)."""
        mask = close_before_cutoff_mask(["2025-07-31"], HAIKU)
        assert mask == [False]

    def test_close_at_after_cutoff_not_flagged(self):
        """close_at = 2025-08-01 > C => False."""
        mask = close_before_cutoff_mask(["2025-08-01"], HAIKU)
        assert mask == [False]

    def test_mixed(self):
        mask = close_before_cutoff_mask(
            ["2025-07-30", "2025-07-31", "2025-08-15"],
            HAIKU,
        )
        assert mask == [True, False, False]


class TestCloseBeforeTMask:
    """
    close_before_T: True if close_at < T = resolved_at - 30d.
    """

    def test_close_before_T_is_flagged(self):
        """
        resolved_at = 2025-09-15, T = 2025-09-15 - 30d = 2025-08-16.
        close_at = 2025-07-31 < 2025-08-16 => True (flagged).
        """
        mask = close_before_T_mask(["2025-07-31"], ["2025-09-15"])
        assert mask == [True]

    def test_close_at_T_exactly_not_flagged(self):
        """
        resolved_at = 2025-09-15, T = 2025-08-16.
        close_at = 2025-08-16 = T => not flagged (condition is strict <).
        """
        mask = close_before_T_mask(["2025-08-16"], ["2025-09-15"])
        assert mask == [False]

    def test_close_after_T_not_flagged(self):
        """
        T = 2025-08-16; close_at = 2025-08-20 > T => False.
        """
        mask = close_before_T_mask(["2025-08-20"], ["2025-09-15"])
        assert mask == [False]

    def test_mixed(self):
        """
        resolved_at = 2025-09-15 for all; T = 2025-08-16.
        close_at: [2025-07-31 < T, 2025-08-16 = T, 2025-08-20 > T]
        => [True, False, False]
        """
        mask = close_before_T_mask(
            ["2025-07-31", "2025-08-16", "2025-08-20"],
            ["2025-09-15", "2025-09-15", "2025-09-15"],
        )
        assert mask == [True, False, False]

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            close_before_T_mask(["2025-08-01", "2025-08-02"], ["2025-09-01"])


# ===========================================================================
# assign_splits — integration smoke test
# ===========================================================================

class TestAssignSplits:
    def test_returns_all_three_masks(self):
        result = assign_splits(
            resolved_at_list=["2025-08-30", "2025-08-29"],
            close_at_list=   ["2025-07-31", "2025-07-30"],
            model=HAIKU,
        )
        assert "clean" in result
        assert "close_before_cutoff" in result
        assert "close_before_T" in result

    def test_known_values(self):
        """
        Q0: res=2025-08-30, close=2025-07-31
            clean: True (both boundaries satisfied)
            close_before_cutoff: False (close_at = C, not < C)
            close_before_T:
              T = 2025-08-30 - 30d = 2025-07-31
              close_at = 2025-07-31 = T => NOT flagged (strict <)

        Q1: res=2025-08-29, close=2025-07-30
            clean: False (res < C+30d)
            close_before_cutoff: True (close_at = 2025-07-30 < C = 2025-07-31)
            close_before_T:
              T = 2025-08-29 - 30d = 2025-07-30
              close_at = 2025-07-30 = T => NOT flagged
        """
        result = assign_splits(
            resolved_at_list=["2025-08-30", "2025-08-29"],
            close_at_list=   ["2025-07-31", "2025-07-30"],
            model=HAIKU,
        )
        assert result["clean"]               == [True,  False]
        assert result["close_before_cutoff"] == [False, True]
        assert result["close_before_T"]      == [False, False]
