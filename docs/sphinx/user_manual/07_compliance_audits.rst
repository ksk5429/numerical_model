Compliance Audits
=================

Op^3 includes built-in conformance audit scripts for two international
design standards: DNV-ST-0126 (Support structures for wind turbines)
and IEC 61400-3 (Design requirements for offshore wind turbines).

Running audits from the web application
---------------------------------------

In the **Compliance & Actions** tab of the Op^3 web application:

1. Click **Run DNV-ST-0126 audit** to evaluate nine design-code
   clauses against the current project configuration.
2. Click **Run IEC 61400-3 audit** for the IEC conformance check.
3. Click **Dispatch DLC 1.1** to start a six-wind-speed design
   load case sweep in the background.

Each button runs the corresponding Python script in a subprocess
and displays the result as a structured JSON panel.

Running audits from the command line
------------------------------------

.. code-block:: bash

    python scripts/dnv_st_0126_conformance.py --all
    python scripts/iec_61400_3_conformance.py --all

The scripts print a clause-by-clause PASS / FAIL / WAIVER table
and write a JSON summary to the validation output directory.

Interpreting the results
------------------------

Each clause is evaluated independently. A **PASS** means the current
foundation configuration satisfies the clause requirements. A **FAIL**
means a requirement is not met. A **WAIVER** means the clause is
not applicable to the current foundation type or load case.

The one expected flag for the Gunsan demonstrator is the 1P resonance
proximity clause, which is a known characteristic of the turbine
class and is documented in the dissertation Appendix C.
