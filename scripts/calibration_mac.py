"""
Mode shape MAC comparison (Phase 1 / Task 1.5).

For each example with an ElastoDyn deck, compare the Op^3 first
fore-aft tower bending mode shape against the NREL polynomial mode
shape (TwFAM1Sh coefficients) using the Modal Assurance Criterion:

    MAC(a,b) = |a^T b|^2 / ((a^T a)(b^T b))

MAC = 1.0 means the shapes are identical (up to scaling). MAC > 0.95
is the conventional threshold for "well-correlated" modes in
structural dynamics.

Usage
-----
    python scripts/calibration_mac.py
    python scripts/calibration_mac.py 02_nrel_5mw_oc3_monopile

Output: validation/benchmarks/calibration_mac.json + printed table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.opensees_foundations import builder as B  # noqa: E402
from op3.opensees_foundations.tower_loader import (  # noqa: E402
    evaluate_mode_shape,
    load_elastodyn_tower,
    published_mode_shape,
)


def _mac(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    num = float(np.dot(a, b)) ** 2
    den = float(np.dot(a, a) * np.dot(b, b))
    return num / den if den > 0 else 0.0


def op3_first_mode_x(example_id: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Build the example, run eigenvalue, and return (z_array, psi_x_array)
    for the first mode along the tower stick. Reads the OpenSeesPy
    nodeEigenvector for DOF 1 (x = fore-aft) at every tower node.
    """
    import openseespy.opensees as ops
    from scripts.test_three_analyses import import_build

    mod = import_build(REPO_ROOT / "examples" / example_id)
    model = mod.build()
    model.eigen(n_modes=3)

    # Tower nodes are 1000..1000+n. Walk upward until nodeCoord fails.
    zs: list[float] = []
    psis: list[float] = []
    base = 1000
    for i in range(0, 100):
        tag = base + i
        try:
            xyz = ops.nodeCoord(tag)
        except Exception:
            break
        try:
            v = ops.nodeEigenvector(tag, 1, 1)  # mode 1, DOF 1 (x)
        except Exception:
            break
        zs.append(float(xyz[2]))
        psis.append(float(v))
    return np.asarray(zs), np.asarray(psis)


def compute_mac_for(example_id: str, tower_template: str) -> dict:
    ed_main, ed_tower = B._resolve_ed(tower_template)
    if not ed_main:
        return {"example": example_id, "error": "no ElastoDyn deck registered"}

    tpl = load_elastodyn_tower(ed_main, ed_tower=ed_tower)
    twr_text = Path(tpl.source_files[-1]).read_text(errors="replace")
    coeffs = published_mode_shape(twr_text, "TwFAM1Sh")
    if coeffs is None:
        return {"example": example_id,
                "error": "TwFAM1Sh coefficients not found"}

    zs, psi_op3 = op3_first_mode_x(example_id)
    if zs.size < 3:
        return {"example": example_id, "error": "insufficient mode-shape data"}

    # Map z to eta along the tower (base..top of the parsed template)
    z_base = tpl.tower_base_z_m
    z_top = z_base + tpl.tower_height_m
    eta = (zs - z_base) / (z_top - z_base)
    mask = (eta >= -0.01) & (eta <= 1.01)
    eta = np.clip(eta[mask], 0.0, 1.0)
    psi_op3 = psi_op3[mask]

    psi_nrel = evaluate_mode_shape(coeffs, eta)

    # Normalize each shape so the tip displacement = +1 (sign convention)
    if abs(psi_op3[-1]) > 1e-12:
        psi_op3 = psi_op3 / psi_op3[-1]
    if abs(psi_nrel[-1]) > 1e-12:
        psi_nrel = psi_nrel / psi_nrel[-1]

    mac = _mac(psi_op3, psi_nrel)
    rmse = float(np.sqrt(np.mean((psi_op3 - psi_nrel) ** 2)))
    return {
        "example": example_id,
        "tower_template": tower_template,
        "n_points": int(eta.size),
        "MAC": mac,
        "RMSE_normalized": rmse,
        "coeffs_TwFAM1Sh": coeffs.tolist(),
        "eta": eta.tolist(),
        "psi_op3": psi_op3.tolist(),
        "psi_nrel": psi_nrel.tolist(),
    }


# Map example -> tower template name
EXAMPLES = {
    "01_nrel_5mw_baseline":     "nrel_5mw_tower",
    "02_nrel_5mw_oc3_monopile": "nrel_5mw_oc3_tower",
    "07_iea_15mw_monopile":     "iea_15mw_tower",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("examples", nargs="*",
                    help="Example IDs (default: all ED-registered examples)")
    args = ap.parse_args()

    targets = args.examples or list(EXAMPLES.keys())
    results = []
    print()
    print(f"  {'example':<32} {'MAC':>8} {'RMSE':>8}  status")
    print("  " + "-" * 60)
    for ex in targets:
        tower = EXAMPLES.get(ex)
        if tower is None:
            print(f"  {ex:<32} -- not registered --")
            continue
        r = compute_mac_for(ex, tower)
        results.append(r)
        if "error" in r:
            print(f"  {ex:<32} ERROR: {r['error']}")
            continue
        flag = "[OK] " if r["MAC"] > 0.95 else "[XX] "
        print(f"  {flag}{ex:<27} {r['MAC']:>8.4f} {r['RMSE_normalized']:>8.4f}")

    out = REPO_ROOT / "validation/benchmarks/calibration_mac.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n  JSON written: {out}\n")


if __name__ == "__main__":
    main()
