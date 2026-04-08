Foundation modes
================

Op\ :sup:`3` supports four foundation idealisations forming a hierarchy
from rigid to fully nonlinear:

.. list-table::
   :header-rows: 1
   :widths: 6 18 50 26

   * - Mode
     - Name
     - Representation
     - When to use
   * - A
     - ``FIXED``
     - Rigid body at the mudline
     - preliminary sizing, sanity checks
   * - B
     - ``STIFFNESS_6X6``
     - 6x6 K at pile head (DNV / ISO / API / OWA / PISA)
     - code-compliant design
   * - C
     - ``DISTRIBUTED_BNWF``
     - Distributed Winkler springs along the embedded length
     - site-specific p-y / soil dynamics
   * - D
     - ``DISSIPATION_WEIGHTED``
     - Distributed Winkler with energy weighting
     - post-yield assessment, fatigue, scour-aware

Mode B factories
----------------

.. autofunction:: op3.foundations.foundation_from_pisa

.. autofunction:: op3.standards.pisa.pisa_pile_stiffness_6x6

.. autofunction:: op3.standards.dnv_st_0126.dnv_monopile_stiffness

.. autofunction:: op3.standards.iso_19901_4.iso_pile_stiffness

.. autofunction:: op3.standards.api_rp_2geo.api_pile_stiffness

.. autofunction:: op3.standards.owa_bearing.owa_suction_bucket_stiffness

Mode D formulation
------------------

See `Mode D dissipation-weighted formulation <https://github.com/ksk5429/numerical_model/blob/main/docs/MODE_D_DISSIPATION_WEIGHTED.md>`_ for the formal definition of
the dissipation-weighted distributed BNWF.
