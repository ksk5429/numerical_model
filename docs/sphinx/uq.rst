Uncertainty quantification (Phase 5)
=====================================

The :mod:`op3.uq` package implements three orthogonal UQ tools:

* **Monte Carlo propagation** -- :mod:`op3.uq.propagation`
* **Polynomial Chaos Expansion** -- :mod:`op3.uq.pce`
* **Bayesian calibration** -- :mod:`op3.uq.bayesian`

Soil parameter propagation
--------------------------

.. autoclass:: op3.uq.propagation.SoilPrior
   :members:

.. autofunction:: op3.uq.propagation.propagate_pisa_mc

.. autofunction:: op3.uq.propagation.summarise_samples

Polynomial Chaos Expansion
--------------------------

.. autoclass:: op3.uq.pce.HermitePCE
   :members:

.. autofunction:: op3.uq.pce.build_pce_1d

.. autofunction:: op3.uq.pce.build_pce_2d

Bayesian calibration
--------------------

.. autoclass:: op3.uq.bayesian.BayesianPosterior
   :members:

.. autofunction:: op3.uq.bayesian.normal_likelihood

.. autofunction:: op3.uq.bayesian.grid_bayesian_calibration

Example: NREL 5 MW OC3 EI calibration
-------------------------------------

The Op\ :sup:`3` Bayesian calibration of the NREL 5 MW OC3 monopile
tower EI scale factor against the published Jonkman & Musial (2010)
reference frequency yields:

.. code-block:: text

   posterior mean   = 1.014
   posterior std    = 0.076
   5%-95% interval  = [0.888, 1.145]

Translation: the published OC3 tower stiffness is consistent with the
Op\ :sup:`3` model to within ±1.4% mean and a 13% credible interval.

Reference: ``tests/test_uq.py::test_5_3_4_op3_calibration_demo``.
