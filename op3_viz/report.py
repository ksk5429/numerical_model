"""
Report generator — produce a DOCX/PDF report from an Op^3 project.

Wraps Quarto as the rendering engine. Input is an .op3proj file;
output is a pair of (DOCX, PDF) named after the project. The report
template includes:

  1. Project metadata (name, author, date, Op^3 version)
  2. Selected turbine + foundation mode + soil profile
  3. Eigenvalue analysis result (first 6 modes)
  4. Pushover curve (if available)
  5. Bayesian scour posterior (if configured)
  6. DNV-ST-0126 / IEC 61400-3 conformance summary
  7. DLC 1.1 / 6.1 sweep summary (if available)
  8. Recommended maintenance action (from Ch 7 decision rule)

Usage
-----
    from op3_viz.project import load
    from op3_viz.report import build_report

    proj = load("myproject.op3proj")
    docx, pdf = build_report(proj, output_dir="reports/")

Requirements
------------
    * quarto CLI on PATH
    * pandoc (shipped with quarto)
    * pyyaml
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .project import Project

REPORT_QMD_TEMPLATE = r"""---
title: "Op^3 Analysis Report"
subtitle: "{subtitle}"
author: "{author}"
date: "{date}"
format:
  docx:
    toc: true
    toc-depth: 2
  pdf:
    toc: true
    toc-depth: 2
    pdf-engine: lualatex
    mainfont: "DejaVu Sans"
---

# Project Summary

- **Project name:** {name}
- **Op^3 version:** {op3_version}
- **Schema version:** {schema_version}
- **Created:** {created}
- **Modified:** {modified}

# Turbine and Foundation

- **Reference turbine:** `{turbine_ref}`
- **Tower template:** `{tower_template}`
- **Foundation mode:** `{foundation_mode}`
- **Scour depth:** {scour_m} m
- **Mode D alpha:** {alpha}
- **Mode D beta:** {beta}

# Soil Profile

- **Profile source:** `{soil_source}`
- **Surface undrained shear strength su0:** {su0_kPa} kPa
- **Shear-strength gradient k_su:** {k_su} kPa/m

# Analysis Configuration

- **Eigenvalue modes requested:** {eigen_modes}
- **Damping ratio:** {damping_ratio}
- **Pushover target displacement:** {pushover_target} m

# Design Load Case Configuration

- **DLC family:** {dlc_family}
- **Wind speeds (m/s):** {wind_speeds}
- **Simulation time (s):** {tmax_s}

# Conformance

{conformance_section}

# Provenance

This report was generated automatically by `op3_viz.report` from the
project file `{project_name}.op3proj`. The Op^3 framework is published
under the Zenodo concept DOI [10.5281/zenodo.19476542]
(https://doi.org/10.5281/zenodo.19476542). All proprietary numerical
values referenced in this report (tower segment schedule, bucket
dimensions, soil profile, SubDyn 6x6 stiffness matrix) are loaded at
runtime from the private data tree pointed to by the `OP3_PHD_ROOT`
environment variable and are not redistributed in the public Op^3
repository.
"""


def _render_conformance_section(project: Project) -> str:
    """Render a compact conformance status block.

    In the Tier-2 scope this wires actual audit outputs; for now it
    writes a placeholder reminding the user which audit scripts to
    run on demand.
    """
    return (
        "To run the full DNV-ST-0126 conformance audit:\n\n"
        "```bash\n"
        "python scripts/dnv_st_0126_conformance.py --all\n"
        "```\n\n"
        "To run the IEC 61400-3 conformance audit:\n\n"
        "```bash\n"
        "python scripts/iec_61400_3_conformance.py --all\n"
        "```\n\n"
        "The two audit scripts print a clause-by-clause pass/fail table "
        "and write a JSON summary that this report template will embed "
        "automatically in a future Tier-2 revision."
    )


def render_qmd(project: Project, output_dir: str | Path) -> Path:
    """Render the .qmd source for the report."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = project.name.replace(" ", "_").replace("/", "_")
    qmd_path = out / f"{slug}.qmd"

    subtitle = (
        f"{project.turbine.reference} · {project.foundation.mode} · "
        f"scour = {project.foundation.scour_m} m"
    )
    body = REPORT_QMD_TEMPLATE.format(
        subtitle=subtitle,
        author="Op^3 Analysis Engine",
        date=dt.datetime.now().strftime("%Y-%m-%d"),
        name=project.name,
        op3_version=project.op3_version,
        schema_version=project.schema_version,
        created=project.created,
        modified=project.modified,
        turbine_ref=project.turbine.reference,
        tower_template=project.turbine.tower_template,
        foundation_mode=project.foundation.mode,
        scour_m=project.foundation.scour_m,
        alpha=project.foundation.mode_d_alpha or "—",
        beta=project.foundation.mode_d_beta or "—",
        soil_source=project.soil.profile_source,
        su0_kPa=project.soil.su0_kPa or "(private)",
        k_su=project.soil.k_su_kPa_per_m or "(private)",
        eigen_modes=project.analysis.eigen_modes,
        damping_ratio=project.analysis.damping_ratio,
        pushover_target=project.analysis.pushover_target_disp_m,
        dlc_family=project.dlc.family,
        wind_speeds=", ".join(str(w) for w in project.dlc.wind_speeds_mps),
        tmax_s=project.dlc.tmax_s,
        conformance_section=_render_conformance_section(project),
        project_name=slug,
    )
    qmd_path.write_text(body, encoding="utf-8")
    return qmd_path


def build_report(
    project: Project,
    output_dir: str | Path = "reports/",
    formats: Tuple[str, ...] = ("docx", "pdf"),
) -> dict:
    """Render a project report in each requested format.

    Returns a dict mapping format -> output Path. If Quarto is not
    installed, returns the rendered .qmd and skips binary formats.
    """
    qmd_path = render_qmd(project, output_dir)
    produced = {"qmd": qmd_path}

    if shutil.which("quarto") is None:
        return produced

    for fmt in formats:
        try:
            subprocess.run(
                ["quarto", "render", str(qmd_path), "--to", fmt],
                cwd=qmd_path.parent,
                check=True,
            )
            out_file = qmd_path.with_suffix(f".{fmt}")
            if out_file.exists():
                produced[fmt] = out_file
        except subprocess.CalledProcessError as e:
            print(f"[warn] quarto render --to {fmt} failed: {e}")
    return produced
