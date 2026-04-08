# Example 08: IEA 15MW on VolturnUS-S semi-submersible (floating)

**Tier:** Tier 3 — Large turbine reference
**Rotor:** `iea_15mw_rwt`
**Tower:** `iea_15mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

The NREL-UMaine VolturnUS-S semi-submersible floating
platform with the IEA 15MW turbine. Extends Op^3 to floating
applications. The Op^3 Mode B 6x6 matrix for a floating platform is
a linearization of the mooring + hydrostatic restoring stiffness at
the operational draft; it is much softer than any fixed-bottom
foundation.

## Expected first natural frequency

Published reference: **0.04 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/08_iea_15mw_volturnus/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

```bash
export OPENFAST_EXE=/path/to/openfast_x64
python examples/08_iea_15mw_volturnus/run_aeroelastic.py
```

Runs OpenFAST against `nrel_reference/iea_15mw/OpenFAST_volturnus/IEA-15-240-RWT-UMaineSemi.fst`.

## Source attribution

Published reference value: **Allen et al. (2020), NREL TP-5000-76773**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
