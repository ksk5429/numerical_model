# Example 06: Gunsan U136 tower on equivalent monopile (Op^3 isolation test)

**Tier:** Tier 2 — Op^3 scientific contribution
**Rotor:** `unison_u136`
**Tower:** `gunsan_u136_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

Op^3 original composition. Takes the Gunsan Unison U136
tower and puts it on an equivalent monopile (borrowing the OC3
monopile stiffness matrix). Paired with Example 4 (same tower on
tripod) to isolate the effect of the foundation on the Gunsan
tower's first natural frequency. This is the mirror of Example 5:
different rotor+tower, same foundation comparison.

## Expected first natural frequency

No published reference (this is an Op^3 original composition). The expected behavior is a frequency that sits between its sibling examples in the foundation-variant matrix — see the CROSS_COMPARABILITY table.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/06_gunsan_tower_on_monopile/run_eigen.py
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
