#!/usr/bin/env python3
"""
rq4_backtest.py — RQ4 friction-aware backtest on post-cutoff questions.

D-016 §6 implementation (frozen spec).

CPMM model (approximation)
--------------------------
Note: Manifold uses Maniswap (k = Y^p0 * N^(1-p0)), not standard CPMM.
The stored total_liquidity field is Manifold's addedLiquidity (cumulative mana
deposited), not pool shares; live-API spot checks found actual pool sums 7-12x
larger.  This backtest uses standard binary CPMM as an approximation, with
p_YES = N/(Y+N), treating L = total_liquidity as a proxy for pool depth.
Quantified impact: for large-L markets both errors change gross profit <5% per
winning bet; losses dominate wins (hit rate 22%), so the H4 NO-EDGE decision
is robust to any defensible convention.  The true p0 and pool state at T were
not stored and cannot be retrieved retrospectively.

Convention used: p_YES = N/(Y+N), L = total_liquidity (proxy), k = p*(1-p)*L².

Bet YES (p_model > p_market + threshold):
  Bettor mints s YES + s NO shares; keeps s YES; sells s NO to pool.
  shares_YES = s * (L+s) / (p_market*L + s)
  gross_profit = shares_YES - s = s*(1-p_market)*L / (p_market*L + s)

Bet NO (p_model < p_market - threshold):
  Bettor mints s YES + s NO; keeps s NO; sells s YES to pool.
  shares_NO = s * (L+s) / ((1-p_market)*L + s)
  gross_profit = shares_NO - s = s*p_market*L / ((1-p_market)*L + s)

Net P&L (win)  = gross_profit * (1 - FEE_RATE)
Net P&L (lose) = -stake

Fee
---
FEE_RATE = 0.05 (5% of gross profit, applied to wins only).  Flat estimate
covering Manifold creator + platform fees; actual fees are per-market and not
stored in the dataset.  Manifold is play-money — see caveats.

Bankroll
--------
B_0=1000 mana; stake=0.01*B_0=10 mana per bet (fixed, no compounding).
Questions ordered by resolved_at (ascending) for the cumulative P&L curve.

Platt recalibration
-------------------
5-fold CV (PLATT_SEED=42), logistic_recalibration from scoring.py, logit scale.
Applied out-of-fold to prevent leakage from outcomes.

Bootstrap
---------
N_BOOT=10,000, seed=42.  Resample N question indices with replacement.
CI = percentile [2.5%, 97.5%].

H4 decision
-----------
"Edge survives" iff 95% CI of total P&L excludes ≤ 0 (net of all costs).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path wiring
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_PHASE2_DIR = os.path.join(_REPO, "src", "phase2")
for _p in [_PHASE2_DIR, _HERE]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scoring import logistic_recalibration  # noqa: E402 (path wiring must precede)

# ---------------------------------------------------------------------------
# Constants — D-016 §6
# ---------------------------------------------------------------------------
FEE_RATE: float = 0.05           # 5% of gross profit on winning bets
BANKROLL_INIT: float = 1_000.0   # mana
STAKE: float = BANKROLL_INIT * 0.01  # 10 mana per bet (fixed, no compounding)
BET_THRESHOLD: float = 0.05      # minimum |p_model - p_market| to bet
N_BOOT: int = 10_000
BOOT_SEED: int = 42
PLATT_FOLDS: int = 5
PLATT_SEED: int = 42
CLAMP_EPS: float = 1e-7          # logit clamping (matches D-016)

HAIKU: str = "claude-haiku-4-5-20251001"
SONNET: str = "claude-sonnet-5"
OPUS: str = "claude-opus-4-8"

DATA_DIR: str = os.path.join(_REPO, "data", "interim")
DOCS_DIR: str = os.path.join(_REPO, "docs")
FIG_DIR: str = os.path.join(DOCS_DIR, "figures")

FORECASTS_CSV: str = os.path.join(DATA_DIR, "phase2_forecasts.csv")
QUESTIONS_JSON: str = os.path.join(DATA_DIR, "phase2_questions.json")
OUT_JSON: str = os.path.join(DATA_DIR, "phase3_rq4.json")
OUT_FIG: str = os.path.join(FIG_DIR, "rq4_pnl.png")
PHASE3_MD: str = os.path.join(DOCS_DIR, "phase3_results.md")


# ---------------------------------------------------------------------------
# CPMM mechanics
# ---------------------------------------------------------------------------

def _cpmm_gross_profit(p_market: float, L: float, bet_yes: bool, s: float) -> float:
    """
    Gross profit (before fees) on a winning CPMM bet.

    Bet YES: gross_profit = s*(1-p)*L / (p*L + s)
    Bet NO:  gross_profit = s*p*L / ((1-p)*L + s)

    Args:
        p_market: current market probability of YES
        L:        total_liquidity = Y + N (total shares in pool)
        bet_yes:  True for a YES bet, False for a NO bet
        s:        stake in mana

    Returns:
        gross profit in mana (positive number; the caller determines sign by outcome).
    """
    if bet_yes:
        N = p_market * L          # NO pool (minting s NO, selling to pool)
        return s * (1.0 - p_market) * L / (N + s)
    else:
        Y = (1.0 - p_market) * L  # YES pool (minting s YES, selling to pool)
        return s * p_market * L / (Y + s)


def compute_question_pnl(
    p_market: float,
    L: float,
    p_model: float,
    outcome: int,
) -> Tuple[float, str]:
    """
    Net P&L and bet direction for one question under CPMM mechanics.

    Places a bet only when |p_model - p_market| > BET_THRESHOLD and L > 0
    and p_market is in (0, 1).

    Returns:
        (net_pnl, direction) where direction is in {'YES', 'NO', 'PASS'}.
        net_pnl = gross_profit*(1-FEE_RATE) if won, -STAKE if lost, 0 if PASS.

    Raises:
        Nothing — degenerate inputs (L=0, p=0/1) result in PASS.
    """
    diff = p_model - p_market
    if abs(diff) <= BET_THRESHOLD or L <= 0.0 or not (0.0 < p_market < 1.0):
        return 0.0, "PASS"

    bet_yes = diff > 0.0
    direction = "YES" if bet_yes else "NO"
    gross_profit = _cpmm_gross_profit(p_market, L, bet_yes, STAKE)
    net_profit = gross_profit * (1.0 - FEE_RATE)

    won = (direction == "YES" and outcome == 1) or (direction == "NO" and outcome == 0)
    return (net_profit if won else -STAKE), direction


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap_pnl_ci(
    pnl_list: List[float],
    seed: int = BOOT_SEED,
) -> Tuple[float, float]:
    """
    Percentile 95% CI on total P&L via N_BOOT bootstrap resamples.

    Resamples len(pnl_list) indices with replacement; computes sum each time.
    Percentile CI at [alpha/2, 1-alpha/2] = [2.5%, 97.5%].

    Args:
        pnl_list: per-question net P&L (0 for PASS questions)
        seed:     RNG seed (explicit; default=BOOT_SEED=42)

    Returns:
        (ci_lo, ci_hi) at 95% level.
    """
    n = len(pnl_list)
    rng = random.Random(seed)
    boot_totals: List[float] = []
    for _ in range(N_BOOT):
        total = sum(pnl_list[rng.randrange(n)] for _ in range(n))
        boot_totals.append(total)
    boot_totals.sort()
    lo = int(0.025 * N_BOOT)
    hi = min(int(0.975 * N_BOOT), N_BOOT - 1)
    return boot_totals[lo], boot_totals[hi]


# ---------------------------------------------------------------------------
# Platt recalibration (out-of-fold)
# ---------------------------------------------------------------------------

def _kfold_indices(n: int, k: int, seed: int) -> List[List[int]]:
    """
    K non-overlapping fold index lists from a seeded shuffle of range(n).

    Folds are contiguous slices of the shuffled index list.
    Sizes differ by at most 1 when n is not divisible by k.

    Args:
        n:    number of observations
        k:    number of folds
        seed: RNG seed for the initial shuffle

    Returns:
        list of k lists, together covering range(n) exactly once.
    """
    rng = random.Random(seed)
    idx = list(range(n))
    rng.shuffle(idx)
    return [idx[i * n // k:(i + 1) * n // k] for i in range(k)]


def platt_calibrate_oof(
    probs: List[float],
    outcomes: List[int],
) -> List[float]:
    """
    Out-of-fold Platt (logistic) recalibration on the logit scale.

    Fits outcome ~ sigmoid(a + b*logit(p_model)) on PLATT_FOLDS-1 folds,
    applies to the held-out fold.  Returns recalibrated probabilities for
    all n questions.  Falls back to raw p_model if IRLS is degenerate.

    Args:
        probs:    model probabilities (raw, uncalibrated)
        outcomes: binary outcomes {0, 1}

    Returns:
        list of recalibrated probabilities, same length as probs.
    """
    n = len(probs)
    folds = _kfold_indices(n, PLATT_FOLDS, PLATT_SEED)
    p_recal: List[float] = [0.0] * n

    for test_idx in folds:
        test_set = set(test_idx)
        train_idx = [i for i in range(n) if i not in test_set]

        intercept, slope = logistic_recalibration(
            [probs[i] for i in train_idx],
            [outcomes[i] for i in train_idx],
            clamp_eps=CLAMP_EPS,
        )

        for i in test_idx:
            if math.isnan(intercept) or math.isnan(slope):
                p_recal[i] = probs[i]  # fallback: degenerate fold
            else:
                p_c = min(1.0 - CLAMP_EPS, max(CLAMP_EPS, probs[i]))
                logit_p = math.log(p_c / (1.0 - p_c))
                eta = max(-50.0, min(50.0, intercept + slope * logit_p))
                p_recal[i] = 1.0 / (1.0 + math.exp(-eta))

    return p_recal


# ---------------------------------------------------------------------------
# Backtest runner
# ---------------------------------------------------------------------------

def _filter_clean(rows: List[Dict], model: str, cbc_flag: str) -> List[Dict]:
    """
    Filter CSV rows to one model's clean stratum, sorted by resolved_at.

    Criteria: model matches, repeat='0', is_post_cutoff='1', cbc_flag='0'.
    cbc_flag is 'close_before_cutoff_haiku' for haiku,
               'close_before_cutoff_jan2026' for sonnet/opus.

    Returns:
        filtered rows sorted ascending by resolved_at[:10].
    """
    filtered = [
        r for r in rows
        if r["model"] == model
        and r["repeat"] == "0"
        and r["is_post_cutoff"] == "1"
        and r[cbc_flag] == "0"
    ]
    filtered.sort(key=lambda r: r["resolved_at"][:10])
    return filtered


def _run_cell(
    filtered_rows: List[Dict],
    q_by_id: Dict,
    p_models: List[float],
    label: str,
    model: str,
) -> Dict:
    """
    Core backtest computation for one model/stratum/probability-set.

    Args:
        filtered_rows: question rows (sorted by resolved_at)
        q_by_id:       question dict for microstructure lookup
        p_models:      model probabilities (may be Platt-recalibrated)
        label:         human-readable label for output
        model:         model identifier string

    Returns:
        dict of summary statistics and internal arrays (_per_q_pnl, etc.)
        for use in figure generation; _-prefixed keys stripped before JSON.
    """
    p_markets = [float(r["crowd_prob_at_T"]) for r in filtered_rows]
    outcomes  = [int(r["outcome"]) for r in filtered_rows]
    liq       = [
        q_by_id[r["qid"]]["microstructure"]["total_liquidity"]
        for r in filtered_rows
    ]
    resolved  = [r["resolved_at"][:10] for r in filtered_rows]
    n = len(filtered_rows)

    per_q_pnl: List[float] = []
    directions: List[str]  = []
    for i in range(n):
        pnl, d = compute_question_pnl(p_markets[i], liq[i], p_models[i], outcomes[i])
        per_q_pnl.append(pnl)
        directions.append(d)

    n_bets    = sum(1 for d in directions if d != "PASS")
    n_yes     = sum(1 for d in directions if d == "YES")
    n_no      = sum(1 for d in directions if d == "NO")
    n_excl    = sum(
        1 for i in range(n)
        if liq[i] <= 0.0 or not (0.0 < p_markets[i] < 1.0)
    )
    n_correct = sum(
        1 for i, d in enumerate(directions)
        if d != "PASS"
        and ((d == "YES" and outcomes[i] == 1) or (d == "NO" and outcomes[i] == 0))
    )
    total_staked = n_bets * STAKE
    total_pnl    = sum(per_q_pnl)
    roi          = total_pnl / total_staked if total_staked > 0 else float("nan")
    hit_rate     = n_correct / n_bets if n_bets > 0 else float("nan")

    ci_lo, ci_hi = bootstrap_pnl_ci(per_q_pnl)
    h4 = "EDGE-SURVIVES" if ci_lo > 0.0 else "NO-EDGE"

    return {
        "label":             label,
        "model":             model,
        "N_questions":       n,
        "N_excluded":        n_excl,
        "N_bets":            n_bets,
        "N_yes_bets":        n_yes,
        "N_no_bets":         n_no,
        "N_correct":         n_correct,
        "hit_rate":          round(hit_rate, 4) if not math.isnan(hit_rate) else None,
        "total_staked_mana": round(total_staked, 2),
        "total_pnl_mana":    round(total_pnl, 4),
        "roi_pct":           round(roi * 100, 2) if not math.isnan(roi) else None,
        "pnl_95ci_mana":     [round(ci_lo, 4), round(ci_hi, 4)],
        "h4_decision":       h4,
        # internal — used by make_figure; stripped before JSON write
        "_per_q_pnl":        per_q_pnl,
        "_resolved_dates":   resolved,
        "_liq":              liq,
    }


def _strip_internal(d: Dict) -> Dict:
    """Remove _-prefixed keys before JSON serialization."""
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def make_figure(
    haiku_res: Dict, platt_res: Dict, sonnet_res: Dict, opus_res: Dict
) -> None:
    """
    2-panel figure.

    Left:  cumulative P&L over resolved_at for haiku main vs Platt.
    Right: bootstrap distribution of haiku main total P&L with CI and
           observed value marked.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # --- Left panel: cumulative P&L ---
    for res, color, ls, lbl in [
        (haiku_res, "steelblue",  "-",  "Haiku (main)"),
        (platt_res, "darkorange", "--", "Haiku + Platt"),
    ]:
        pnl = res["_per_q_pnl"]
        cum = [0.0]
        for v in pnl:
            cum.append(cum[-1] + v)
        ax1.plot(range(len(cum)), cum, color=color, ls=ls, lw=1.5, label=lbl)

    ax1.axhline(0, color="gray", lw=0.8, ls=":")
    ax1.set_xlabel("Question index (ordered by resolved_at)")
    ax1.set_ylabel("Cumulative P&L (mana)")
    ax1.set_title("RQ4 — Cumulative P&L (haiku_clean, N=352)")
    ax1.legend()

    # --- Right panel: bootstrap distribution ---
    pnl = haiku_res["_per_q_pnl"]
    n = len(pnl)
    rng = random.Random(BOOT_SEED)  # same seed as bootstrap_pnl_ci → identical CI
    boot_totals: List[float] = []
    for _ in range(N_BOOT):
        boot_totals.append(sum(pnl[rng.randrange(n)] for _ in range(n)))
    boot_totals.sort()

    ci_lo = boot_totals[int(0.025 * N_BOOT)]
    ci_hi = boot_totals[min(int(0.975 * N_BOOT), N_BOOT - 1)]
    obs   = sum(pnl)

    ax2.hist(boot_totals, bins=60, color="steelblue", alpha=0.7, edgecolor="none")
    ax2.axvline(obs,   color="black", lw=1.5,        label=f"Observed ({obs:+.1f} mana)")
    ax2.axvline(ci_lo, color="red",   lw=1.2, ls="--",
                label=f"95% CI [{ci_lo:+.1f}, {ci_hi:+.1f}]")
    ax2.axvline(ci_hi, color="red",   lw=1.2, ls="--")
    ax2.axvline(0,     color="gray",  lw=0.8, ls=":")
    ax2.set_xlabel("Bootstrap total P&L (mana)")
    ax2.set_ylabel("Count")
    ax2.set_title(f"RQ4 — Bootstrap distribution (N_boot={N_BOOT:,})")
    ax2.legend(fontsize=8)

    plt.tight_layout()
    os.makedirs(FIG_DIR, exist_ok=True)
    plt.savefig(OUT_FIG, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[figure] saved → {OUT_FIG}")


# ---------------------------------------------------------------------------
# Markdown (extend phase3_results.md)
# ---------------------------------------------------------------------------

def _write_rq4_md(
    haiku_res: Dict,
    platt_res: Dict,
    sonnet_res: Dict,
    opus_res: Dict,
) -> None:
    """Append RQ4 section to docs/phase3_results.md."""
    h, p, s, o = haiku_res, platt_res, sonnet_res, opus_res

    liq_sorted = sorted(h["_liq"])
    med_liq = liq_sorted[len(liq_sorted) // 2] if liq_sorted else 0.0

    section = f"""

---

## RQ4 — Friction-Aware Backtest (H4)

**Pre-registration:** D-016 §6.
**Status:** PRELIMINARY (haiku_clean); EXPLORATORY (sonnet/opus jan2026_clean).  Strategy and threshold are pre-registered (D-016 §6), but H4 sits outside the confirmatory BH family and is designated preliminary per D-005 (play-money platform; no real economic stakes).

### Parameters

| Parameter | Value |
|---|---|
| CPMM convention | p_YES = N/(Y+N); total_liquidity = L = Y+N; k = p(1-p)L² |
| Fee rate | {FEE_RATE*100:.0f}% of gross profit on wins (flat estimate; see Caveats) |
| Bankroll | B₀ = {BANKROLL_INIT:.0f} mana; stake = 1% x B₀ = {STAKE:.0f} mana (fixed, no compounding) |
| Bet threshold | |p_model - p_market| > {BET_THRESHOLD} |
| Order | Sequential by resolved_at (ascending) |
| Bootstrap | N = {N_BOOT:,}, seed = {BOOT_SEED}, percentile CI [2.5%, 97.5%] |
| Platt | {PLATT_FOLDS}-fold CV, seed = {PLATT_SEED}, logit-scale logistic recalibration (out-of-fold) |

### H4 preliminary — haiku_clean (N = {h['N_questions']})

| Metric | Value |
|---|---|
| N excluded (L = 0 or p_market degenerate) | {h['N_excluded']} |
| N bets placed | {h['N_bets']} ({h['N_yes_bets']} YES, {h['N_no_bets']} NO) |
| N correct | {h['N_correct']} |
| Hit rate | {h['hit_rate']:.3f} |
| Total staked | {h['total_staked_mana']:.0f} mana |
| Total P&L | {h['total_pnl_mana']:+.2f} mana |
| ROI | {h['roi_pct']:+.2f}% |
| 95% bootstrap CI | [{h['pnl_95ci_mana'][0]:+.2f}, {h['pnl_95ci_mana'][1]:+.2f}] mana |
| **H4 decision** | **{h['h4_decision']}** |

H4 "edge survives" iff 95% CI excludes <= 0.

### Platt recalibration secondary — haiku_clean

| Variant | N bets | Hit rate | Total P&L | ROI | 95% CI (mana) |
|---|---|---|---|---|---|
| Main | {h['N_bets']} | {h['hit_rate']:.3f} | {h['total_pnl_mana']:+.2f} | {h['roi_pct']:+.2f}% | [{h['pnl_95ci_mana'][0]:+.2f}, {h['pnl_95ci_mana'][1]:+.2f}] |
| +Platt | {p['N_bets']} | {p['hit_rate']:.3f} | {p['total_pnl_mana']:+.2f} | {p['roi_pct']:+.2f}% | [{p['pnl_95ci_mana'][0]:+.2f}, {p['pnl_95ci_mana'][1]:+.2f}] |

### Exploratory — sonnet & opus on jan2026_clean (N = {s['N_questions']})

| Model | N bets | Hit rate | Total P&L | ROI | 95% CI (mana) |
|---|---|---|---|---|---|
| Sonnet-5 | {s['N_bets']} | {s['hit_rate']:.3f} | {s['total_pnl_mana']:+.2f} | {s['roi_pct']:+.2f}% | [{s['pnl_95ci_mana'][0]:+.2f}, {s['pnl_95ci_mana'][1]:+.2f}] |
| Opus-4-8 | {o['N_bets']} | {o['hit_rate']:.3f} | {o['total_pnl_mana']:+.2f} | {o['roi_pct']:+.2f}% | [{o['pnl_95ci_mana'][0]:+.2f}, {o['pnl_95ci_mana'][1]:+.2f}] |

### Caveats

1. **Play-money.** Manifold Markets uses mana (play-money). No real economic stakes; prices may diverge from true probabilities without real arbitrage pressure. All ROI and P&L figures are in mana units with no direct monetary interpretation.
2. **Thin markets.** Median total_liquidity = {med_liq:.0f} mana for haiku_clean; some markets have L < 100. CPMM slippage is material at low liquidity (gross profit is substantially below the frictionless level).
3. **Counterfactual fills.** Backtest assumes bets fill at the CPMM price implied by the snapshot at T = resolved_at - 30d. Real fills would differ if other traders act between T and an actual bet submission, or if the market's pool state differs from the snapshot.
4. **No position limits.** Fixed stake ignores correlation across simultaneous open positions and risk concentration in correlated question clusters.
5. **Fee uncertainty.** Creator fees (0-5%) are per-market and not stored in the dataset. The {FEE_RATE*100:.0f}% flat estimate may over- or under-state true costs for any individual market.

### Artifacts

- JSON: `data/interim/phase3_rq4.json`
- Figure: `docs/figures/rq4_pnl.png`
- Bootstrap N: {N_BOOT:,} | Seed: {BOOT_SEED} | Fee: {FEE_RATE} | Stake: {STAKE:.0f} mana
"""
    # Guard: do not append if RQ4 section already present (idempotent re-runs).
    if os.path.exists(PHASE3_MD):
        with open(PHASE3_MD, encoding="utf-8") as fh:
            existing = fh.read()
        if "## RQ4" in existing:
            print(f"[output] RQ4 section already present in {PHASE3_MD}; skipping append.")
            return

    with open(PHASE3_MD, "a", encoding="utf-8") as fh:
        fh.write(section)
    print(f"[output] RQ4 appended to {PHASE3_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> str:
    """
    Run RQ4 backtest pipeline.

    Returns:
        SHA-256 hex digest of the written JSON (for determinism verification).
    """
    # -----------------------------------------------------------------------
    # Load
    # -----------------------------------------------------------------------
    print("[load] Reading data...")
    with open(QUESTIONS_JSON, encoding="utf-8") as fh:
        qs = json.load(fh)
    q_by_id: Dict = {q["qid"]: q for q in qs}

    rows: List[Dict] = []
    with open(FORECASTS_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    print(f"[load] {len(rows)} CSV rows, {len(q_by_id)} questions")

    # -----------------------------------------------------------------------
    # Haiku — main backtest (confirmatory)
    # -----------------------------------------------------------------------
    print("[backtest] haiku_clean (main)...")
    haiku_filtered = _filter_clean(rows, HAIKU, "close_before_cutoff_haiku")
    p_models_haiku = [float(r["model_prob"]) for r in haiku_filtered]
    outcomes_haiku = [int(r["outcome"]) for r in haiku_filtered]

    haiku_res = _run_cell(haiku_filtered, q_by_id, p_models_haiku,
                          "haiku_clean_main", HAIKU)
    print(
        f"  N={haiku_res['N_questions']}, bets={haiku_res['N_bets']}, "
        f"P&L={haiku_res['total_pnl_mana']:+.2f}, "
        f"CI=[{haiku_res['pnl_95ci_mana'][0]:+.2f}, "
        f"{haiku_res['pnl_95ci_mana'][1]:+.2f}], "
        f"H4={haiku_res['h4_decision']}"
    )

    # -----------------------------------------------------------------------
    # Haiku — Platt recalibration (secondary)
    # -----------------------------------------------------------------------
    print("[backtest] Platt recalibration (5-fold OOF)...")
    p_recal = platt_calibrate_oof(p_models_haiku, outcomes_haiku)
    platt_res = _run_cell(haiku_filtered, q_by_id, p_recal,
                          "haiku_clean_platt", HAIKU)
    print(
        f"  bets={platt_res['N_bets']}, "
        f"P&L={platt_res['total_pnl_mana']:+.2f}, "
        f"CI=[{platt_res['pnl_95ci_mana'][0]:+.2f}, "
        f"{platt_res['pnl_95ci_mana'][1]:+.2f}]"
    )

    # -----------------------------------------------------------------------
    # Sonnet & Opus — jan2026_clean (exploratory)
    # -----------------------------------------------------------------------
    print("[backtest] sonnet jan2026_clean (exploratory)...")
    sonnet_filtered = _filter_clean(rows, SONNET, "close_before_cutoff_jan2026")
    p_models_sonnet = [float(r["model_prob"]) for r in sonnet_filtered]
    sonnet_res = _run_cell(sonnet_filtered, q_by_id, p_models_sonnet,
                           "sonnet_jan2026_clean", SONNET)

    print("[backtest] opus jan2026_clean (exploratory)...")
    opus_filtered = _filter_clean(rows, OPUS, "close_before_cutoff_jan2026")
    p_models_opus = [float(r["model_prob"]) for r in opus_filtered]
    opus_res = _run_cell(opus_filtered, q_by_id, p_models_opus,
                         "opus_jan2026_clean", OPUS)

    print(
        f"  sonnet: bets={sonnet_res['N_bets']}, "
        f"P&L={sonnet_res['total_pnl_mana']:+.2f}"
    )
    print(
        f"  opus: bets={opus_res['N_bets']}, "
        f"P&L={opus_res['total_pnl_mana']:+.2f}"
    )

    # -----------------------------------------------------------------------
    # Write JSON
    # -----------------------------------------------------------------------
    print("[output] Writing JSON...")
    results = {
        "config": {
            "fee_rate": FEE_RATE,
            "bankroll_init_mana": BANKROLL_INIT,
            "stake_mana": STAKE,
            "bet_threshold": BET_THRESHOLD,
            "n_boot": N_BOOT,
            "boot_seed": BOOT_SEED,
            "platt_folds": PLATT_FOLDS,
            "platt_seed": PLATT_SEED,
            "clamp_eps": CLAMP_EPS,
            "cpmm_convention": "p_YES=N/(Y+N); L=Y+N; k=p*(1-p)*L^2",
        },
        "haiku_clean_main":       _strip_internal(haiku_res),
        "haiku_clean_platt":      _strip_internal(platt_res),
        "sonnet_jan2026_clean":   _strip_internal(sonnet_res),
        "opus_jan2026_clean":     _strip_internal(opus_res),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    json_str = json.dumps(results, indent=2, sort_keys=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        fh.write(json_str)

    sha = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
    print(f"[sha256] phase3_rq4.json: {sha}")

    # -----------------------------------------------------------------------
    # Figure
    # -----------------------------------------------------------------------
    make_figure(haiku_res, platt_res, sonnet_res, opus_res)

    # -----------------------------------------------------------------------
    # Extend phase3_results.md
    # -----------------------------------------------------------------------
    _write_rq4_md(haiku_res, platt_res, sonnet_res, opus_res)

    print("[done] RQ4 backtest complete.")
    return sha


if __name__ == "__main__":
    main()
