Troubleshooting
===============

Common issues and their solutions.

The web application shows an error card
---------------------------------------

**Symptom:** The 3D Viewer tab shows "Could not build the default
scene" instead of the foundation geometry.

**Cause:** The ``OP3_PHD_ROOT`` environment variable is not set or
points to a directory that does not contain the required private
data files (``tower_segments.csv``, ``tower_metadata.yaml``).

**Fix:** Set the environment variable to point at the private data
tree before launching the application::

    # Windows (cmd)
    set OP3_PHD_ROOT=C:\path\to\private\data
    python -m op3_viz.dash_app.app

Port 8050 is already in use
----------------------------

Another application (or a previous Op^3 instance) is listening on
port 8050. Either close the other application or specify a different
port in the launch command.

OpenSeesPy import fails
------------------------

On Linux, OpenSeesPy requires the companion wheel
``openseespylinux``::

    pip install openseespylinux

On Windows, ``openseespy`` installs directly via pip.

PDF report generation fails
----------------------------

Quarto must be installed. Download from https://quarto.org/ and
ensure it is on the system PATH.

Release audit shows FAIL on openfast_runner
-------------------------------------------

The OpenFAST binary (``OpenFAST.exe`` on Windows) must be on the
system PATH or its location must be specified in the runner
configuration. This is an infrastructure requirement, not a
test-logic error.

Sequential tracker shows flat posterior
---------------------------------------

If the posterior does not tighten across epochs, check that the
sensor readings are actually changing between epochs. Identical
readings produce identical likelihoods, and the posterior does not
update.
