"""
Wire the calibrated Gunsan tower into the v5 Gunsan deck (Task 6).

The committed v4 Gunsan directory ships
``Gunsan-4p2MW_ElastoDyn_tower_calibrated.dat`` with real UNISON
U136 tower dimensions (OD 4.2 m base to 3.5 m top, 28 sections,
S420ML steel). The v5 deck currently inherits the OC3 Tripod tower
file, which has NREL 5 MW geometry.

This script copies the calibrated tower file into the v5 deck and
rewires ``TwrFile`` in the main ElastoDyn file to point at it.

Run:
    python scripts/wire_gunsan_calibrated_tower.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SRC = REPO_ROOT / "gunsan_4p2mw/openfast_deck/Gunsan-4p2MW_ElastoDyn_tower_calibrated.dat"
DST_DIR = REPO_ROOT / "gunsan_4p2mw/openfast_deck_v5"
DST = DST_DIR / "Gunsan-4p2MW_ElastoDyn_Tower_calibrated.dat"
ED_MAIN = DST_DIR / "Gunsan-4p2MW_ElastoDyn.dat"


def main():
    if not SRC.exists():
        print(f"Calibrated tower file not found: {SRC}")
        return 1
    if not ED_MAIN.exists():
        print(f"v5 ElastoDyn main file not found: {ED_MAIN}")
        return 2

    shutil.copy2(SRC, DST)
    print(f"Copied {SRC.name} -> {DST}")

    text = ED_MAIN.read_text(errors="replace")
    new = re.sub(
        r'"[^"]*Tower[^"]*\.dat"\s+(TwrFile\b)',
        f'"{DST.name}"    \\1',
        text, count=1,
    )
    if new == text:
        print("WARNING: TwrFile line not matched; left unchanged")
        return 3
    ED_MAIN.write_text(new, encoding="utf-8")
    print(f"Updated TwrFile reference in {ED_MAIN.name}")
    print("\nVerify with:")
    print("  python scripts/run_openfast.py gunsan --tmax 3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
