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


# ============================================================
# Fu & Bienen (2017) ASCE J Geotech Geoenviron Eng
# "Uniaxial Capacities of Skirted Circular Foundations in Clay"
# ============================================================
FU_BIENEN_2017 = {
    "source": "Fu & Bienen (2017) J Geotech Geoenviron Eng 143(7)",
    "test_type": "3D FE (Modified Cam Clay) + centrifuge 200g validation",
    "D_m": 14.0,  # prototype
    "L_D_range": [0.0, 0.1, 0.25, 0.5],
    "soil": "NC kaolin clay, MCC (lambda=0.205, kappa=0.044, M=0.890)",
    "benchmark_values": {
        # NcV = V_ult / (A * su) for different d/D and kD/su0
        "NcV_surface": {
            "kD_su0_0": 5.94, "kD_su0_1": 6.82, "kD_su0_2": 7.56,
            "kD_su0_3": 8.13, "kD_su0_5": 9.14,
        },
        "NcV_dD_0.5": {
            "kD_su0_0": 10.51, "kD_su0_1": 11.13, "kD_su0_2": 11.04,
        },
        "NcH_surface": {
            "kD_su0_0": 1.02, "kD_su0_1": 1.02, "kD_su0_2": 1.02,
        },
        "NcH_dD_0.5": {
            "kD_su0_0": 4.47, "kD_su0_1": 3.92, "kD_su0_2": 3.24,
        },
        "NcM_surface": {
            "kD_su0_0": 0.71, "kD_su0_1": 0.83, "kD_su0_2": 0.94,
        },
        "NcM_dD_0.5": {
            "kD_su0_0": 1.60, "kD_su0_1": 1.48, "kD_su0_2": 1.28,
        },
    },
    "normalised_formulas": {
        "NcV_surf": "6.05 * (1 + 0.14*(kD/su0) - 0.0074*(kD/su0)^2)",
        "NcV_ratio_homo": "1 + 1.9*ln(1 + d/D)",
        "NcH_ratio_homo": "1 + 8.15*ln(1 + d/D)",
        "NcM_ratio_homo": "1 + 1.7*(d/D)",
    },
    "notes": "Most directly comparable to Op³ suction bucket geometry. "
             "Average absolute error <= 0.5% in fitted formulas.",
}

# ============================================================
# Achmus et al. (2013) Applied Ocean Research
# "Load-bearing behavior of suction bucket foundations in sand"
# ============================================================
ACHMUS_2013 = {
    "source": "Achmus et al. (2013) Applied Ocean Research",
    "test_type": "3D FE (Mohr-Coulomb, stress-dependent stiffness)",
    "D_m": 12.0,  # reference system
    "L_m": 9.0,
    "L_D": 0.75,
    "soil": "very dense sand (phi=40, kappa=600) and medium dense (phi=35, kappa=400)",
    "validation": "Frederikshavn (D=2m) and Sandy Haven (D=4m) field tests",
    "benchmark_values": {
        "Hu_pure_horizontal_MN": 45.0,  # approx, at load eccentricity h=0
        "Hu_h20m_MN": 8.0,  # at 20m eccentricity
        "hyperbolic_factor": 0.92,  # Hu(FEM)/Hu(hyperbolic)
    },
    "key_findings": [
        "capacity more sensitive to L/D than to t/D",
        "initial stiffness more sensitive to D than to L",
        "vertical preload has <10% effect on horizontal capacity",
    ],
    "notes": "Normalised capacity equations for L/D=0.5-1.0 in sand. "
             "Directly comparable to Op³ Mode C pushover.",
}

# ============================================================
# Lai et al. (2023) Soil Dynamics and Earthquake Engineering
# "Effects of soil small strain nonlinearity on dynamic
#  impedance of horizontally loaded suction caisson"
# ============================================================
LAI_2023 = {
    "source": "Lai et al. (2023) Soil Dyn Earthquake Eng 165:107731",
    "test_type": "3D FE (Plaxis 3D, Hardening Soil Small-Strain)",
    "D_m": 30.0,
    "L_m": 10.0,
    "L_D": 0.333,
    "soil": "marine clay (c'=4.7kPa, phi'=28.7, G0_ref=42MPa, gamma_0.7=3e-4)",
    "benchmark_values": {
        "stiffness_reduction_high_NL_pct": 20.0,  # at gamma_0.7 = 1e-4
        "stiffness_reduction_low_NL_pct": 10.0,   # at gamma_0.7 = 5e-4
        "max_shear_strain_H10MN": 1.57e-3,
        "max_shear_strain_M100MNm": 1.04e-3,
    },
    "degradation_formula": "Gs/G0 = 1 / (1 + 0.385 * |gamma/gamma_0.7|)",
    "notes": "Dynamic impedance with nonlinearity for large-diameter "
             "suction caisson. Directly comparable to Op³ Mode B "
             "stiffness extraction under varying load levels.",
}

# ============================================================
# Skau et al. (2018) Géotechnique
# "A numerical study of capacity and stiffness of circular
#  skirted foundations in clay under combined static and
#  cyclic general loading"
# ============================================================
SKAU_2018 = {
    "source": "Skau et al. (2018) Géotechnique 68(3):205-220",
    "test_type": "3D FE (HVMcap + Plaxis 3D)",
    "D_m": 10.0,
    "L_D_range": [0.5, 1.0],
    "soil": "Drammen clay, OCR=1/4/40, DSS undrained shear strength",
    "benchmark_values": {
        "drammen_clay_su": {
            "OCR_1": {"su0_kPa": 24.0, "gradient_kPa_m": 1.44},
            "OCR_4": {"su0_kPa": 41.0, "gradient_kPa_m": 2.46},
            "OCR_40": {"su_kPa": 68.0},
        },
        "displacement_scaling": {
            "OCR_40_Neq_10_hD_1.0": {
                "zeta_v": 1.40, "zeta_h": 1.60, "zeta_theta": 1.50,
            },
        },
    },
    "key_findings": [
        "normalised failure envelopes insensitive to cyclic degradation",
        "framework for combined VHM under cyclic loading",
    ],
    "notes": "Provides cyclic degradation factors applicable to Op³ "
             "Mode D dissipation-weighted foundation.",
}

# ============================================================
# Vulpe (2015) Géotechnique
# "Design method for the undrained capacity of skirted
#  circular foundations under combined loading"
# ============================================================
VULPE_2015 = {
    "source": "Vulpe (2015) Géotechnique 65(8):669-683",
    "test_type": "3D FE (Abaqus, small-strain)",
    "L_D_range": [0.0, 0.10, 0.25, 0.50],
    "soil": "NC clay, Eu/su=500, nu=0.499, gamma'=6 kN/m3",
    "benchmark_values": {
        # Bearing capacity factors NcV, NcH, NcM for rough interface
        "rough_dD_0.5": {
            "kappa_0":   {"NcV": 10.69, "NcH": 4.17, "NcM": 1.48},
            "kappa_6":   {"NcV": 11.22, "NcH": 3.31, "NcM": 1.21},
            "kappa_20":  {"NcV": 11.34, "NcH": 3.00, "NcM": 1.07},
            "kappa_60":  {"NcV": 11.39, "NcH": 2.82, "NcM": 1.05},
            "kappa_100": {"NcV": 11.16, "NcH": 2.80, "NcM": 1.03},
        },
        "rough_dD_0.25": {
            "kappa_0":   {"NcV": 8.71, "NcH": 2.90, "NcM": 1.01},
            "kappa_6":   {"NcV": 10.73, "NcH": 2.50, "NcM": 0.99},
            "kappa_20":  {"NcV": 11.08, "NcH": 2.21, "NcM": 0.88},
        },
        "smooth_dD_0.5": {
            "kappa_0":   {"NcV": 7.91, "NcH": 3.65, "NcM": 1.06},
            "kappa_6":   {"NcV": 9.10, "NcH": 2.89, "NcM": 0.86},
            "kappa_20":  {"NcV": 9.33, "NcH": 2.61, "NcM": 0.75},
        },
    },
    "notes": "Comprehensive VHM capacity factors for skirted circular "
             "foundations. kappa = kD/sum (heterogeneity index). "
             "Directly comparable to Op³ Mode D VH envelope.",
}

# ============================================================
# Jalbi et al. (2018) Ocean Engineering
# "Impedance functions for rigid skirted caissons supporting
#  offshore wind turbines"
# ============================================================
JALBI_2018 = {
    "source": "Jalbi et al. (2018) Ocean Eng 148",
    "test_type": "3D FE (Plaxis 3D) + regression",
    "L_D_range": [0.5, 2.0],
    "soil_profiles": ["homogeneous", "linear (Gibson)", "parabolic (sand)"],
    "benchmark_values": {
        # Impedance coefficients: K = f(L/D) * D^n * E_f
        "homogeneous": {
            "KL_coeffs":  {"a0": 0.56, "a1": 2.91, "exp": 0.96},
            "KLR_coeffs": {"a0": 1.47, "a1": 1.87, "exp": 1.06},
            "KR_coeffs":  {"a0": 1.92, "a1": 2.70, "exp": 0.96},
        },
        "linear": {
            "KL_coeffs":  {"a0": 1.33, "a1": 2.53, "exp": 0.96},
            "KLR_coeffs": {"a0": 2.29, "a1": 2.02, "exp": 0.96},
            "KR_coeffs":  {"a0": 2.90, "a1": 2.46, "exp": 0.96},
        },
        # Example: 5MW OWT, L=6m, D=12m, L/D=0.5, Es=40MPa
        "example_5MW": {
            "KL_GN_m": 0.294,
            "KLR_GN": 5.3,
            "KR_GNm_rad": 44.0,
            "f_fixed_Hz": 0.26,
            "f_flexible_Hz": 0.17,
        },
    },
    "validation_vs_doherty": {
        "KL_LD_0.5_homo_v0.2":  {"doherty": 9.09, "proposed": 9.08},
        "KR_LD_0.5_homo_v0.2":  {"doherty": 16.77, "proposed": 13.1},
        "KL_LD_2.0_homo_v0.2":  {"doherty": 18.04, "proposed": 19.87},
        "KR_LD_2.0_homo_v0.2":  {"doherty": 201.6, "proposed": 187.41},
    },
    "notes": "Most directly comparable to Op³ Mode B 6x6 stiffness "
             "matrix. Regression formulas give KL, KLR, KR for L/D "
             "0.5-2.0 across three ground profiles.",
}

# ============================================================
# Gazetas group (2015, 2018)
# Elastic and non-linear stiffness for suction caissons
# ============================================================
GAZETAS_2018 = {
    "source": "Efthymiou & Gazetas (2018) J Geotech Geoenviron Eng 145(2)",
    "test_type": "closed-form elastic solutions",
    "benchmark_values": {
        # Design example: L = R = 10m, G = 5MPa, nu=0.5, H=30m bedrock
        "example": {
            "L_m": 10.0, "R_m": 10.0, "G_MPa": 5.0,
            "KH_MN_m": 955.0,
            "KR_MNm_rad": 121110.0,
            "KHR_MN": 5730.0,
            "theta_rad": 1.66e-3,
            "u1_cm": 1.4,
        },
    },
    "key_findings": [
        "closed-form expressions for KV, KH, KR, KHR",
        "covers homogeneous and Gibson (G=lambda*z) soil",
        "sidewall shell contributes 68-100% of caisson stiffness at L/R>=0.5",
    ],
    "notes": "Closed-form stiffness validation target for Op³ Mode B.",
}

# ============================================================
# Doherty et al. (2005) ASCE J Geotech Geoenviron Eng
# "Stiffness of flexible caisson foundations embedded in
#  nonhomogeneous elastic soil"
# ============================================================
DOHERTY_2005 = {
    "source": "Doherty et al. (2005) J Geotech Geoenviron Eng 131(12):1498-1508",
    "test_type": "semi-analytical (scaled boundary FE)",
    "benchmark_values": {
        # Five dimensionless stiffness coefficients: KV, KH, KM, KT, KC
        # for variable D/B = 0.2, 0.5, 1.0 and nu = 0.49
        "notes": "Reference elastic stiffness coefficients for flexible "
                 "and rigid caissons. Used as validation target by Jalbi "
                 "2018 and Suryasentana 2017/2020.",
    },
    "notes": "Canonical reference for suction caisson elastic stiffness. "
             "Op³ Mode B extraction should match within 5-15%.",
}

# ============================================================
# Suryasentana et al. (2020) Géotechnique
# "A Winkler model for suction caisson foundations (OxCaisson)"
# ============================================================
SURYASENTANA_2020 = {
    "source": "Suryasentana et al. (2020) Géotechnique 70(9):815-834",
    "test_type": "calibrated 1D Winkler model (OxCaisson)",
    "benchmark_values": {
        "notes": "Six independent stiffness coefficients: KH, KV, KM, "
                 "KQ (twist), KC (coupling). Calibrated against Doherty "
                 "2005. Poisson ratio dependency up to 40% for KV.",
    },
    "key_findings": [
        "local stiffness matrix: symmetric and positive definite",
        "coupling KHR ≈ 0.6*KHL typical ratio",
        "millisecond execution vs hours for 3D FE",
    ],
    "notes": "OxCaisson is the closest published equivalent to Op³ "
             "Mode B. Direct comparison of 6x6 global stiffness.",
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
        "Fu_Bienen_2017": FU_BIENEN_2017,
        "Achmus_2013": ACHMUS_2013,
        "Lai_2023": LAI_2023,
        "Skau_2018": SKAU_2018,
        "Vulpe_2015": VULPE_2015,
        "Jalbi_2018": JALBI_2018,
        "Gazetas_2018": GAZETAS_2018,
        "Doherty_2005": DOHERTY_2005,
        "Suryasentana_2020": SURYASENTANA_2020,
    }
