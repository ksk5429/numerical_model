Getting started
===============

Installation
------------

.. code-block:: bash

   git clone https://github.com/ksk5429/numerical_model.git
   cd numerical_model
   pip install -r requirements.txt

   # Optional: install the OpenFAST v5 binary for end-to-end simulation
   bash tools/openfast/install.sh

Bootstrapping the v5 r-test
---------------------------

The end-to-end OpenFAST runner needs the v5.0.0 r-test directory
(provides the OC3 Tripod template + DISCON.dll). Clone it once:

.. code-block:: bash

   mkdir -p tools/r-test_v5 && cd tools/r-test_v5
   git clone --depth=1 --branch v5.0.0 https://github.com/OpenFAST/r-test.git

First run
---------

.. code-block:: python

   from op3 import build_foundation, compose_tower_model

   foundation = build_foundation(mode="fixed")
   model = compose_tower_model(
       rotor="nrel_5mw_baseline",
       tower="nrel_5mw_oc3_tower",
       foundation=foundation,
   )
   freqs = model.eigen(n_modes=3)
   print(f"f1 = {freqs[0]:.4f} Hz  (expect 0.275 Hz)")

End-to-end OpenFAST run
-----------------------

.. code-block:: bash

   python scripts/run_openfast.py site_a
   python scripts/run_dlc11_partial.py --tmax 5
   python scripts/run_dlc61_parked.py --vmax 50

Verification
------------

.. code-block:: bash

   python tests/test_code_verification.py
   python tests/test_pisa.py
   python tests/test_uq.py
   python tests/test_reproducibility.py
   python scripts/calibration_regression.py
   python scripts/dnv_st_0126_conformance.py --all

Each test prints a numbered status line for every falsification gate
and exits 0 only if all gates pass.
