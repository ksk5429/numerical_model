"""
Example 04: eigenvalue analysis runner.

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
    print("Example 04: Gunsan 4.2 MW on tripod suction bucket (as built)")
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
        print(f"    Mode {i}: {f:.4f} Hz")

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
                print(f"  Reference f1 = {exp_f1:.4f} Hz  "
                      f"(Op^3 = {freqs[0]:.4f}, {rel_err*100:.1f}% error, {flag})")

    # Save results
    results_path = HERE / "results_eigen.json"
    results_path.write_text(json.dumps({
        "example_id": "04_gunsan_4p2mw_tripod",
        "title": "Gunsan 4.2 MW on tripod suction bucket (as built)",
        "first_6_frequencies_Hz": list(freqs),
    }, indent=2))
    print(f"\n  Results saved to: {results_path}")


if __name__ == "__main__":
    main()
