"""
Extended cross-validation reference data extracted from the
processed literature at F:/TREE_OF_THOUGHT/RESEARCH/.

Each entry provides published benchmark values that Op³ can be
compared against. The data was extracted directly from the
processed PDFs; all values are attributed to their source paper.
"""
from __future__ import annotations

# ============================================================
# DJ Kim et al. (2014) ASCE J Geotech Geoenviron Eng
# "Investigation of monotonic and cyclic behavior of tripod
#  suction bucket foundations using centrifuge modeling"
# ============================================================
DJ_KIM_2014 = {
    "source": "DJ Kim et al. (2014) J Geotech Geoenviron Eng 140(11)",
    "test_type": "centrifuge 70g",
    "tripod": {
        "D_m": 6.5, "L_m": 8.0, "L_D": 1.23,
        "CtC_m": 26.85,
        "soil": "SM/ML layered (silty sand over silt)",
        "My_MNm": 93.0,      # yield moment (prototype)
        "theta_y_deg": 0.6,   # rotation at yield
        "design_moment_MNm": 115.0,
        "notes": "bilinear moment-rotation, yield at 0.6 deg"
    },
    "monopod": {
        "D_m": 15.5, "L_m": 8.0, "L_D": 0.52,
        "My_MNm": 198.0,
        "theta_y_deg": 3.1,
        "notes": "gradual decrease in slope, no clear yield"
    },
}

# ============================================================
# Chen et al. (2018) ASTM J Testing Evaluation
# "Model test study on horizontal static loading of suction
#  bucket foundation under different scour conditions"
# ============================================================
CHEN_2018 = {
    "source": "Chen et al. (2018) J Testing Evaluation 47(4)",
    "test_type": "1g model test",
    "soil": "poorly graded fine sand, e=0.574, gamma=1.8 g/cm3",
    # Normalised ultimate horizontal capacity Fu = F / (2*pi*R^3*gamma')
    # D = 200 mm for L/D = 0.5, 0.75, 1.0; D = 100 mm for L/D = 6
    "no_scour": {
        "L_D_0.5":  {"D_mm": 200, "L_mm": 100, "Fu_norm": 0.60},
        "L_D_0.75": {"D_mm": 200, "L_mm": 150, "Fu_norm": 0.79},
        "L_D_1.0":  {"D_mm": 200, "L_mm": 200, "Fu_norm": 1.64},
    },
    "with_scour": {
        # L/D = 6 bucket under global scour at S/D = 0.5, 1.0, 1.5
        "L_D_6_SD_0.5": {"D_mm": 100, "L_mm": 600, "S_D": 0.5,
                         "Fu_reduction_pct": "reported in Fig 6-8"},
        "L_D_6_SD_1.0": {"D_mm": 100, "L_mm": 600, "S_D": 1.0,
                         "Fu_reduction_pct": "reported in Fig 6-8"},
    },
    "normalised_curve": "F/Fu = 2.4611 * (S/D)^0.3199",
}

# ============================================================
# Jin et al. (2025) Computers and Geotechnics
# "Evolution of bearing capacity and macroelement modelling for
#  suction caisson foundations in sand considering local scour"
# ============================================================
JIN_2025 = {
    "source": "Jin et al. (2025) Computers and Geotechnics",
    "test_type": "3D FE (hypoplastic sand model)",
    "D_m": 8.0, "L_m": 8.0, "L_D": 1.0,
    "soil": "dense sand, Dr=80%, phi=37 deg",
    "key_findings": [
        "scour depth dominates capacity reduction over scour width and angle",
        "failure envelope shape unchanged by scour, only dimensions change",
        "H-M failure envelope with scour depth parameterisation",
    ],
    "notes": "provides empirical formulas for scour-dependent VH envelope "
             "that Op³ Mode D can be compared against",
}

# ============================================================
# Barari et al. (2021) Computers and Geotechnics
# "Tripod suction caisson foundations for offshore wind energy
#  and their monotonic and cyclic responses in silty sand"
# ============================================================
BARARI_2021 = {
    "source": "Barari et al. (2021) Computers and Geotechnics",
    "test_type": "centrifuge + 3D FE",
    "D_m": "varies (centrifuge scale)",
    "soil": "silty sand",
    "key_findings": [
        "validated 3D FE against centrifuge for tripod suction caisson",
        "monotonic and cyclic responses documented",
        "failure mechanism analysis for tripod configuration",
    ],
}

# ============================================================
# Houlsby et al. (2005) Géotechnique
# "Field trials of suction caissons in clay"
# ============================================================
HOULSBY_2005_CLAY = {
    "source": "Houlsby et al. (2005) Proc ICE Geotech Eng 158(1)",
    "test_type": "field trial (intermediate scale)",
    "site": "Bothkennar, Scotland",
    "soil": "soft clay, su ~ 15-30 kPa",
    "D_m": 1.5,  # 1.5 m and 3.0 m caissons tested
    "L_D_range": [0.5, 1.0],
    "key_findings": [
        "field-scale installation and loading of suction caissons in clay",
        "measured installation suction pressures",
        "load-displacement under cyclic horizontal + moment loading",
    ],
}

# ============================================================
# Houlsby et al. (2006) Géotechnique
# "Field trials of suction caissons in sand"
# ============================================================
HOULSBY_2006_SAND = {
    "source": "Houlsby et al. (2006) Proc ICE Geotech Eng 159(3)",
    "test_type": "field trial (intermediate scale)",
    "site": "Luce Bay, Scotland",
    "soil": "dense sand",
    "D_m": 1.5,
    "L_D_range": [0.5, 1.0],
    "key_findings": [
        "field-scale suction installation in sand",
        "moment-rotation under combined VHM",
        "comparison with Villalobos lab data",
    ],
}

# ============================================================
# Jeong et al. (2021) KSCE J Civil Engineering
# "Centrifuge modeling for the evaluation of cyclic behavior
#  of offshore wind turbine with tripod foundation"
# ============================================================
JEONG_2021 = {
    "source": "Jeong et al. (2021) KSCE J Civil Eng",
    "test_type": "centrifuge 70g (KAIST)",
    "soil": "Saemangeum sand",
    "D_m": "centrifuge scale (prototype ~6-8m)",
    "key_findings": [
        "permanent rotation: 0.047 deg at 100 cycles, 0.103 deg at 1M cycles",
        "approaching but not exceeding 0.5 deg serviceability limit",
        "CPT-calibrated tripod at 70g",
    ],
    "benchmark_values": {
        "perm_rotation_100_deg": 0.047,
        "perm_rotation_1M_deg": 0.103,
        "serviceability_limit_deg": 0.5,
    },
}

# ============================================================
# Chortis et al. (2020) Ocean Engineering
# "Influence of scour depth and type on p-y curves for
#  monopiles in sand under monotonic lateral loading"
# ============================================================
CHORTIS_2020 = {
    "source": "Chortis et al. (2020) Ocean Engineering 197",
    "test_type": "centrifuge 100g",
    "foundation": "monopile",
    "D_m": 6.0,  # prototype
    "L_m": 36.0,
    "L_D": 6.0,
    "soil": "dense sand, Dr~75%",
    "key_findings": [
        "global scour reduces capacity 20-40% less than local scour "
        "at S=2D because global preserves passive wedge",
        "lateral capacity loss ~50% at S=2D (local scour)",
        "p-y curve modification factors for scour provided",
    ],
    "benchmark_values": {
        "H_reduction_local_S2D_pct": 50.0,
        "H_reduction_global_S2D_pct": 30.0,  # approximate
    },
}

# ============================================================
# Villalobos et al. (2009) Géotechnique (via Villalobos thesis 2006)
# VH failure envelope for suction caisson in clay
# ============================================================
VILLALOBOS_2009 = {
    "source": "Villalobos et al. (2009) Géotechnique 59(7)",
    "test_type": "1g model test",
    "D_m": 0.293, "L_m": 0.146, "L_D": 0.5,
    "soil": "kaolin clay, su ~ 8 kPa",
    "benchmark_values": {
        "H_norm_pure_lateral": 0.12,  # H / (A * su)
        "V_norm_pure_vertical": 1.0,  # V / (A * su)
        "A_m2": 0.0674,  # pi * (0.293/2)^2
    },
}

# ============================================================
# Kallehave et al. (2015) Phil Trans R Soc A
# "Optimization of monopiles for offshore wind turbines"
# ============================================================
KALLEHAVE_2015 = {
    "source": "Kallehave et al. (2015) Phil Trans R Soc A 373",
    "test_type": "field measurement compilation",
    "key_findings": [
        "measured frequencies exceed API predictions by up to 20%",
        "proposed modified API p-y initial stiffness for sand",
        "compilation of data from multiple North Sea wind farms",
    ],
    "benchmark_values": {
        "api_overprediction_range_pct": (0, 20),
        "notes": "Op³ avoids API p-y entirely by extracting stiffness "
                 "from 3D FE contact pressures, so this benchmark "
                 "validates the motivation for the Op³ approach",
    },
}


def all_references() -> dict:
    """Return all reference datasets as a dict keyed by short name."""
    return {
        "DJ_Kim_2014": DJ_KIM_2014,
        "Chen_2018": CHEN_2018,
        "Jin_2025": JIN_2025,
        "Barari_2021": BARARI_2021,
        "Houlsby_2005_clay": HOULSBY_2005_CLAY,
        "Houlsby_2006_sand": HOULSBY_2006_SAND,
        "Jeong_2021": JEONG_2021,
        "Chortis_2020": CHORTIS_2020,
        "Villalobos_2009": VILLALOBOS_2009,
        "Kallehave_2015": KALLEHAVE_2015,
    }
