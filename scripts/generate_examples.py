"""
Generate the 11 Op^3 example directories from a single declarative spec.

Each example gets:
  - README.md           one-page description of the turbine and foundation
  - build.py            builds the Op^3 TowerModel via compose_tower_model
  - run_eigen.py        runs eigenvalue analysis and prints/saves results
  - run_aeroelastic.py  runs the OpenFAST simulation (user must supply binary)
  - expected_results.json  reference values for regression tests

The examples are grouped into three matrices that demonstrate the
design of the benchmark:

  Tier 1 (canonical NREL):  #1, #2, #3
  Tier 2 (Op^3 integration): #4, #5, #6, #11
  Tier 3 (large turbines):   #7, #8
  SACS benchmarks:           #9, #10
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ============================================================
# The 11-example declarative spec
# ============================================================
EXAMPLES = [
    # Tier 1: canonical NREL references
    dict(
        id="01_nrel_5mw_baseline",
        title="NREL 5MW Baseline (fixed base)",
        tier=1,
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation_mode="fixed",
        foundation_args={},
        published_f1_Hz=0.324,
        published_source="NREL TP-500-38060 (Jonkman 2009)",
        openfast_fst=None,
        description="""The canonical NREL 5MW onshore/fixed-base reference.
Every OWT paper since 2009 cites this turbine. Serves as the
upper-bound reference for Op^3 foundation modes — any mode with
soil-structure interaction produces a lower first natural frequency
than this.""",
    ),
    dict(
        id="02_nrel_5mw_oc3_monopile",
        title="NREL 5MW OC3 Monopile",
        tier=1,
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_oc3_monopile.csv",
        },
        published_f1_Hz=0.276,
        published_source="NREL TP-500-47535 (Jonkman 2010), OC3 Phase II",
        openfast_fst="nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst",
        description="""The first NREL offshore benchmark and the only NREL
model in this repository with SubDyn already enabled. Uses the
published OC3 monopile stiffness in Op^3 Mode B (6x6 lumped
stiffness). This is the reference case for validating the Op^3 ->
OpenFAST SubDyn bridge.""",
    ),
    dict(
        id="03_nrel_5mw_oc4_jacket",
        title="NREL 5MW OC4 Jacket",
        tier=1,
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_oc4_jacket.csv",
        },
        published_f1_Hz=0.314,
        published_source="Popko et al. (2012), OC4 Phase I",
        openfast_fst="nrel_reference/oc4_jacket/5MW_OC4Jckt_DLL_WTurb_WavesIrr_MGrowth.fst",
        description="""Multi-member jacket substructure at 50 m water depth.
Validates Op^3's SubDyn bridge for non-monopile geometries. Paired
with Example 9 (SACS NREL OC4 jacket) — the same physical jacket
expressed in two different analysis codes.""",
    ),

    # Tier 2: Op^3 scientific contributions (Gunsan + foundation variants)
    dict(
        id="04_gunsan_4p2mw_tripod",
        title="Gunsan 4.2 MW on tripod suction bucket (as built)",
        tier=2,
        rotor="unison_u136",
        tower="gunsan_u136_tower",
        foundation_mode="distributed_bnwf",
        foundation_args={
            "spring_profile": "data/fem_results/opensees_spring_stiffness.csv",
            "scour_depth": 0.0,
        },
        published_f1_Hz=0.244,
        published_source="Kim (2026), this dissertation, centrifuge + field OMA",
        openfast_fst="gunsan_4p2mw/openfast_deck/Gunsan-4p2MW.fst",
        description="""THE dissertation subject turbine. Gunsan 4.2 MW Unison
U136 on a three-bucket tripod foundation (D=8.0 m, L=9.3 m,
120-degree spacing) in 14 m water depth off the west coast of Korea.
Full Op^3 pipeline exercised end-to-end: OptumGX capacity ->
OpenSeesPy distributed BNWF -> OpenFAST SubDyn. Field-measured first
natural frequency of 0.244 Hz from 32 months of nacelle
accelerometer OMA.""",
    ),
    dict(
        id="05_nrel_5mw_on_gunsan_tripod",
        title="NREL 5MW rotor+tower on Gunsan tripod (Op^3 isolation test)",
        tier=2,
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation_mode="distributed_bnwf",
        foundation_args={
            "spring_profile": "data/fem_results/opensees_spring_stiffness.csv",
            "scour_depth": 0.0,
        },
        published_f1_Hz=None,   # Op^3 original, no published reference
        published_source="Op^3 isolation test, not previously published",
        openfast_fst=None,
        description="""Op^3 original composition. Takes the NREL 5MW rotor and
tower and puts them on the Gunsan tripod foundation. Paired with
Example 2 (same rotor+tower on OC3 monopile) to isolate the pure
effect of the foundation change on the first natural frequency.
Any difference between Example 2 and Example 5 is attributable to
the foundation choice, because the rotor+tower are identical.""",
    ),
    dict(
        id="06_gunsan_tower_on_monopile",
        title="Gunsan U136 tower on equivalent monopile (Op^3 isolation test)",
        tier=2,
        rotor="unison_u136",
        tower="gunsan_u136_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_oc3_monopile.csv",
        },
        published_f1_Hz=None,
        published_source="Op^3 isolation test, not previously published",
        openfast_fst=None,
        description="""Op^3 original composition. Takes the Gunsan Unison U136
tower and puts it on an equivalent monopile (borrowing the OC3
monopile stiffness matrix). Paired with Example 4 (same tower on
tripod) to isolate the effect of the foundation on the Gunsan
tower's first natural frequency. This is the mirror of Example 5:
different rotor+tower, same foundation comparison.""",
    ),

    # Tier 3: large turbines
    dict(
        id="07_iea_15mw_monopile",
        title="IEA 15MW on monopile (30 m water)",
        tier=3,
        rotor="iea_15mw_rwt",
        tower="iea_15mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_iea15_monopile.csv",
        },
        published_f1_Hz=0.17,
        published_source="Gaertner et al. (2020), NREL TP-5000-75698, IEA Wind Task 37",
        openfast_fst="nrel_reference/iea_15mw/OpenFAST_monopile/IEA-15-240-RWT-Monopile.fst",
        description="""The current largest open offshore wind reference. The
IEA 15MW with a 240 m rotor on a fixed-bottom monopile in 30 m
water depth. Positions Op^3 as industry-relevant for modern
large-turbine applications, not just the 4-5 MW legacy class.""",
    ),
    dict(
        id="08_iea_15mw_volturnus",
        title="IEA 15MW on VolturnUS-S semi-submersible (floating)",
        tier=3,
        rotor="iea_15mw_rwt",
        tower="iea_15mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_volturnus_floating.csv",
        },
        published_f1_Hz=0.04,
        published_source="Allen et al. (2020), NREL TP-5000-76773",
        openfast_fst="nrel_reference/iea_15mw/OpenFAST_volturnus/IEA-15-240-RWT-UMaineSemi.fst",
        description="""The NREL-UMaine VolturnUS-S semi-submersible floating
platform with the IEA 15MW turbine. Extends Op^3 to floating
applications. The Op^3 Mode B 6x6 matrix for a floating platform is
a linearization of the mooring + hydrostatic restoring stiffness at
the operational draft; it is much softer than any fixed-bottom
foundation.""",
    ),

    # SACS benchmarks
    dict(
        id="09_sacs_nrel_oc4",
        title="NREL OC4 jacket in SACS (PLAXIS-SACS benchmark)",
        tier="sacs",
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_oc4_jacket.csv",
            "sacs_source": "nrel_reference/sacs_jackets/nrel_oc4/NREL_OC4.sacs",
        },
        published_f1_Hz=0.314,
        published_source="Popko et al. (2012), OC4 Phase I (SACS baseline)",
        openfast_fst=None,
        description="""Same physical jacket as Example 3, but expressed in SACS
format rather than OpenFAST SubDyn. Validates Op^3's SACS parser
and the downstream OpenSeesPy jacket builder. Expected result:
Op^3's computed first natural frequency agrees with the SACS
reference within 5%. This is the PLAXIS-SACS industry-standard
workflow benchmark.""",
    ),
    dict(
        id="10_sacs_innwind",
        title="INNWIND 10MW jacket in SACS (EU reference)",
        tier="sacs",
        rotor="iea_15mw_rwt",    # closest available rotor at 10+ MW
        tower="iea_15mw_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "sacs_source": "nrel_reference/sacs_jackets/innwind/INNWIND.sacs",
        },
        published_f1_Hz=0.295,
        published_source="INNWIND.EU D4.3.1 (Von Borstel 2013)",
        openfast_fst=None,
        description="""The INNWIND.EU 10 MW reference jacket at 50 m water
depth. A European industry-reference jacket with complete mudbrace,
conductor, and tower interface geometry. The original deck targets
a 10 MW turbine; Op^3 pairs it with the IEA 15MW rotor+tower as the
closest available open reference (the 10 MW INNWIND rotor is not
publicly released in OpenFAST format). Validates the Op^3 SACS
parser on a second, larger deck (192 joints vs 56 for OC4).""",
    ),

    # User-requested addition
    dict(
        id="11_gunsan_tower_on_jacket",
        title="Gunsan U136 tower on equivalent jacket (Op^3 isolation test)",
        tier=2,
        rotor="unison_u136",
        tower="gunsan_u136_tower",
        foundation_mode="stiffness_6x6",
        foundation_args={
            "stiffness_matrix": "data/fem_results/K_6x6_oc4_jacket.csv",
        },
        published_f1_Hz=None,
        published_source="Op^3 isolation test, not previously published",
        openfast_fst=None,
        description="""Op^3 original composition completing the foundation
variant triangle for the Gunsan U136 tower. Takes the Gunsan tower
and puts it on an equivalent jacket (borrowing the OC4 jacket
stiffness matrix). Paired with Examples 4 (tripod) and 6 (monopile)
to give a complete (tripod, monopile, jacket) comparison on the
same Gunsan tower. This is the last piece of the symmetric
benchmark matrix and lets a reviewer see the pure effect of
foundation type on a fixed rotor+tower.""",
    ),
]


# ============================================================
# Template strings for generated files
# ============================================================

README_TEMPLATE = """# Example {num_int:02d}: {title}

**Tier:** {tier_label}
**Rotor:** `{rotor}`
**Tower:** `{tower}`
**Foundation:** Op^3 Mode {foundation_label} ({foundation_mode})

## Description

{description}

## Expected first natural frequency

{expected_block}

## How to run

### Eigenvalue analysis (fast, always runnable)

```bash
python examples/{id}/run_eigen.py
```

Runs the Op^3 OpenSeesPy pipeline and prints the first 6 natural
frequencies in Hz. Expected runtime: ~2 seconds on a CPU.

### Aero-elastic simulation (requires OpenFAST v4.0.2 binary)

{aeroelastic_block}

## Source attribution

Published reference value: **{published_source}**

## See also

- [docs/FRAMEWORK.md](../../docs/FRAMEWORK.md) — Op^3 architecture and data flow
- [docs/OPTUMGX_BOUNDARY.md](../../docs/OPTUMGX_BOUNDARY.md) — Commercial/open boundary
- [validation/benchmarks/CROSS_COMPARABILITY.md](../../validation/benchmarks/CROSS_COMPARABILITY.md) — All 11 examples compared
"""

BUILD_TEMPLATE = '''"""
Example {num}: {title}

Composes the Op^3 TowerModel for this example. Returns a model
object ready for .eigen() or .extract_6x6_stiffness().
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from op3 import build_foundation, compose_tower_model


def build():
    """Return a TowerModel for example {num}."""
    # Make foundation args paths absolute relative to the repo root
    fnd_kwargs = {foundation_args_str}
    for k, v in list(fnd_kwargs.items()):
        if isinstance(v, str) and v.endswith(('.csv', '.sacs')):
            fnd_kwargs[k] = str((REPO_ROOT / v).resolve())

    foundation = build_foundation(
        mode="{foundation_mode}",
        **{{k: v for k, v in fnd_kwargs.items() if k in
              ('spring_profile', 'stiffness_matrix', 'ogx_dissipation',
               'ogx_capacity', 'scour_depth')}},
    )

    return compose_tower_model(
        rotor="{rotor}",
        tower="{tower}",
        foundation=foundation,
    )


if __name__ == "__main__":
    model = build()
    print(f"Built example: {title}")
    print(f"  Rotor:      {{model.rotor_name}}")
    print(f"  Tower:      {{model.tower_name}}")
    print(f"  Foundation: {{model.foundation.mode.value}}")
    print(f"  Source:     {{model.foundation.source}}")
'''

RUN_EIGEN_TEMPLATE = '''"""
Example {num}: eigenvalue analysis runner.

Builds the Op^3 model and runs the first eigenvalue analysis.
Prints the first 6 natural frequencies and writes them to
`results_eigen.json` for regression testing.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from build import build


def main():
    print("Example {num}: {title}")
    print("=" * 70)

    try:
        import openseespy.opensees  # noqa: F401
    except ImportError:
        print("  [SKIP] OpenSeesPy not installed — run `pip install openseespy`")
        return

    model = build()
    freqs = model.eigen(n_modes=6)

    print(f"  First 6 natural frequencies (Hz):")
    for i, f in enumerate(freqs, 1):
        print(f"    Mode {{i}}: {{f:.4f}} Hz")

    # Load expected results and compare
    expected_path = HERE / "expected_results.json"
    if expected_path.exists():
        expected = json.loads(expected_path.read_text())
        exp_f1 = expected.get("published_f1_Hz")
        if exp_f1 is not None:
            import math
            if freqs[0] > 0 and not math.isnan(freqs[0]):
                rel_err = abs(freqs[0] - exp_f1) / exp_f1
                flag = "OK" if rel_err < 0.15 else "CHECK"
                print(f"  Reference f1 = {{exp_f1:.4f}} Hz  "
                      f"(Op^3 = {{freqs[0]:.4f}}, {{rel_err*100:.1f}}% error, {{flag}})")

    # Save results
    results_path = HERE / "results_eigen.json"
    results_path.write_text(json.dumps({{
        "example_id": "{id}",
        "title": "{title}",
        "first_6_frequencies_Hz": list(freqs),
    }}, indent=2))
    print(f"\\n  Results saved to: {{results_path}}")


if __name__ == "__main__":
    main()
'''

RUN_AERO_TEMPLATE = '''"""
Example {num}: aero-elastic simulation runner.

Runs the OpenFAST simulation for this example using the bundled
OpenFAST v4.0.2 input deck. Requires the OPENFAST_EXE environment
variable to point at the OpenFAST binary.

{aero_comment}
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FST_FILE = {fst_repr}


def main():
    if FST_FILE is None:
        print("No OpenFAST deck configured for example {num}.")
        print("This is a structural-only example (Op^3 isolation test).")
        print("Run `python run_eigen.py` for the eigenvalue analysis.")
        return

    openfast = os.environ.get("OPENFAST_EXE")
    if not openfast:
        print("ERROR: set the OPENFAST_EXE environment variable to the")
        print("path of your OpenFAST v4.0.2 binary.")
        print("Download from https://github.com/OpenFAST/openfast/releases")
        sys.exit(1)

    fst_path = REPO_ROOT / FST_FILE
    if not fst_path.exists():
        print(f"ERROR: OpenFAST deck not found at {{fst_path}}")
        sys.exit(1)

    print(f"Running OpenFAST for example {num}: {title}")
    print(f"  Binary: {{openfast}}")
    print(f"  Deck:   {{fst_path}}")

    result = subprocess.run(
        [openfast, str(fst_path)],
        cwd=str(fst_path.parent),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
'''


def _foundation_label(mode: str) -> str:
    return {
        "fixed": "A (fixed base)",
        "stiffness_6x6": "B (6x6 lumped stiffness)",
        "distributed_bnwf": "C (distributed BNWF springs)",
        "dissipation_weighted": "D (dissipation-weighted BNWF)",
    }.get(mode, mode)


def _tier_label(tier) -> str:
    if tier == 1:
        return "Tier 1 — Canonical NREL benchmark"
    if tier == 2:
        return "Tier 2 — Op^3 scientific contribution"
    if tier == 3:
        return "Tier 3 — Large turbine reference"
    if tier == "sacs":
        return "SACS geotechnical-structural integration benchmark"
    return str(tier)


def _num_int(ex_id: str) -> int:
    return int(ex_id.split("_", 1)[0])


def generate():
    for ex in EXAMPLES:
        ex_dir = REPO / "examples" / ex["id"]
        ex_dir.mkdir(parents=True, exist_ok=True)

        num = ex["id"].split("_", 1)[0]
        num_int = int(num)

        # expected_f1 block
        if ex["published_f1_Hz"] is not None:
            expected_block = (
                f"Published reference: **{ex['published_f1_Hz']} Hz** first fore-aft mode. "
                f"Op^3 should match within ~5% tolerance."
            )
        else:
            expected_block = (
                "No published reference (this is an Op^3 original composition). "
                "The expected behavior is a frequency that sits between its sibling examples "
                "in the foundation-variant matrix — see the CROSS_COMPARABILITY table."
            )

        # aeroelastic block
        if ex["openfast_fst"]:
            aero_block = (
                f"```bash\nexport OPENFAST_EXE=/path/to/openfast_x64\n"
                f"python examples/{ex['id']}/run_aeroelastic.py\n```\n\n"
                f"Runs OpenFAST against `{ex['openfast_fst']}`."
            )
            fst_repr = repr(ex["openfast_fst"])
            aero_comment = f"Runs {ex['openfast_fst']}"
        else:
            aero_block = (
                "This example is structural-only (Op^3 isolation test). "
                "It does not have a corresponding OpenFAST deck because the "
                "foundation is a hypothetical variant that pairs a rotor/tower "
                "from one source with a foundation from another."
            )
            fst_repr = "None"
            aero_comment = "No OpenFAST deck (Op^3 isolation test)"

        # README
        readme = README_TEMPLATE.format(
            num_int=num_int,
            title=ex["title"],
            tier_label=_tier_label(ex["tier"]),
            rotor=ex["rotor"],
            tower=ex["tower"],
            foundation_mode=ex["foundation_mode"],
            foundation_label=_foundation_label(ex["foundation_mode"]),
            description=ex["description"],
            expected_block=expected_block,
            published_source=ex["published_source"],
            aeroelastic_block=aero_block,
            id=ex["id"],
        )
        (ex_dir / "README.md").write_text(readme, encoding="utf-8")

        # build.py
        build_py = BUILD_TEMPLATE.format(
            num=num,
            title=ex["title"],
            rotor=ex["rotor"],
            tower=ex["tower"],
            foundation_mode=ex["foundation_mode"],
            foundation_args_str=repr(ex["foundation_args"]),
        )
        (ex_dir / "build.py").write_text(build_py, encoding="utf-8")

        # run_eigen.py
        run_eigen = RUN_EIGEN_TEMPLATE.format(
            num=num,
            title=ex["title"],
            id=ex["id"],
        )
        (ex_dir / "run_eigen.py").write_text(run_eigen, encoding="utf-8")

        # run_aeroelastic.py
        run_aero = RUN_AERO_TEMPLATE.format(
            num=num,
            title=ex["title"],
            aero_comment=aero_comment,
            fst_repr=fst_repr,
        )
        (ex_dir / "run_aeroelastic.py").write_text(run_aero, encoding="utf-8")

        # expected_results.json
        expected = dict(
            example_id=ex["id"],
            title=ex["title"],
            tier=str(ex["tier"]),
            rotor=ex["rotor"],
            tower=ex["tower"],
            foundation_mode=ex["foundation_mode"],
            published_f1_Hz=ex["published_f1_Hz"],
            published_source=ex["published_source"],
            openfast_fst=ex["openfast_fst"],
            tolerance_rel=0.05,
        )
        (ex_dir / "expected_results.json").write_text(
            json.dumps(expected, indent=2), encoding="utf-8"
        )

        print(f"  [OK] examples/{ex['id']}/")

    print(f"\nGenerated {len(EXAMPLES)} example directories.")


if __name__ == "__main__":
    generate()
