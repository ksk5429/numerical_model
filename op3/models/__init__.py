"""
Op^3 validated-model catalog.

Each subpackage of :mod:`op3.models` is a **self-contained dossier**
for one foundation + tower + site combination. A dossier holds:

- ``site.yaml``      — site metadata, coordinates, water depth
- ``geometry.yaml``  — foundation geometry, wall schedule, tower
- ``soil.yaml``      — layered soil profile
- ``vvc.yaml``       — Verification / Validation / Calibration status
- ``build.py``       — script that instantiates the model via the
                       new :mod:`op3.foundations.types` API
- ``tests/``         — per-model pytest modules

Dossiers are the canonical home of dissertation-grade numerical
artefacts. A model is only cleared for use in results chapters when
every acceptance metric in its ``vvc.yaml`` reads ``GREEN``.

Current roster
--------------
+------------------------------+-------------+-------------------------+
| Dossier                      | Foundation  | Status                  |
+==============================+=============+=========================+
| nrel_5mw_oc3_monopile        | Monopile    | RED (skeleton, PR #1)   |
+------------------------------+-------------+-------------------------+
| nrel_5mw_oc4_jacket          | Jacket      | not-started             |
+------------------------------+-------------+-------------------------+
| gunsan_4mw_tripod            | Tripod      | not-started (port legacy|
|                              |             | v1 spine-ribs physics)  |
+------------------------------+-------------+-------------------------+
| nrel_5mw_gunsan_tripod       | Tripod      | not-started             |
+------------------------------+-------------+-------------------------+
"""
