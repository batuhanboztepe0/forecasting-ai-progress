#!/usr/bin/env python3
"""
reproduce_from_release.py — Verify headline numbers from the public release data.

A third party can clone the repo, install requirements, and run:

    python3.11 src/analysis/reproduce_from_release.py

The script:
  1. Loads data/release/questions.csv + data/release/forecasts.csv.
  2. Rebuilds the interim data files needed by the analysis library in a
     temp directory.
  3. Monkey-patches path constants in rq_confirmatory and rq4_backtest so
     they read from the release data and write to the temp directory.
  4. Runs both analyses (same code, same seeds → bit-identical results).
  5. Compares key numbers against data/release/reference_results.json.
  6. Prints a PASS/FAIL table and exits non-zero on any mismatch.

Args:
    --out-dir DIR   directory for temp outputs (default: temp/reproduce_out)
    --tol FLOAT     absolute tolerance for float comparisons (default: 1e-6)

Hard rules respected:
  - No outcome information was used in model prompts.
  - No raw API payloads are included in the release.
  - Seeds are fixed (D-016); results are bit-identical across runs.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_THIS, "..", ".."))
_RELEASE = os.path.join(_REPO, "data", "release")

# Add analysis dir to path so we can import peer modules
if _THIS not in sys.path:
    sys.path.insert(0, _THIS)

# Also add src/phase2 (scoring imports from there)
_PHASE2 = os.path.join(_REPO, "src", "phase2")
if _PHASE2 not in sys.path:
    sys.path.insert(0, _PHASE2)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_questions(path: str) -> list[dict]:
    """Load data/release/questions.csv into a list of dicts."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_forecasts(path: str) -> list[dict]:
    """Load data/release/forecasts.csv into a list of dicts."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def questions_to_json_format(questions: list[dict]) -> list[dict]:
    """
    Convert questions.csv rows to the JSON format expected by the analysis
    library (nested microstructure dict, typed fields).

    Only the fields actually read by rq_confirmatory and rq4_backtest are
    required: qid, close_at, microstructure.total_liquidity.
    """
    out = []
    for q in questions:
        out.append({
            "qid":       q["qid"],
            "source":    q["source"],
            "title":     q["title"],
            "close_at":  q["close_at"],
            "resolved_at": q["resolved_at"],
            "outcome":   int(q["outcome"]),
            "crowd_prob_at_T": float(q["crowd_prob_at_T"]),
            "stratum":   q["stratum"],
            "microstructure": {
                "total_liquidity": float(q["total_liquidity"]) if q["total_liquidity"] else 0.0,
                "unique_bettors_at_T": int(q["unique_bettors_at_T"]) if q["unique_bettors_at_T"] else 0,
                "volume_mana_at_T": float(q["volume_mana_at_T"]) if q["volume_mana_at_T"] else 0.0,
                "trade_count_at_T": int(q["trade_count_at_T"]) if q["trade_count_at_T"] else 0,
            },
        })
    return out


# ---------------------------------------------------------------------------
# Monkey-patch helpers
# ---------------------------------------------------------------------------

def _patch_module(mod, patches: dict) -> dict:
    """
    Temporarily patch attributes on a module.

    Returns a dict of original values so they can be restored.
    """
    originals = {}
    for attr, val in patches.items():
        originals[attr] = getattr(mod, attr)
        setattr(mod, attr, val)
    return originals


def _restore_module(mod, originals: dict) -> None:
    for attr, val in originals.items():
        setattr(mod, attr, val)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def compare_results(computed: dict, reference: dict, tol: float) -> list[tuple]:
    """
    Compare computed analysis results against reference values.

    Returns a list of (test_name, status, computed_val, ref_val) tuples.
    status is 'PASS' or 'FAIL'.
    """
    rows = []

    def _chk(name: str, got, exp):
        if isinstance(exp, float):
            ok = _near(got, exp, tol)
        elif isinstance(exp, bool):
            ok = (got == exp)
        elif isinstance(exp, str):
            ok = (got == exp)
        else:
            ok = (got == exp)
        rows.append((name, "PASS" if ok else "FAIL", got, exp))

    rq1_ref = reference["rq1"]
    rq2_ref = reference["rq2"]
    rq3_ref = reference["rq3"]
    bh_ref  = reference["bh"]
    rq4_ref = reference["rq4"]

    # RQ1
    rq1 = computed["rq123"]["rq1"]
    crowd_row = next(r for r in rq1 if r["label"] == "crowd" and r["status"] == "confirmatory")
    haiku_row = next(r for r in rq1 if r["label"] == "Haiku" and r["status"] == "confirmatory")
    _chk("RQ1 crowd CITL",      crowd_row["citl"],          rq1_ref["crowd_citl"])
    _chk("RQ1 crowd CITL lo",   crowd_row["citl_lo"],       rq1_ref["crowd_citl_lo"])
    _chk("RQ1 crowd CITL hi",   crowd_row["citl_hi"],       rq1_ref["crowd_citl_hi"])
    _chk("RQ1 crowd p",         crowd_row["citl_p"],        rq1_ref["crowd_citl_p"])
    _chk("RQ1 crowd decision",  crowd_row["h1_decision"],   rq1_ref["crowd_decision"])
    _chk("RQ1 haiku CITL",      haiku_row["citl"],          rq1_ref["haiku_citl"])
    _chk("RQ1 haiku CITL lo",   haiku_row["citl_lo"],       rq1_ref["haiku_citl_lo"])
    _chk("RQ1 haiku CITL hi",   haiku_row["citl_hi"],       rq1_ref["haiku_citl_hi"])
    _chk("RQ1 haiku p",         haiku_row["citl_p"],        rq1_ref["haiku_citl_p"])
    _chk("RQ1 haiku decision",  haiku_row["h1_decision"],   rq1_ref["haiku_decision"])

    # RQ2
    rq2 = computed["rq123"]["rq2"]
    h_rq2 = next(r for r in rq2 if r["label"] == "Haiku" and r["status"] == "confirmatory")
    _chk("RQ2 haiku ΔBSS",       h_rq2["delta_bss"],  rq2_ref["haiku_delta_bss"])
    _chk("RQ2 haiku ΔBSS lo",    h_rq2["delta_lo"],   rq2_ref["haiku_delta_lo"])
    _chk("RQ2 haiku ΔBSS hi",    h_rq2["delta_hi"],   rq2_ref["haiku_delta_hi"])
    _chk("RQ2 haiku p",          h_rq2["delta_p"],    rq2_ref["haiku_delta_p"])

    # RQ3
    rq3 = computed["rq123"]["rq3"]
    h_rq3 = next(r for r in rq3 if r["status"] == "confirmatory")
    _chk("RQ3 haiku b_crowd",   h_rq3["b_crowd"],       rq3_ref["haiku_b_crowd"])
    _chk("RQ3 haiku b_model",   h_rq3["b_model"],       rq3_ref["haiku_b_model"])
    _chk("RQ3 haiku p_crowd",   h_rq3["p_crowd_wald"],  rq3_ref["haiku_p_crowd"])
    _chk("RQ3 haiku p_model",   h_rq3["p_model_wald"],  rq3_ref["haiku_p_model"])

    # BH family
    bh_computed = computed["rq123"]["bh_correction"]
    for test_name, exp_rej in bh_ref.items():
        got_rej = bh_computed[test_name]["bh_rejected"]
        _chk(f"BH {test_name} rejected", got_rej, exp_rej)

    # RQ4
    rq4c = computed["rq4"]
    _chk("RQ4 haiku_main P&L",      rq4c["haiku_clean_main"]["total_pnl_mana"],      rq4_ref["haiku_clean_main_pnl"])
    _chk("RQ4 haiku_main CI lo",    rq4c["haiku_clean_main"]["pnl_95ci_mana"][0],    rq4_ref["haiku_clean_main_ci_lo"])
    _chk("RQ4 haiku_main CI hi",    rq4c["haiku_clean_main"]["pnl_95ci_mana"][1],    rq4_ref["haiku_clean_main_ci_hi"])
    _chk("RQ4 haiku_main decision", rq4c["haiku_clean_main"]["h4_decision"],          rq4_ref["haiku_clean_main_decision"])
    _chk("RQ4 haiku_platt P&L",     rq4c["haiku_clean_platt"]["total_pnl_mana"],     rq4_ref["haiku_clean_platt_pnl"])

    return rows


def print_table(rows: list[tuple]) -> int:
    """Print PASS/FAIL table. Returns number of failures."""
    n_fail = sum(1 for _, s, _, _ in rows if s == "FAIL")
    n_pass = sum(1 for _, s, _, _ in rows if s == "PASS")

    col_w = max(len(r[0]) for r in rows) + 2
    print("\n" + "=" * 70)
    print(f"{'Test':<{col_w}} {'Status':<6}  {'Computed':>20}  {'Reference':>20}")
    print("-" * 70)
    for name, status, got, exp in rows:
        g_str = f"{got:.8f}" if isinstance(got, float) else str(got)
        e_str = f"{exp:.8f}" if isinstance(exp, float) else str(exp)
        flag = "  <-- MISMATCH" if status == "FAIL" else ""
        print(f"{name:<{col_w}} {status:<6}  {g_str:>20}  {e_str:>20}{flag}")
    print("-" * 70)
    print(f"TOTAL: {n_pass} PASS / {n_fail} FAIL")
    print("=" * 70)
    return n_fail


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce release headline numbers.")
    parser.add_argument("--out-dir", default=os.path.join(_REPO, "temp", "reproduce_out"),
                        help="Directory for temporary analysis outputs.")
    parser.add_argument("--tol", type=float, default=1e-6,
                        help="Absolute float comparison tolerance.")
    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("reproduce_from_release.py")
    print(f"  release dir: {_RELEASE}")
    print(f"  output dir:  {out_dir}")
    print(f"  tolerance:   {args.tol}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load release CSVs
    # ------------------------------------------------------------------
    print("\n[1] Loading release data...")
    q_path = os.path.join(_RELEASE, "questions.csv")
    f_path = os.path.join(_RELEASE, "forecasts.csv")
    questions = load_questions(q_path)
    forecasts = load_forecasts(f_path)
    print(f"  {len(questions)} questions, {len(forecasts)} forecast rows")

    # ------------------------------------------------------------------
    # 2. Write temp questions JSON (analysis library expects JSON format)
    # ------------------------------------------------------------------
    print("\n[2] Converting questions.csv → temp questions JSON...")
    q_json = questions_to_json_format(questions)
    tmp_q_path = os.path.join(out_dir, "phase2_questions_from_release.json")
    with open(tmp_q_path, "w", encoding="utf-8") as fh:
        json.dump(q_json, fh, indent=2)
    print(f"  Written: {tmp_q_path}")

    # Write a temp forecasts CSV (same content, but stored in out_dir for
    # provenance; the release CSV is read directly)
    tmp_f_path = f_path   # read directly from release

    # ------------------------------------------------------------------
    # 3. Import and monkey-patch analysis modules
    # ------------------------------------------------------------------
    print("\n[3] Importing analysis library (rq_confirmatory, rq4_backtest)...")
    import rq_confirmatory  # noqa: E402
    import rq4_backtest     # noqa: E402

    rq123_out  = os.path.join(out_dir, "phase3_rq123.json")
    rq4_out    = os.path.join(out_dir, "phase3_rq4.json")
    md_out     = os.path.join(out_dir, "phase3_results.md")
    fig123_out = os.path.join(out_dir, "rq3_coef_forest.png")
    fig4_out   = os.path.join(out_dir, "rq4_pnl.png")

    patches_123 = {
        "FORECASTS_CSV":  tmp_f_path,
        "QUESTIONS_JSON": tmp_q_path,
        "OUT_JSON":       rq123_out,
        "MD_PATH":        md_out,
        "FIG_PATH":       fig123_out,
    }
    patches_rq4 = {
        "FORECASTS_CSV":  tmp_f_path,
        "QUESTIONS_JSON": tmp_q_path,
        "OUT_JSON":       rq4_out,
        "OUT_FIG":        fig4_out,
        "PHASE3_MD":      md_out,
    }

    orig_123 = _patch_module(rq_confirmatory, patches_123)
    orig_rq4 = _patch_module(rq4_backtest,    patches_rq4)

    # ------------------------------------------------------------------
    # 4. Run RQ1–RQ3
    # ------------------------------------------------------------------
    print("\n[4] Running RQ1–RQ3 confirmatory analysis...")
    try:
        rq_confirmatory.main()
    finally:
        _restore_module(rq_confirmatory, orig_123)

    with open(rq123_out, encoding="utf-8") as fh:
        rq123_computed = json.load(fh)
    print(f"  RQ1-3 output: {rq123_out}")

    # ------------------------------------------------------------------
    # 5. Run RQ4 backtest
    # ------------------------------------------------------------------
    print("\n[5] Running RQ4 backtest...")
    try:
        rq4_backtest.main()
    finally:
        _restore_module(rq4_backtest, orig_rq4)

    with open(rq4_out, encoding="utf-8") as fh:
        rq4_computed = json.load(fh)
    print(f"  RQ4 output:   {rq4_out}")

    # ------------------------------------------------------------------
    # 6. Compare against reference
    # ------------------------------------------------------------------
    print("\n[6] Comparing against reference_results.json...")
    ref_path = os.path.join(_RELEASE, "reference_results.json")
    with open(ref_path, encoding="utf-8") as fh:
        reference = json.load(fh)

    computed = {"rq123": rq123_computed, "rq4": rq4_computed}
    result_rows = compare_results(computed, reference, tol=args.tol)
    n_fail = print_table(result_rows)

    if n_fail > 0:
        print(f"\nREPRODUCTION FAILED: {n_fail} mismatches found.")
        sys.exit(1)
    else:
        print("\nREPRODUCTION PASSED: all headline numbers match within tolerance.")
        sys.exit(0)


if __name__ == "__main__":
    main()
