# Paper extraction backlog

The Op^3 framework includes three benchmark harnesses whose
*infrastructure* is in place but whose *numerical reference values*
have not yet been extracted from the source publications. The harnesses
are designed so that filling in the reference values requires no code
change -- the comparison status flips automatically from
`AWAITING_VERIFY` to `PASS` or `FAIL`.

This document is the master TODO for that extraction work.

## 1. PISA test pile cross-validation

**Harness:** [`scripts/pisa_cross_validation.py`](../../scripts/pisa_cross_validation.py)
**JSON output:** [`pisa_cross_validation.json`](pisa_cross_validation.json)

| Case | Op^3 K_xx (N/m) | Reference source | Page / Table |
|------|-----------------|------------------|--------------|
| Dunkirk DM7 (sand)  | 9.45e+09 | Byrne et al. (2020) | Geotechnique 70(11), Fig 8 / Tab 4 |
| Cowden CM1 (clay)   | 8.95e+08 | Burd et al. (2020)  | Geotechnique 70(11), Fig 9 / Tab 4 |
| Borkum Riffgrund-1  | 2.84e+10 | Murphy et al. (2018) | Marine Structures 60, 263-281 |

**To resolve:** open each paper, locate the back-analysed initial
small-strain lateral head stiffness in the cited table, and write the
value into the `reference_Kxx_N_per_m` field of the corresponding
`CrossValCase` in `pisa_cross_validation.py`. Do the same for `K_rxrx`.

## 2. OC6 Phase II benchmark

**Harness:** [`scripts/oc6_phase2_benchmark.py`](../../scripts/oc6_phase2_benchmark.py)
**JSON output:** [`oc6_phase2_benchmark.json`](oc6_phase2_benchmark.json)

| Case | Quantity | Op^3 prediction | Reference source |
|------|----------|-----------------|------------------|
| LC1.1 K_xx          | initial small-strain     | 3.13e+10 N/m  | Bergua 2021 Tab 4 |
| LC1.1 K_rxrx        | initial small-strain     | 1.74e+13 Nm/rad | Bergua 2021 Tab 4 |
| LC1.1 K_xrx         | lateral-rocking coupling | -6.56e+11 N   | Bergua 2021 Tab 4 |
| LC2.1 cyclic ratio  | gamma=1e-4               | 0.500         | Bergua 2021 Fig 12 |
| LC2.2 u_x_peak      | 0.1 Hz @ 5 MN load       | 1.6e-04 m     | Bergua 2021 Sec 4.2 |
| LC2.3 system f1     | NREL 5 MW + OC3 + soil   | 0.281 Hz      | Bergua 2021 Tab 6 |

Source paper: Bergua, R., Robertson, A., Jonkman, J., & Platt, A.
(2021). "Specification Document for OC6 Phase II: Verification of an
Advanced Soil-Structure Interaction Model for Offshore Wind Turbines".
NREL/TP-5000-79989. https://doi.org/10.2172/1811648

**To resolve:** download the NREL technical report (open access),
extract the six numerical references, write them into the `CASES`
list in `oc6_phase2_benchmark.py`. Each entry has a `reference_value`
field that defaults to `None` (= AWAITING_VERIFY).

## 3. Why this is captured here rather than fabricated

The project memory rule
[feedback_session_2026_04_01_final.md](../../../../memory/feedback_session_2026_04_01_final.md)
records: *"Never fabricate measured data. Check for existing MC
databases first."* This applies to PISA back-analyses and OC6
benchmark numbers as much as it does to centrifuge measurements.
The harnesses run end-to-end *without* the reference numbers because
the Op^3 prediction is the only side that comes from this codebase;
the reference side comes from the literature and must be cited
verbatim from the source.

The cost of waiting until the actual numbers are extracted is small
(a few hours of focused PDF reading) and the cost of mis-citing or
making up numbers is large (publication-grade claims that would not
survive review).
