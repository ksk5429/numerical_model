"""
DLC 6.1 parked-configuration deck generator (Task 4).

DLC 6.1 per IEC 61400-3-1 requires the rotor to be parked (pitched
to feather, brakes engaged) at the 50-year extreme wind speed. The
OC3 Tripod r-test template runs in normal-production mode, which
causes the blades to deflect into the tower when the wind speed
exceeds ~30 m/s.

This script derives a parked variant of the committed v5 SiteA
deck (or any OC3-tripod-derived deck) by:

  1. Copying the deck directory to a *_parked sibling
  2. Editing the ElastoDyn input: rotor speed init = 0, azimuth 0,
     pitch = 90 deg, yaw DOF locked, rotor DOFs disabled
  3. Setting CompServo = 0 in the .fst so the Bladed controller does
     not override the pitch
  4. Preserving all other modules (hydro, sub, soildyn) for load
     evaluation

Run:
    python scripts/build_dlc61_parked_deck.py
    python scripts/build_dlc61_parked_deck.py --source oc3_tripod
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


SOURCES = {
    "site_a_v5": REPO_ROOT / "site_a_ref4mw/openfast_deck_v5",
    "oc3_tripod": REPO_ROOT / "tools/r-test_v5/r-test/glue-codes/openfast/"
                   "5MW_OC3Trpd_DLL_WSt_WavesReg",
}


def patch_elastodyn(ed_path: Path) -> None:
    text = ed_path.read_text(errors="replace")

    # Disable all rotor DOFs
    for dof in ("FlapDOF1", "FlapDOF2", "EdgeDOF", "TeetDOF",
                "DrTrDOF", "GenDOF", "YawDOF"):
        text = re.sub(
            rf"^(True|False)(\s+{dof}\b[^\n]*)",
            r"False\g<2>",
            text, flags=re.MULTILINE,
        )

    # Initial conditions: rotor stopped, blades pitched to feather
    replacements = {
        "RotSpeed":  "0.0",
        "BlPitch\\(1\\)": "90.0",
        "BlPitch\\(2\\)": "90.0",
        "BlPitch\\(3\\)": "90.0",
        "Azimuth":   "0.0",
        "NacYaw":    "0.0",
    }
    for key, value in replacements.items():
        text = re.sub(
            rf"^\s*([-\d.Ee+]+)(\s+{key}\b[^\n]*)",
            rf"       {value}\g<2>",
            text, count=1, flags=re.MULTILINE,
        )

    ed_path.write_text(text, encoding="utf-8")


def patch_fst(fst_path: Path) -> None:
    text = fst_path.read_text(errors="replace")
    # CompServo = 0 so the DISCON DLL does not reset pitch
    text = re.sub(
        r"^(\s+)1(\s+CompServo\b[^\n]*)",
        r"\g<1>0\g<2>",
        text, count=1, flags=re.MULTILINE,
    )
    fst_path.write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES.keys()),
                    default="site_a_v5")
    ap.add_argument("--dest", default=None,
                    help="Destination directory (default: <source>_parked)")
    args = ap.parse_args()

    src = SOURCES[args.source]
    if not src.exists():
        print(f"Source deck not found: {src}")
        return 1

    dest = Path(args.dest) if args.dest else src.with_name(src.name + "_parked")
    if dest.exists():
        print(f"Destination already exists, skipping copy: {dest}")
    else:
        shutil.copytree(src, dest)
        print(f"Copied {src.name} -> {dest}")

    # Patch each .dat and .fst in place
    for fst in dest.glob("*.fst"):
        patch_fst(fst)
        print(f"  patched {fst.name} (CompServo=0)")
    for ed in dest.glob("*ElastoDyn*.dat"):
        if "Tower" in ed.name or "blade" in ed.name.lower():
            continue
        patch_elastodyn(ed)
        print(f"  patched {ed.name} (parked ICs)")

    print(f"\nRun with:")
    print(f"  cd {dest}")
    print(f"  ../../tools/openfast/OpenFAST.exe SiteA-Ref4MW.fst")
    return 0


if __name__ == "__main__":
    sys.exit(main())
