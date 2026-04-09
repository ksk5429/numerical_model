"""
Op^3 visualization package (v0.5 roadmap).

Two complementary interfaces built on top of the headless Op^3
framework:

* ``op3_viz.dash_app``  -- user-friendly Dash web UI at localhost:8050
                           for engaging with Op^3 results interactively
* ``op3_viz.vtk_scene`` -- PyVista / VTK 3D visualization with real
                           dimensions and stress / strain / dissipation
                           field overlays

Both import the Op^3 core via the public API
(``op3.build_foundation``, ``op3.compose_tower_model``,
``op3.data_sources.*``, ``op3.uq.*``) and never duplicate data
or algorithms.

Install the optional extras:

    pip install -e ".[viz]"

which pulls in dash, plotly, pyvista, vtk.
"""
__all__ = ["dash_app", "vtk_scene"]
