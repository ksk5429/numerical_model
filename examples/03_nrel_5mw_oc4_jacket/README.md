# Example 03: NREL 5MW OC4 Jacket

**Tier:** Tier 1 — Canonical NREL benchmark
**Rotor:** `nrel_5mw_baseline`
**Tower:** `nrel_5mw_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

Multi-member jacket substructure at 50 m water depth.
Validates Op^3's SubDyn bridge for non-monopile geometries. Paired
with Example 9 (SACS NREL OC4 jacket) — the same physical jacket
expressed in two different analysis codes.

## Expected first natural frequency

Published reference: **0.314 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/03_nrel_5mw_oc4_jacket/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

```bash
export OPENFAST_EXE=/path/to/openfast_x64
python examples/03_nrel_5mw_oc4_jacket/run_aeroelastic.py
```

Runs OpenFAST against `nrel_reference/oc4_jacket/5MW_OC4Jckt_DLL_WTurb_WavesIrr_MGrowth.fst`.

## Source attribution

Published reference value: **Popko et al. (2012), OC4 Phase I**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
