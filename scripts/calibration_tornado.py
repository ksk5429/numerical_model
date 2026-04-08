"""
Calibration sensitivity tornado (Phase 1 / Task 1.4).

For each example with a published reference, perturb the dominant
calibration inputs by +/- 10% one at a time and report the resulting
shift in the first tower bending frequency. Output is a tornado-style
ranking that tells the analyst which parameters drive frequency
uncertainty and where measurement effort should focus.

Perturbed inputs (one at a time, +/- 10%):

  - tower mass density (TMassDen, scaled via AdjTwMa equivalent)
  - tower fore-aft stiffness (TwFAStif, via AdjFASt equivalent)
  - hub mass (HubMass)
  - nacelle mass (NacMass)
  - blade mass (per-blade, integrated from BMassDen)
  - nacelle CM vertical offset (Twr2Shft + NacCMzn)
  - nacelle yaw inertia (NacYIner)

Usage
-----
    python scripts/calibration_tornado.py 01_nrel_5mw_baseline
    python scripts/calibration_tornado.py --all
    python scripts/calibration_tornado.py --all --pct 0.20

Output: validation/benchmarks/calibration_tornado_<example>.json plus
a printed ranked table.
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.opensees_foundations import tower_loader as TL  # noqa: E402


PERTURBATIONS = [
    "tower_mass",
    "tower_EI",
    "hub_mass",
    "nac_mass",
    "blade_mass",
    "nac_cm_z",
    "nac_yiner",
]


@contextmanager
def patched_loaders(perturb: str, factor: float):
    """
    Temporarily wrap tower_loader.load_elastodyn_tower and
    load_elastodyn_rna to apply a single multiplicative perturbation.
    """
    orig_tower = TL.load_elastodyn_tower
    orig_rna = TL.load_elastodyn_rna

    def wrapped_tower(*args, **kwargs):
        tpl = orig_tower(*args, **kwargs)
        if perturb == "tower_mass":
            return replace(tpl, mass_density_kg_m=tpl.mass_density_kg_m * factor)
        if perturb == "tower_EI":
            return replace(
                tpl,
                ei_fa_Nm2=tpl.ei_fa_Nm2 * factor,
                ei_ss_Nm2=tpl.ei_ss_Nm2 * factor,
            )
        return tpl

    def wrapped_rna(*args, **kwargs):
        rna = orig_rna(*args, **kwargs)
        if perturb == "hub_mass":
            return replace(rna, hub_mass_kg=rna.hub_mass_kg * factor)
        if perturb == "nac_mass":
            return replace(rna, nac_mass_kg=rna.nac_mass_kg * factor)
        if perturb == "blade_mass":
            return replace(rna, blade_mass_kg=rna.blade_mass_kg * factor)
        if perturb == "nac_cm_z":
            return replace(rna, nac_cm_zn_m=rna.nac_cm_zn_m * factor)
        if perturb == "nac_yiner":
            return replace(rna, nac_yiner_kgm2=rna.nac_yiner_kgm2 * factor)
        return rna

    TL.load_elastodyn_tower = wrapped_tower
    TL.load_elastodyn_rna = wrapped_rna
    try:
        yield
    finally:
        TL.load_elastodyn_tower = orig_tower
        TL.load_elastodyn_rna = orig_rna


def run_eigen(example_id: str) -> float:
    from scripts.test_three_analyses import import_build

    mod = import_build(REPO_ROOT / "examples" / example_id)
    model = mod.build()
    return float(model.eigen(n_modes=3)[0])


def tornado(example_id: str, pct: float) -> dict:
    f0 = run_eigen(example_id)
    rows = []
    for p in PERTURBATIONS:
        with patched_loaders(p, 1.0 + pct):
            f_hi = run_eigen(example_id)
        with patched_loaders(p, 1.0 - pct):
            f_lo = run_eigen(example_id)
        rows.append({
            "parameter": p,
            "f1_baseline_hz": f0,
            "f1_plus_hz": f_hi,
            "f1_minus_hz": f_lo,
            "df_plus_pct": (f_hi - f0) / f0 * 100,
            "df_minus_pct": (f_lo - f0) / f0 * 100,
            "swing_pct": (f_hi - f_lo) / f0 * 100,
        })
    rows.sort(key=lambda r: abs(r["swing_pct"]), reverse=True)
    return {"example": example_id, "f1_baseline_hz": f0,
            "perturbation_pct": pct * 100, "rows": rows}


def print_table(result: dict) -> None:
    print(f"\n  Example: {result['example']}   "
          f"f1 baseline = {result['f1_baseline_hz']:.4f} Hz   "
          f"+/-{result['perturbation_pct']:.0f}% on each input\n")
    print(f"  {'parameter':<14} {'-pct':>10} {'+pct':>10} {'swing':>10}")
    print("  " + "-" * 48)
    for r in result["rows"]:
        print(f"  {r['parameter']:<14} {r['df_minus_pct']:>+9.2f}% "
              f"{r['df_plus_pct']:>+9.2f}% {r['swing_pct']:>+9.2f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("examples", nargs="*",
                    help="Example IDs (default: all calibrated examples)")
    ap.add_argument("--all", action="store_true",
                    help="Run all examples in REFERENCES catalog")
    ap.add_argument("--pct", type=float, default=0.10,
                    help="Perturbation magnitude (default 0.10 = +/-10%%)")
    args = ap.parse_args()

    if args.all or not args.examples:
        from scripts.calibration_regression import REFERENCES
        targets = list(REFERENCES.keys())
    else:
        targets = args.examples

    out_dir = REPO_ROOT / "validation/benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_results = []
    for ex in targets:
        result = tornado(ex, args.pct)
        print_table(result)
        all_results.append(result)
        (out_dir / f"calibration_tornado_{ex}.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8")

    (out_dir / "calibration_tornado_summary.json").write_text(
        json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\n  JSON written under: {out_dir}\n")


if __name__ == "__main__":
    main()
