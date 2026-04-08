User manual
===========

This chapter walks through the Op\ :sup:`3` workflow end-to-end with
one worked example per foundation mode, one per standard, one per UQ
tool, and one full OpenFAST coupling. Copy-paste any code block and
it will run on a correctly set-up environment (see
:doc:`environment`).

.. contents:: Contents
   :local:
   :depth: 2

1. Anatomy of an Op\ :sup:`3` model
-----------------------------------

Every Op\ :sup:`3` analysis goes through three objects:

.. code-block:: python

   from op3 import build_foundation, compose_tower_model

   foundation = build_foundation(mode="fixed")                 # (1) Foundation handle
   model = compose_tower_model(                                 # (2) TowerModel
       rotor="nrel_5mw_baseline",
       tower="nrel_5mw_oc3_tower",
       foundation=foundation,
   )
   freqs = model.eigen(n_modes=3)                               # (3) Analysis call

Three layers:

1. **Foundation** -- a declarative handle describing the soil-structure
   interaction model (Mode A / B / C / D). No OpenSees calls happen
   yet; the handle is pure Python data.
2. **TowerModel** -- a composite of ``(rotor, tower, foundation)``
   that knows how to build itself into an OpenSees domain when asked.
3. **Analysis** -- one of ``eigen()``, ``pushover()``,
   ``transient()``, or ``extract_6x6_stiffness()``. The first call
   triggers the OpenSees build; subsequent calls reuse the model.

2. Foundation modes -- worked examples
--------------------------------------

Mode A -- fixed base
~~~~~~~~~~~~~~~~~~~~

The simplest mode. Appropriate for preliminary sizing, sanity checks,
and any case where the foundation stiffness vastly exceeds the tower
stiffness.

.. code-block:: python

   from op3 import build_foundation, compose_tower_model

   model = compose_tower_model(
       rotor="nrel_5mw_baseline",
       tower="nrel_5mw_oc3_tower",
       foundation=build_foundation(mode="fixed"),
   )
   f1 = model.eigen(n_modes=3)[0]
   print(f"NREL 5MW fixed-base f1 = {f1:.4f} Hz")
   # Expected: 0.3158 Hz (Jonkman 2009 reference: 0.324 Hz)

Mode B -- 6x6 lumped stiffness
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Used when a calibrated 6x6 matrix is available from an external
source: a PISA analysis, a DNV / ISO / API formula, or an OptumGX
export. The matrix is attached at the tower base via a zero-length
element with one uniaxial material per diagonal term.

**From a CSV file**:

.. code-block:: python

   foundation = build_foundation(
       mode="stiffness_6x6",
       stiffness_matrix="data/fem_results/K_6x6_oc3_monopile.csv",
   )

**From an in-memory NumPy array**:

.. code-block:: python

   import numpy as np
   K = np.diag([2.0e10, 2.0e10, 5.0e9, 1.0e13, 1.0e13, 5.0e12])
   foundation = build_foundation(mode="stiffness_6x6", stiffness_matrix=K)

**From the PISA framework directly**:

.. code-block:: python

   from op3.foundations import foundation_from_pisa
   from op3.standards.pisa import SoilState

   profile = [
       SoilState(0.0,  5.0e7, 35, "sand"),
       SoilState(15.0, 1.0e8, 35, "sand"),
       SoilState(36.0, 1.5e8, 36, "sand"),
   ]
   foundation = foundation_from_pisa(
       diameter_m=6.0,
       embed_length_m=36.0,
       soil_profile=profile,
   )

Mode C -- distributed BNWF springs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Site-specific p-y / t-z distributed springs along the embedded
length. Accepts a CSV file with columns ``depth_m``, ``k_ini_kN_per_m``,
``p_ult_kN_per_m``, ``spring_type``. This is the most faithful
representation when you have OptumGX or PLAXIS soil output.

.. code-block:: python

   foundation = build_foundation(
       mode="distributed_bnwf",
       spring_profile="data/fem_results/spring_profile_op3.csv",
       scour_depth=0.0,     # optional scour correction
   )

Mode D -- dissipation-weighted generalised BNWF
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The novel Op\ :sup:`3` contribution. Applies a multiplicative
weighting :math:`w(D) = \beta + (1-\beta)(1-D/D_{\max})^\alpha` to
the distributed Winkler springs, reducing the stiffness of layers
that have accumulated plastic dissipation. Requires both a spring
profile and an OptumGX dissipation export.

.. code-block:: python

   foundation = build_foundation(
       mode="dissipation_weighted",
       spring_profile="data/fem_results/spring_profile_op3.csv",
       ogx_dissipation="data/fem_results/dissipation_profile.csv",
       mode_d_alpha=2.0,    # sensitivity exponent, default 1.0
       mode_d_beta=0.05,    # stiffness floor, default 0.05 (5%)
   )

After ``model.eigen()`` runs, the diagnostics dictionary on the
foundation records the actual weighting applied:

.. code-block:: python

   print(foundation.diagnostics)
   # {'mode_d_alpha': 2.0, 'mode_d_beta': 0.05,
   #  'mode_d_w_min': 0.050, 'mode_d_w_max': 1.000, ...}

See `docs/MODE_D_DISSIPATION_WEIGHTED.md <https://github.com/ksk5429/numerical_model/blob/main/docs/MODE_D_DISSIPATION_WEIGHTED.md>`_ for the formal derivation.

3. Industry standards (Mode B factories)
-----------------------------------------

Op\ :sup:`3` ships calibrated implementations of the major offshore
geotechnical standards. Each returns a 6x6 matrix that you can feed
straight into ``build_foundation(mode="stiffness_6x6", ...)``.

DNV-ST-0126 monopile
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.standards.dnv_st_0126 import dnv_monopile_stiffness

   K = dnv_monopile_stiffness(
       diameter_m=8.0,
       embed_length_m=30.0,
       soil_type="dense_sand",
   )

ISO 19901-4 shallow and pile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.standards.iso_19901_4 import iso_shallow_foundation_stiffness

   K = iso_shallow_foundation_stiffness(
       diameter_m=20.0,
       G=5.0e7,
       nu=0.33,
   )

API RP 2GEO / Gazetas
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.standards.api_rp_2geo import gazetas_full_6x6

   K = gazetas_full_6x6(
       diameter_m=12.0,
       G=6.0e7,
       nu=0.30,
       embedment_m=5.0,
   )

Carbon Trust OWA suction bucket
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.standards.owa_bearing import owa_suction_bucket_stiffness

   K = owa_suction_bucket_stiffness(
       diameter_m=8.0,
       skirt_length_m=9.3,
       n_buckets=3,
       spacing_m=18.0,
       soil_type="soft_clay",
   )

PISA monopile (Burd 2020 / Byrne 2020)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6

   K = pisa_pile_stiffness_6x6(
       diameter_m=8.0,
       embed_length_m=30.0,
       soil_profile=[
           SoilState(0.0,  6.0e7, 35, "sand"),
           SoilState(30.0, 1.2e8, 36, "sand"),
       ],
   )

4. Analyses
-----------

Eigenvalue
~~~~~~~~~~

.. code-block:: python

   freqs = model.eigen(n_modes=5)
   # Returns numpy array of natural frequencies in Hz

Pushover
~~~~~~~~

.. code-block:: python

   result = model.pushover(target_disp_m=0.5, n_steps=20)
   # result has keys: displacement_m, reaction_kN, n_steps

   import matplotlib.pyplot as plt
   plt.plot(result["displacement_m"], result["reaction_kN"])
   plt.xlabel("Hub displacement (m)")
   plt.ylabel("Base shear (kN)")

Transient
~~~~~~~~~

.. code-block:: python

   tr = model.transient(duration_s=10.0, dt_s=0.02)
   # tr has keys: time_s, hub_disp_m, hub_node

Static condensation to a 6x6
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   K_6x6 = model.extract_6x6_stiffness()
   # Uses the analytic Winkler integral for Modes C / D
   # For Mode B returns the stored matrix unchanged
   # For Mode A returns diag(1e20) (numerically rigid)

5. Cyclic soil degradation
--------------------------

Storm-level cyclic loading softens the soil via Hardin-Drnevich. The
``cyclic_stiffness_6x6`` wrapper degrades the profile then re-runs
PISA:

.. code-block:: python

   from op3.standards.cyclic_degradation import cyclic_stiffness_6x6

   K_storm = cyclic_stiffness_6x6(
       diameter_m=6.0,
       embed_length_m=36.0,
       soil_profile=profile,
       cyclic_strain=1.0e-3,    # storm-level strain
       PI_percent=30.0,         # clay plasticity index
   )

At :math:`\gamma = \gamma_{\rm ref}` the stiffness is exactly halved
(:math:`G/G_{\max} = 0.5` by Hardin-Drnevich definition).

6. Uncertainty quantification
-----------------------------

Monte Carlo soil propagation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.uq import SoilPrior, propagate_pisa_mc, summarise_samples

   priors = [
       SoilPrior(0.0,  5.0e7, G_cov=0.30, soil_type="sand"),
       SoilPrior(15.0, 1.0e8, G_cov=0.30, soil_type="sand"),
       SoilPrior(36.0, 1.5e8, G_cov=0.30, soil_type="sand"),
   ]
   samples = propagate_pisa_mc(
       diameter_m=6.0,
       embed_length_m=36.0,
       soil_priors=priors,
       n_samples=500,
   )
   summary = summarise_samples(samples)
   for k in ("Kxx", "Krxrx"):
       s = summary[k]
       print(f"{k}: mean={s['mean']:.2e}, COV={s['cov']:.2f}, "
             f"5%-95% = [{s['p05']:.2e}, {s['p95']:.2e}]")

Hermite polynomial chaos expansion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Build a closed-form polynomial surrogate of an expensive response
function:

.. code-block:: python

   import numpy as np
   from op3.uq import build_pce_1d, pce_mean_var

   # Surrogate: f(xi) where xi ~ N(0, 1) maps to a physical parameter
   # e.g. tower EI scale factor = 1.0 + 0.1 * xi
   def expensive_forward(xi):
       scale = 1.0 + 0.1 * xi
       # ... run Op3 eigen ...
       return 0.315 * np.sqrt(scale)   # toy example

   pce = build_pce_1d(expensive_forward, order=4)
   mean, var = pce_mean_var(pce)
   print(f"mean = {mean:.4f}, std = {np.sqrt(var):.4f}")

   # Evaluate at a new point in ~microseconds:
   print(pce.evaluate(0.5))   # instead of re-running the solver

Grid Bayesian calibration
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import numpy as np
   from op3.uq import grid_bayesian_calibration, normal_likelihood

   # Forward model: parameter -> predicted observable
   def forward_model(scale):
       m = compose_tower_model(
           rotor="nrel_5mw_baseline",
           tower="nrel_5mw_oc3_tower",
           foundation=build_foundation(mode="fixed"),
       )
       # ... apply scale to tower EI ...
       return float(m.eigen(n_modes=3)[0])

   post = grid_bayesian_calibration(
       forward_model=forward_model,
       likelihood_fn=normal_likelihood(measured=0.2766, sigma=0.01),
       grid=np.linspace(0.7, 1.3, 51),
   )
   print(f"EI scale posterior: mean={post.mean:.3f} +/- {post.std:.3f}")
   print(f"5%-95%: [{post.p05:.3f}, {post.p95:.3f}]")

7. OpenFAST coupling
--------------------

Exporting a SoilDyn input file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from op3.openfast_coupling.soildyn_export import write_soildyn_from_pisa

   out = write_soildyn_from_pisa(
       "Gunsan-4p2MW_SoilDyn.dat",
       diameter_m=6.0,
       embed_length_m=36.0,
       soil_profile=profile,
       location_xyz=(-24.80, 0.0, -45.0),   # SubDyn joint coordinates
   )

Then in your ``.fst``:

.. code-block:: text

   1   CompSoil   - Compute soil-structural dynamics (switch) {1=SoilDyn}
   "Gunsan-4p2MW_SoilDyn.dat"   SoilFile   - Name of SoilDyn input file

Running an OpenFAST simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python scripts/run_openfast.py gunsan --tmax 5
   python scripts/run_openfast.py oc3 --tmax 10
   python scripts/run_openfast.py iea15_monopile --tmax 60

   # DLC sweeps
   python scripts/run_dlc11_partial.py --tmax 600 --speeds 8 12 18
   python scripts/run_dlc61_parked.py --vmax 50 --tmax 10

8. Standards conformance audits
-------------------------------

.. code-block:: bash

   python scripts/dnv_st_0126_conformance.py --all
   python scripts/iec_61400_3_conformance.py --all

Both audits emit per-example PASS / FAIL / WARNING flags for every
clause and write a JSON artifact under
``validation/benchmarks/``.

9. LaTeX table generation for the dissertation
-----------------------------------------------

.. code-block:: bash

   python scripts/generate_latex_tables.py --out PHD/tables

Produces six ``.tex`` files ready to ``\input{}`` from any Quarto or
LaTeX chapter: calibration regression, DNV conformance, IEC
conformance, sensitivity tornado, PISA cross-validation, OC6
Phase II.

10. Complete end-to-end example
-------------------------------

The 5-minute quickstart notebook combines everything above:

.. code-block:: bash

   jupyter notebook docs/tutorials/01_quickstart.ipynb

See `Quickstart notebook <https://github.com/ksk5429/numerical_model/blob/main/docs/tutorials/01_quickstart.ipynb>`_ for the full walkthrough.

Related documentation
---------------------

* :doc:`environment` -- setup and troubleshooting
* :doc:`technical_reference` -- mathematical formulation
* :doc:`foundation_modes` -- deeper dive on Mode A/B/C/D
* :doc:`standards` -- citation table for each calibrated standard
* :doc:`uq` -- UQ module reference
* :doc:`openfast_coupling` -- SoilDyn bridge details
* :doc:`verification` -- V&V evidence
* :doc:`troubleshooting` -- FAQ
