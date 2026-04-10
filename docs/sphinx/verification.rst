Verification & Validation
=========================

The Op\ :sup:`3` V&V suite contains 115+ active falsification gates
across 14 test modules. All tests must pass before any commit reaches
``main``.

Test summary
------------

.. list-table::
   :header-rows: 1

   * - Module
     - Tests
     - Topic
   * - ``tests/test_code_verification.py``
     - 4
     - Analytical closed-form references (Euler-Bernoulli, Rayleigh)
   * - ``tests/test_consistency.py``
     - 4
     - Cross-path internal consistency
   * - ``tests/test_sensitivity.py``
     - 5
     - Physical sensitivity invariants
   * - ``tests/test_extended_vv.py``
     - 8
     - Damping, energy, reciprocity, units, coordinates, orthogonality
   * - ``tests/test_pisa.py``
     - 9
     - PISA conic + 6x6 stiffness invariants
   * - ``tests/test_cyclic_degradation.py``
     - 10
     - Hardin-Drnevich + Vucetic-Dobry
   * - ``tests/test_hssmall.py``
     - 8
     - HSsmall constitutive wrapper + CSV round-trip
   * - ``tests/test_mode_d.py``
     - 8
     - Mode D dissipation-weighted formulation
   * - ``tests/test_openfast_runner.py``
     - 6
     - OpenFAST runner infrastructure
   * - ``tests/test_backlog_closure.py``
     - 3
     - Static condensation, SACS round-trip, Mode B/C
   * - ``tests/test_uq.py``
     - 13
     - MC propagation, PCE, Bayesian
   * - ``tests/test_reproducibility.py``
     - 6
     - Snapshot byte-identical reproduction
   * - ``scripts/calibration_regression.py``
     - 4
     - Published-source frequency calibration
   * - ``scripts/test_three_analyses.py``
     - 33
     - Eigenvalue + pushover + transient on 11 examples

Calibration regression
----------------------

.. list-table::
   :header-rows: 1

   * - Example
     - Op\ :sup:`3` f1 (Hz)
     - Reference (Hz)
     - Source
     - Error
   * - NREL 5 MW fixed
     - 0.316
     - 0.324
     - Jonkman 2009 NREL/TP-500-38060
     - -2.5%
   * - NREL 5 MW OC3 monopile
     - 0.275
     - 0.277
     - Jonkman & Musial 2010 NREL/TP-500-47535
     - -0.4%
   * - SiteA 4 MW class tripod
     - 0.235
     - 0.244
     - PhD Ch. 5 field OMA
     - -3.7%
   * - IEA 15 MW monopile
     - 0.188
     - 0.170
     - Gaertner 2020 NREL/TP-5000-75698
     - +10.6%

Standards conformance
---------------------

DNV-ST-0126 audit (9 clauses x 4 examples = 36 checks): **35/36 PASS**.
The single failure is the SiteA tripod 1P frequency separation
(6.8% < 10% required), which is a real engineering finding.

IEC 61400-3 audit (12 clauses x 4 examples = 48 checks): structural
and foundation provisions all PASS; DLC coverage is partial as
documented in the OpenFAST runner section.

Cross-validation against published benchmarks
----------------------------------------------

In addition to the internal V&V tests above, Op\ :sup:`3` has been
cross-validated against **31 independent benchmarks** from 20+ published
sources, achieving a **96% verification rate** (27/28 in-scope).

See :doc:`cross_validation` for the complete cross-validation report
including OptumGX bearing capacity factors (0.8--7.8% error vs Vulpe
2015), foundation stiffness (3--26% vs Doherty 2005 / OxCaisson), and
the Bothkennar field trial comparison (-21% vs measured K\ :sub:`r`).
