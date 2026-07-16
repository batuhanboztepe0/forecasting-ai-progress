#!/usr/bin/env python3
"""
splits.py — Per-model clean/probe stratum assignment per D-014.

Clean condition (both must hold, per D-014):
    resolved_at >= cutoff(model) + SNAPSHOT_LEAD_DAYS  (inclusive)
    close_at    >= cutoff(model)                        (inclusive)

Sensitivity masks (D-014 §3 pre-registered analyses):
    close_before_cutoff_<model>: close_at < cutoff(model)   => True flags the issue
    close_before_T:              close_at < T = resolved_at - lead_days => True

Boundary convention: both >= comparisons are INCLUSIVE, matching D-014's language
("resolved_at >= C + 30d AND close_at >= C") and phase2_config.HAIKU_CLEAN_MIN_RESOLVED
which uses 2025-08-30 as the minimum (i.e., 2025-08-30 is IN the clean set).

Cutoffs are read from phase2_config.TRAINING_CUTOFFS — not duplicated here.
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Pull in config — cutoffs and lead days live there; do not duplicate.
# ---------------------------------------------------------------------------
_PHASE2_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "phase2"))
if _PHASE2_DIR not in sys.path:
    sys.path.insert(0, _PHASE2_DIR)

from phase2_config import TRAINING_CUTOFFS, SNAPSHOT_LEAD_DAYS  # noqa: E402


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def parse_date(s: str) -> datetime.date:
    """
    Parse an ISO date string 'YYYY-MM-DD' to datetime.date.

    Args:
        s: date string

    Returns:
        datetime.date

    Raises:
        ValueError: if the string is not a valid ISO date.
    """
    return datetime.date.fromisoformat(s)


# ---------------------------------------------------------------------------
# Core clean-stratum predicate (D-014)
# ---------------------------------------------------------------------------

def is_clean(
    resolved_at: str,
    close_at: str,
    model: str,
    cutoffs: Dict[str, str] | None = None,
    lead_days: int = SNAPSHOT_LEAD_DAYS,
) -> bool:
    """
    Return True iff the question belongs to the clean stratum for the given model.

    Clean iff BOTH conditions hold (D-014, inclusive boundaries):
        resolved_at >= C + lead_days
        close_at    >= C
    where C = training cutoff for the model.

    Args:
        resolved_at: ISO date string 'YYYY-MM-DD'
        close_at:    ISO date string 'YYYY-MM-DD'
        model:       model ID (must be a key in cutoffs)
        cutoffs:     model -> ISO cutoff string; defaults to TRAINING_CUTOFFS
        lead_days:   snapshot lead time in days; defaults to SNAPSHOT_LEAD_DAYS (30)

    Returns:
        bool

    Raises:
        KeyError: if model not found in cutoffs.
        ValueError: if date strings are malformed.
    """
    if cutoffs is None:
        cutoffs = TRAINING_CUTOFFS

    C = parse_date(cutoffs[model])
    res = parse_date(resolved_at)
    clo = parse_date(close_at)

    min_resolved = C + datetime.timedelta(days=lead_days)
    return res >= min_resolved and clo >= C


def clean_mask(
    resolved_at_list: Sequence[str],
    close_at_list: Sequence[str],
    model: str,
    cutoffs: Dict[str, str] | None = None,
    lead_days: int = SNAPSHOT_LEAD_DAYS,
) -> List[bool]:
    """
    Apply is_clean to parallel lists of resolved_at and close_at strings.

    Args:
        resolved_at_list: sequence of ISO date strings
        close_at_list:    sequence of ISO date strings, same length
        model:            model ID
        cutoffs:          model -> ISO cutoff string; defaults to TRAINING_CUTOFFS
        lead_days:        snapshot lead time in days

    Returns:
        list of bool, True = question is in the clean stratum for this model.

    Raises:
        ValueError: if the input lists have different lengths.
    """
    if len(resolved_at_list) != len(close_at_list):
        raise ValueError(
            f"resolved_at_list ({len(resolved_at_list)}) and "
            f"close_at_list ({len(close_at_list)}) must have equal length."
        )
    return [
        is_clean(r, c, model, cutoffs, lead_days)
        for r, c in zip(resolved_at_list, close_at_list)
    ]


# ---------------------------------------------------------------------------
# D-014 sensitivity masks
# ---------------------------------------------------------------------------

def close_before_cutoff_mask(
    close_at_list: Sequence[str],
    model: str,
    cutoffs: Dict[str, str] | None = None,
) -> List[bool]:
    """
    Flag questions where close_at < training cutoff for the model.

    True => the market window ended before the model's knowledge cutoff,
    meaning the outcome may have been knowable from training data (admin lag).
    These questions are excluded from the clean stratum and flagged
    `close_before_cutoff_<model>` per D-014.

    Args:
        close_at_list: sequence of ISO date strings
        model:         model ID
        cutoffs:       model -> ISO cutoff string; defaults to TRAINING_CUTOFFS

    Returns:
        list of bool, True = flagged (close_at < C).
    """
    if cutoffs is None:
        cutoffs = TRAINING_CUTOFFS
    C = parse_date(cutoffs[model])
    return [parse_date(c) < C for c in close_at_list]


def close_before_T_mask(
    close_at_list: Sequence[str],
    resolved_at_list: Sequence[str],
    lead_days: int = SNAPSHOT_LEAD_DAYS,
) -> List[bool]:
    """
    Flag questions where close_at < T = resolved_at - lead_days.

    True => the market had already closed at the snapshot time T, so
    crowd_prob_at_T equals the market's closing price (no new trades after
    close_at).  This is a pre-registered sensitivity flag per D-014 §3(b).

    Args:
        close_at_list:    sequence of ISO date strings
        resolved_at_list: sequence of ISO date strings, same length
        lead_days:        snapshot lead time T = resolved_at - lead_days

    Returns:
        list of bool, True = flagged (close_at < T).

    Raises:
        ValueError: if the input lists have different lengths.
    """
    if len(close_at_list) != len(resolved_at_list):
        raise ValueError(
            f"close_at_list ({len(close_at_list)}) and "
            f"resolved_at_list ({len(resolved_at_list)}) must have equal length."
        )
    lead = datetime.timedelta(days=lead_days)
    return [
        parse_date(c) < parse_date(r) - lead
        for c, r in zip(close_at_list, resolved_at_list)
    ]


# ---------------------------------------------------------------------------
# Convenience: assign all splits for a model in one call
# ---------------------------------------------------------------------------

def assign_splits(
    resolved_at_list: Sequence[str],
    close_at_list: Sequence[str],
    model: str,
    cutoffs: Dict[str, str] | None = None,
    lead_days: int = SNAPSHOT_LEAD_DAYS,
) -> Dict[str, List[bool]]:
    """
    Compute all split masks for one model in a single pass.

    Returns a dict with keys:
        "clean"                   : True = clean stratum (D-014 main rule)
        "close_before_cutoff"     : True = close_at < C (sensitivity flag)
        "close_before_T"          : True = close_at < T (sensitivity flag)

    Use key "close_before_cutoff" and label it "close_before_cutoff_<model>"
    in downstream column names per D-014 naming convention.

    Args:
        resolved_at_list: sequence of ISO date strings
        close_at_list:    sequence of ISO date strings, same length
        model:            model ID in cutoffs
        cutoffs:          model -> ISO cutoff string; defaults to TRAINING_CUTOFFS
        lead_days:        snapshot lead time in days

    Returns:
        dict of mask name -> list[bool]
    """
    return {
        "clean": clean_mask(resolved_at_list, close_at_list, model, cutoffs, lead_days),
        "close_before_cutoff": close_before_cutoff_mask(close_at_list, model, cutoffs),
        "close_before_T": close_before_T_mask(close_at_list, resolved_at_list, lead_days),
    }
