Troubleshooting and FAQ
=======================

Solutions to the most common issues encountered when installing,
running, or extending Op\ :sup:`3`. Organized by subsystem so you can
jump to the relevant section.

.. contents:: Contents
   :local:
   :depth: 2

Installation
------------

Q: ``pip install -e ".[test,docs]"`` fails with a C compiler error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You are likely on Python 3.13, which does not yet have pre-built
NumPy / SciPy wheels for Windows. Downgrade to Python 3.12:

.. code-block:: bash

   pyenv install 3.12.9
   pyenv local 3.12.9
   python -m venv .venv
   source .venv/Scripts/activate
   pip install -e ".[test,docs]"

Q: ``openseespy`` is not found after install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OpenSeesPy is listed in ``pyproject.toml`` but some PyPI
distributions miss Windows x64 wheels for specific Python versions.
Try the direct install:

.. code-block:: bash

   pip install openseespy==3.5.1

If still missing, check https://pypi.org/project/openseespy/#files
for the latest available wheel matching your Python version.

Q: ``from op3 import ...`` fails with a ``ModuleNotFoundError``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You are running outside the repository root or you forgot the
editable install. From the repo root:

.. code-block:: bash

   pip install -e .                 # editable
   python -c "import op3; print(op3.__file__)"

The printed path should be inside the cloned repository, not inside
``site-packages``.

OpenSees runtime
----------------

Q: ``WARNING: symbolic analysis returns -8`` followed by a solver crash
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your OpenSees domain has stale state from a previous build. The
``conftest.py`` autouse fixture wipes the domain before every
pytest, but if you are running scripts directly you need to call
``ops.wipe()`` before each rebuild. Or use the new analysis context
manager:

.. code-block:: python

   from op3._opensees_state import analysis
   with analysis("eigen"):
       freqs = model.eigen(n_modes=3)

Q: ``can't set handler after analysis is created``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same root cause. The ``analysis()`` context manager handles this
automatically, or wrap the rebuild in
``ops.wipeAnalysis()`` + re-setup:

.. code-block:: python

   import openseespy.opensees as ops
   ops.wipeAnalysis()
   ops.system("BandGeneral")
   ops.numberer("RCM")
   ops.constraints("Plain")
   ops.algorithm("Linear")
   # ... re-setup analysis as needed

Q: Mode C ``extract_6x6_stiffness()`` used to return garbage values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This was a bug in v0.3.0: the finite-difference SP-constraint probe
interacted badly with BNWF anchor topology and returned ~zero. Fixed
in v0.3.1: the new implementation uses the analytic Winkler integral
directly.

If you hit this on an older version, upgrade to v0.3.1+:

.. code-block:: bash

   git fetch --tags
   git checkout v0.3.2

Q: Two consecutive ``model.eigen()`` calls give different answers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a sign of stale OpenSees state leaking between builds. The
V&V test idempotence asserts that two calls in
the same Python process give bit-identical results. If you hit this:

1. Make sure each ``compose_tower_model`` is fresh (not reused).
2. Wrap your test in the analysis context manager.
3. File a bug report with the two numeric values and the exact
   sequence that reproduces the drift.

OpenFAST runtime
----------------

Q: OpenFAST v5 rejects my deck with ``Invalid numerical input ... CompServo``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your deck was authored against OpenFAST v4.0.x or earlier. The v5
deck format requires ``NRotors``, ``CompSoil``, and ``MirrorRotor``
in the feature switches block. Either:

1. Use the v5 deck under ``gunsan_4p2mw/openfast_deck_v5/`` (already
   in the correct format), or
2. Regenerate your deck against the v5.0.0 r-test templates:

.. code-block:: bash

   ls tools/r-test_v5/r-test/glue-codes/openfast/

Q: OpenFAST v5 rejects my ElastoDyn file with ``Invalid logical input ... PtfmYDOF``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your ElastoDyn file is newer than v5.0.0. Check for ``PtfmYDOF`` in
the file (v5.0.0 supports it) and make sure the v5.0.0 binary is
what's actually running:

.. code-block:: bash

   tools/openfast/OpenFAST.exe -v
   # Should print:  OpenFAST-v5.0.0

Q: DISCON.dll could not be loaded
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The OC3 Tripod r-test expects
``../5MW_Baseline/ServoData/DISCON.dll`` relative to the deck
directory. Download the Bladed controller DLL from the OpenFAST v5
release:

.. code-block:: bash

   curl -L -o tools/r-test_v5/r-test/glue-codes/openfast/5MW_Baseline/ServoData/DISCON.dll \
     https://github.com/OpenFAST/openfast/releases/download/v5.0.0/Discon.dll

Or set ``CompServo = 0`` in your ``.fst`` to disable ServoDyn
entirely (you lose the controller and cannot run production DLCs,
but parked / structural-only runs still work).

Q: DLC 6.1 run terminates with "Tower strike" at ~1 second
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the expected behaviour for the OC3 Tripod template at the
50-year extreme wind speed: the Bladed controller is in normal-
production mode (blades not feathered), so the rotor deflects into
the tower. This is not a software bug; it is a real physical
constraint flagged by Op\ :sup:`3`'s runner as PARTIAL rather than
FAIL.

To get a proper DLC 6.1 run, build a parked-configuration variant:

.. code-block:: bash

   python scripts/build_dlc61_parked_deck.py --source gunsan_v5

This copies the deck to a ``*_parked`` sibling, sets
``CompServo = 0`` in the ``.fst``, and disables all rotor DOFs with
pitch = 90 deg in ``ElastoDyn.dat``.

Q: OpenFAST runs but produces no .outb file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check the ``run_log.txt`` in the workdir. Common causes:

* The ``OutList`` block in the ElastoDyn file is empty.
* ``SumPrint = True`` but the summary file write failed on disk
  permissions.
* The simulation terminated abnormally before any output time step
  was reached (e.g. tower strike at t = 0.1 s).

PISA and geotechnical
---------------------

Q: Op\ :sup:`3` PISA gives K_xx 100x higher than my published reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two separate issues may be at play:

1. **You are comparing raw K_xx to a published k_Hinit** which is
   defined as the secant slope of H vs ground-level displacement
   under a load applied at height h above ground. These are NOT the
   same quantity. Use ``effective_head_stiffness(K, h_load_m)``
   instead:

   .. code-block:: python

      from op3.standards.pisa import effective_head_stiffness
      k_eff = effective_head_stiffness(K, h_load_m=10.0)

2. **You are using Op\ :sup:`3` v0.3.0 or earlier**, which lacks the
   L/D-dependent depth functions from Burd 2020 Table 5. Upgrade to
   v0.3.2+ to reduce the error by 10-30x.

Even after both fixes, expect a residual 3-13x on short rigid piles
(L/D < 5) because Op\ :sup:`3` uses the published generic PISA
calibration, not site-specific re-calibration. This is documented in
:doc:`scientific_report` section 4.3.

Q: ``cyclic_stiffness_6x6`` gives a ratio of 0.833 instead of 0.5 at gamma=1e-4
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You are using a clay profile but passing the sand default
gamma_ref = 1e-4. For clay with PI = 30%, the Vucetic-Dobry
gamma_ref is 5e-4. To get G/G_max = 0.5 exactly, call:

.. code-block:: python

   from op3.standards.cyclic_degradation import vucetic_dobry_gamma_ref
   gamma_ref = vucetic_dobry_gamma_ref(30.0)     # 5e-4 for PI=30%
   K = cyclic_stiffness_6x6(
       diameter_m=..., embed_length_m=...,
       soil_profile=profile,
       cyclic_strain=gamma_ref,     # exactly at gamma_ref
       PI_percent=30.0,
   )

Q: My SoilDyn .dat file fails with "Soil location ... is above mudline"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``location_xyz`` you passed to ``write_soildyn_input`` has a
z-coordinate above the mudline. SoilDyn requires the coupling point
to be at or below the seabed. For the OC3 Tripod template
(``WtrDpth = 45``), the coupling point must have z <= -45.0:

.. code-block:: python

   write_soildyn_from_pisa(
       "Gunsan_SoilDyn.dat",
       diameter_m=6.0, embed_length_m=36.0,
       soil_profile=profile,
       location_xyz=(0.0, 0.0, -45.0),   # <= mudline
   )

Q: SoilDyn fails with "Closest SubDyn Node is more than 0.1m away"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``location_xyz`` must coincide with an existing SubDyn mesh node
within 0.1 m. For the OC3 Tripod the reaction joints are at:

* Joint 1: (-24.80, 0.00, -45.00)
* Joint 2: (12.40, 21.48, -45.00)
* Joint 3: (12.40, -21.48, -45.00)

Pick one and use it verbatim. Stock OpenFAST CalcOption=1 supports
only a single coupling point, so for the tripod you must either
(a) pick one leg and accept the approximation, or (b) use
CalcOption=3 with a custom multi-point DLL.

UQ module
---------

Q: PCE mean comes out as 2*pi instead of 0 for f(xi) = xi
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This was a v0.3.0 bug: ``numpy.polynomial.hermite_e.hermegauss``
returns weights for ``integral f(x) exp(-x^2/2) dx`` rather than the
standard-normal expectation ``integral f(x) (1/sqrt(2pi)) exp(-x^2/2) dx``.
The missing factor ``1/sqrt(2pi)`` explains the 2*pi discrepancy in
the variance.

Fixed in v0.3.0+ -- if you hit this, upgrade.

Q: MC propagation gives COV(K_xx) = 0 for my profile
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You are passing ``correlated=True`` (the default) with all
``SoilPrior.G_cov = 0``, so every sample draws the same value. Set a
non-zero COV (typical values are 0.15-0.40 per Phoon & Kulhawy
1999):

.. code-block:: python

   priors = [
       SoilPrior(0.0, 5.0e7, G_cov=0.30, soil_type="sand"),
       ...
   ]

Q: Bayesian calibration posterior is flat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your measurement sigma is too large relative to the forward-model
sensitivity range. Reduce sigma or widen the grid:

.. code-block:: python

   post = grid_bayesian_calibration(
       forward_model=forward,
       likelihood_fn=normal_likelihood(measured, sigma=0.005),  # tighter
       grid=np.linspace(0.5, 1.5, 101),                          # wider
   )

V&V tests
---------

Q: ``test_reproducibility`` fails after a code change
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The snapshot has drifted because your change affected a canonical
output. This is expected when you make intentional physics changes.
Regenerate the snapshot:

.. code-block:: bash

   rm tests/reproducibility_snapshot.json
   python tests/test_reproducibility.py     # writes fresh snapshot
   python tests/test_reproducibility.py     # verifies reproduction
   git add tests/reproducibility_snapshot.json

Include the snapshot update in the same commit as the physics change
so the git history preserves the cause-and-effect link.

Q: ``test_extended_vv`` fails on the energy conservation test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Newmark average-acceleration is unconditionally stable but not
exactly energy-preserving. The test allows 8% drift over 5 cycles
(test 2.8). If your BLAS / OpenSeesPy version
introduces slightly different numerical noise, you may see 8-12%.
Report it as a bug with the observed drift percentage and your
BLAS version.

Q: ``test_calibration_regression`` fails with a different f1 value
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Either (a) an intentional physics change affected the calibration
(update the reference and re-run the V&V sweep before committing),
or (b) something in the Op\ :sup:`3` pipeline has drifted
unintentionally.

Debug flow:

1. ``git bisect`` to find the commit that introduced the drift.
2. If intentional, update ``scripts/calibration_regression.py`` with
   the new reference and explain in the commit message.
3. If unintentional, file a bug with the before/after numbers.

Environment and platform
------------------------

Q: Korean text prints as ``mojibake`` / ``???``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set ``PYTHONUTF8=1`` before running any script. The Windows default
``cp949`` codec is hostile to UTF-8 stdout:

.. code-block:: bash

   # Git Bash / PowerShell:
   export PYTHONUTF8=1
   python scripts/release_validation_report.py

Q: The repo is huge (>1 GB clone)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The r-test v5.0.0 clone is ~1.6 GB. It is ``.gitignore``'d so it
does not enter the main repo history. If your local clone is still
huge, check for leftover files:

.. code-block:: bash

   du -sh tools/r-test_v5 tools/openfast validation/openfast_runs

These three directories carry all the large binary artifacts.

Q: I cannot push to ``origin`` because of a large file error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You probably accidentally staged one of the OpenFAST binaries or
``.outb`` files. Check ``git status`` and ``.gitignore``:

.. code-block:: bash

   git status --short | head -20
   grep -E "tools/|openfast_runs|\.outb$" .gitignore

If a large file slipped into a commit, use ``git filter-repo`` or
``BFG Repo-Cleaner`` to remove it from history before pushing.

Getting help
------------

If none of the above resolves your issue:

1. Search the GitHub issue tracker:
   https://github.com/ksk5429/numerical_model/issues
2. Check the developer notes for recent changes:
   `docs/DEVELOPER_NOTES.md <https://github.com/ksk5429/numerical_model/blob/main/docs/DEVELOPER_NOTES.md>`_
3. Open a new issue using the bug report template:
   https://github.com/ksk5429/numerical_model/issues/new?template=bug_report.md

Please include:

* Op\ :sup:`3` commit SHA (``git rev-parse HEAD``)
* Python version (``python --version``)
* Operating system and version
* The minimal code that reproduces the issue
* Full traceback / log output
