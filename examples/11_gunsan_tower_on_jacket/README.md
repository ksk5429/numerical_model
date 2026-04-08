# Example 11: Gunsan U136 tower on equivalent jacket (Op^3 isolation test)

**Tier:** Tier 2 — Op^3 scientific contribution
**Rotor:** `unison_u136`
**Tower:** `gunsan_u136_tower`
**Foundation:** Op^3 Mode B (6x6 lumped stiffness) (stiffness_6x6)

## Description

Op^3 original composition completing the foundation
variant triangle for the Gunsan U136 tower. Takes the Gunsan tower
and puts it on an equivalent jacket (borrowing the OC4 jacket
stiffness matrix). Paired with Examples 4 (tripod) and 6 (monopile)
to give a complete (tripod, monopile, jacket) comparison on the
same Gunsan tower. This is the last piece of the symmetric
benchmark matrix and lets a reviewer see the pure effect of
foundation type on a fixed rotor+tower.

## Expected first natural frequency

No published reference (this is an Op^3 original composition). The expected behavior is a frequency that sits between its sibling examples in the foundation-variant matrix — see the CROSS_COMPARABILITY table.

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/11_gunsan_tower_on_jacket/run_eigen.py
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
