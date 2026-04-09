Case Study - KEPCO engineer assesses scour at a new site
=========================================================

This chapter walks through a complete Op^3 session from the perspective
of a **third-party engineer** -- not the framework author -- who has a
concrete problem to solve. The walk-through is written as a narrative
so a reader can follow the same steps end-to-end without prior Op^3
experience.

The scenario
------------

*Ji-Hoon is a geotechnical engineer at KEPCO Research Institute
(KEPRI). A 4 MW-class offshore wind turbine on a tripod suction
bucket foundation at a demonstration site has reported a 0.5 %
drop in its first-bending natural frequency over the last six
months. The operations team want to know:*

- *Is this scour? If so, how deep?*
- *What is the remaining lateral capacity?*
- *Should we inspect, mitigate, or continue monitoring?*
- *What sensor would give a tighter estimate next?*

*Ji-Hoon has never used Op^3 before.*

Step 1 - Launch the application
-------------------------------

.. code-block:: bash

    pip install op3[viz]
    python -m op3_viz.dash_app.app

Opens ``http://127.0.0.1:8050/`` in Chrome. Six tabs visible.

Step 2 - Create a project
--------------------------

.. code-block:: python

    from op3_viz.project import Project, save
    p = Project.new(name="Demo Site A - scour check")
    p.turbine.reference = "ref_4mw_owt"
    p.foundation.mode = "distributed_bnwf"
    p.soil.su0_kPa = 18.0
    p.soil.k_su_kPa_per_m = 1.9
    save(p, "demo_site_a.op3proj")

Step 3 - Baseline eigenvalue analysis
--------------------------------------

.. code-block:: python

    from op3 import build_foundation, compose_tower_model
    f = build_foundation(mode="distributed_bnwf", scour_depth=0.0)
    model = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="gunsan_u136_tower",
        foundation=f,
        damping_ratio=0.01,
    )
    f0 = model.eigen(n_modes=6)

The first frequency is 0.245 Hz. Site measurement is 0.243 Hz --
a 0.8 % drop. Consistent with shallow scour.

Step 4 - Bayesian scour inference
----------------------------------

Ji-Hoon clicks the Bayesian Scour tab. Posterior:

- Mean scour depth: **1.2 m**
- 90 % credible interval: **[0.5, 2.1] m**
- Effective sample size: 145

Step 5 - Remaining capacity check
----------------------------------

.. code-block:: python

    f_scoured = build_foundation(mode="distributed_bnwf", scour_depth=1.2)
    model_scoured = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="gunsan_u136_tower",
        foundation=f_scoured,
        damping_ratio=0.01,
    )
    curve = model_scoured.pushover(target_disp_m=1.0, n_steps=50)
    peak_kN = max(curve["reaction_kN"])

Peak lateral capacity ~23,000 kN. 50-year storm demand 14,500 kN.
Safety factor 1.59, above the design requirement of 1.30.

**Preliminary conclusion: scour is real but manageable; foundation
still meets the design SF.**

Step 6 - VoI check
-------------------

From the preposterior tree (Ch 7 Section 7.5.3):

- Channel A (frequency): VoI ~ 0.22 C_ref
- Channel B (strain): VoI ~ 0.48 C_ref
- Channel C (statistics): VoI ~ 0.29 C_ref

**Recommendation:** add a strain gauge, not another accelerometer.

Step 7 - Generate report
-------------------------

.. code-block:: python

    from op3_viz.project import load
    from op3_viz.report import build_report
    proj = load("demo_site_a.op3proj")
    produced = build_report(proj, output_dir="reports/")

Report contains project state, eigenvalue result, scour posterior,
pushover curve, and a provenance footer with the Op^3 version and
commit hash.

Step 8 - Compliance audit
--------------------------

In the Compliance and Actions tab, click *Run DNV-ST-0126 audit*.
JSON panel fills with clause-by-clause PASS / FAIL / WAIVER.

Total time from install to signed-off report: approximately 45
minutes.

What this demonstrates
----------------------

- Zero prior Op^3 experience is required
- Site-specific data drives every step
- The decision layer turns an ambiguous signal into a concrete
  prescription
- Reports are self-provenanced via Op^3 version + Zenodo DOI +
  commit hash
