Op\ :sup:`3` -- OptumGX-OpenSeesPy-OpenFAST integration framework
==================================================================

Op\ :sup:`3` is an integrated numerical modelling framework for offshore
wind turbine support structures. It bridges three open-source and
commercial codes:

* **OptumGX** -- 3D finite-element limit analysis (commercial,
  proprietary)
* **OpenSeesPy** -- structural dynamics solver (BSD 3-Clause)
* **OpenFAST v5** -- aero-hydro-servo-elastic coupled wind turbine
  simulation (Apache 2.0)

The framework was developed for the dissertation *"Digital Twin
Encoder for Prescriptive Maintenance of Offshore Wind Turbine
Foundations"* (Seoul National University, June 2026).

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   foundation_modes
   standards
   uq
   openfast_coupling
   verification
   api

Getting started
---------------

.. code-block:: python

   from op3 import build_foundation, compose_tower_model

   foundation = build_foundation(mode="fixed")
   model = compose_tower_model(
       rotor="nrel_5mw_baseline",
       tower="nrel_5mw_oc3_tower",
       foundation=foundation,
   )
   freqs = model.eigen(n_modes=3)
   print(f"f1 = {freqs[0]:.4f} Hz")

Run the bundled examples
------------------------

.. code-block:: bash

   python scripts/test_three_analyses.py
   python scripts/calibration_regression.py
   python scripts/run_openfast.py gunsan
   python scripts/run_dlc11_partial.py
   python scripts/dnv_st_0126_conformance.py --all

Verification & validation
-------------------------

The full V&V suite consists of 115 active tests across 12 modules.
See :doc:`verification` for the complete list of falsification gates
and the published-source calibration regression.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
