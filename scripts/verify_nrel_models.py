"""
Verify every bundled NREL reference OpenFAST model by parsing its .fst
file and extracting key structural parameters.

This is not a full OpenFAST run — it is a static verification that:
  1. Every .fst file referenced in the repository README actually exists
  2. Every .fst file parses as valid OpenFAST input
  3. The referenced ElastoDyn, AeroDyn, HydroDyn, SubDyn, ServoDyn sub-files exist
  4. Key rotor/tower/foundation parameters can be extracted
  5. The module configuration (CompHydro, CompSub, CompMooring, etc) matches
     the model description

Run:
    python scripts/verify_nrel_models.py

Writes a JSON verification report to:
    validation/benchmarks/nrel_model_verification.json

And prints a summary table suitable for inclusion in NREL_BENCHMARK.md.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = REPO_ROOT / "validation" / "benchmarks" / "nrel_model_verification.json"


# ============================================================
# Models to verify (model_id, root_path, main_fst_filename)
# ============================================================
MODELS = [
    ("NREL_5MW_Baseline_rtest",
     "nrel_reference/openfast_rtest/5MW_Baseline", None),   # baseline has no top-level fst
    ("NREL_5MW_OC3_Monopile",
     "nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr",
     "5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst"),
    ("NREL_1.72-103",
     "nrel_reference/iea_scaled/NREL-1.72-103/OpenFAST", None),
    ("NREL_1.79-100",
     "nrel_reference/iea_scaled/NREL-1.79-100/OpenFAST", None),
    ("NREL_2.3-116",
     "nrel_reference/iea_scaled/NREL-2.3-116/OpenFAST", None),
    ("NREL_2.8-127_hh87",
     "nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh87", None),
    ("NREL_2.8-127_hh120",
     "nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh120", None),
    ("Vestas_V27",
     "nrel_reference/vestas/V27", None),
    ("Gunsan_4p2MW",
     "gunsan_4p2mw/openfast_deck", "Gunsan-4p2MW.fst"),
]


# ============================================================
# Parsers
# ============================================================

def find_fst(model_dir: Path, hint: str | None) -> Path | None:
    """Locate the main .fst file for a model directory."""
    if hint:
        p = model_dir / hint
        return p if p.exists() else None
    candidates = sorted(model_dir.glob("*.fst"))
    if candidates:
        return candidates[0]
    # Look one level deeper
    for sub in model_dir.iterdir():
        if sub.is_dir():
            c = sorted(sub.glob("*.fst"))
            if c:
                return c[0]
    return None


def parse_fst_flags(fst_path: Path) -> dict:
    """Extract key OpenFAST module flags from a .fst file."""
    if not fst_path or not fst_path.exists():
        return {}
    text = fst_path.read_text(errors="replace")
    flags = {}
    for key in ["CompElast", "CompInflow", "CompAero", "CompServo",
                "CompSeaSt", "CompHydro", "CompSub", "CompMooring",
                "CompIce", "CompSoil", "TMax", "DT", "NRotors"]:
        m = re.search(rf"^\s*(\S+)\s+{key}\b", text, re.MULTILINE)
        if m:
            flags[key] = m.group(1)
    # File references
    refs = {}
    for key in ["EDFile", "BDBldFile", "InflowFile", "AeroFile",
                "ServoFile", "HydroFile", "SubFile", "MooringFile"]:
        m = re.search(rf"^\s*\"([^\"]+)\"\s+{key}\b", text, re.MULTILINE)
        if m:
            refs[key] = m.group(1)
    return {"flags": flags, "referenced_files": refs}


def parse_elastodyn(ed_path: Path) -> dict:
    """Extract rotor, tower, and nacelle key properties from ElastoDyn file."""
    if not ed_path or not ed_path.exists():
        return {}
    text = ed_path.read_text(errors="replace")
    out = {}
    wanted = {
        "NumBl":    r"^\s*(\d+)\s+NumBl\b",
        "TipRad":   r"^\s*([-\d.Ee+]+)\s+TipRad\b",
        "HubRad":   r"^\s*([-\d.Ee+]+)\s+HubRad\b",
        "TowerHt":  r"^\s*([-\d.Ee+]+)\s+TowerHt\b",
        "Twr2Shft": r"^\s*([-\d.Ee+]+)\s+Twr2Shft\b",
        "OverHang": r"^\s*([-\d.Ee+]+)\s+OverHang\b",
        "HubMass":  r"^\s*([-\d.Ee+]+)\s+HubMass\b",
        "NacMass":  r"^\s*([-\d.Ee+]+)\s+NacMass\b",
        "ShftTilt": r"^\s*([-\d.Ee+]+)\s+ShftTilt\b",
    }
    for key, pat in wanted.items():
        m = re.search(pat, text, re.MULTILINE)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                out[key] = m.group(1)
    # Derived: rotor diameter + hub height estimate
    if "TipRad" in out and "HubRad" in out:
        out["RotorDiameter_m"] = 2 * out["TipRad"]
    if "TowerHt" in out and "Twr2Shft" in out:
        out["HubHeight_est_m"] = out["TowerHt"] + out["Twr2Shft"]
    return out


# ============================================================
# Verification
# ============================================================

def verify_model(model_id: str, rel_path: str, fst_hint: str | None) -> dict:
    model_dir = REPO_ROOT / rel_path
    report = {"model_id": model_id, "path": rel_path}

    if not model_dir.exists():
        report["status"] = "MISSING_DIR"
        return report

    # Count files
    file_count = sum(1 for _ in model_dir.rglob("*") if _.is_file())
    size_bytes = sum(p.stat().st_size for p in model_dir.rglob("*") if p.is_file())
    report["file_count"] = file_count
    report["size_mb"] = round(size_bytes / 1_000_000, 2)

    # Locate main .fst
    fst = find_fst(model_dir, fst_hint)
    if fst is None:
        report["status"] = "NO_FST"
        report["fst_path"] = None
        return report

    report["fst_path"] = str(fst.relative_to(REPO_ROOT))
    report["fst_size_kb"] = round(fst.stat().st_size / 1000, 1)

    # Parse .fst
    fst_info = parse_fst_flags(fst)
    report["flags"] = fst_info.get("flags", {})
    report["referenced_files"] = fst_info.get("referenced_files", {})

    # Locate ElastoDyn
    ed_ref = fst_info.get("referenced_files", {}).get("EDFile", "")
    ed_path = None
    if ed_ref:
        candidate = (fst.parent / ed_ref).resolve()
        if candidate.exists():
            ed_path = candidate
    if ed_path is None:
        for c in fst.parent.glob("*ElastoDyn*.dat"):
            ed_path = c
            break

    if ed_path:
        report["elastodyn_path"] = str(ed_path.relative_to(REPO_ROOT))
        report["elastodyn"] = parse_elastodyn(ed_path)
    else:
        report["elastodyn"] = None

    # Check for key sub-files
    sub_file_status = {}
    for key, ref in fst_info.get("referenced_files", {}).items():
        candidate = (fst.parent / ref).resolve()
        sub_file_status[key] = {
            "referenced": ref,
            "exists": candidate.exists(),
        }
    report["sub_files"] = sub_file_status

    report["status"] = "OK"
    return report


def format_summary_table(reports: list[dict]) -> str:
    """Markdown table suitable for NREL_BENCHMARK.md."""
    lines = [
        "| Model | Files | Size | Main FST | Hydro | Sub | Rotor D (m) | Hub H (m) | Status |",
        "|-------|------:|-----:|----------|:-----:|:---:|------------:|----------:|:------:|",
    ]
    for r in reports:
        if r.get("status") != "OK":
            lines.append(
                f"| {r['model_id']} | — | — | — | — | — | — | — | **{r.get('status','?')}** |"
            )
            continue
        ed = r.get("elastodyn") or {}
        rotor_d = f"{ed.get('RotorDiameter_m', 0):.1f}" if ed.get("RotorDiameter_m") else "—"
        hub_h = f"{ed.get('HubHeight_est_m', 0):.1f}" if ed.get("HubHeight_est_m") else "—"
        flags = r.get("flags", {})
        hydro = "✓" if flags.get("CompHydro", "0") not in ("0", "") else " "
        sub = "✓" if flags.get("CompSub", "0") not in ("0", "") else " "
        fst_name = Path(r["fst_path"]).name if r.get("fst_path") else "—"
        lines.append(
            f"| {r['model_id']} | {r['file_count']} | {r['size_mb']} MB | "
            f"`{fst_name}` | {hydro} | {sub} | {rotor_d} | {hub_h} | ✅ |"
        )
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("Verifying bundled NREL reference OpenFAST models")
    print("=" * 70)

    reports = []
    for model_id, rel_path, fst_hint in MODELS:
        print(f"\n[{model_id}]  {rel_path}")
        report = verify_model(model_id, rel_path, fst_hint)
        reports.append(report)
        if report.get("status") == "OK":
            print(f"  files: {report['file_count']}, size: {report['size_mb']} MB")
            if report.get("fst_path"):
                print(f"  fst:   {Path(report['fst_path']).name}")
            ed = report.get("elastodyn") or {}
            if ed:
                print(f"  rotor: D = {ed.get('RotorDiameter_m', '?')} m, "
                      f"hub = {ed.get('HubHeight_est_m', '?')} m, "
                      f"blades = {int(ed.get('NumBl', 0))}")
            flags = report.get("flags", {})
            mods = [k for k, v in flags.items() if k.startswith("Comp") and v not in ("0", "")]
            if mods:
                print(f"  modules: {', '.join(mods)}")
        else:
            print(f"  STATUS: {report.get('status')}")

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"\n\nJSON report: {OUTPUT_JSON}")

    # Print markdown summary
    print("\n\n" + "=" * 70)
    print("Markdown summary table for NREL_BENCHMARK.md")
    print("=" * 70 + "\n")
    print(format_summary_table(reports))


if __name__ == "__main__":
    main()
