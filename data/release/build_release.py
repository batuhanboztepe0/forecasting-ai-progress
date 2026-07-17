#!/usr/bin/env python3
"""
build_release.py — One-shot script to produce data/release/questions.csv
and data/release/forecasts.csv from the interim data.

Run from repo root:
    python3.11 data/release/build_release.py

Writes:
    data/release/questions.csv   (1,187 rows)
    data/release/forecasts.csv   (3,761 rows)
    data/release/reference_results.json
"""

import csv
import json
import os

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_INTERIM = os.path.join(_REPO, "data", "interim")
_OUT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# questions.csv
# ---------------------------------------------------------------------------
def build_questions() -> int:
    with open(os.path.join(_INTERIM, "phase2_questions.json"), encoding="utf-8") as fh:
        questions = json.load(fh)

    out_path = os.path.join(_OUT, "questions.csv")
    fields = [
        "qid", "source", "title", "created_at", "close_at", "resolved_at",
        "outcome", "crowd_prob_at_T",
        "total_liquidity", "unique_bettors_at_T", "volume_mana_at_T", "trade_count_at_T",
        "content_hash", "classifier_verdict", "stratum",
        "close_before_cutoff_haiku", "close_before_cutoff_jan2026", "close_before_T",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for q in questions:
            ms = q.get("microstructure", {})
            row = {
                "qid":                      q["qid"],
                "source":                   q["source"],
                "title":                    q["title"],
                "created_at":               q.get("created_at", ""),
                "close_at":                 q.get("close_at", ""),
                "resolved_at":              q.get("resolved_at", ""),
                "outcome":                  q["outcome"],
                "crowd_prob_at_T":          q["crowd_prob_at_T"],
                "total_liquidity":          ms.get("total_liquidity", ""),
                "unique_bettors_at_T":      ms.get("unique_bettors_at_T", ""),
                "volume_mana_at_T":         ms.get("volume_mana_at_T", ""),
                "trade_count_at_T":         ms.get("trade_count_at_T", ""),
                "content_hash":             q.get("content_hash", ""),
                "classifier_verdict":       "keep",   # all 1187 passed v1.1 filter
                # D-014: haiku_clean requires close_at >= haiku_cutoff (close_before_cutoff_haiku=0)
                "stratum": (
                    "haiku_clean"
                    if q.get("stratum") == "haiku_clean"
                    and not q.get("close_before_cutoff_haiku", False)
                    else "pre_cutoff_probe"
                ),
                "close_before_cutoff_haiku":    int(q.get("close_before_cutoff_haiku", False)),
                "close_before_cutoff_jan2026":  int(q.get("close_before_cutoff_jan2026", False)),
                "close_before_T":               int(q.get("close_before_T", False)),
            }
            w.writerow(row)

    print(f"  questions.csv: {len(questions)} rows → {out_path}")
    return len(questions)


# ---------------------------------------------------------------------------
# forecasts.csv
# ---------------------------------------------------------------------------
def build_forecasts() -> int:
    src = os.path.join(_INTERIM, "phase2_forecasts.csv")
    out_path = os.path.join(_OUT, "forecasts.csv")

    # Fields to include in the release (subset of phase2_forecasts.csv)
    # outcome + crowd_prob_at_T + flags are retained so the runner can
    # reproduce the analysis without needing the questions JSON at all
    # for the simple cases.
    keep = [
        "qid", "model", "protocol", "repeat",
        "model_prob", "elicited_at", "cache_hit", "parse_error",
        "outcome", "crowd_prob_at_T", "resolved_at",
        "is_post_cutoff",
        "close_before_cutoff_haiku", "close_before_cutoff_jan2026", "close_before_T",
    ]

    rows_out = []
    with open(src, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows_out.append({k: row[k] for k in keep})

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keep)
        w.writeheader()
        w.writerows(rows_out)

    print(f"  forecasts.csv: {len(rows_out)} rows → {out_path}")
    return len(rows_out)


# ---------------------------------------------------------------------------
# reference_results.json
# ---------------------------------------------------------------------------
def build_reference() -> None:
    rq123 = json.load(open(os.path.join(_INTERIM, "phase3_rq123.json")))
    rq4   = json.load(open(os.path.join(_INTERIM, "phase3_rq4.json")))

    # Extract confirmatory RQ1 entries
    rq1_crowd = next(r for r in rq123["rq1"] if r["label"] == "crowd" and r["status"] == "confirmatory")
    rq1_haiku = next(r for r in rq123["rq1"] if r["label"] == "Haiku" and r["status"] == "confirmatory")

    # Extract confirmatory RQ2
    rq2_haiku = next(r for r in rq123["rq2"] if r["label"] == "Haiku" and r["status"] == "confirmatory")

    # Extract confirmatory RQ3 (haiku)
    rq3_haiku = next(r for r in rq123["rq3"] if r["status"] == "confirmatory")

    ref = {
        "_description": (
            "Reference values for reproduce_from_release.py. "
            "All generated with seeds fixed per D-016; re-runs must be bit-identical "
            "(tolerance 1e-6 on floats)."
        ),
        "tolerance": 1e-6,
        "rq1": {
            "crowd_citl":     rq1_crowd["citl"],
            "crowd_citl_lo":  rq1_crowd["citl_lo"],
            "crowd_citl_hi":  rq1_crowd["citl_hi"],
            "crowd_citl_p":   rq1_crowd["citl_p"],
            "crowd_decision": rq1_crowd["h1_decision"],
            "haiku_citl":     rq1_haiku["citl"],
            "haiku_citl_lo":  rq1_haiku["citl_lo"],
            "haiku_citl_hi":  rq1_haiku["citl_hi"],
            "haiku_citl_p":   rq1_haiku["citl_p"],
            "haiku_decision": rq1_haiku["h1_decision"],
        },
        "rq2": {
            "haiku_delta_bss":  rq2_haiku["delta_bss"],
            "haiku_delta_lo":   rq2_haiku["delta_lo"],
            "haiku_delta_hi":   rq2_haiku["delta_hi"],
            "haiku_delta_p":    rq2_haiku["delta_p"],
        },
        "rq3": {
            "haiku_b_crowd":     rq3_haiku["b_crowd"],
            "haiku_b_model":     rq3_haiku["b_model"],
            "haiku_p_crowd":     rq3_haiku["p_crowd_wald"],
            "haiku_p_model":     rq3_haiku["p_model_wald"],
        },
        "bh": {k: v["bh_rejected"] for k, v in rq123["bh_correction"].items()},
        "rq4": {
            "haiku_clean_main_pnl":      rq4["haiku_clean_main"]["total_pnl_mana"],
            "haiku_clean_main_ci_lo":    rq4["haiku_clean_main"]["pnl_95ci_mana"][0],
            "haiku_clean_main_ci_hi":    rq4["haiku_clean_main"]["pnl_95ci_mana"][1],
            "haiku_clean_main_decision": rq4["haiku_clean_main"]["h4_decision"],
            "haiku_clean_platt_pnl":     rq4["haiku_clean_platt"]["total_pnl_mana"],
        },
    }

    out_path = os.path.join(_OUT, "reference_results.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(ref, fh, indent=2)
    print(f"  reference_results.json → {out_path}")


if __name__ == "__main__":
    print("Building data/release/ artifacts...")
    n_q = build_questions()
    n_f = build_forecasts()
    build_reference()
    print(f"Done. questions={n_q} forecasts={n_f}")
