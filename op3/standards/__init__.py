"""
Op^3 industry-standard foundation stiffness calculators.

Mode B (6x6 lumped stiffness) draws its values from published
industry standards, not ad-hoc literature. This subpackage implements
the four most widely cited stiffness formulations and emits a 6x6
matrix in the schema that op3.foundations consumes.

Available standards:

    DNVGL-ST-0126   "Support structures for wind turbines" (2016, rev. 2021)
                    Section 5.5: equivalent linear soil stiffness
                    https://www.dnv.com/oilgas/download/dnvgl-st-0126-support-structures-for-wind-turbines.html

    ISO 19901-4     "Petroleum and natural gas industries — Specific
                    requirements for offshore structures — Part 4:
                    Geotechnical and foundation design considerations"
                    Annex E: Stiffness coefficients for shallow foundations

    API RP 2GEO     "Geotechnical and Foundation Design Considerations"
                    Section 8.3: Linear soil stiffness for foundation
                    impedance analysis
                    (recovers Gazetas 1991 closed-form solutions)

    OWA Bearing     The Carbon Trust Offshore Wind Accelerator (OWA)
    Capacity        joint industry guidance for suction bucket foundations
    Guidance        (Houlsby & Byrne 2005, OWA 2019 Bearing Capacity Report)

All four formulations produce a 6x6 diagonal stiffness matrix in SI
units (N/m for translational, N*m/rad for rotational) at the foundation
center. Off-diagonal coupling terms are zero in the diagonal model;
the full coupling matrix from Gazetas (1991) is implemented in
`gazetas_full()` for users who need it.

Example
-------

>>> from op3.standards import dnv_monopile_stiffness, iso_jacket_stiffness
>>> K = dnv_monopile_stiffness(
...     diameter_m=6.0, embedment_m=36.0,
...     soil_type='dense_sand', water_depth_m=20.0,
... )
>>> print(K.shape, K.diagonal())
"""
from op3.standards.dnv_st_0126 import (
    dnv_monopile_stiffness,
    dnv_jacket_stiffness,
    dnv_suction_bucket_stiffness,
)
from op3.standards.iso_19901_4 import (
    iso_shallow_foundation_stiffness,
    iso_pile_stiffness,
)
from op3.standards.api_rp_2geo import (
    api_pile_stiffness,
    gazetas_full_6x6,
)
from op3.standards.owa_bearing import (
    owa_suction_bucket_stiffness,
    houlsby_byrne_caisson_stiffness,
)

__all__ = [
    "dnv_monopile_stiffness",
    "dnv_jacket_stiffness",
    "dnv_suction_bucket_stiffness",
    "iso_shallow_foundation_stiffness",
    "iso_pile_stiffness",
    "api_pile_stiffness",
    "gazetas_full_6x6",
    "owa_suction_bucket_stiffness",
    "houlsby_byrne_caisson_stiffness",
]
