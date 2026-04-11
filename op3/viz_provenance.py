"""
Provenance tagging for Op3 figures.

Adds a small text annotation to the bottom of every matplotlib figure
indicating the data source. This prevents anyone from mistaking a
synthetic demonstration for a real analysis result.

Usage::

    from op3.viz_provenance import stamp

    fig, ax = plt.subplots()
    ax.plot(x, y)
    stamp(fig, "OptumGX FELA, D=10m, su=50kPa, 2026-04-10")
    fig.savefig("output.png")

Provenance categories:
    COMPUTED  — result from Op3 code execution (eigenvalue, pushover, etc.)
    OPTUMGX  — result from OptumGX limit analysis (date + mesh params)
    OPENFAST — result from OpenFAST simulation (DLC, wind speed, duration)
    PUBLISHED — data extracted from published paper (citation)
    SYNTHETIC — demonstration only, not from real analysis
    FIELD     — field measurement data (site, date range, sensor type)
"""
from __future__ import annotations

from datetime import date

import matplotlib.pyplot as plt


def stamp(
    fig: plt.Figure,
    source: str,
    category: str = "COMPUTED",
    fontsize: int = 7,
    alpha: float = 0.5,
) -> None:
    """Add provenance text to bottom-left of figure.

    Parameters
    ----------
    fig : matplotlib Figure
    source : str
        Description of data origin (e.g., "OptumGX FELA, D=10m, su=50kPa")
    category : str
        One of: COMPUTED, OPTUMGX, OPENFAST, PUBLISHED, SYNTHETIC, FIELD
    """
    today = date.today().isoformat()
    text = f"[{category}] {source} | Op3 v1.0.0-rc2 | {today}"

    fig.text(
        0.01, 0.005, text,
        fontsize=fontsize, color='gray', alpha=alpha,
        transform=fig.transFigure,
        ha='left', va='bottom',
        family='monospace',
    )


# Pre-built stamps for common sources
def stamp_optumgx(fig, D, L=None, su=None, mesh_el=None, date_str=None):
    parts = [f"D={D}m"]
    if L: parts.append(f"L={L}m")
    if su: parts.append(f"su={su}kPa")
    if mesh_el: parts.append(f"{mesh_el}el")
    if date_str: parts.append(date_str)
    stamp(fig, ", ".join(parts), category="OPTUMGX")


def stamp_openfast(fig, turbine, dlc=None, ws=None, duration=None):
    parts = [turbine]
    if dlc: parts.append(f"DLC {dlc}")
    if ws: parts.append(f"Ws={ws}m/s")
    if duration: parts.append(f"T={duration}s")
    stamp(fig, ", ".join(parts), category="OPENFAST")


def stamp_published(fig, citation):
    stamp(fig, citation, category="PUBLISHED")


def stamp_synthetic(fig, description="demonstration only"):
    stamp(fig, description, category="SYNTHETIC")


def stamp_field(fig, site, date_range=None, sensor=None):
    parts = [site]
    if date_range: parts.append(date_range)
    if sensor: parts.append(sensor)
    stamp(fig, ", ".join(parts), category="FIELD")
