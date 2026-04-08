---
name: Calibration request
about: Add a new turbine / site to the calibration regression
title: "[CALIB] "
labels: calibration
assignees: ksk5429
---

## Turbine identification

- Manufacturer & model:
- Rated power (MW):
- Rotor diameter (m):
- Hub height (m):
- Foundation type: monopile / tripod / jacket / suction-bucket / floating

## Reference frequency

- f1 (Hz):
- Source: (paper / report / field measurement, with full citation)
- Boundary condition: fixed-base / monopile-soil / etc.
- Tolerance band requested:

## Available input data

- [ ] OpenFAST ElastoDyn deck (or equivalent)
- [ ] Tower distributed mass + EI
- [ ] RNA mass + inertia
- [ ] Soil profile / foundation stiffness
- [ ] Field-measured natural frequency

## What you're asking for

- [ ] Add to `scripts/calibration_regression.py` REFERENCES catalog
- [ ] Add to `examples/` as a new build.py
- [ ] Run V&V audit (DNV-ST-0126 + IEC 61400-3)
