# SACS Jacket Reference Decks

This directory contains two reference offshore wind turbine jacket
substructure models expressed in **SACS** (Structural Analysis
Computer System, Bentley) input format. These are geotechnical-
structural integration benchmarks used by the Op^3 framework to
validate its OpenSeesPy jacket implementation against an industry-
standard analysis code that is commonly paired with PLAXIS for
soil-structure interaction.

## Why SACS decks matter for Op^3

SACS is the dominant commercial code for offshore fixed-bottom
substructure analysis in the oil-and-gas and offshore-wind
industries. The typical industry workflow is:

```
PLAXIS (3D FE soil) --> SACS (jacket structure) --> OpenFAST (rotor)
```

This is structurally equivalent to the Op^3 workflow:

```
OptumGX (3D FE soil) --> OpenSeesPy (jacket structure) --> OpenFAST (rotor)
```

The two workflows should produce the same jacket natural frequencies,
pushover capacities, and 6x6 foundation stiffness matrices when
applied to the same physical problem. The SACS decks in this
directory provide the industry-standard reference that Op^3's
OpenSeesPy jacket model must match within engineering tolerance
(~5% on first natural frequency, ~10% on 6x6 K matrix diagonal
entries).

## Files

### `innwind/INNWIND.sacs`

- **Source:** INNWIND.EU Deliverable D4.3.1 "Innovative design of a
  10 MW offshore wind turbine support structure" (2013-2017)
  and supporting SACS reference deck provided by the DTU Wind
  Energy consortium.
- **Turbine:** INNWIND reference 10 MW offshore wind turbine
- **Substructure:** 4-legged jacket, ~50 m water depth (tower
  interface at +20.4 m MSL, seabed at -50 m)
- **Lines:** 974
- **Licence:** open research use (INNWIND.EU was EU-FP7 funded,
  deliverables are public domain per the EU research funding rules
  applicable at the time of publication)
- **Reference:**
  https://www.innwind.eu/publications/deliverable-reports
- **Use in Op^3:** Example 10 "INNWIND Jacket" — tests the
  OpenSeesPy jacket-assembly builder against a 4-legged jacket
  with braces, conductors, and seabed interface.

### `nrel_oc4/NREL_OC4.sacs`

- **Source:** NREL OC4 (Offshore Code Comparison Collaboration,
  Continuation) jacket case 3 SACS deck, distributed with the
  Bentley SACS academic example set
- **Turbine:** NREL 5 MW baseline on OC4 jacket (seabed at -42.5 m)
- **Substructure:** 4-legged jacket, X-bracing, mudline transition
  piece
- **Lines:** 450
- **Licence:** NREL/Apache 2.0 for the turbine definition; the
  SACS deck format itself is a plain-text representation and
  contains no copyrightable expression beyond the structural
  parameters
- **Reference:**
  https://www.nrel.gov/wind/nwtc/oc4.html
  Popko, W. et al. (2012). Offshore code comparison collaboration
  continuation (OC4), Phase I — Results of coupled simulations of
  an offshore wind turbine with jacket support structure.
  *Journal of Ocean and Wind Energy*.
- **Use in Op^3:** Example 9 "PLAXIS-SACS Example (NREL Jacket
  #3)" — the reference jacket for validating Op^3's OpenSeesPy
  jacket implementation against published SACS/PLAXIS results.
  This is **also the same physical jacket** as Example 3
  (NREL 5MW OC4 Jacket in OpenFAST r-test format), so Examples 3
  and 9 are paired: one running the jacket in OpenFAST SubDyn
  (Example 3), the other running it in SACS (Example 9), both
  targeting the same natural frequencies and mode shapes.

## Op^3's SACS parser

Op^3 includes a read-only SACS parser at
[`../../op3/sacs_interface/`](../../op3/sacs_interface/) that
reads a `.sacs` deck and extracts:

- Joint coordinates (JOINT cards)
- Member connectivity (MEMBER cards)
- Section properties (SECT + GRUP cards)
- Load cases (LOAD + LCOMB cards)
- Seabed elevation (from LDOPT header)

The parser produces a neutral JSON representation that the Op^3
OpenSeesPy jacket builder can consume. The round trip
`SACS -> JSON -> OpenSeesPy -> eigen analysis` is demonstrated in
[`examples/09_sacs_nrel_oc4/build.py`](../../examples/09_sacs_nrel_oc4/build.py)
and [`examples/10_sacs_innwind/build.py`](../../examples/10_sacs_innwind/build.py).

Op^3 does **not** include a SACS writer — the parser is
intentionally one-way, because the purpose is to consume
published SACS decks as benchmarks, not to generate new ones.
Users who need a SACS writer should use the Bentley SACS tool
directly (academic licenses are available from Bentley).

## Verification expectation

For both SACS decks, the first fore-aft natural frequency computed
by Op^3's OpenSeesPy jacket model should agree with the published
SACS reference to within 5%. Specifically:

| Deck          | SACS reference f1 (Hz) | Op^3 target | Tolerance |
|---------------|:---------------------:|:------------:|:---------:|
| NREL OC4      | ~0.314                | ~0.314       | ± 5%      |
| INNWIND 10MW  | ~0.295                | ~0.295       | ± 5%      |

The SACS reference values are from the respective published papers
and are redocumented in each example's `expected_results.json`.
A regression test in [`tests/test_sacs_parsers.py`](../../tests/test_sacs_parsers.py)
asserts the Op^3-computed value matches the reference within
tolerance.

## License summary

- INNWIND deck: EU-FP7 public research deliverable, redistributable
  for research use with attribution.
- NREL OC4 deck: NREL/Apache 2.0 per the underlying turbine
  definition; the SACS input format itself is descriptive.
- Both files are redistributed here under the repository's MIT
  license, with original attribution preserved in this README.

If you are the rights holder of either file and object to
redistribution, please open an issue at
https://github.com/ksk5429/numerical_model/issues and the file will
be removed immediately.
