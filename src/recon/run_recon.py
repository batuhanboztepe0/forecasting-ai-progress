"""
run_recon.py — Phase-0 reconnaissance entrypoint.

Usage:
    python3 src/recon/run_recon.py [--offline]

Flags:
    --offline   Skip API calls; load from existing data/raw/recon/*.json files.
                Use this after the first full run to re-run analysis without API calls.

Steps:
    1. Fetch Metaculus resolved binary AI-progress questions.
    2. Fetch Manifold resolved binary AI-progress markets.
    3. Save combined normalised list to data/interim/questions_combined.json.
    4. Run analyses (distribution, clean-N, liquidity, classifier precision).
    5. Run power sketch simulation.
    6. Write committed manifest to data/recon_manifest.json.
    7. Generate docs/recon_report.md.
    8. Append a row to docs/EXPERIMENTS.md.
"""

import json
import os
import sys
import hashlib
import random
from datetime import datetime, timezone

# Ensure src/recon is on the path when called from repo root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config import (
    INTERIM_DIR,
    MANIFEST_PATH,
    REPORT_PATH,
    EXPERIMENTS_PATH,
    RAW_DIR,
    RANDOM_SEED,
    MANIFOLD_AI_GROUP_SLUGS,
)
from fetch_metaculus import fetch_metaculus_questions
from fetch_manifold import fetch_manifold_questions
from analyze_recon import (
    resolution_distribution,
    clean_n_per_cutoff,
    manifold_liquidity_stats_v2,
    classifier_precision_sample,
    save_interim,
)
from power_sketch import run_power_grid
from report_generator import generate_report, write_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_existing_raw() -> tuple[list[dict], list[dict]]:
    """
    Load previously fetched questions from data/interim/questions_combined.json.
    Falls back to empty lists if not found.
    """
    path = os.path.join(INTERIM_DIR, "questions_combined.json")
    if not os.path.exists(path):
        print(f"  [OFFLINE] No existing file found at {path}. Returning empty lists.", flush=True)
        return [], []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    meta_q = [q for q in data if q.get("source") == "metaculus"]
    manifold_q = [q for q in data if q.get("source") == "manifold"]
    print(f"  [OFFLINE] Loaded {len(meta_q)} Metaculus + {len(manifold_q)} Manifold questions.", flush=True)
    return meta_q, manifold_q


def _append_experiments_row(run_id: str, timestamp: str, n_total: int) -> None:
    """
    Append a run row to docs/EXPERIMENTS.md (idempotent — skips if run_id already present).
    Keeps the running total correct (always USD 0.00 for this run).
    """
    if not os.path.exists(EXPERIMENTS_PATH):
        print(f"  [WARN] {EXPERIMENTS_PATH} not found; skipping EXPERIMENTS.md update.", flush=True)
        return

    with open(EXPERIMENTS_PATH, encoding="utf-8") as fh:
        content = fh.read()

    # Idempotency check: skip if this run_id is already recorded
    if f"| {run_id} |" in content and "_example_" not in f"| {run_id} |":
        print(f"  EXPERIMENTS.md: run {run_id} already recorded, skipping.", flush=True)
        return

    # Build the new row for the run registry
    config_ref = "src/recon/config.py@HEAD"
    new_run_row = (
        f"| {run_id} | {timestamp[:10]} | 0 | data-pull+simulation | "
        f"{config_ref} | {RANDOM_SEED} | none (no API keys) | {n_total} | "
        f"data/interim/questions_combined.json | "
        f"Phase-0 recon: {n_total} AI-progress questions (Manifold only; Metaculus blocked — auth required); "
        f"no LLM calls; pilot elicitation deferred until API keys present |"
    )

    # Build the new cost ledger row
    new_cost_row = f"| {run_id} | none | 0 | 0 | no | no | 0.00 | 0.00 |"

    # Insert run row before the _example_ row in the run registry
    run_registry_marker = "| _example_ |"
    if run_registry_marker in content:
        content = content.replace(
            run_registry_marker,
            new_run_row + "\n" + run_registry_marker,
            1,  # replace only the first occurrence
        )
    else:
        content += f"\n{new_run_row}\n"

    # Insert cost row before the _example_ cost ledger row
    cost_marker = "| _example_ | claude-sonnet"
    if cost_marker in content:
        content = content.replace(
            cost_marker,
            new_cost_row + "\n" + cost_marker,
            1,
        )

    with open(EXPERIMENTS_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"  EXPERIMENTS.md updated with run {run_id}.", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    offline = "--offline" in sys.argv
    run_timestamp = datetime.now(timezone.utc).isoformat()
    run_id = f"recon-{run_timestamp[:10]}"

    print("=" * 70, flush=True)
    print("Phase-0 Reconnaissance", flush=True)
    print(f"  Run ID:     {run_id}", flush=True)
    print(f"  Timestamp:  {run_timestamp}", flush=True)
    print(f"  Mode:       {'OFFLINE (loading existing data)' if offline else 'LIVE (API calls)'}", flush=True)
    print("=" * 70, flush=True)

    all_manifest: list[dict] = []
    meta_dropped: list[dict] = []
    manifold_dropped: list[dict] = []
    manifold_found_groups: list[str] = []
    api_notes: list[str] = []

    if offline:
        meta_questions, manifold_questions = _load_existing_raw()
        meta_manifest: list[dict] = []
        manifold_manifest: list[dict] = []
        # Load context from the live manifest (do not overwrite it with empty data)
        if os.path.exists(MANIFEST_PATH):
            with open(MANIFEST_PATH, encoding="utf-8") as _fh:
                _sm = json.load(_fh)
            meta_dropped = _sm.get("_dropped_meta", [])
            manifold_dropped = _sm.get("_dropped_manifold", [])
            manifold_found_groups = _sm.get("manifold_found_groups", [])
            api_notes = _sm.get("api_notes", [])
        else:
            meta_dropped = []
            manifold_dropped = []
    else:
        # ---- Metaculus ----
        print("\n[1/5] Fetching Metaculus questions...", flush=True)
        try:
            meta_questions, meta_dropped, meta_manifest = fetch_metaculus_questions(verbose=True)
            api_notes.append(
                f"Metaculus: used /api2/questions/ endpoint (deprecated /api2/ may be available; "
                f"tested and working as of {run_timestamp[:10]}). "
                f"Filter: type=forecast, status=resolved, resolution=yes,no."
            )
        except Exception as exc:
            print(f"  [ERROR] Metaculus fetch failed: {exc}", flush=True)
            meta_questions = []
            meta_manifest = []
            api_notes.append(f"Metaculus fetch FAILED: {exc}")

        # ---- Manifold ----
        print("\n[2/5] Fetching Manifold questions...", flush=True)
        try:
            manifold_questions, manifold_dropped, manifold_manifest = fetch_manifold_questions(verbose=True)
            # Extract which groups were found
            for entry in manifold_manifest:
                if entry.get("type") == "group_lookup" and entry.get("group_id"):
                    manifold_found_groups.append(entry.get("slug", ""))
            api_notes.append(
                f"Manifold: used /v0/group/{{slug}} + /v0/markets?groupId=... endpoints. "
                f"Groups tried: {len(MANIFOLD_AI_GROUP_SLUGS)}; resolved: {len(manifold_found_groups)}."
            )
        except Exception as exc:
            print(f"  [ERROR] Manifold fetch failed: {exc}", flush=True)
            manifold_questions = []
            manifold_manifest = []
            api_notes.append(f"Manifold fetch FAILED: {exc}")

        all_manifest = meta_manifest + manifold_manifest

    # ---- Save combined questions ----
    print("\n[3/5] Saving combined questions and running analyses...", flush=True)
    combined = meta_questions + manifold_questions
    combined_path = save_interim(combined, "questions_combined.json")
    print(f"  Combined questions saved: {combined_path}", flush=True)

    # ---- Analyses ----
    dist = resolution_distribution(combined)
    cutoff_rows = clean_n_per_cutoff(combined)
    liquidity = manifold_liquidity_stats_v2(combined)
    precision = classifier_precision_sample(combined, n_sample=30, seed=RANDOM_SEED)

    save_interim(dist, "resolution_distribution.json")
    save_interim(cutoff_rows, "clean_n_per_cutoff.json")
    save_interim(liquidity, "manifold_liquidity.json")
    save_interim(precision, "classifier_precision.json")

    # ---- Power sketch ----
    print("\n[4/5] Running power sketch simulation...", flush=True)
    # Pass actual observed clean N values for extra rows in the power grid
    extra_ns = list(set(
        row["snap_feasible_combined"]
        for row in cutoff_rows
        if row["snap_feasible_combined"] > 0
    ))
    power = run_power_grid(extra_n_values=extra_ns, verbose=True)
    save_interim(power, "power_sketch.json")

    # ---- Manifest ----
    print("\n[5/5] Writing manifest and report...", flush=True)
    if not offline:
        manifest = {
            "run_id": run_id,
            "run_timestamp_utc": run_timestamp,
            "mode": "live",
            "random_seed": RANDOM_SEED,
            "n_metaculus": len(meta_questions),
            "n_manifold": len(manifold_questions),
            "n_combined": len(combined),
            "api_notes": api_notes,
            "manifold_found_groups": manifold_found_groups,
            # Store dropped lists so offline re-runs can recover them
            "_dropped_meta": meta_dropped,
            "_dropped_manifold": manifold_dropped,
            "_dropped_manifold_ambiguous_count": sum(
                1 for d in manifold_dropped if "resolution" in d.get("reason", "")
            ),
            "entries": all_manifest,
        }
        os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
        with open(MANIFEST_PATH, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, ensure_ascii=False, indent=2)
        print(f"  Manifest written: {MANIFEST_PATH}", flush=True)
    else:
        print(f"  [OFFLINE] Manifest preserved (not overwritten): {MANIFEST_PATH}", flush=True)

    # ---- Report ----
    meta_dropped_ambiguous = sum(1 for d in meta_dropped if d.get("reason") == "ambiguous_resolution")
    # manifold_dropped may be a list of individual records OR a single summary record with a 'count' key
    manifold_dropped_ambiguous = sum(
        d.get("count", 1)
        for d in manifold_dropped
        if "resolution" in d.get("reason", "") or "ambiguous" in d.get("reason", "")
    )
    # Also check the manifest's dedicated counter if present
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, encoding="utf-8") as _mf:
            _mdata = json.load(_mf)
        _mf_amb = _mdata.get("_dropped_manifold_ambiguous_count")
        if _mf_amb is not None and manifold_dropped_ambiguous == 0:
            manifold_dropped_ambiguous = _mf_amb

    # Derive meta group note
    meta_group_note = (
        "Note: Metaculus /api2/questions/ does not expose a stable tag-filter parameter in the "
        "v2 API response; keyword filter applied on returned titles. Category-based pre-filter "
        "not available in this endpoint version — keyword recall may include some false positives."
    )

    report_text = generate_report(
        meta_total=len(meta_questions),
        manifold_total=len(manifold_questions),
        meta_dropped_ambiguous=meta_dropped_ambiguous,
        manifold_dropped_ambiguous=manifold_dropped_ambiguous,
        dist=dist,
        cutoff_rows=cutoff_rows,
        liquidity=liquidity,
        precision=precision,
        power=power,
        run_timestamp=run_timestamp,
        meta_group_note=meta_group_note,
        manifold_found_groups=manifold_found_groups,
        api_notes=api_notes,
    )
    write_report(report_text)

    # ---- EXPERIMENTS.md ----
    _append_experiments_row(run_id, run_timestamp, len(combined))

    # ---- Summary ----
    print("\n" + "=" * 70, flush=True)
    print("RECON COMPLETE", flush=True)
    print(f"  Metaculus AI-progress binary: {len(meta_questions)}", flush=True)
    print(f"  Manifold  AI-progress binary: {len(manifold_questions)}", flush=True)
    print(f"  Combined:                     {len(combined)}", flush=True)
    print(f"  Report:   {REPORT_PATH}", flush=True)
    print(f"  Manifest: {MANIFEST_PATH}", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
