API Reference
=============

The full Op^3 API is documented via autodoc in the main Sphinx
build. Key entry points are listed below for quick reference.

Core API
--------

.. code-block:: python

    from op3 import build_foundation, compose_tower_model, cross_compare

    # Build a foundation
    f = build_foundation(mode="distributed_bnwf", scour_depth=1.0)

    # Compose a tower model
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=f,
    )

    # Run analyses
    freqs = model.eigen(n_modes=6)
    curve = model.pushover(target_disp_m=1.0)

Web application API
-------------------

.. code-block:: python

    from op3_viz.dash_app.app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=8050)

Project file API
----------------

.. code-block:: python

    from op3_viz.project import Project, save, load
    p = Project.new(name="My Project")
    save(p, "my_project.op3proj")
    p2 = load("my_project.op3proj")

Sequential Bayesian API
-----------------------

.. code-block:: python

    from op3.uq.sequential_bayesian import SequentialBayesianTracker
    tracker = SequentialBayesianTracker()
    result = tracker.update(freq_ratio=0.99, capacity_ratio=0.95, anomaly=True)
    print(tracker.summary())

Decision agent API
------------------

.. code-block:: python

    from op3.agents.decision_agent import DecisionAgent
    agent = DecisionAgent()
    report = agent.run(freq_ratio=0.968, capacity_ratio=0.74, anomaly=True)
    report.save("diagnostic_report.md")
