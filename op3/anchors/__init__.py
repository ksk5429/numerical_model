"""
Op^3 suction-anchor module for floating offshore wind mooring.

This package extends Op^3 from fixed-bottom foundations to floating-
platform anchors. The public API mirrors the existing Op^3 pattern;
new symbols are added incrementally as each phase of the module lands.

    from op3.anchors import (
        SuctionAnchor,
        UndrainedClayProfile,
        MooringLoad,
    )

Design boundaries
-----------------
* Analytical capacity methods (DNV-RP-E303, Murff & Hamilton 1993,
  API RP 2SK, Aubeny et al. 2003) are pure Python with no OptumGX
  dependency.
* Method 5 (FE-calibrated) consumes the CSV emitted by the OptumGX
  driver script ``op3/anchors/optumgx_anchor_run.py``. The Python
  layer never generates synthetic FE data; if the CSV is absent an
  explicit ``FileNotFoundError`` is raised with the expected path.
* Mooring coupling uses the real MoorPy package (NREL) -- no stubs.

References
----------
DNV-RP-E303 (2021) "Geotechnical Design and Installation of Suction
    Anchors in Clay".
API RP 2SK (2005, reaff. 2015) "Design and Analysis of Stationkeeping
    Systems for Floating Structures".
ISO 19901-7 (2013) "Stationkeeping systems for floating offshore
    structures and mobile offshore units".
Randolph, M. F., & Gourvenec, S. (2011). "Offshore Geotechnical
    Engineering". Spon Press, Ch. 9.
Randolph, M. F., & House, A. R. (2002). "Analysis of suction caisson
    capacity in clay". OTC 14236.
Supachawarote, C., Randolph, M. F., & Gourvenec, S. (2005). "The
    effect of crack formation on the inclined pull-out capacity of
    suction caissons". IACMAG, Turin.
Aubeny, C. P., Han, S.-W., & Murff, J. D. (2003). "Inclined load
    capacity of suction caissons". IJNAMG 27(14), 1235-1254.
Murff, J. D., & Hamilton, J. M. (1993). "P-Ultimate for undrained
    analysis of laterally loaded piles". J. Geotech. Eng., 119(1),
    91-107.
Andersen, K. H. (2015). "Cyclic soil parameters for offshore
    foundation design". Frontiers in Offshore Geotechnics III,
    Meyer (ed.), Taylor & Francis, 5-82.
"""
from __future__ import annotations

from op3.anchors.anchor import (
    SuctionAnchor,
    UndrainedClayProfile,
    MooringLoad,
)
from op3.anchors.capacity import (
    AnchorCapacityResult,
    anchor_capacity,
    capacity_dnv_rp_e303,
    capacity_murff_hamilton,
    capacity_api_rp_2sk,
    capacity_aubeny_2003,
    capacity_fe_calibrated,
)

__all__ = [
    # Data model
    "SuctionAnchor",
    "UndrainedClayProfile",
    "MooringLoad",
    # Capacity
    "AnchorCapacityResult",
    "anchor_capacity",
    "capacity_dnv_rp_e303",
    "capacity_murff_hamilton",
    "capacity_api_rp_2sk",
    "capacity_aubeny_2003",
    "capacity_fe_calibrated",
]
