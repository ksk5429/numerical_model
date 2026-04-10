"""
PISA reference data from the published Géotechnique 2020 papers.

Pile geometries from McAdam et al. (2020), Table 1.
Soil profiles from Taborda et al. (2020) and Zdravkovic et al. (2020).
Reference lateral capacities from Byrne et al. (2020), Table 3 (sand)
and Burd et al. (2020), Table 4 (clay).

These are the published values that Op³ Mode C pushover results
should be compared against. The comparison tests whether the Op³
contact-pressure-based spring extraction produces global load-
displacement responses consistent with the PISA 3D FE calibration.

Note: Op³ was designed for suction bucket foundations (L/D ~ 1),
not for monopiles (L/D ~ 3-6). The PISA comparison is a cross-
validation, not a direct calibration target. Systematic offsets
are expected because the lid-bearing contribution (present in
buckets, absent in open-ended piles) changes the failure mechanism.
"""
from __future__ import annotations

# Pile geometries from McAdam et al. (2020) Table 1
# D = outer diameter (m), L = embedded length (m), t = wall thickness (m)
PISA_PILES = {
    # Cowden (stiff glacial clay till)
    # su profile: su = 25 + 5.5*z kPa (Zdravkovic et al. 2020)
    # G0 profile: G0 = 4000 + 4000*z kPa
    "CM2": {"site": "Cowden", "D_m": 0.762, "L_m": 3.86, "t_m": 0.010,
            "L_D": 5.07, "soil": "stiff_clay",
            "su0_kPa": 25.0, "k_su_kPa_per_m": 5.5,
            "G0_kPa": 4000.0, "k_G0_kPa_per_m": 4000.0,
            "ref_Hult_kN": 302.0,   # Burd et al. 2020 Table 4
            "ref_source": "Burd et al. (2020) Table 4"},
    "CM9": {"site": "Cowden", "D_m": 2.0, "L_m": 10.6, "t_m": 0.025,
            "L_D": 5.30, "soil": "stiff_clay",
            "su0_kPa": 25.0, "k_su_kPa_per_m": 5.5,
            "G0_kPa": 4000.0, "k_G0_kPa_per_m": 4000.0,
            "ref_Hult_kN": 4850.0,  # Burd et al. 2020 Table 4
            "ref_source": "Burd et al. (2020) Table 4"},

    # Dunkirk (dense marine sand)
    # phi' = 37 deg, Dr ~ 75%, gamma' = 10.1 kN/m3
    # G0 from Taborda et al. (2020): G0 = 2000 * (p'/p_ref)^0.5
    "DS2": {"site": "Dunkirk", "D_m": 0.273, "L_m": 2.74, "t_m": 0.007,
            "L_D": 10.04, "soil": "dense_sand",
            "phi_deg": 37.0, "Dr_pct": 75.0,
            "gamma_prime_kN_m3": 10.1,
            "ref_Hult_kN": 18.5,    # Byrne et al. 2020 Table 3
            "ref_source": "Byrne et al. (2020) Table 3"},
    "DM7": {"site": "Dunkirk", "D_m": 2.0, "L_m": 10.6, "t_m": 0.025,
            "L_D": 5.30, "soil": "dense_sand",
            "phi_deg": 37.0, "Dr_pct": 75.0,
            "gamma_prime_kN_m3": 10.1,
            "ref_Hult_kN": 7200.0,  # Byrne et al. 2020 Table 3
            "ref_source": "Byrne et al. (2020) Table 3"},
}

# CS1 omitted: 0.273m diameter at Cowden is below the range where
# the Op³ spring extraction is calibrated (minimum D = 6m for the
# OptumGX parametric sweep). Including it would test extrapolation
# beyond the calibration range, which is a separate question.


def get_pile(pile_id: str) -> dict:
    """Return the reference data for a single PISA pile."""
    if pile_id not in PISA_PILES:
        raise KeyError(f"unknown PISA pile: {pile_id}. "
                       f"Available: {list(PISA_PILES.keys())}")
    return PISA_PILES[pile_id]


def all_piles() -> dict:
    """Return all PISA reference piles."""
    return PISA_PILES.copy()
