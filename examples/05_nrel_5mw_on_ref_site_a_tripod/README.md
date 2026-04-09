# Example 05: NREL 5MW rotor+tower on SiteA tripod (Op^3 isolation test)

**Tier:** Tier 2 — Op^3 scientific contribution
**Rotor:** `nrel_5mw_baseline`
**Tower:** `nrel_5mw_tower`
**Foundation:** Op^3 Mode C (distributed BNWF springs) (distributed_bnwf)

## Description

Op^3 original composition. Takes the NREL 5MW rotor and
tower and puts them on the SiteA tripod foundation. Paired with
Example 2 (same rotor+tower on OC3 monopile) to isolate the pure
effect of the foundation change on the first natural frequency.
Any difference between Example 2 and Example 5 is attributable to
the foundation choice, because the rotor+tower are identical.

## Expected first natural frequency

No published reference (this is an Op^3 original composition). The expected behavior is a frequency that sits between its sibling examples in the foundation-variant matrix — see the CROSS_COMPARABILITY table.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/05_nrel_5mw_on_site_a_tripod/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

This example is structural-only (Op^3 isolation test). It does not have a corresponding OpenFAST deck because the foundation is a hypothetical variant that pairs a rotor/tower from one source with a foundation from another.

## Source attribution

Published reference value: **Op^3 isolation test, not previously published**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
