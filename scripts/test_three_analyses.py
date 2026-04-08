"""
Run eigenvalue + pushover + transient on all 11 Op^3 examples and
report OK/FAIL for each combination. Honest verification of the
three-analysis framework.

Output: validation/benchmarks/three_analyses_results.json
"""
from __future__ import annotations

import importlib.util
import json
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


def test_one(example_dir: Path) -> dict:
    r = {
        "id": example_dir.name,
        "build": None, "eigen": None, "pushover": None, "transient": None,
        "freqs": None, "pushover_max_kN": None, "transient_period_s": None,
        "errors": {},
    }
    try:
        mod = import_build(example_dir)
        model = mod.build()
        r["build"] = "OK"
    except Exception as e:
        r["build"] = "FAIL"
        r["errors"]["build"] = str(e)
        return r

    # Eigenvalue
    try:
        freqs = model.eigen(n_modes=3)
        r["eigen"] = "OK"
        r["freqs"] = [round(float(f), 4) for f in freqs]
    except Exception as e:
        r["eigen"] = "FAIL"
        r["errors"]["eigen"] = str(e)

    # Pushover (rebuild model — pushover wipes domain state)
    try:
        model = mod.build()
        po = model.pushover(target_disp_m=0.5, n_steps=20)
        if po.get("displacement_m"):
            r["pushover"] = "OK"
            r["pushover_max_kN"] = round(max(po["reaction_kN"]) if po["reaction_kN"] else 0, 2)
        elif "error" in po:
            r["pushover"] = "FAIL"
            r["errors"]["pushover"] = po["error"]
        else:
            r["pushover"] = "EMPTY"
    except Exception as e:
        r["pushover"] = "FAIL"
        r["errors"]["pushover"] = str(e)

    # Transient
    try:
        model = mod.build()
        tr = model.transient(duration_s=5.0, dt_s=0.02)
        if tr.get("time_s"):
            r["transient"] = "OK"
            # Estimate period from zero crossings
            disps = tr["hub_disp_m"]
            times = tr["time_s"]
            if len(disps) > 4:
                # Crude period from peak-to-peak distance
                import numpy as np
                d = np.array(disps)
                peaks = []
                for i in range(1, len(d) - 1):
                    if d[i] > d[i - 1] and d[i] > d[i + 1]:
                        peaks.append(times[i])
                if len(peaks) >= 2:
                    r["transient_period_s"] = round(peaks[1] - peaks[0], 3)
        elif "error" in tr:
            r["transient"] = "FAIL"
            r["errors"]["transient"] = tr["error"]
    except Exception as e:
        r["transient"] = "FAIL"
        r["errors"]["transient"] = str(e)

    return r


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    examples = sorted((REPO / "examples").iterdir())
    examples = [e for e in examples if e.is_dir() and (e / "build.py").exists()]

    print(f"Testing {len(examples)} examples on three analyses")
    print("=" * 80)

    results = []
    for ex_dir in examples:
        print(f"\n[{ex_dir.name}]")
        r = test_one(ex_dir)
        results.append(r)
        print(f"  build: {r['build']}, eigen: {r['eigen']}, "
              f"pushover: {r['pushover']}, transient: {r['transient']}")
        if r["freqs"]:
            print(f"  f1 = {r['freqs'][0]:.4f} Hz")
        if r["pushover_max_kN"]:
            print(f"  pushover max reaction = {r['pushover_max_kN']:.2f} kN")
        if r["transient_period_s"]:
            print(f"  transient peak-to-peak period = {r['transient_period_s']:.3f} s "
                  f"(implied f = {1/r['transient_period_s']:.3f} Hz)")
        for k, v in r["errors"].items():
            print(f"  ERROR ({k}): {v}")

    # Summary
    print()
    print("=" * 80)
    n_eigen = sum(1 for r in results if r["eigen"] == "OK")
    n_pushover = sum(1 for r in results if r["pushover"] == "OK")
    n_transient = sum(1 for r in results if r["transient"] == "OK")
    print(f"SUMMARY: eigen {n_eigen}/{len(results)} | "
          f"pushover {n_pushover}/{len(results)} | "
          f"transient {n_transient}/{len(results)}")
    print("=" * 80)
    print(f"\n{'Example':<40}{'eigen':<10}{'pushover':<12}{'transient':<12}")
    for r in results:
        print(f"  {r['id']:<38}{(r['eigen'] or '-'):<10}"
              f"{(r['pushover'] or '-'):<12}{(r['transient'] or '-'):<12}")

    # Save JSON
    out = REPO / "validation" / "benchmarks" / "three_analyses_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nJSON saved: {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
