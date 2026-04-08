# Example 09: NREL OC4 jacket in SACS (PLAXIS-SACS benchmark)

**Tier:** SACS geotechnical-structural integration benchmark
**Rotor:** `nrel_5mw_baseline`
**Tower:** `nrel_5mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

Same physical jacket as Example 3, but expressed in SACS
format rather than OpenFAST SubDyn. Validates Op^3's SACS parser
and the downstream OpenSeesPy jacket builder. Expected result:
Op^3's computed first natural frequency agrees with the SACS
reference within 5%. This is the PLAXIS-SACS industry-standard
workflow benchmark.

## Expected first natural frequency

Published reference: **0.314 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/09_sacs_nrel_oc4/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

This example is structural-only (Op^3 isolation test). It does not have a corresponding OpenFAST deck because the foundation is a hypothetical variant that pairs a rotor/tower from one source with a foundation from another.

## Source attribution

Published reference value: **Popko et al. (2012), OC4 Phase I (SACS baseline)**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
