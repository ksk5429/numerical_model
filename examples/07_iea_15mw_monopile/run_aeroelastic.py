"""
Example 07: aero-elastic simulation runner.

Runs the OpenFAST simulation for this example using the bundled
OpenFAST v4.0.2 input deck. Requires the OPENFAST_EXE environment
variable to point at the OpenFAST binary.

Runs nrel_reference/iea_15mw/OpenFAST_monopile/IEA-15-240-RWT-Monopile.fst
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FST_FILE = 'nrel_reference/iea_15mw/OpenFAST_monopile/IEA-15-240-RWT-Monopile.fst'


def main():
    if FST_FILE is None:
        print("No OpenFAST deck configured for example 07.")
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
        print(f"ERROR: OpenFAST deck not found at {fst_path}")
        sys.exit(1)

    print(f"Running OpenFAST for example 07: IEA 15MW on monopile (30 m water)")
    print(f"  Binary: {openfast}")
    print(f"  Deck:   {fst_path}")

    result = subprocess.run(
        [openfast, str(fst_path)],
        cwd=str(fst_path.parent),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
