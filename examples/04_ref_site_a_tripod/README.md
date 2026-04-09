# Example 04: SiteA 4 MW class on tripod suction bucket (as built)

**Tier:** Tier 2 — Op^3 scientific contribution
**Rotor:** `ref_4mw_owt`
**Tower:** `site_a_rt1_tower`
**Foundation:** Op^3 Mode C (distributed BNWF springs) (distributed_bnwf)

## Description

THE dissertation subject turbine. SiteA 4 MW class RefOEM
RT1 on a three-bucket tripod foundation (dimensions loaded from private data,
120-degree spacing) in 14 m water depth off the west coast of Korea.
Full Op^3 pipeline exercised end-to-end: OptumGX capacity ->
OpenSeesPy distributed BNWF -> OpenFAST SubDyn. Field-measured first
natural frequency of 0.244 Hz from 32 months of nacelle
accelerometer OMA.

## Expected first natural frequency

Published reference: **0.244 Hz** first fore-aft mode. Op^3 should match within ~5% tolerance.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/04_site_a_ref4mw_tripod/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

```bash
export OPENFAST_EXE=/path/to/openfast_x64
python examples/04_site_a_ref4mw_tripod/run_aeroelastic.py
```

Runs OpenFAST against `site_a_ref4mw/openfast_deck/SiteA-Ref4MW.fst`.

## Source attribution

Published reference value: **Kim (2026), this dissertation, centrifuge + field OMA**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
