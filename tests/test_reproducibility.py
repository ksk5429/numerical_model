"""
Reproducibility snapshot harness (Phase 6 / Task 6.1).

Independent reproduction proof: pins a small set of canonical Op^3
outputs (PISA stiffness, calibrated example frequencies, mode shapes,
SoilDyn export hash) into a committed JSON snapshot, and re-runs the
pipeline to verify byte-identical reproduction.

If a future commit changes any of these values, the snapshot test
fails and the maintainer must either:
  (a) confirm the change is intentional and bump the snapshot, or
  (b) revert the change.

The snapshot doubles as a clean-room reproducibility certificate:
anyone who clones the repo, installs the dependencies, and runs

    python tests/test_reproducibility.py

should see all checks PASS without modification. If they don't, the
environment differs from the reference (BLAS, numpy version,
OpenSeesPy build) in a way that affects numerical output and the
discrepancy must be investigated.

Snapshot file: tests/reproducibility_snapshot.json
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6  # noqa: E402
from op3.openfast_coupling.soildyn_export import write_soildyn_input  # noqa: E402

SNAPSHOT_PATH = REPO_ROOT / "tests/reproducibility_snapshot.json"
TOL_REL = 1e-9


# ---------------------------------------------------------------------------
# Canonical pipeline outputs
# ---------------------------------------------------------------------------

def _canonical_pisa() -> dict:
    profile = [
        SoilState(0.0,  5.0e7, 35.0, "sand"),
        SoilState(15.0, 1.0e8, 35.0, "sand"),
        SoilState(36.0, 1.5e8, 36.0, "sand"),
    ]
    K = pisa_pile_stiffness_6x6(diameter_m=8.0, embed_length_m=30.0,
                                soil_profile=profile)
    return {f"K[{i}][{j}]": float(K[i, j]) for i in range(6) for j in range(6)}


def _canonical_eigen(example_id: str) -> dict:
    from scripts.test_three_analyses import import_build
    mod = import_build(REPO_ROOT / "examples" / example_id)
    freqs = mod.build().eigen(n_modes=3)
    return {f"f{i+1}_hz": float(freqs[i]) for i in range(3)}


def _canonical_soildyn_export() -> dict:
    """Hash the bytes of a deterministic SoilDyn export to lock the
    file format AND the Op^3 numerical pipeline in one check."""
    profile = [
        SoilState(0.0,  5.0e7, 35.0, "sand"),
        SoilState(15.0, 1.0e8, 35.0, "sand"),
        SoilState(36.0, 1.5e8, 36.0, "sand"),
    ]
    K = pisa_pile_stiffness_6x6(diameter_m=8.0, embed_length_m=30.0,
                                soil_profile=profile)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat",
                                     delete=False, encoding="utf-8") as f:
        out = Path(f.name)
    try:
        write_soildyn_input(out, K, location_xyz=(0, 0, -30),
                            provenance="reproducibility_snapshot")
        h = hashlib.sha256(out.read_bytes()).hexdigest()
    finally:
        out.unlink()
    return {"soildyn_sha256": h, "size_bytes": int(K.shape[0] * K.shape[1])}


def collect_canonical() -> dict:
    return {
        "pisa_8m_30m_3layer": _canonical_pisa(),
        "soildyn_export": _canonical_soildyn_export(),
        "eigen_01_nrel_5mw_baseline": _canonical_eigen("01_nrel_5mw_baseline"),
        "eigen_02_nrel_5mw_oc3_monopile": _canonical_eigen("02_nrel_5mw_oc3_monopile"),
        "eigen_04_ref_site_a_tripod": _canonical_eigen("04_ref_site_a_tripod"),
        "eigen_07_iea_15mw_monopile": _canonical_eigen("07_iea_15mw_monopile"),
    }


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------

def _close(a: float, b: float) -> bool:
    if a == 0 and b == 0:
        return True
    denom = max(abs(a), abs(b), 1e-30)
    return abs(a - b) / denom < TOL_REL


def compare(snapshot: dict, current: dict, prefix: str = "") -> list[str]:
    diffs: list[str] = []
    for k, v in current.items():
        path = f"{prefix}{k}"
        if k not in snapshot:
            diffs.append(f"{path}: NEW")
            continue
        ref = snapshot[k]
        if isinstance(v, dict):
            diffs.extend(compare(ref, v, path + "."))
        elif isinstance(v, str):
            if v != ref:
                diffs.append(f"{path}: '{v}' != '{ref}'")
        else:
            if not _close(float(v), float(ref)):
                diffs.append(f"{path}: {v} != {ref}")
    for k in snapshot:
        if k not in current:
            diffs.append(f"{prefix}{k}: REMOVED")
    return diffs


def main():
    print()
    print("=" * 78)
    print(" Op3 reproducibility snapshot test -- Phase 6 / Task 6.1")
    print("=" * 78)

    current = collect_canonical()

    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2),
                                  encoding="utf-8")
        print(f"  Snapshot did not exist; wrote initial reference to:")
        print(f"  {SNAPSHOT_PATH}")
        print("  Re-run this script to verify reproduction.")
        return 0

    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    diffs = compare(snapshot, current)

    sections = sorted(current.keys())
    for s in sections:
        section_diffs = [d for d in diffs if d.startswith(s)]
        marker = "[OK]" if not section_diffs else "[XX]"
        print(f"  {marker} {s}  ({len(section_diffs)} diffs)")
        for d in section_diffs[:3]:
            print(f"        {d}")

    print("=" * 78)
    if not diffs:
        print(f" REPRODUCIBLE  --  {len(current)} canonical outputs all match snapshot")
        print("=" * 78)
        return 0
    print(f" {len(diffs)} differences found  --  reproduction has drifted")
    print("=" * 78)
    return 1


if __name__ == "__main__":
    sys.exit(main())
