Suction anchors (floating OWT)
===============================

The :mod:`op3.anchors` package extends Op\ :sup:`3` from fixed-bottom
foundations to floating-platform suction-anchor mooring design. It
covers ultimate capacity (four analytical methods + an FE-calibrated
path), installation feasibility, optimal padeye depth (including a
novel dissipation-centroid method), cyclic-storm degradation, and
MoorPy coupling for full safety-factor time-series checks.

.. contents::
   :local:
   :depth: 2

Scope and standards
-------------------

The module is built around the design framework of:

* DNV-RP-E303 (2021) -- *Geotechnical Design and Installation of
  Suction Anchors in Clay* (default capacity method).
* API RP 2SK (2005, reaff. 2015) -- *Stationkeeping Systems for
  Floating Structures*.
* ISO 19901-7 (2013) -- *Stationkeeping systems*.
* DNV-ST-0119 (2021) -- *Floating wind turbine structures*
  (consequence-class partial safety factors).

It is restricted to clay sites with linearly increasing undrained
shear strength :math:`s_u(z) = s_{u0} + k_z\,z`. Layered profiles
require segment-wise integration; sand sites are out of scope (no
analytical N\ :sub:`p` table is published for granular anchors).

Quick start
-----------

.. code-block:: python

   from op3.anchors import (
       SuctionAnchor, UndrainedClayProfile, MooringLoad,
       anchor_capacity, installation_analysis,
       optimal_padeye_analytical, cyclic_capacity_reduction,
   )

   anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          padeye_depth_m=10.0,
                          submerged_weight_kN=250.0)
   soil   = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
   load   = MooringLoad(tension_kN=4000.0,
                        angle_at_padeye_deg=25.0)

   r = anchor_capacity(anchor, soil, method='dnv_rp_e303', load=load)
   print(f"H_ult = {r.H_ult_kN:.0f} kN")
   print(f"V_ult = {r.V_ult_kN:.0f} kN")
   print(f"T_ult = {r.T_ult_kN:.0f} kN")
   print(f"FoS   = {r.factor_of_safety(load.tension_kN):.2f}")

Capacity methods
----------------

Five independently testable methods behind a unified dispatcher
:func:`op3.anchors.anchor_capacity`:

.. list-table::
   :header-rows: 1
   :widths: 22 25 53

   * - method=
     - Reference
     - When to use
   * - ``'dnv_rp_e303'`` (default)
     - DNV-RP-E303 (2021)
     - Code-compliant design baseline
   * - ``'murff_hamilton'``
     - Murff & Hamilton (1993)
     - Upper-bound cross-check
   * - ``'api_rp_2sk'``
     - API RP 2SK (2005)
     - Conservative API-style envelope (linear V-H)
   * - ``'aubeny_2003'``
     - Aubeny, Han & Murff (2003)
     - Detailed N\ :sub:`p`(z/D) for smooth/rough interface
   * - ``'fe_calibrated'``
     - OptumGX driver
     - Anchor-specific FE envelope (real CSV required)

Every method returns the same :class:`AnchorCapacityResult` shape
(H, V, T at the load angle + V-H envelope DataFrame + depth profile
DataFrame). The FE method raises ``FileNotFoundError`` with a clear
hint when its CSV is missing -- the Python layer never fabricates FE
data.

Installation analysis
---------------------

:func:`installation_analysis` runs three checks per DNV-RP-E303
Sections 5.2-5.4:

#. Self-weight penetration -- bisection on
   :math:`W'_\text{sub} = R(z)`.
#. Required suction vs depth: :math:`s_\text{req}(z) = (R(z) - W')\,/\,A_\text{lid,inner}`.
#. Plug-heave stability ratio: :math:`R_\text{plug} = S_\text{pull}\,/\,S_\text{resist}`.

Cavitation limit
   :math:`s_\text{allow}(z) = 0.9\,(\gamma_w\,z_w + \gamma'\,z)`
   per RP-E303 Section 5.3.5 (0.9 cavitation margin for pump
   inefficiency + seawater vapour pressure).

Optimal padeye
--------------

Three approaches:

* :func:`optimal_padeye_analytical(method='supachawarote_2005')`
  -- Supachawarote et al. (2005) Table 2 interpolation by L/D and
  s\ :sub:`u` profile shape.
* :func:`optimal_padeye_analytical(method='murff_hamilton')`
  -- constant 0.67 L per Murff & Hamilton (1993).
* :func:`optimal_padeye_from_dissipation` -- **novel Op\ :sup:`3`
  contribution**: centroid of the plastic-dissipation field at
  collapse, derived from OptumGX Mode D output. Extends Op\ :sup:`3`
  Mode D (cavity-expansion framework) to anchor design.

The dissipation-centroid method requires a real ``dissipation.csv``
produced by ``op3/anchors/optumgx_anchor_run.py``. See
``docs/ANCHOR_OPTUMGX_GUIDE.md`` for the LLM-assisted workflow.

Cyclic degradation
------------------

:func:`cyclic_capacity_reduction` applies the Andersen 2015
Drammen-clay surrogate

.. math::

   \frac{s_{u,\text{cyc}}}{s_{u,\text{static}}} =
   1 - 0.45\,\bigl(\tau_\text{cyc}/s_u\bigr)^{1.2}\,
       \log_{10}(N) / \log_{10}(10^4)

calibrated to the four corner cases of Andersen (2015) FOG III Fig. 4
(N=10,1000 vs τ/s\ :sub:`u`=0.3,0.8). PI dependence is a small linear
correction.

For a 3-hour storm with T\ :sub:`p`=12 s, τ/s\ :sub:`u`=0.5, this
gives δ ≈ 0.86 (≈14% capacity drop).

MoorPy coupling
---------------

:func:`extract_anchor_loads_from_moorpy_system` solves MoorPy's
non-linear catenary equilibrium at every step of a prescribed body
motion DataFrame (surge / sway / heave) and returns the real
anchor-side tension + angle time series.
:func:`anchor_safety_factor_timeseries` evaluates the capacity at
each step and reports a per-step FoS against DNV-ST-0119 ULS = 1.30.

OptumGX driver
--------------

The commercial-boundary FE driver
``op3/anchors/optumgx_anchor_run.py`` is loaded into OPTUM GX's
desktop scripting console (it ``from OptumGX import *`` -- not
importable from a stock Python interpreter). It builds a 3D
anchor model via 2D revolution, sweeps a configurable list of load
angles (default 0/15/30/45/60/75/90 °), and writes:

* ``envelope.csv`` -- ``angle_deg, T_ult_kN_half, H_ult_kN, V_ult_kN``
* ``dissipation.csv`` -- ``depth_m, w_z, D_total_kJ`` at the design angle
* ``plates_a<ANG>.xlsx`` -- raw plate-element data per probe
* ``summary.json`` -- run config + timings

The pure-Python post-processor
:func:`op3.anchors.fe_postprocess.load_anchor_fe_results` then assembles
:class:`AnchorCapacityResult` + the dissipation-centroid padeye in one call.

Validation
----------

* Aubeny et al. (2003) Table 2 deep N\ :sub:`p` (smooth=9.14, rough=11.94)
* API RP 2SK Section 5.4.2.3 cut-off (z/D=6 -> N\ :sub:`p`=9)
* DNV-RP-E303 Section 4.3.3.2 N\ :sub:`p` profile
* Closed-form :math:`H_\text{ult}` integral with linear s\ :sub:`u`
* Randolph & House (2002) effective N\ :sub:`p` band for L/D ≥ 5

Total: **134 anchor tests passing** (`pytest tests/test_anchors/ -v`).

API reference
-------------

.. autosummary::
   :toctree: api/

   op3.anchors.SuctionAnchor
   op3.anchors.UndrainedClayProfile
   op3.anchors.MooringLoad
   op3.anchors.AnchorCapacityResult
   op3.anchors.anchor_capacity
   op3.anchors.installation_analysis
   op3.anchors.optimal_padeye_analytical
   op3.anchors.optimal_padeye_from_dissipation
   op3.anchors.cyclic_capacity_reduction
   op3.anchors.extract_anchor_loads_from_moorpy_system
   op3.anchors.anchor_safety_factor_timeseries
   op3.anchors.generate_anchor_report

References
----------

Andersen, K. H. (2015). "Cyclic soil parameters for offshore foundation
design." *Frontiers in Offshore Geotechnics III*, 5-82.

API (2005, reaff. 2015). *RP 2SK: Design and Analysis of Stationkeeping
Systems for Floating Structures*, 3rd ed.

Aubeny, C. P., Han, S.-W., & Murff, J. D. (2003). "Inclined load
capacity of suction caissons." *IJNAMG* 27(14), 1235-1254.

DNV (2021). *RP-E303: Geotechnical design and installation of suction
anchors in clay*.

Murff, J. D., & Hamilton, J. M. (1993). "P-Ultimate for undrained
analysis of laterally loaded piles." *J. Geotech. Eng.* 119(1), 91-107.

Randolph, M. F., & House, A. R. (2002). "Analysis of suction caisson
capacity in clay." *OTC* 14236.

Supachawarote, C., Randolph, M. F., & Gourvenec, S. (2005). "The effect
of crack formation on the inclined pull-out capacity of suction
caissons." *IACMAG Turin*, Vol. 3, 577-584.
