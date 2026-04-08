"""
Shim entry point: Chapter 8 ablation experiment (frequency tautology refutation).

Invokes ``PHD/code/ch8_ablation_experiment.py`` which refutes the
frequency-tautology concern by running three encoder variants:
  1. baseline with f1_f0 as an input feature   (r = 0.9997)
  2. f1_f0 removed                              (r = 0.9972)
  3. raw capacity only                          (r = 0.9842)

Run
---
    python scripts/dissertation/run_ch8_ablation.py
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

    script = root / "code/ch8_ablation_experiment.py"
    if not script.exists():
        print(f"ERROR: PHD script missing: {script}")
        return 2

    print("=" * 72)
    print(" Op3 -> PHD shim: Chapter 8 ablation experiment")
    print("=" * 72)
    print(f"  script : {script}")
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
