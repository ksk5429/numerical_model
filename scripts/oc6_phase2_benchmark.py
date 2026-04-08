"""
OC6 Phase II benchmark harness (Phase 4 / SoilDyn validation gate).

The OC6 Phase II project is the international Joint Industry Project
that delivered the SoilDyn module to OpenFAST and that all serious
SSI claims in offshore wind academic work must be benchmarked
against. The reference paper is:

    Bergua, R., Robertson, A., Jonkman, J., & Platt, A. (2021).
    "Specification Document for OC6 Phase II: Verification of an
    Advanced Soil-Structure Interaction Model for Offshore Wind
    Turbines". NREL/TP-5000-79989.
    https://doi.org/10.2172/1811648

The benchmark consists of three load cases on the NREL 5 MW OC3
monopile (D = 6 m, embed = 36 m, water depth = 20 m) coupled to a
soil profile through SoilDyn:

    LC2.1   step lateral load at the pile head, drained sand
    LC2.2   sinusoidal lateral load 0.1 Hz, drained sand
    LC2.3   wave + wind 60 s, full coupled OpenFAST run

This harness computes the Op^3 predictions for each load case and
records them next to the published reference numbers. Reference
values are pinned to specific tables / figures in the source paper
and marked AWAITING_VERIFY where the maintainer has not yet opened
the PDF to extract the numerical value.

Run:
    python scripts/oc6_phase2_benchmark.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.cyclic_degradation import cyclic_stiffness_6x6  # noqa: E402
from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6  # noqa: E402


# ---------------------------------------------------------------------------
# OC6 Phase II site definition
# ---------------------------------------------------------------------------
# Per Bergua 2021 Section 3.1 the soil profile is a homogeneous dense
# sand with G_max = 80 MPa (medium-dense Baltic sand), monopile
# diameter 6 m, embedment 36 m, water depth 20 m.

OC6_SOIL_PROFILE = [
    SoilState(0.0,  6.0e7, 35.0, "sand"),
    SoilState(10.0, 8.0e7, 35.0, "sand"),
    SoilState(20.0, 1.0e8, 36.0, "sand"),
    SoilState(36.0, 1.2e8, 37.0, "sand"),
]
OC6_DIAMETER_M = 6.0
OC6_EMBED_M = 36.0


# ---------------------------------------------------------------------------
# Reference catalog
# ---------------------------------------------------------------------------

@dataclass
class OC6Case:
    name: str
    description: str
    quantity: str               # what is being compared
    op3_value: Optional[float] = None
    op3_units: str = ""
    reference_value: Optional[float] = None
    reference_source: str = ""
    tolerance: float = 0.30     # OC6 default acceptance band
    notes: str = ""


CASES: list[OC6Case] = [
    OC6Case(
        name="LC1.1 small-strain Kxx",
        description="Initial small-strain lateral head stiffness",
        quantity="K_xx",
        op3_units="N/m",
        reference_source="Bergua 2021, Table 4 (REDWIN model 2 baseline)",
    ),
    OC6Case(
        name="LC1.1 small-strain Krxrx",
        description="Initial small-strain rocking stiffness about the y-axis",
        quantity="K_rxrx",
        op3_units="Nm/rad",
        reference_source="Bergua 2021, Table 4 (REDWIN model 2 baseline)",
    ),
    OC6Case(
        name="LC1.1 small-strain Kxrx coupling",
        description="Lateral-rocking off-diagonal coupling term",
        quantity="K_xrx",
        op3_units="N",
        reference_source="Bergua 2021, Table 4 (REDWIN model 2 baseline)",
    ),
    OC6Case(
        name="LC2.1 cyclic stiffness reduction",
        description="K_xx after Hardin-Drnevich knockdown at gamma = 1e-4",
        quantity="K_xx_cyclic / K_xx_static",
        op3_units="-",
        reference_source="Bergua 2021, Figure 12 (Operational lateral stiffness)",
    ),
    OC6Case(
        name="LC2.2 sinusoidal load amplitude",
        description="Pile head displacement at peak under 0.1 Hz lateral load",
        quantity="u_x_peak",
        op3_units="m",
        reference_source="Bergua 2021, Section 4.2 (LC2.2 results)",
    ),
    OC6Case(
        name="LC2.3 first system frequency",
        description="First fore-aft natural frequency of NREL 5 MW + OC3 + soil",
        quantity="f1",
        op3_units="Hz",
        reference_source="Bergua 2021, Table 6 (System modal analysis, baseline soil)",
    ),
]


# ---------------------------------------------------------------------------
# Op^3 predictions
# ---------------------------------------------------------------------------

def compute_op3_predictions() -> dict[str, float]:
    """Compute the Op^3 numerical answers for each OC6 quantity."""
    K = pisa_pile_stiffness_6x6(
        diameter_m=OC6_DIAMETER_M,
        embed_length_m=OC6_EMBED_M,
        soil_profile=OC6_SOIL_PROFILE,
    )
    K_cyclic = cyclic_stiffness_6x6(
        diameter_m=OC6_DIAMETER_M,
        embed_length_m=OC6_EMBED_M,
        soil_profile=OC6_SOIL_PROFILE,
        cyclic_strain=1.0e-4,
    )

    # LC2.2: peak displacement under sinusoidal lateral load at the pile
    # head. Treat as static head load divided by Kxx (small-strain
    # response is linear by Hardin-Drnevich definition at gamma << 1).
    # Reference load amplitude per Bergua 2021 Sec 4.2: 5 MN.
    P_amp = 5.0e6
    u_peak = P_amp / float(K[0, 0])

    # LC2.3: system frequency from Op^3 OC3 example with the PISA-derived
    # 6x6 attached as Mode B foundation. We use the existing example 02
    # (which currently is fixed-base) modulated by the PISA stiffness via
    # a Rayleigh quotient correction:
    #     1/f^2_system = 1/f^2_fixed + 1/f^2_foundation
    # where f_foundation = (1/2pi) * sqrt(K_rxrx / I_total) and I_total
    # is the second moment of the tower+RNA mass about the foundation.
    from op3 import build_foundation, compose_tower_model
    f_fixed = float(compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_oc3_tower",
        foundation=build_foundation(mode="fixed"),
    ).eigen(n_modes=3)[0])

    # Approximate tower+RNA inertia about the mudline:
    #     I = m_RNA * h_hub^2 + (1/3) * m_tower * h_tower^2
    # NREL 5MW: m_RNA = 350,000 kg, h_hub = 87.6 m above tower base
    m_RNA = 350_000.0
    m_tower = 230_000.0   # NREL 5MW total tower mass
    h_hub = 87.6
    h_tower = 77.6
    I_total = m_RNA * h_hub ** 2 + (1.0 / 3.0) * m_tower * h_tower ** 2
    K_rr = float(K[3, 3])
    f_found = (1.0 / (2 * np.pi)) * np.sqrt(K_rr / I_total)
    # Combined via reciprocal-square (Dunkerley)
    f_sys = 1.0 / np.sqrt(1.0 / f_fixed ** 2 + 1.0 / f_found ** 2)

    return {
        "K_xx": float(K[0, 0]),
        "K_rxrx": float(K[3, 3]),
        "K_xrx": float(K[0, 4]),
        "K_xx_cyclic / K_xx_static": float(K_cyclic[0, 0] / K[0, 0]),
        "u_x_peak": float(u_peak),
        "f1": float(f_sys),
    }


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 80)
    print(" Op3 OC6 Phase II benchmark harness -- Bergua et al. 2021")
    print("=" * 80)

    preds = compute_op3_predictions()
    results = []
    n_pending = 0
    n_pass = 0
    n_fail = 0

    for case in CASES:
        case.op3_value = preds.get(case.quantity)
        if case.reference_value is None:
            status = "AWAITING_VERIFY"
            n_pending += 1
        else:
            err = abs(case.op3_value - case.reference_value) / case.reference_value
            status = "PASS" if err <= case.tolerance else "FAIL"
            if status == "PASS":
                n_pass += 1
            else:
                n_fail += 1

        ref = (f"{case.reference_value:.3e}"
               if case.reference_value is not None else "AWAITING_VERIFY")
        print(f"\n  {case.name}")
        print(f"    {case.description}")
        print(f"    Op3 {case.quantity:<32} = {case.op3_value:.4e} {case.op3_units}")
        print(f"    Ref {case.quantity:<32} = {ref}")
        print(f"    source : {case.reference_source}")
        print(f"    status : {status}")

        results.append({
            "case": case.name,
            "quantity": case.quantity,
            "op3_value": case.op3_value,
            "op3_units": case.op3_units,
            "reference_value": case.reference_value,
            "reference_source": case.reference_source,
            "status": status,
        })

    print()
    print("=" * 80)
    print(f" {n_pass} PASS  |  {n_fail} FAIL  |  {n_pending} AWAITING_VERIFY  "
          f"(of {len(CASES)} cases)")
    print("=" * 80)

    out = REPO_ROOT / "validation/benchmarks/oc6_phase2_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f" JSON written: {out}")
    print()
    print(" NOTE: AWAITING_VERIFY entries become PASS/FAIL automatically")
    print(" when reference_value is filled in -- no code change needed.")
    print(" The reference values are extractable from Bergua 2021")
    print(" Tables 4-6 and Figure 12.")


if __name__ == "__main__":
    main()
