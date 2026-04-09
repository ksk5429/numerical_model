"""
Shim entry point: Chapter 8 supervised digital-twin encoder.

Invokes the authoritative training script at
``F:/TREE_OF_THOUGHT/PHD/code/ch8_supervised.py``. The PHD script
trains the dim1 correlation = 0.9976 supervised encoder on the
real 1794-sample OptumGX MC database (which is now accessible via
``op3.uq.encoder_bridge.load_site_a_mc()``).

Run
---
    python scripts/dissertation/run_ch8_supervised_encoder.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from op3.data_sources import get_phd_root


def main():
    root = get_phd_root()
    if root is None:
        print("ERROR: PHD root not found.")
        return 1

    script = root / "code/ch8_supervised.py"
    if not script.exists():
        print(f"ERROR: PHD script missing: {script}")
        return 2

    print("=" * 72)
    print(" Op3 -> PHD shim: Chapter 8 supervised encoder")
    print("=" * 72)
    print(f"  PHD root : {root}")
    print(f"  script   : {script}")
    print()

    env = {**os.environ, "PYTHONUTF8": "1",
           "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    return subprocess.call(
        [sys.executable, str(script)],
        cwd=str(root),
        env=env,
    )


if __name__ == "__main__":
    sys.exit(main())
