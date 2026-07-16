"""
fix_manifest.py — D-014 §5 provenance fixes + per-question close_at flags.

Actions (all offline, no API):
  1. Add per-question close_at flags to phase2_questions.json:
       close_before_cutoff_haiku   (close_at < 2025-07-31)
       close_before_cutoff_jan2026 (close_at < 2026-01-31)
       close_before_T              (close_at < T = resolved_at - 30d)
  2. Write phase2_questions.json with indent=2, then SHA-256 the FILE BYTES.
  3. Remove stale v1.0 "strata" block from manifest (strata_v11 is authoritative).
  4. Fix manifest "phase" label (2-step-A → 2).
  5. Update manifest artifact SHA-256 + add per-model clean Ns.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECON = os.path.normpath(os.path.join(_HERE, "..", "recon"))
for _p in [_HERE, _RECON]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from phase2_config import (  # noqa
    PHASE2_QUESTIONS_PATH,
    PHASE2_MANIFEST_PATH,
    SNAPSHOT_LEAD_DAYS,
    HAIKU_CLEAN_MIN_RESOLVED,
    JAN2026_CLEAN_MIN_RESOLVED,
    TRAINING_CUTOFFS,
)

# Per-model cutoff dates (end-of-month, conservative)
_HAIKU_CUTOFF     = "2025-07-31"
_JAN2026_CUTOFF   = "2026-01-31"


def _parse_dt(s: str):
    """Parse ISO date/datetime string to UTC-aware datetime; return None on failure."""
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        return None


def _parse_date(s: str):
    """Parse YYYY-MM-DD string to UTC-aware datetime at midnight."""
    if not s:
        return None
    try:
        return datetime(int(s[:4]), int(s[5:7]), int(s[8:10]), tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def _sha256_file(path: str) -> str:
    """SHA-256 of file bytes as written on disk."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> None:
    print("D-014 manifest fixes + close_at flags", flush=True)

    # ------------------------------------------------------------------ #
    # 1. Load questions; compute close_at flags
    # ------------------------------------------------------------------ #
    with open(PHASE2_QUESTIONS_PATH, encoding="utf-8") as fh:
        records = json.load(fh)
    print(f"  Loaded {len(records)} records", flush=True)

    haiku_cutoff_dt   = _parse_date(_HAIKU_CUTOFF)
    jan2026_cutoff_dt = _parse_date(_JAN2026_CUTOFF)

    n_close_before_haiku   = 0
    n_close_before_jan2026 = 0
    n_close_before_T       = 0

    for r in records:
        close_dt   = _parse_dt(r.get("close_at", ""))
        resolved_dt = _parse_dt(r.get("resolved_at", ""))

        T_dt = (resolved_dt - timedelta(days=SNAPSHOT_LEAD_DAYS)) if resolved_dt else None

        cbch  = bool(close_dt and close_dt < haiku_cutoff_dt)
        cbcj  = bool(close_dt and close_dt < jan2026_cutoff_dt)
        cbt   = bool(close_dt and T_dt and close_dt < T_dt)

        r["close_before_cutoff_haiku"]    = cbch
        r["close_before_cutoff_jan2026"]  = cbcj
        r["close_before_T"]               = cbt

        if cbch:  n_close_before_haiku   += 1
        if cbcj:  n_close_before_jan2026 += 1
        if cbt:   n_close_before_T       += 1

    print(f"  close_before_cutoff_haiku:    {n_close_before_haiku}", flush=True)
    print(f"  close_before_cutoff_jan2026:  {n_close_before_jan2026}", flush=True)
    print(f"  close_before_T:               {n_close_before_T}", flush=True)

    # ------------------------------------------------------------------ #
    # 2. Per-model clean Ns (D-014 §1)
    # ------------------------------------------------------------------ #
    haiku_clean_all = [r for r in records if r["stratum"] == "haiku_clean"]
    jan26_clean_all = [
        r for r in records
        if r["stratum"] == "haiku_clean"
        and (r.get("resolved_at", "") >= JAN2026_CLEAN_MIN_RESOLVED)
    ]

    n_haiku_clean_confirmed = sum(
        1 for r in haiku_clean_all if not r["close_before_cutoff_haiku"]
    )
    n_jan26_clean_confirmed = sum(
        1 for r in jan26_clean_all if not r["close_before_cutoff_jan2026"]
    )
    n_haiku_close_before_T = sum(
        1 for r in haiku_clean_all if r["close_before_T"]
    )

    print(f"\n  Per-model clean Ns (D-014 §1):", flush=True)
    print(f"    haiku_clean total:            {len(haiku_clean_all)}", flush=True)
    print(f"    haiku_clean CONFIRMED          "
          f"(not close_before_cutoff_haiku): {n_haiku_clean_confirmed}", flush=True)
    print(f"    haiku_clean close_before_T:   {n_haiku_close_before_T}", flush=True)
    print(f"    jan2026_clean total:           {len(jan26_clean_all)}", flush=True)
    print(f"    jan2026_clean CONFIRMED        "
          f"(not close_before_cutoff_jan2026): {n_jan26_clean_confirmed}", flush=True)

    # Assert D-014 §2: haiku confirmatory N should be 352
    assert n_haiku_clean_confirmed == 352, (
        f"Expected haiku confirmatory N=352 per D-014, got {n_haiku_clean_confirmed}"
    )
    print(f"\n  [ASSERT PASS] haiku confirmatory N = {n_haiku_clean_confirmed}", flush=True)

    # ------------------------------------------------------------------ #
    # 3. Rewrite phase2_questions.json; SHA-256 file bytes
    # ------------------------------------------------------------------ #
    with open(PHASE2_QUESTIONS_PATH, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)

    file_sha256 = _sha256_file(PHASE2_QUESTIONS_PATH)
    print(f"\n  phase2_questions.json SHA-256 (file bytes): {file_sha256}", flush=True)

    # ------------------------------------------------------------------ #
    # 4. Fix manifest
    # ------------------------------------------------------------------ #
    with open(PHASE2_MANIFEST_PATH, encoding="utf-8") as fh:
        manifest = json.load(fh)

    # Fix phase label
    manifest["phase"] = "2"

    # Remove stale v1.0 strata block
    if "strata" in manifest:
        del manifest["strata"]
        print("  Removed stale v1.0 'strata' block", flush=True)

    # Update artifact SHA-256 (file bytes)
    if "artifacts" not in manifest:
        manifest["artifacts"] = {}
    manifest["artifacts"]["phase2_questions_json"] = {
        "path":                "data/interim/phase2_questions.json",
        "n_records":           len(records),
        "sha256_file_bytes":   file_sha256,
        "classifier_version":  "v1.1",
        "note":                "SHA-256 of file bytes as written (indent=2, utf-8)",
    }

    # Add per-model clean Ns
    manifest["clean_ns_d014"] = {
        "haiku_clean_total":               len(haiku_clean_all),
        "haiku_clean_confirmed_n":         n_haiku_clean_confirmed,
        "haiku_clean_close_before_cutoff": n_close_before_haiku,
        "haiku_clean_close_before_T":      n_haiku_close_before_T,
        "jan2026_clean_total":             len(jan26_clean_all),
        "jan2026_clean_confirmed_n":       n_jan26_clean_confirmed,
        "jan2026_clean_close_before_cutoff": n_close_before_jan2026,
        "rq3_status": {
            "haiku":   "CONFIRMATORY (N=352, power≈99% at ρ̂=0.57)",
            "jan2026": "EXPLORATORY",
        },
        "cutoffs": {
            "haiku":    _HAIKU_CUTOFF,
            "jan2026":  _JAN2026_CUTOFF,
        },
    }

    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()

    with open(PHASE2_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    # Verify hash
    written_sha256 = _sha256_file(PHASE2_QUESTIONS_PATH)
    assert written_sha256 == file_sha256, "Hash mismatch after rewrite!"
    print(f"  [VERIFY] SHA-256 on-disk matches manifest: {written_sha256[:16]}...", flush=True)
    print(f"  Manifest written: {PHASE2_MANIFEST_PATH}", flush=True)

    print("\nFix complete.", flush=True)

    return {
        "n_haiku_clean_confirmed": n_haiku_clean_confirmed,
        "n_jan26_clean_confirmed":  n_jan26_clean_confirmed,
        "n_close_before_haiku":    n_close_before_haiku,
        "n_close_before_jan2026":  n_close_before_jan2026,
        "n_close_before_T":        n_close_before_T,
        "file_sha256":             file_sha256,
    }


if __name__ == "__main__":
    main()
