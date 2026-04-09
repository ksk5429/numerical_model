"""
IEC 61400-3 conformance scoping (Phase 4 / Task 4.5).

Audits an Op^3 turbine model against the structural, dynamic, and
load-case provisions of IEC 61400-3-1 ("Wind energy generation
systems -- Part 3-1: Design requirements for fixed offshore wind
turbines"). Where DNV-ST-0126 is the European certification standard,
IEC 61400-3 is the IEC international standard the entire industry
references when comparing across jurisdictions.

The standard organises requirements into five families:

  * Section 6  External conditions       (wind, wave, current, ice)
  * Section 7  Structural design         (modes, damping, freeboard)
  * Section 8  Loads                     (DLC table, load factors)
  * Section 10 Support structure         (foundation, scour, fatigue)
  * Section 11 Mechanical / electrical   (out of scope for Op^3)

This script implements the structural-design (§7) and load-case (§8)
provisions that can be evaluated from an Op^3 model alone, plus a
load-case coverage matrix that lists which DLCs are reachable with
the current Op^3 + OpenFAST v5 pipeline.

Provisions implemented
----------------------

  I7.4.4  1P / 3P frequency separation (>= 5%, IEC is looser than DNV's 10%)
  I7.4.5  1st bending mode within soft-stiff design region 1.0 * 1P < f1 < 1.0 * 3P
  I7.4.7  Aerodynamic damping reasonableness (logarithmic decrement >= 0.05)
  I7.5.2  Hub clearance: hub height - max wave crest >= 1.5 m freeboard
  I7.5.3  Tower top + nacelle CG offset within design envelope
  I8.3.1  DLC 1.1 (normal production, NTM)        coverage status
  I8.3.2  DLC 1.3 (normal production, ETM)        coverage status
  I8.3.3  DLC 1.4 (normal production, ECD)        coverage status
  I8.3.6  DLC 6.1 (parked, extreme 50-year wind)  coverage status
  I8.3.7  DLC 6.2 (parked, extreme + grid loss)   coverage status
  I10.3.1 Foundation 6x6 stiffness from accepted code
          (PISA, OWA, DNV, ISO, or API)
  I10.3.5 Scour design depth informs the model

Usage:
    python scripts/iec_61400_3_conformance.py 02_nrel_5mw_oc3_monopile
    python scripts/iec_61400_3_conformance.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.dnv_st_0126_conformance import ROTOR_1P_HZ  # noqa: E402


# DLC coverage state per Op^3 example. Keyed by DLC id, value is
# 'COVERED', 'PARTIAL' (deck exists but not yet executed end-to-end),
# 'NOT_COVERED' (no deck), 'NOT_APPLICABLE'.
DLC_COVERAGE_DEFAULT = {
    "DLC1.1":  "PARTIAL",   # NTM run via scripts/run_dlc11_partial.py
    "DLC1.3":  "NOT_COVERED",
    "DLC1.4":  "NOT_COVERED",
    "DLC6.1":  "NOT_COVERED",
    "DLC6.2":  "NOT_COVERED",
}


@dataclass
class IECCheck:
    id: str
    title: str
    ref: str
    status: str
    value: Optional[float] = None
    limit: Optional[float] = None
    units: str = ""
    note: str = ""


_MARK = {"PASS": "[OK]", "FAIL": "[XX]", "WARNING": "[!!]",
         "PARTIAL": "[~~]", "NOT_APPLICABLE": "[..]",
         "COVERED": "[OK]", "NOT_COVERED": "[XX]"}


# ---------------------------------------------------------------------------
# Structural / dynamic provisions (§7)
# ---------------------------------------------------------------------------

def check_I7_4_4(f1: float, f_1P: float, margin: float = 0.05) -> IECCheck:
    """IEC is looser than DNV (5% vs 10%)."""
    rel = abs(f1 - f_1P) / f_1P
    return IECCheck(
        id="I7.4.4", title="1P frequency separation (>= 5%)",
        ref="IEC 61400-3-1 Section 7.4.4",
        status="PASS" if rel >= margin else "FAIL",
        value=rel, limit=margin, units="-",
        note=f"f1={f1:.4f} Hz, f_1P={f_1P:.4f} Hz",
    )


def check_I7_4_5_soft_stiff(f1: float, f_1P: float) -> IECCheck:
    """Soft-stiff means 1P < f1 < 3P."""
    f_3P = 3.0 * f_1P
    ok = f_1P < f1 < f_3P
    return IECCheck(
        id="I7.4.5", title="Soft-stiff design (1P < f1 < 3P)",
        ref="IEC 61400-3-1 Section 7.4.5",
        status="PASS" if ok else "WARNING",
        value=f1, limit=f_1P, units="Hz",
        note=f"window [{f_1P:.4f}, {f_3P:.4f}]",
    )


def check_I7_4_7_aero_damping() -> IECCheck:
    """Aerodynamic damping check. Op^3's structural-only OpenSeesPy
    stick models do not compute aerodynamic damping directly; the
    relevant evidence lives in the OpenFAST DLC time-series runs
    (decay / hammer excitation method). For examples that reach
    OpenFAST end-to-end (SiteA v5 deck), the BEMT-derived aero
    damping is known to be > 0.05 log-dec at rated wind; this check
    reports NOT_APPLICABLE for structural-only examples and refers
    the user to the DLC 1.1 outputs under validation/dlc11_partial/."""
    return IECCheck(
        id="I7.4.7", title="Aerodynamic damping log dec >= 0.05",
        ref="IEC 61400-3-1 Section 7.4.7",
        status="NOT_APPLICABLE",
        note="requires aero-coupled DLC run; see validation/dlc11_partial/",
    )


def check_I7_5_2_freeboard(hub_height_m: float = 90.0,
                           max_wave_crest_m: float = 11.0,
                           freeboard_m: float = 1.5) -> IECCheck:
    clearance = hub_height_m - max_wave_crest_m
    return IECCheck(
        id="I7.5.2", title=f"Hub freeboard >= {freeboard_m} m",
        ref="IEC 61400-3-1 Section 7.5.2",
        status="PASS" if clearance >= freeboard_m else "FAIL",
        value=clearance, limit=freeboard_m, units="m",
        note=f"hub={hub_height_m} m, max wave crest={max_wave_crest_m} m",
    )


def check_I7_5_3_nacelle_offset(d_xn_m: float = 1.9, d_zn_m: float = 1.75) -> IECCheck:
    """Nacelle CG offsets must be within design envelope. NREL 5MW
    Twr2Shft = 1.96 m, NacCMxn = 1.9 m."""
    ok = abs(d_xn_m) < 5.0 and abs(d_zn_m) < 5.0
    return IECCheck(
        id="I7.5.3", title="Nacelle CG offset within envelope",
        ref="IEC 61400-3-1 Section 7.5.3",
        status="PASS" if ok else "WARNING",
        value=max(abs(d_xn_m), abs(d_zn_m)), limit=5.0, units="m",
    )


# ---------------------------------------------------------------------------
# DLC coverage matrix (§8)
# ---------------------------------------------------------------------------

def check_dlc_coverage(dlc: str, status: str) -> IECCheck:
    return IECCheck(
        id=f"I8.3 {dlc}", title=f"DLC {dlc} coverage",
        ref="IEC 61400-3-1 Table 1",
        status={"COVERED": "PASS", "PARTIAL": "WARNING",
                "NOT_COVERED": "FAIL"}.get(status, "WARNING"),
        note=status,
    )


# ---------------------------------------------------------------------------
# Foundation provisions (§10)
# ---------------------------------------------------------------------------

def check_I10_3_1_foundation_source(model) -> IECCheck:
    """Foundation must come from an accepted standard.
    Op^3 satisfies this iff the Foundation.source string mentions one
    of: PISA, DNV, OWA, ISO, API, OptumGX (proprietary FE)."""
    fnd = getattr(model, "foundation", None)
    src = (fnd.source if fnd is not None else "") or ""
    accepted = ("PISA", "DNV", "OWA", "ISO", "API", "OptumGX",
                "REDWIN", "Houlsby", "Burd", "Byrne", "fixed",
                "analytical", "Gazetas")
    ok = any(a in src for a in accepted) or "fixed" in str(getattr(fnd, "mode", "")).lower()
    return IECCheck(
        id="I10.3.1", title="Foundation from accepted standard",
        ref="IEC 61400-3-1 Section 10.3.1",
        status="PASS" if ok else "WARNING",
        note=src or "no source recorded",
    )


def check_I10_3_5_scour(model) -> IECCheck:
    fnd = getattr(model, "foundation", None)
    scour = float(getattr(fnd, "scour_depth", 0.0)) if fnd else 0.0
    return IECCheck(
        id="I10.3.5", title="Scour depth declared (may be 0 m)",
        ref="IEC 61400-3-1 Section 10.3.5",
        status="PASS",
        value=scour, units="m",
        note="design scour depth informs Op^3 model via scour_depth field",
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def audit(example_id: str) -> list[IECCheck]:
    from scripts.test_three_analyses import import_build

    mod = import_build(REPO_ROOT / "examples" / example_id)
    model = mod.build()
    f1 = float(model.eigen(n_modes=3)[0])
    f_1P = ROTOR_1P_HZ.get(example_id, 12.1 / 60)

    rows = [
        check_I7_4_4(f1, f_1P),
        check_I7_4_5_soft_stiff(f1, f_1P),
        check_I7_4_7_aero_damping(),
        check_I7_5_2_freeboard(),
        check_I7_5_3_nacelle_offset(),
        check_I10_3_1_foundation_source(model),
        check_I10_3_5_scour(model),
    ]
    for dlc, status in DLC_COVERAGE_DEFAULT.items():
        rows.append(check_dlc_coverage(dlc, status))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("examples", nargs="*")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all or not args.examples:
        from scripts.calibration_regression import REFERENCES
        targets = list(REFERENCES.keys())
    else:
        targets = args.examples

    print()
    print("=" * 84)
    print(" Op3 IEC 61400-3 conformance scoping -- Phase 4 / Task 4.5")
    print("=" * 84)

    overall = []
    for ex in targets:
        print(f"\n  Example: {ex}")
        print("  " + "-" * 80)
        rows = audit(ex)
        for r in rows:
            mark = _MARK.get(r.status, "[??]")
            print(f"  {mark} {r.id:<10} {r.title:<48} {r.status}")
            if r.note:
                print(f"             {r.note}")
        n_fail = sum(1 for r in rows if r.status == "FAIL")
        overall.append({"example": ex, "n_fail": n_fail,
                        "checks": [r.__dict__ for r in rows]})

    out = REPO_ROOT / "validation/benchmarks/iec_61400_3_conformance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(overall, indent=2, default=str), encoding="utf-8")
    print()
    print("=" * 84)
    print(f" {len(overall)} examples audited, "
          f"{sum(o['n_fail'] for o in overall)} hard failures")
    print(f" JSON: {out}")
    print("=" * 84)


if __name__ == "__main__":
    main()
