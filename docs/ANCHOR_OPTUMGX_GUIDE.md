# Op^3 Anchor Module -- OptumGX Driver Guide

This guide explains how to produce the real finite-element data the
Op^3 anchor module needs for two features:

1. `capacity_fe_calibrated()` -- VHM envelope from a real FE sweep.
2. `optimal_padeye_from_dissipation()` -- novel padeye centroid from
   the Op^3 Mode D dissipation field.

The Op^3 Python layer never fabricates FE data. If either CSV is
absent, the corresponding function raises `FileNotFoundError` with
a hint pointing you back to this guide.

## Prerequisites

| Item | Version |
|------|---------|
| OPTUM CE / OPTUM GX | 2024.x or later, academic or commercial license |
| Python | 3.12 (`C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe`) |
| Op^3 | `pip install -e .` from this repo so `import op3` works |

OPTUM GX can typically be installed to `C:\Program Files\OPTUM CE\OPTUM GX\`.
The Python bindings (`from OptumGX import *`) are loaded automatically
when you run a script from the OptumGX GUI's built-in scripting console.
They are NOT installed as a pip package -- so `import OptumGX` from a
stock Python interpreter always fails. This is by design.

## Workflow (LLM-assisted, user operates GUI)

Typical interaction when a new user clones this repo and asks Claude
Code / another LLM to run an anchor analysis:

1. **User (prompt to LLM):**
   > Run an anchor VHM analysis for D=5 m, L=15 m in NC clay
   > (su = 5 + 1.5 z kPa). Also extract the dissipation field.

2. **LLM (sets up):**
   - Edits `op3/anchors/optumgx_anchor_run.py` at the
     `CONFIGURATION` section so `D`, `L`, `SU0`, `K_SU`,
     `PADEYE_DEPTH_M`, and `SWEEP_ANGLES_DEG` match the user's case.
   - Commits the parameter edit to a branch.

3. **LLM (instructs user):**
   > Please open OPTUM GX on your desktop. Click
   > File -> Open Script -> select
   > `F:\...\op3\anchors\optumgx_anchor_run.py` -> Run.
   > Expected runtime: ~2-6 min per angle, ~7 angles in default sweep.

4. **User:** opens OptumGX, runs the script, waits.

5. **User (back to LLM, once finished):**
   > Done. Output is in `results_anchor_D5_L15_a65/`.

6. **LLM (consumes the output):**
   ```python
   from op3.anchors import SuctionAnchor, UndrainedClayProfile
   from op3.anchors.fe_postprocess import load_anchor_fe_results

   anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          padeye_depth_m=10.0,
                          submerged_weight_kN=500.0)
   soil   = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
   fe = load_anchor_fe_results(
       "results_anchor_D5_L15_a65",
       anchor, soil, load_angle_deg=30.0,
   )
   print("FE H_ult =", fe.capacity.H_ult_kN, "kN")
   print("FE V_ult =", fe.capacity.V_ult_kN, "kN")
   print("Dissipation-centroid z_opt =", fe.optimal_padeye_m, "m")
   ```

7. **LLM (optional):** copies the canonical CSVs into
   `data/anchor_benchmarks/` so future `anchor_03_padeye_optimization.py`
   runs can auto-discover them.

## Files produced by the driver

All under `results_anchor_<tag>/` relative to the OptumGX working
directory:

| File | Columns | Consumer |
|------|---------|----------|
| `envelope.csv` | `angle_deg, T_ult_kN_half, H_ult_kN, V_ult_kN, time_s` | `capacity_fe_calibrated` |
| `dissipation.csv` | `depth_m, w_z, D_total_kJ` | `optimal_padeye_from_dissipation` |
| `plates_a{ANG}.xlsx` | raw plate-element data per probe | diagnostics |
| `summary.json` | configuration, per-angle timings, totals | provenance |

## Troubleshooting

- **`ImportError: No module named 'OptumGX'` when running from stock Python.**
  Expected. Run the script from inside OptumGX.

- **`FileNotFoundError: envelope.csv` from `capacity_fe_calibrated`.**
  The driver has not yet run, or the `results_dir` you pointed Op^3 at
  is wrong. Re-check the path printed at the end of the driver run.

- **Negative `w_z` in `dissipation.csv`.**
  OptumGX occasionally reports negative collapse-mechanism norms in
  near-zero-work regions. Op^3's `optimal_padeye_from_dissipation`
  refuses such files (ValueError). Clamp the negatives to zero in
  post-processing or re-mesh with higher adaptivity.

- **Cavitation warning during installation check.**
  Covered by `installation_analysis(..., water_depth_m=...)`. Not a
  GUI issue.

## Citation

If you publish results derived from this pipeline, cite

> Kim, K. S. (2026). *Integrated Numerical and Digital Twin Framework
> for Scour Assessment of OWT with Tripod Suction Bucket Foundations.*
> PhD dissertation, Seoul National University.

alongside DNV-RP-E303 (2021) and the relevant analytical sources
(Aubeny et al. 2003, Murff & Hamilton 1993, Supachawarote et al.
2005).
