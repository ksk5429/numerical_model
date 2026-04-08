# Example 01: NREL 5MW Baseline (fixed base)

**Tier:** Tier 1 — Canonical NREL benchmark
**Rotor:** `nrel_5mw_baseline`
**Tower:** `nrel_5mw_tower`
**Foundation:** Op^3 Mode A (fixed base) (fixed)

## Description

The canonical NREL 5MW onshore/fixed-base reference.
Every OWT paper since 2009 cites this turbine. Serves as the
upper-bound reference for Op^3 foundation modes — any mode with
soil-structure interaction produces a lower first natural frequency
than this.

## Expected first natural frequency

Published reference: **0.324 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/01_nrel_5mw_baseline/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

This example is structural-only (Op^3 isolation test). It does not have a corresponding OpenFAST deck because the foundation is a hypothetical variant that pairs a rotor/tower from one source with a foundation from another.

## Source attribution

Published reference value: **NREL TP-500-38060 (Jonkman 2009)**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
