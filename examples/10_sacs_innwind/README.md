# Example 10: INNWIND 10MW jacket in SACS (EU reference)

**Tier:** SACS geotechnical-structural integration benchmark
**Rotor:** `iea_15mw_rwt`
**Tower:** `iea_15mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

The INNWIND.EU 10 MW reference jacket at 50 m water
depth. A European industry-reference jacket with complete mudbrace,
conductor, and tower interface geometry. The original deck targets
a 10 MW turbine; Op^3 pairs it with the IEA 15MW rotor+tower as the
closest available open reference (the 10 MW INNWIND rotor is not
publicly released in OpenFAST format). Validates the Op^3 SACS
parser on a second, larger deck (192 joints vs 56 for OC4).

## Expected first natural frequency

Published reference: **0.295 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/10_sacs_innwind/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

This example is structural-only (Op^3 isolation test). It does not have a corresponding OpenFAST deck because the foundation is a hypothetical variant that pairs a rotor/tower from one source with a foundation from another.

## Source attribution

Published reference value: **INNWIND.EU D4.3.1 (Von Borstel 2013)**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
