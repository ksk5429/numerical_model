# Example 02: NREL 5MW OC3 Monopile

**Tier:** Tier 1 — Canonical NREL benchmark
**Rotor:** `nrel_5mw_baseline`
**Tower:** `nrel_5mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

The first NREL offshore benchmark and the only NREL
model in this repository with SubDyn already enabled. Uses the
published OC3 monopile stiffness in Op^3 Mode B (6x6 lumped
stiffness). This is the reference case for validating the Op^3 ->
OpenFAST SubDyn bridge.

## Expected first natural frequency

Published reference: **0.276 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/02_nrel_5mw_oc3_monopile/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

```bash
export OPENFAST_EXE=/path/to/openfast_x64
python examples/02_nrel_5mw_oc3_monopile/run_aeroelastic.py
```

Runs OpenFAST against `nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst`.

## Source attribution

Published reference value: **NREL TP-500-47535 (Jonkman 2010), OC3 Phase II**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
