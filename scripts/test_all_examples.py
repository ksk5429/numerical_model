"""
Smoke test all 11 Op^3 examples to verify the eigenvalue path runs.

This is the honest verification step. It imports each example's
build.py, builds the model, runs eigen, and reports OK/FAIL with the
first 3 frequencies. Does not assert against published values yet —
that comes later after the tower templates are calibrated.

Pushover and transient analyses are flagged as NOT_IMPLEMENTED if
the example's foundation mode does not yet support them.
"""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def import_build(example_dir: Path):
    spec = importlib.util.spec_from_file_location(
        f"build_{example_dir.name}",
        example_dir / "build.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example(example_dir: Path) -> dict:
    result = {
        "id": example_dir.name,
        "build": "FAIL",
        "eigen": "FAIL",
        "freqs": None,
        "error": None,
    }
    try:
        mod = import_build(example_dir)
        model = mod.build()
        result["build"] = "OK"

        freqs = model.eigen(n_modes=3)
        result["eigen"] = "OK"
        result["freqs"] = [round(float(f), 4) for f in freqs]
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    examples = sorted((REPO / "examples").iterdir())
    examples = [e for e in examples if e.is_dir() and (e / "build.py").exists()]

    print(f"Testing {len(examples)} examples")
    print("=" * 70)

    results = []
    for ex_dir in examples:
        print(f"\n[{ex_dir.name}]")
        r = test_example(ex_dir)
        results.append(r)
        print(f"  build: {r['build']}")
        print(f"  eigen: {r['eigen']}")
        if r["freqs"]:
            print(f"  first 3 Hz: {r['freqs']}")
        if r["error"]:
            print(f"  error: {r['error']}")

    n_ok = sum(1 for r in results if r["eigen"] == "OK")
    print()
    print("=" * 70)
    print(f"SUMMARY: {n_ok}/{len(results)} examples pass eigen")
    print("=" * 70)
    for r in results:
        marker = "OK" if r["eigen"] == "OK" else "FAIL"
        f1 = f"{r['freqs'][0]:.3f} Hz" if r["freqs"] else "  -  "
        print(f"  [{marker:4}] {r['id']:<35}  f1 = {f1}")


if __name__ == "__main__":
    main()
