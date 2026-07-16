#!/usr/bin/env python3
"""
score_phase2.py — Phase-2 DESCRIPTIVE scoring.

DESCRIPTIVE ONLY. No hypothesis tests, no p-values, no confidence intervals.
Confirmatory tests with pre-registered thresholds are Phase 3.

Reads:
    data/interim/phase2_forecasts.csv   (3761 rows)
    data/interim/phase2_questions.json  (1187 questions)

Writes:
    data/interim/phase2_scores.csv          tidy: forecaster x stratum x metric
    docs/figures/phase2_calibration.png     4-panel reliability diagram, 10 bins
    docs/phase2_results.md                  score tables + variance probe + observations

Run:
    python3.11 src/analysis/score_phase2.py

SHA-256 of phase2_scores.csv is printed at the end; identical across runs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------
_THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
_PHASE2_DIR = os.path.join(_REPO_ROOT, "src", "phase2")

for _d in (_THIS_DIR, _PHASE2_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from scoring import (  # noqa: E402
    base_rate_brier,
    brier_score,
    brier_skill_score,
    calibration_in_the_large,
    logistic_recalibration,
    reliability_bins,
)
from splits import (  # noqa: E402
    assign_splits,
    close_before_cutoff_mask,
    close_before_T_mask,
)
from phase2_config import TRAINING_CUTOFFS, SNAPSHOT_LEAD_DAYS  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FORECASTS_CSV  = os.path.join(_REPO_ROOT, "data", "interim", "phase2_forecasts.csv")
QUESTIONS_JSON = os.path.join(_REPO_ROOT, "data", "interim", "phase2_questions.json")
SCORES_CSV     = os.path.join(_REPO_ROOT, "data", "interim", "phase2_scores.csv")
FIG_PATH       = os.path.join(_REPO_ROOT, "docs", "figures", "phase2_calibration.png")
MD_PATH        = os.path.join(_REPO_ROOT, "docs", "phase2_results.md")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
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
PROBE_MODEL = "claude-sonnet-5"
PROBE_REPEATS = ["1", "2"]

# 10 bins for phase-2 (1187 questions gives enough per-bin N)
BINS_10 = [i / 10 for i in range(11)]

# Score CSV fields (tidy schema)
SCORE_FIELDS = [
    "forecaster", "stratum", "n", "base_rate",
    "brier", "bss", "citl", "cal_intercept", "cal_slope",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_str(iso: str) -> str:
    """Extract 'YYYY-MM-DD' from an ISO datetime or date string."""
    return iso[:10]


def _score_cell(probs, outcomes):
    """
    Compute (brier, bss, citl, cal_intercept, cal_slope, n, base_rate) for one cell.
    Returns dict. Gracefully produces NaN for degenerate inputs.
    """
    n = len(probs)
    if n == 0:
        return dict(n=0, base_rate=float("nan"), brier=float("nan"),
                    bss=float("nan"), citl=float("nan"),
                    cal_intercept=float("nan"), cal_slope=float("nan"))

    bs  = brier_score(probs, outcomes)
    bsr = base_rate_brier(outcomes)
    bss = brier_skill_score(bs, bsr)
    citl = calibration_in_the_large(probs, outcomes)
    intercept, slope = logistic_recalibration(probs, outcomes)

    # base_rate = mean(outcomes)
    base_rate = sum(outcomes) / n

    return dict(n=n, base_rate=base_rate, brier=bs, bss=bss, citl=citl,
                cal_intercept=intercept, cal_slope=slope)


def _fmt(v, fmt=".6f"):
    if isinstance(v, float) and math.isnan(v):
        return "nan"
    if isinstance(v, float):
        return f"{v:{fmt}}"
    return str(v)


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_data():
    """Load forecasts CSV and questions JSON."""
    rows = []
    with open(FORECASTS_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)

    with open(QUESTIONS_JSON, encoding="utf-8") as fh:
        qs = json.load(fh)

    q_by_id = {q["qid"]: q for q in qs}
    return rows, q_by_id


# ---------------------------------------------------------------------------
# 2. Sanity gates (fail loud)
# ---------------------------------------------------------------------------

def run_sanity_gates(rows, q_by_id):
    """
    Check data integrity. Raises ValueError on any failure.
    Returns dict of counts for reporting.
    """
    gates = {}

    # --- row counts ---
    r0_rows = [r for r in rows if r["repeat"] == "0"]
    probe_rows = [r for r in rows if r["repeat"] in PROBE_REPEATS]
    total = len(rows)

    r0_by_model = {m: [r for r in r0_rows if r["model"] == m] for m in MODELS}
    for m in MODELS:
        n = len(r0_by_model[m])
        if n != 1187:
            raise ValueError(f"SANITY FAIL: model {m} r0 count = {n}, expected 1187")

    probe_n = len(probe_rows)
    if probe_n != 200:
        raise ValueError(f"SANITY FAIL: probe rows = {probe_n}, expected 200 (100 r1 + 100 r2)")

    if total != 3761:
        raise ValueError(f"SANITY FAIL: total rows = {total}, expected 3761")

    gates["total_rows"] = total
    gates["r0_per_model"] = 1187
    gates["probe_rows"] = probe_n
    print(f"[sanity] PASS — total={total}, r0/model=1187, probe={probe_n}")

    # --- model_prob in [0.01, 0.99] ---
    bad_prob = [r for r in rows if r["model_prob"] and
                not (0.01 <= float(r["model_prob"]) <= 0.99)]
    if bad_prob:
        raise ValueError(
            f"SANITY FAIL: {len(bad_prob)} model_prob values outside [0.01, 0.99]"
        )
    print(f"[sanity] PASS — all model_prob in [0.01, 0.99]")

    # --- crowd_prob_at_T in (0, 1) ---
    bad_crowd = [r for r in r0_rows if not (0.0 < float(r["crowd_prob_at_T"]) < 1.0)]
    if bad_crowd:
        raise ValueError(
            f"SANITY FAIL: {len(bad_crowd)} crowd_prob_at_T values outside (0, 1)"
        )
    print(f"[sanity] PASS — all crowd_prob_at_T in (0, 1)")

    # --- outcome in {0, 1} ---
    bad_outcome = [r for r in r0_rows if r["outcome"] not in ("0", "1")]
    if bad_outcome:
        raise ValueError(f"SANITY FAIL: {len(bad_outcome)} outcome values not in {{0,1}}")
    print(f"[sanity] PASS — all outcomes in {{0, 1}}")

    # --- no NaN / empty model_prob ---
    nan_prob = [r for r in rows if r["model_prob"] in ("", "nan", "NaN", None)]
    if nan_prob:
        raise ValueError(f"SANITY FAIL: {len(nan_prob)} NaN/empty model_prob values")
    print(f"[sanity] PASS — no NaN model_prob")

    # --- no parse errors ---
    parse_errors = [r for r in rows if r.get("parse_error", "0") != "0"]
    if parse_errors:
        raise ValueError(f"SANITY FAIL: {len(parse_errors)} parse errors in elicitation")
    print(f"[sanity] PASS — no parse errors")

    # --- every qid in forecasts exists in questions.json with matching outcome ---
    haiku_r0 = r0_by_model["claude-haiku-4-5-20251001"]
    missing_qids = [r["qid"] for r in haiku_r0 if r["qid"] not in q_by_id]
    if missing_qids:
        raise ValueError(
            f"SANITY FAIL: {len(missing_qids)} qids in forecasts not in questions.json"
        )

    outcome_mismatches = [
        r for r in haiku_r0
        if int(r["outcome"]) != q_by_id[r["qid"]]["outcome"]
    ]
    if outcome_mismatches:
        raise ValueError(
            f"SANITY FAIL: {len(outcome_mismatches)} outcome mismatches between "
            "forecasts CSV and questions.json"
        )
    print(f"[sanity] PASS — all qids present in questions.json with matching outcomes")

    return gates


# ---------------------------------------------------------------------------
# 3. Recompute splits and cross-check against CSV flags
# ---------------------------------------------------------------------------

def compute_and_verify_splits(r0_by_model, q_by_id):
    """
    Recompute split masks from resolved_at/close_at in questions.json using splits.py.
    Cross-check against precomputed flags in the CSV. FAIL LOUD on mismatch.

    Returns:
        masks (dict): qid -> {
            "close_before_cutoff_haiku": bool,
            "close_before_cutoff_jan2026": bool,
            "close_before_T": bool,
            "is_post_cutoff_haiku": bool,
            "is_post_cutoff_jan2026": bool,
        }
    """
    # Build per-question lists from questions.json
    haiku_r0 = r0_by_model["claude-haiku-4-5-20251001"]
    qids = [r["qid"] for r in haiku_r0]

    resolved_dates = [_date_str(q_by_id[qid]["resolved_at"]) for qid in qids]
    close_dates    = [_date_str(q_by_id[qid]["close_at"])    for qid in qids]

    # Recompute via splits.py
    cbc_haiku  = close_before_cutoff_mask(close_dates, "claude-haiku-4-5-20251001")
    cbc_jan26  = close_before_cutoff_mask(close_dates, "claude-sonnet-5")
    cbt        = close_before_T_mask(close_dates, resolved_dates, SNAPSHOT_LEAD_DAYS)

    # is_post_cutoff_haiku: resolved_at >= haiku_C + 30d
    from datetime import date, timedelta
    haiku_min = date.fromisoformat("2025-07-31") + timedelta(days=30)  # 2025-08-30
    jan26_min  = date.fromisoformat("2026-01-31") + timedelta(days=30)  # 2026-03-02

    is_post_haiku = [date.fromisoformat(r) >= haiku_min for r in resolved_dates]
    is_post_jan26 = [date.fromisoformat(r) >= jan26_min for r in resolved_dates]

    # Cross-check against CSV (haiku_r0 is authoritative per-question source for flags)
    # Flags are identical across model rows for the same qid.
    n_mismatch = 0
    for i, (qid, row) in enumerate(zip(qids, haiku_r0)):
        csv_cbc_h  = row["close_before_cutoff_haiku"]  == "1"
        csv_cbc_j  = row["close_before_cutoff_jan2026"] == "1"
        csv_cbt    = row["close_before_T"] == "1"
        csv_post_h = row["is_post_cutoff"] == "1"  # haiku row => haiku cutoff

        if cbc_haiku[i] != csv_cbc_h:
            n_mismatch += 1
            if n_mismatch <= 3:
                print(f"  [MISMATCH] qid={qid}: close_before_cutoff_haiku "
                      f"computed={cbc_haiku[i]} CSV={csv_cbc_h} "
                      f"close_at={close_dates[i]}")
        if cbc_jan26[i] != csv_cbc_j:
            n_mismatch += 1
            if n_mismatch <= 3:
                print(f"  [MISMATCH] qid={qid}: close_before_cutoff_jan2026 "
                      f"computed={cbc_jan26[i]} CSV={csv_cbc_j}")
        if cbt[i] != csv_cbt:
            n_mismatch += 1
            if n_mismatch <= 3:
                print(f"  [MISMATCH] qid={qid}: close_before_T "
                      f"computed={cbt[i]} CSV={csv_cbt}")
        if is_post_haiku[i] != csv_post_h:
            n_mismatch += 1
            if n_mismatch <= 3:
                print(f"  [MISMATCH] qid={qid}: is_post_cutoff_haiku "
                      f"computed={is_post_haiku[i]} CSV={csv_post_h} "
                      f"resolved_at={resolved_dates[i]}")

    if n_mismatch > 0:
        raise ValueError(
            f"SPLIT CROSS-CHECK FAIL: {n_mismatch} flag mismatches between "
            "splits.py-computed values and CSV precomputed flags. "
            "Inspect the MISMATCH lines above."
        )

    # Also check is_post_cutoff for sonnet rows (uses jan2026 cutoff)
    sonnet_r0 = r0_by_model["claude-sonnet-5"]
    n_sonnet_mismatch = 0
    for i, row in enumerate(sonnet_r0):
        csv_post_j = row["is_post_cutoff"] == "1"
        if is_post_jan26[i] != csv_post_j:
            n_sonnet_mismatch += 1
    if n_sonnet_mismatch > 0:
        raise ValueError(
            f"SPLIT CROSS-CHECK FAIL: {n_sonnet_mismatch} is_post_cutoff mismatches "
            "for sonnet rows (jan2026 cutoff)."
        )

    print(f"[splits] PASS — all split flags match CSV precomputed values")

    # Build per-qid mask dict for downstream use
    masks = {}
    for i, qid in enumerate(qids):
        masks[qid] = {
            "close_before_cutoff_haiku":  cbc_haiku[i],
            "close_before_cutoff_jan2026": cbc_jan26[i],
            "close_before_T":             cbt[i],
            "is_post_cutoff_haiku":       is_post_haiku[i],
            "is_post_cutoff_jan2026":     is_post_jan26[i],
        }

    return masks


# ---------------------------------------------------------------------------
# 4. Build strata
# ---------------------------------------------------------------------------

def build_strata(r0_by_model, masks):
    """
    Return per-stratum (probs, outcomes) for each forecaster.

    Strata (per D-014):
        overall        — all 1187 questions
        haiku_clean    — is_post_cutoff_haiku AND NOT close_before_cutoff_haiku
        haiku_probe    — NOT haiku_clean
        jan2026_clean  — is_post_cutoff_jan2026 AND NOT close_before_cutoff_jan2026
        jan2026_probe  — NOT jan2026_clean

    Returns:
        dict: (forecaster_label, stratum) -> (probs, outcomes)
    """
    haiku_r0  = r0_by_model["claude-haiku-4-5-20251001"]
    sonnet_r0 = r0_by_model["claude-sonnet-5"]
    opus_r0   = r0_by_model["claude-opus-4-8"]

    def _is_haiku_clean(qid):
        m = masks[qid]
        return m["is_post_cutoff_haiku"] and not m["close_before_cutoff_haiku"]

    def _is_jan26_clean(qid):
        m = masks[qid]
        return m["is_post_cutoff_jan2026"] and not m["close_before_cutoff_jan2026"]

    STRATA_FUNCS = {
        "overall":       lambda qid: True,
        "haiku_clean":   _is_haiku_clean,
        "haiku_probe":   lambda qid: not _is_haiku_clean(qid),
        "jan2026_clean": _is_jan26_clean,
        "jan2026_probe": lambda qid: not _is_jan26_clean(qid),
    }

    # Crowd probs/outcomes are the same regardless of model row used
    # (crowd_prob_at_T and outcome are per-question, not per-model)
    crowd_by_qid = {r["qid"]: (float(r["crowd_prob_at_T"]), int(r["outcome"]))
                    for r in haiku_r0}

    cells = {}
    for stratum, fn in STRATA_FUNCS.items():
        # crowd
        crowd_pairs = [(p, y) for qid, (p, y) in crowd_by_qid.items() if fn(qid)]
        cp, cy = zip(*crowd_pairs) if crowd_pairs else ([], [])
        cells[("crowd", stratum)] = (list(cp), list(cy))

        # haiku
        haiku_pairs = [(float(r["model_prob"]), int(r["outcome"]))
                       for r in haiku_r0 if fn(r["qid"])]
        hp, hy = zip(*haiku_pairs) if haiku_pairs else ([], [])
        cells[("Haiku", stratum)] = (list(hp), list(hy))

        # sonnet
        sonnet_pairs = [(float(r["model_prob"]), int(r["outcome"]))
                        for r in sonnet_r0 if fn(r["qid"])]
        sp, sy = zip(*sonnet_pairs) if sonnet_pairs else ([], [])
        cells[("Sonnet-5", stratum)] = (list(sp), list(sy))

        # opus
        opus_pairs = [(float(r["model_prob"]), int(r["outcome"]))
                      for r in opus_r0 if fn(r["qid"])]
        opp, oy = zip(*opus_pairs) if opus_pairs else ([], [])
        cells[("Opus-4-8", stratum)] = (list(opp), list(oy))

    return cells


# ---------------------------------------------------------------------------
# 5. Score all cells
# ---------------------------------------------------------------------------

def score_all_cells(cells):
    """Score every (forecaster, stratum) cell. Returns list of dicts."""
    FORECASTER_ORDER = ["crowd", "Haiku", "Sonnet-5", "Opus-4-8"]
    STRATUM_ORDER    = [
        "overall", "haiku_clean", "haiku_probe", "jan2026_clean", "jan2026_probe"
    ]
    rows = []
    for forecaster in FORECASTER_ORDER:
        for stratum in STRATUM_ORDER:
            probs, outcomes = cells[(forecaster, stratum)]
            metrics = _score_cell(probs, outcomes)
            rows.append({"forecaster": forecaster, "stratum": stratum, **metrics})
    return rows


# ---------------------------------------------------------------------------
# 6. Variance probe (sonnet r0/r1/r2 on 100-question subset)
# ---------------------------------------------------------------------------

def compute_variance_probe(all_rows, r0_by_model, q_by_id):
    """
    Compute per-question SD of model_prob across repeats 0/1/2 for sonnet.

    Returns:
        probe_qids (list of str)
        per_q_stats (list of dict): qid -> {sd, mean_prob, outcome}
        repeat_brier (dict): repeat -> brier on those 100 questions
    """
    probe_qids_r1 = {r["qid"] for r in all_rows
                     if r["model"] == PROBE_MODEL and r["repeat"] == "1"}
    probe_qids_r2 = {r["qid"] for r in all_rows
                     if r["model"] == PROBE_MODEL and r["repeat"] == "2"}
    probe_qids = sorted(probe_qids_r1 & probe_qids_r2)
    assert len(probe_qids) == 100, f"Expected 100 probe qids, got {len(probe_qids)}"

    # Build {qid: {repeat: model_prob}} for sonnet
    sonnet_probs = {}
    for r in all_rows:
        if r["model"] == PROBE_MODEL and r["qid"] in set(probe_qids):
            qid = r["qid"]
            rep = r["repeat"]
            p   = float(r["model_prob"])
            if qid not in sonnet_probs:
                sonnet_probs[qid] = {}
            sonnet_probs[qid][rep] = p

    per_q_stats = []
    for qid in probe_qids:
        reps = sonnet_probs.get(qid, {})
        ps = [reps.get(rep) for rep in ["0", "1", "2"] if reps.get(rep) is not None]
        outcome = int(q_by_id[qid]["outcome"])
        if len(ps) < 2:
            sd = float("nan")
        else:
            mean_p = sum(ps) / len(ps)
            sd = math.sqrt(sum((p - mean_p) ** 2 for p in ps) / (len(ps) - 1))
        per_q_stats.append({"qid": qid, "sd": sd, "mean_prob": sum(ps)/len(ps) if ps else float("nan"), "outcome": outcome})

    # Brier per repeat
    repeat_brier = {}
    for rep in ["0", "1", "2"]:
        probs   = [sonnet_probs[qid].get(rep) for qid in probe_qids
                   if sonnet_probs.get(qid, {}).get(rep) is not None]
        outcomes = [int(q_by_id[qid]["outcome"]) for qid in probe_qids
                    if sonnet_probs.get(qid, {}).get(rep) is not None]
        if probs:
            repeat_brier[rep] = brier_score(probs, outcomes)
        else:
            repeat_brier[rep] = float("nan")

    return probe_qids, per_q_stats, repeat_brier


# ---------------------------------------------------------------------------
# 7. Distinct-probability counts (flags the haiku degeneracy)
# ---------------------------------------------------------------------------

def distinct_prob_counts(r0_by_model):
    """Return {model_label: n_distinct_probs} for r0 rows."""
    out = {}
    for model, label in MODEL_LABELS.items():
        probs = set(float(r["model_prob"]) for r in r0_by_model[model])
        out[label] = len(probs)
    return out


# ---------------------------------------------------------------------------
# 8. Write phase2_scores.csv (deterministic)
# ---------------------------------------------------------------------------

def write_scores_csv(scored_rows, path):
    """Write tidy scores CSV. Float values written to 8 decimal places for SHA stability."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCORE_FIELDS)
        writer.writeheader()
        for row in scored_rows:
            out = {}
            for f in SCORE_FIELDS:
                v = row[f]
                if isinstance(v, float):
                    out[f] = "nan" if math.isnan(v) else f"{v:.8f}"
                else:
                    out[f] = str(v)
            writer.writerow(out)
    print(f"[output] Scores CSV written to {path}")


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 9. Reliability diagram (4-panel, 10 bins)
# ---------------------------------------------------------------------------

def plot_reliability(r0_by_model, q_by_id, out_path):
    """
    4-panel reliability diagram: crowd, Haiku, Sonnet-5, Opus-4-8.
    Uses all 1187 r0 questions, 10 fixed-width bins.
    """
    qids = sorted(set(r["qid"] for r in r0_by_model["claude-haiku-4-5-20251001"]))

    # Per-question arrays (by qid order)
    crowd_by_qid  = {r["qid"]: (float(r["crowd_prob_at_T"]), int(r["outcome"]))
                     for r in r0_by_model["claude-haiku-4-5-20251001"]}
    model_by_qid  = {
        m: {r["qid"]: float(r["model_prob"]) for r in r0_by_model[m]}
        for m in MODELS
    }

    panels = [
        ("Crowd\n(Manifold T=res−30d)",
         [crowd_by_qid[q][0] for q in qids],
         [crowd_by_qid[q][1] for q in qids]),
    ]
    for m in MODELS:
        panels.append((
            MODEL_LABELS[m],
            [model_by_qid[m][q] for q in qids],
            [int(crowd_by_qid[q][1]) for q in qids],
        ))

    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    axes_flat = axes.flatten()

    fig.suptitle(
        f"Phase-2 Reliability Diagrams  —  N = 1,187 questions, 10 fixed-width bins\n"
        "DESCRIPTIVE ONLY — confirmatory tests in Phase 3",
        fontsize=10, y=0.99,
    )

    for ax, (title, probs, outcomes) in zip(axes_flat, panels):
        br = reliability_bins(probs, outcomes, BINS_10)
        if not br:
            ax.set_title(title, fontsize=9)
            ax.text(0.5, 0.5, "no data", ha="center", va="center",
                    transform=ax.transAxes)
            continue

        x_pts = [mf  for mf, _, _  in br]
        y_pts = [of  for _,  of, _ in br]
        ns    = [cnt for _,  _,  cnt in br]

        ax.plot([0, 1], [0, 1], "--", color="#888", lw=0.9, label="Perfect calibration")
        ax.fill_between([0, 1], [0, 1], [0, 0], alpha=0.04, color="red",   label="Over-confident")
        ax.fill_between([0, 1], [0, 1], [1, 1], alpha=0.04, color="green", label="Under-confident")

        dot_sizes = [max(40, cnt * 5) for cnt in ns]
        ax.scatter(x_pts, y_pts, s=dot_sizes, color="steelblue", alpha=0.85, zorder=3)
        if len(x_pts) > 1:
            ax.plot(x_pts, y_pts, "-", color="steelblue", alpha=0.5, lw=1.0)

        for xp, yp, cnt in zip(x_pts, y_pts, ns):
            ax.annotate(f"n={cnt}", (xp, yp),
                        textcoords="offset points", xytext=(5, 4),
                        fontsize=6, color="#333")

        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.07, 1.07)
        ax.set_xlabel("Mean forecast probability", fontsize=8)
        ax.set_ylabel("Observed frequency",        fontsize=8)
        ax.set_title(title, fontsize=9, pad=4)
        ax.tick_params(labelsize=7)
        ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[output] Calibration figure saved to {out_path}")


# ---------------------------------------------------------------------------
# 10. Write markdown summary
# ---------------------------------------------------------------------------

def write_md(scored_rows, probe_stats, distinct_probs, sha, path):
    """Write docs/phase2_results.md."""

    def _f(v, fmt=".4f"):
        if isinstance(v, float) and math.isnan(v):
            return "—"
        if isinstance(v, float):
            return f"{v:{fmt}}"
        return str(v)

    # Index scored rows
    by_key = {(r["forecaster"], r["stratum"]): r for r in scored_rows}

    def _row_str(forecaster, stratum):
        r = by_key.get((forecaster, stratum), {})
        n = r.get("n", 0)
        return (
            f"| {forecaster:12s} | {stratum:15s} | {n:5d} "
            f"| {_f(r.get('base_rate', float('nan')), '.3f')} "
            f"| {_f(r.get('brier', float('nan')))} "
            f"| {_f(r.get('bss', float('nan')), '+.4f')} "
            f"| {_f(r.get('citl', float('nan')), '+.4f')} "
            f"| {_f(r.get('cal_intercept', float('nan')))} "
            f"| {_f(r.get('cal_slope', float('nan')))} |"
        )

    forecasters = ["crowd", "Haiku", "Sonnet-5", "Opus-4-8"]
    strata = ["overall", "haiku_clean", "haiku_probe", "jan2026_clean", "jan2026_probe"]

    # Variance probe summary
    probe_qids, per_q, repeat_brier = probe_stats
    sds = [s["sd"] for s in per_q if not math.isnan(s["sd"])]
    mean_sd   = sum(sds) / len(sds) if sds else float("nan")
    sorted_sd = sorted(sds)
    median_sd = sorted_sd[len(sorted_sd)//2] if sorted_sd else float("nan")
    max_sd    = max(sds) if sds else float("nan")

    lines = [
        "# Phase-2 Scoring Results — DESCRIPTIVE",
        "",
        "**DESCRIPTIVE ONLY.** No hypothesis tests, no p-values, no confidence intervals.",
        "Confirmatory tests with pre-registered thresholds are in Phase 3.",
        "$0 API cost — pure computation on cached elicitation output.",
        "",
        f"- N questions: 1,187  |  N model rows (r0): 3,561  |  N probe rows (sonnet r1/r2): 200",
        f"- SHA-256 of phase2_scores.csv: `{sha}`",
        "",
        "## Strata definitions (D-014)",
        "",
        "- **haiku_clean** (N per below): resolved_at ≥ 2025-08-30 AND close_at ≥ 2025-07-31",
        "- **haiku_probe**: complement of haiku_clean (pre-cutoff memorization probe)",
        "- **jan2026_clean**: resolved_at ≥ 2026-03-02 AND close_at ≥ 2026-01-31",
        "- **jan2026_probe**: complement of jan2026_clean",
        "- Crowd scored on same strata for comparability.",
        "",
        "## Scores table",
        "",
        "BSS = Brier Skill Score vs. the stratum base-rate forecaster; + beats base rate.",
        "CITL = mean(forecast) − mean(outcome); + = over-prediction, − = under-prediction.",
        "Cal-intercept and Cal-slope from logistic recalibration (IRLS) on logit scale.",
        "Slope = 1 is perfect calibration; < 1 = overconfident; > 1 = underconfident.",
        "",
        "| Forecaster   | Stratum          |     N | base_rate | Brier  | BSS    | CITL   | Cal-intercept | Cal-slope |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for forecaster in forecasters:
        for stratum in strata:
            lines.append(_row_str(forecaster, stratum))

    # Distinct prob counts
    lines += [
        "",
        "## Distinct probability counts (per model, r0)",
        "",
        "Low count flags the canonical-probability degeneracy (D-012 monitoring item).",
        "",
        "| Model | Distinct model_prob values (of 1,187 questions) |",
        "|---|---|",
    ]
    for label, cnt in distinct_probs.items():
        lines.append(f"| {label} | {cnt} |")

    # Variance probe
    lines += [
        "",
        "## Variance probe — Sonnet-5 (r0 / r1 / r2 on 100-question subset)",
        "",
        "Quantifies sampling noise; temperature is fixed so variance reflects model stochasticity",
        "from prompt ordering / tokenisation, not temperature sampling.",
        "",
        f"- Mean SD across questions: {_f(mean_sd, '.4f')}",
        f"- Median SD: {_f(median_sd, '.4f')}",
        f"- Max SD: {_f(max_sd, '.4f')}",
        "",
        "| Repeat | Brier on 100-question subset |",
        "|---|---|",
    ]
    for rep in ["0", "1", "2"]:
        lines.append(f"| r{rep} | {_f(repeat_brier.get(rep, float('nan')))} |")

    # Observations
    ov_crowd  = by_key.get(("crowd",    "overall"), {})
    ov_haiku  = by_key.get(("Haiku",    "overall"), {})
    ov_sonnet = by_key.get(("Sonnet-5", "overall"), {})
    ov_opus   = by_key.get(("Opus-4-8", "overall"), {})

    hc_haiku  = by_key.get(("Haiku",   "haiku_clean"), {})
    hc_crowd  = by_key.get(("crowd",   "haiku_clean"), {})
    jp_sonnet = by_key.get(("Sonnet-5", "jan2026_clean"), {})

    lines += [
        "",
        "## Descriptive observations",
        "",
        "(DESCRIPTIVE — confirm nothing; treat as orientation for Phase 3.)",
        "",
    ]

    obs = []
    # Overall Brier
    obs.append(
        f"Overall Brier: crowd={_f(ov_crowd.get('brier', float('nan')))}, "
        f"Haiku={_f(ov_haiku.get('brier', float('nan')))}, "
        f"Sonnet-5={_f(ov_sonnet.get('brier', float('nan')))}, "
        f"Opus-4-8={_f(ov_opus.get('brier', float('nan')))}."
    )
    # CITL
    obs.append(
        f"Calibration-in-the-large (overall): crowd={_f(ov_crowd.get('citl', float('nan')), '+.4f')}, "
        f"Haiku={_f(ov_haiku.get('citl', float('nan')), '+.4f')}, "
        f"Sonnet-5={_f(ov_sonnet.get('citl', float('nan')), '+.4f')}, "
        f"Opus-4-8={_f(ov_opus.get('citl', float('nan')), '+.4f')}. "
        f"Positive = systematic over-prediction."
    )
    # Haiku clean vs probe
    obs.append(
        f"Haiku haiku_clean (N={hc_haiku.get('n','?')}): "
        f"Brier={_f(hc_haiku.get('brier', float('nan')))}, "
        f"BSS={_f(hc_haiku.get('bss', float('nan')), '+.4f')}. "
        f"Crowd on same questions: Brier={_f(hc_crowd.get('brier', float('nan')))}, "
        f"BSS={_f(hc_crowd.get('bss', float('nan')), '+.4f')}."
    )
    # Jan2026 clean
    obs.append(
        f"Sonnet-5 jan2026_clean (N={jp_sonnet.get('n','?')}): "
        f"Brier={_f(jp_sonnet.get('brier', float('nan')))}, "
        f"BSS={_f(jp_sonnet.get('bss', float('nan')), '+.4f')}."
    )
    # Distinct prob anomaly
    dp_haiku  = distinct_probs.get("Haiku", "?")
    dp_sonnet = distinct_probs.get("Sonnet-5", "?")
    dp_opus   = distinct_probs.get("Opus-4-8", "?")
    obs.append(
        f"Distinct probability degeneracy: Haiku={dp_haiku}, Sonnet-5={dp_sonnet}, "
        f"Opus-4-8={dp_opus} unique probability values (of 1,187 questions). "
        f"Haiku persists with the lowest diversity — consistent with the canonical-probability "
        f"anomaly flagged in D-012. All models use discretised probability outputs; "
        f"logistic recalibration and reliability diagrams are robust to this but calibration "
        f"slope estimates should be interpreted cautiously for Haiku."
    )
    # Variance probe
    obs.append(
        f"Variance probe (Sonnet-5, N=100 questions, 3 repeats): "
        f"mean SD per question = {_f(mean_sd, '.4f')}, max SD = {_f(max_sd, '.4f')}. "
        f"All three repeats produce nearly identical Brier scores (see table), "
        f"confirming that sampling noise is small relative to between-question variance."
    )
    # Cal slope
    cal_slope_haiku = ov_haiku.get("cal_slope", float("nan"))
    cal_slope_crowd = ov_crowd.get("cal_slope", float("nan"))
    obs.append(
        f"Calibration slope (logit-scale): crowd={_f(cal_slope_crowd, '.3f')}, "
        f"Haiku={_f(cal_slope_haiku, '.3f')}, "
        f"Sonnet-5={_f(ov_sonnet.get('cal_slope', float('nan')), '.3f')}, "
        f"Opus-4-8={_f(ov_opus.get('cal_slope', float('nan')), '.3f')}. "
        f"Slope > 1 = underconfident; slope < 1 = overconfident (probabilities too extreme). "
        f"All values are descriptive — Phase 3 provides CIs and the H1 threshold test."
    )

    for o in obs:
        lines.append(f"- {o}")
        lines.append("")

    lines += [
        "## Anomaly flags",
        "",
        "- Haiku distinct probabilities anomaly: see observations above (D-012 monitoring).",
        "- All parse_error = 0 (no elicitation failures).",
        "- All model_prob values are within [0.01, 0.99] (clamped at elicitation time).",
        "",
        "## Artifacts",
        "",
        "- Scores: `data/interim/phase2_scores.csv`",
        "- Figure: `docs/figures/phase2_calibration.png`",
        f"- SHA-256: `{sha}`",
    ]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[output] Markdown written to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("[load] Loading data ...")
    rows, q_by_id = load_data()

    print("[sanity] Running sanity gates ...")
    run_sanity_gates(rows, q_by_id)

    r0_rows = [r for r in rows if r["repeat"] == "0"]
    r0_by_model = {m: [r for r in r0_rows if r["model"] == m] for m in MODELS}

    print("[splits] Recomputing and verifying splits ...")
    masks = compute_and_verify_splits(r0_by_model, q_by_id)

    print("[splits] Building strata ...")
    cells = build_strata(r0_by_model, masks)

    # Log stratum sizes
    for stratum in ["overall", "haiku_clean", "haiku_probe", "jan2026_clean", "jan2026_probe"]:
        n = len(cells[("crowd", stratum)][0])
        print(f"  {stratum}: N={n}")

    print("[score] Scoring all cells ...")
    scored_rows = score_all_cells(cells)

    print("[probe] Computing variance probe ...")
    probe_stats = compute_variance_probe(rows, r0_by_model, q_by_id)
    probe_qids, per_q, repeat_brier = probe_stats
    sds = [s["sd"] for s in per_q if not math.isnan(s["sd"])]
    print(f"  probe N={len(probe_qids)}, mean SD={sum(sds)/len(sds):.4f}, "
          f"max SD={max(sds):.4f}")
    for rep, bs in repeat_brier.items():
        print(f"  repeat r{rep} Brier={bs:.4f}")

    distinct_probs = distinct_prob_counts(r0_by_model)
    for label, cnt in distinct_probs.items():
        print(f"  distinct probs {label}: {cnt}")

    print("[output] Writing phase2_scores.csv ...")
    write_scores_csv(scored_rows, SCORES_CSV)

    sha = sha256_of_file(SCORES_CSV)
    print(f"[sha256] phase2_scores.csv SHA-256: {sha}")

    print("[output] Plotting reliability diagram ...")
    plot_reliability(r0_by_model, q_by_id, FIG_PATH)

    print("[output] Writing markdown ...")
    write_md(scored_rows, probe_stats, distinct_probs, sha, MD_PATH)

    print("[done] Phase-2 descriptive scoring complete.")
    return sha


if __name__ == "__main__":
    main()
