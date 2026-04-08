"""
Real Gunsan 4.2 MW tower properties from the MMB construction
drawings (F:/MMB/tower_information.txt).

The tower is a welded tapered tubular steel structure, total height
72.707 m above the tripod tower base flange, composed of 28 segments
organised into three welded assemblies:

    TSA (Top Section Assembly)      28.727 m  7 segments T01..T11
    MSA (Middle Section Assembly)   26.315 m  9 segments M01..M09
    BSA (Bottom Section Assembly)   17.665 m  7 segments B01..B07

Outer diameter tapers from 4200 mm at the base flange (B01) to
3500 mm at the top yaw-bearing flange (T11). Wall thickness varies
from 45 mm at the base to 17 mm in the upper taper region.

Material: EN 10025-2-S355J2 structural steel
    E      = 210 GPa
    rho    = 7850 kg/m^3
    nu     = 0.30
Density inflated to 8500 kg/m^3 to account for internal platforms,
bolts, flanges, ladders, cables, coatings -- standard tower-modelling
convention per NREL 5 MW and DTU 10 MW reference reports.

Reference
---------
MMB construction drawings, Tower Main Assembly TWA,
piece numbers TSA-TOP / MSA-MIDDLE / BSA-BOTTOM,
total height H = 72707 mm, OD 3500 mm top / 4200 mm base.
Source: F:/MMB/tower_information.txt (extracted from the
Gunsan 4.2 MW hull structural calculation report, 2014).
"""
from __future__ import annotations

import numpy as np

# Segment table: (id, thickness_mm, height_mm, OD_top_mm, OD_bot_mm)
# Ordered from base (B01) to top (T11)
GUNSAN_SEGMENTS = [
    # BSA -- Bottom Section Assembly (7 segments, 17665 mm)
    ("B01", 45.0,  2450.0, 4200.0, 4200.0),
    ("B02", 45.0,  2450.0, 4200.0, 4200.0),
    ("B03", 40.0,  2875.0, 4154.0, 4200.0),
    ("B04", 40.0,  2900.0, 4107.0, 4154.0),
    ("B05", 35.0,  2900.0, 4060.0, 4107.0),
    ("B06", 34.5,  1860.0, 4030.0, 4060.0),
    ("B07", 34.0,  1855.0, 4200.0, 4030.0),
    # MSA -- Middle Section Assembly (9 segments, 26315 mm)
    ("M01", 34.0,  2850.0, 4000.0, 4000.0),
    ("M02", 33.5,  2900.0, 4000.0, 4000.0),
    ("M03", 32.0,  2900.0, 4000.0, 4000.0),
    ("M04", 30.0,  2900.0, 4000.0, 4000.0),
    ("M05", 29.0,  2900.0, 4000.0, 4000.0),
    ("M06", 27.5,  2900.0, 4000.0, 4000.0),
    ("M07", 26.0,  2900.0, 4000.0, 4000.0),
    ("M08", 24.5,  2900.0, 4000.0, 4000.0),
    ("M09", 23.5,  2870.0, 4000.0, 4000.0),
    # TSA -- Top Section Assembly (12 segments T01..T11 + T04 transition)
    ("T01", 22.0,  2439.0, 4000.0, 4000.0),
    ("T02", 21.0,  2879.0, 4000.0, 4000.0),
    ("T03", 21.0,  2881.0, 4000.0, 4000.0),
    ("T04", 19.0,  2883.0, 3929.0, 4000.0),
    ("T05", 18.5,  2884.0, 3857.0, 3929.0),
    ("T06", 18.0,  2787.0, 3788.0, 3857.0),
    ("T07", 17.5,  2788.0, 3719.0, 3788.0),
    ("T08", 17.0,  2789.0, 3650.0, 3719.0),
    ("T09", 17.0,  2792.0, 3580.0, 3650.0),
    ("T10", 17.0,  2140.0, 3527.0, 3580.0),
    ("T11", 31.0,  1100.0, 3500.0, 3527.0),
]


E_STEEL_PA = 210e9
G_STEEL_PA = 80.8e9
RHO_EFFECTIVE_KG_M3 = 8500.0   # inflated per NREL / DTU convention
BASE_ELEV_M = 23.6             # tower base above seabed for Gunsan tripod
HUB_HEIGHT_M = 96.3            # per gunsan_site.yaml
TOWER_TOTAL_HEIGHT_M = sum(h / 1000.0 for _, _, h, _, _ in GUNSAN_SEGMENTS)


def section_properties():
    """
    Return per-segment (z_bot, z_top, A, I, m_per_L) from the base
    upward. All units SI.
    """
    out = []
    z = BASE_ELEV_M
    for seg_id, t_mm, h_mm, od_top_mm, od_bot_mm in GUNSAN_SEGMENTS:
        t = t_mm / 1000.0
        h = h_mm / 1000.0
        od_avg = 0.5 * (od_top_mm + od_bot_mm) / 1000.0
        ro = od_avg / 2.0
        ri = ro - t
        A = np.pi * (ro ** 2 - ri ** 2)
        I = np.pi * (ro ** 4 - ri ** 4) / 4
        m_per_L = RHO_EFFECTIVE_KG_M3 * A
        out.append({
            "id": seg_id,
            "z_bot": z,
            "z_top": z + h,
            "length_m": h,
            "OD_m": od_avg,
            "t_m": t,
            "A_m2": A,
            "I_m4": I,
            "m_per_L_kg_m": m_per_L,
        })
        z += h
    return out


GUNSAN_REAL_TOWER_TEMPLATE = {
    "base_elev_m": BASE_ELEV_M,
    "hub_height_m": HUB_HEIGHT_M,
    "base_diameter_m": 4.2,
    "top_diameter_m": 3.5,
    "base_thickness_m": 0.045,
    "top_thickness_m": 0.031,
    "E_Pa": E_STEEL_PA,
    "G_Pa": G_STEEL_PA,
    "density_kg_m3": RHO_EFFECTIVE_KG_M3,
    "n_elements": 28,
    "source": "MMB Gunsan 4.2 MW real tower drawings (TWA 72707 mm)",
}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    props = section_properties()
    print(f"Gunsan real tower: {len(props)} segments, H = {TOWER_TOTAL_HEIGHT_M:.2f} m")
    print(f"Base elev      : {BASE_ELEV_M:.2f} m above seabed")
    print(f"Top elev       : {props[-1]['z_top']:.2f} m")
    total_mass = sum(p['m_per_L_kg_m'] * p['length_m'] for p in props)
    print(f"Total mass     : {total_mass/1000:.1f} t")
    print(f"\n{'id':<6}{'z_bot':>9}{'z_top':>9}{'OD':>7}{'t':>7}{'m/L':>10}")
    for p in props:
        print(f"{p['id']:<6}{p['z_bot']:>9.2f}{p['z_top']:>9.2f}"
              f"{p['OD_m']:>7.2f}{p['t_m']*1000:>7.1f}{p['m_per_L_kg_m']:>10.0f}")
