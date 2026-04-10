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
   :caption: Getting started

   environment
   getting_started
   user_manual/index

.. toctree::
   :maxdepth: 2
   :caption: Reference

   foundation_modes
   standards
   uq
   openfast_coupling
   technical_reference
   api

.. toctree::
   :maxdepth: 2
   :caption: Science and validation

   scientific_report
   verification
   cross_validation

.. note::

   **Tutorials** are planned for the v1.1 release. In the meantime,
   see the demo scripts in ``scripts/`` (e.g., ``visualize_op3.py``,
   ``visualize_optumgx_openfast.py``, ``test_three_analyses.py``)
   and the sample projects in ``sample_projects/``.

.. toctree::
   :maxdepth: 2
   :caption: Operations

   troubleshooting
   contributing

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
   python scripts/run_openfast.py site_a
   python scripts/run_dlc11_partial.py
   python scripts/dnv_st_0126_conformance.py --all

Verification & validation
-------------------------

The full V&V suite consists of 140 active tests across 15 modules
plus 39 cross-validation benchmarks against 20+ published sources.
See :doc:`verification` for the unit-test falsification gates and
:doc:`cross_validation` for the published-benchmark comparison
(35/38 in-scope benchmarks verified, 92%).

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
