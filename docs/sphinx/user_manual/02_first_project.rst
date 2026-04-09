First Project
=============

Your first Op^3 session walks from install to a working analysis of
a reference wind turbine foundation. This chapter uses the NREL 5 MW
sample project because it requires no proprietary data.

Launch the application
----------------------

.. code-block:: bash

    python -m op3_viz.dash_app.app

Open ``http://127.0.0.1:8050/`` in any browser. You should see six
tabs: 3D Viewer, Bayesian Scour, Mode D, PCE Surrogate, DLC 1.1
Time-series, and Compliance & Actions.

Open the NREL 5 MW sample project
----------------------------------

.. code-block:: python

    from op3_viz.project import load
    p = load("sample_projects/nrel_5mw_oc3_monopile.op3proj")
    print(p)

Run a headless eigenvalue analysis
-----------------------------------

.. code-block:: python

    from op3 import build_foundation, compose_tower_model

    foundation = build_foundation(mode="stiffness_6x6")
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=foundation,
        damping_ratio=0.01,
    )
    freqs = model.eigen(n_modes=6)
    print(freqs)

The first fore-aft bending frequency is approximately 0.32 Hz,
matching the published OC3 reference within 0.4 %.

Cross-compare foundation modes
-------------------------------

.. code-block:: python

    from op3 import cross_compare

    results = cross_compare(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        scour_levels=[0.0, 0.5, 1.0, 1.5, 2.0],
    )

Save your own project
---------------------

.. code-block:: python

    from op3_viz.project import Project, save
    p = Project.new(name="My OWT study")
    p.turbine.reference = "nrel_5mw_baseline"
    p.foundation.mode = "distributed_bnwf"
    p.foundation.scour_m = 1.5
    save(p, "my_first_project.op3proj")

Generate a report
-----------------

.. code-block:: python

    from op3_viz.project import load
    from op3_viz.report import build_report

    proj = load("my_first_project.op3proj")
    produced = build_report(proj, output_dir="reports/")
