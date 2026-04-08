# Example 07: IEA 15MW on monopile (30 m water)

**Tier:** Tier 3 — Large turbine reference
**Rotor:** `iea_15mw_rwt`
**Tower:** `iea_15mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

The current largest open offshore wind reference. The
IEA 15MW with a 240 m rotor on a fixed-bottom monopile in 30 m
water depth. Positions Op^3 as industry-relevant for modern
large-turbine applications, not just the 4-5 MW legacy class.

## Expected first natural frequency

Published reference: **0.17 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/07_iea_15mw_monopile/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

```bash
export OPENFAST_EXE=/path/to/openfast_x64
python examples/07_iea_15mw_monopile/run_aeroelastic.py
```

Runs OpenFAST against `nrel_reference/iea_15mw/OpenFAST_monopile/IEA-15-240-RWT-Monopile.fst`.

## Source attribution

Published reference value: **Gaertner et al. (2020), NREL TP-5000-75698, IEA Wind Task 37**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
