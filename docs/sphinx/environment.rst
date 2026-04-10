Environment setup guide
=======================

This page is the complete setup guide for running Op\ :sup:`3` on a
fresh machine. Follow it top-to-bottom and you will have a working
installation with all 140 V&V tests passing in under 30 minutes.

Supported platforms
-------------------

.. list-table::
   :header-rows: 1

   * - Platform
     - Status
     - Notes
   * - Windows 10 / 11 x64
     - **primary**
     - Development and V&V reference platform. All OpenFAST binaries
       are Windows x64.
   * - Ubuntu 22.04 / 24.04 (WSL2 or native)
     - **supported**
     - OpenSeesPy + Python pipeline works; OpenFAST runs via Wine or
       a Linux build from source.
   * - macOS 14+ (arm64 / x86_64)
     - *experimental*
     - OpenSeesPy works; OpenFAST requires source build.

Python prerequisites
--------------------

Op\ :sup:`3` requires **Python 3.11 or 3.12**. Python 3.13 is not yet
supported (OpenSeesPy wheels have not been published).

.. code-block:: bash

   python --version   # should print 3.11.x or 3.12.x

Core dependencies (from ``pyproject.toml``):

.. code-block:: text

   numpy    >= 1.24
   scipy    >= 1.11
   pandas   >= 2.0
   openseespy >= 3.5

Optional extras:

.. code-block:: text

   [test]  pytest >= 7,  pytest-cov >= 4
   [docs]  sphinx >= 7,  alabaster
   [dev]   mypy >= 1.5,  ruff >= 0.1

Step 1 — Clone the repository
-----------------------------

.. code-block:: bash

   git clone https://github.com/ksk5429/numerical_model.git
   cd numerical_model

Step 2 — Create a Python environment
------------------------------------

.. code-block:: bash

   # Windows (PowerShell or Git Bash):
   python -m venv .venv
   source .venv/Scripts/activate

   # Linux / macOS:
   python -m venv .venv
   source .venv/bin/activate

   pip install --upgrade pip

Step 3 — Install Op\ :sup:`3`
-----------------------------

.. code-block:: bash

   pip install -e ".[test,docs]"

This installs the ``op3`` package in editable mode with the pytest,
pytest-cov, sphinx, and alabaster extras. The editable install means
changes to ``op3/*.py`` files take effect immediately without a
re-install step.

Step 4 — Bootstrap the OpenFAST v5.0.0 binary
---------------------------------------------

Op\ :sup:`3` exercises end-to-end coupled wind turbine simulation
through the OpenFAST v5.0.0 binary. The binary is **not bundled** in
the repository (it is 44 MB and tracked in ``.gitignore``). Download
it once into ``tools/openfast/``:

.. code-block:: bash

   mkdir -p tools/openfast
   curl -L -o tools/openfast/OpenFAST.exe \
     https://github.com/OpenFAST/openfast/releases/download/v5.0.0/OpenFAST.exe

   # Verify it runs:
   tools/openfast/OpenFAST.exe -v
   # Expected output: OpenFAST-v5.0.0

Alternatively, set ``OPENFAST_BIN`` to point at an existing install:

.. code-block:: bash

   export OPENFAST_BIN="C:/path/to/OpenFAST.exe"

Op\ :sup:`3`'s runner checks the following locations in order:

1. ``--binary`` CLI flag
2. ``OPENFAST_BIN`` environment variable
3. ``tools/openfast/OpenFAST.exe`` (v5 first)
4. ``tools/openfast/openfast_x64.exe`` (v4 fallback)
5. ``openfast`` / ``openfast_x64`` on ``PATH``
6. ``C:\\openfast\\*``, ``C:\\Program Files\\OpenFAST\\*``,
   ``/usr/local/bin/openfast``, ``/usr/bin/openfast``

Step 5 — Bootstrap the r-test directory
---------------------------------------

Op\ :sup:`3`'s end-to-end OpenFAST runs depend on the canonical NREL
r-test v5.0.0 templates (the OC3 Tripod deck and the shared
``5MW_Baseline`` directory containing the Bladed DISCON.dll
controller, airfoil polars, etc.). Clone it once:

.. code-block:: bash

   mkdir -p tools/r-test_v5
   cd tools/r-test_v5
   git clone --depth=1 --branch v5.0.0 https://github.com/OpenFAST/r-test.git
   cd ../..

Step 6 — Run the V&V suite
--------------------------

.. code-block:: bash

   PYTHONUTF8=1 python scripts/release_validation_report.py

Expected output:

.. code-block:: text

    18/19 PASS  |  0 FAIL  |  1 optional  |  ~42 s total

The single optional failure is the SiteA 1P resonance flag on
DNV-ST-0126 audit -- this is a documented real engineering finding,
not a software bug. See :doc:`verification` for the full explanation.

Quick smoke test
----------------

If ``release_validation_report.py`` passes, you are done. For a
3-second sanity check instead:

.. code-block:: python

   from op3 import build_foundation, compose_tower_model
   model = compose_tower_model(
       rotor="nrel_5mw_baseline",
       tower="nrel_5mw_oc3_tower",
       foundation=build_foundation(mode="fixed"),
   )
   print(f"f1 = {model.eigen(n_modes=3)[0]:.4f} Hz")
   # Expected: f1 = 0.3158 Hz  (NREL/TP-500-38060 reference: 0.324 Hz)

Troubleshooting
---------------

OpenSeesPy import fails with a DLL load error on Windows
  Install Microsoft Visual C++ Redistributable 2019+ from
  https://aka.ms/vs/17/release/vc_redist.x64.exe. OpenSeesPy is
  linked against MSVCRT and will not load without it.

OpenSeesPy eigen crashes with ``WARNING: symbolic analysis returns -8``
  Your domain has stale state from a previous build. Wrap your test
  in ``with op3._opensees_state.analysis("eigen"):`` or call
  ``ops.wipe()`` before the rebuild. The ``tests/conftest.py`` autouse
  fixture handles this automatically for pytest runs.

OpenFAST v5 rejects a SiteA v4 deck with ``Invalid numerical input``
  The v4 deck format differs from v5 (missing ``NRotors``,
  ``CompSoil``, ``MirrorRotor``). Use the v5 deck under
  ``site_a_ref4mw/openfast_deck_v5/`` instead.

Korean UTF-8 text prints as ``mojibake`` in stdout
  Set ``PYTHONUTF8=1`` before running any script. This enables Python
  UTF-8 mode globally and overrides the Windows cp949 default.

``cython`` / ``scipy`` wheel fails to build
  You are on an unsupported Python version (e.g. 3.13). Reinstall
  with Python 3.12: ``pyenv install 3.12.9 && pyenv local 3.12.9``.

See :doc:`troubleshooting` for the complete FAQ.

Next steps
----------

* :doc:`getting_started` -- first Op\ :sup:`3` script
* :doc:`user_manual/index` -- worked examples for each foundation mode
* :doc:`technical_reference` -- mathematical formulation
* :doc:`verification` -- V&V evidence base
