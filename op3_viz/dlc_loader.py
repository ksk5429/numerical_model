"""
DLC time-series loader for the Op^3 viewer. Reads OpenFAST .outb files
from the latest DLC 1.1 partial sweep and exposes them as Plotly
figures and dropdown options.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path
from typing import Dict, List

import numpy as np
import plotly.graph_objects as go

REPO = Path(__file__).resolve().parents[1]
DLC_ROOT = REPO / "validation" / "dlc11_partial"

DARK = dict(
    paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
    font=dict(color="#d0d4dc"),
    xaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
    yaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
    margin=dict(l=50, r=20, t=40, b=40),
)

PRIMARY_CHANNELS = [
    "RootMyb1_[kN-m]", "TwrBsMyt_[kN-m]", "GenPwr_[kW]",
    "RotSpeed_[rpm]", "OoPDefl1_[m]", "BldPitch1_[deg]",
    "Wind1VelX_[m/s]", "YawBrTDxt_[m]",
]


def _latest_sweep() -> Path | None:
    if not DLC_ROOT.exists():
        return None
    subs = sorted([p for p in DLC_ROOT.iterdir() if p.is_dir()])
    return subs[-1] if subs else None


def discover_runs() -> List[Dict]:
    sweep = _latest_sweep()
    if sweep is None:
        return []
    runs = []
    for rundir in sorted(sweep.glob("run_*")):
        outbs = list(rundir.glob("*.outb"))
        if not outbs:
            continue
        m = re.search(r"(\d+)mps", rundir.name)
        ws = float(m.group(1)) / 10 if m else float("nan")
        runs.append({
            "label": f"{rundir.name}  ({ws:.1f} m/s)",
            "value": str(outbs[0]),
            "wind_speed": ws,
        })
    return runs


def available_channels(outb_path: str) -> List[str]:
    try:
        from openfast_io.FAST_output_reader import FASTOutputFile
        df = FASTOutputFile(outb_path).toDataFrame()
        return list(df.columns)
    except Exception:
        return []


def figure_dlc(outb_path: str | None, channels: List[str]) -> go.Figure:
    if not outb_path:
        return go.Figure().update_layout(title="No DLC run selected", **DARK)
    try:
        from openfast_io.FAST_output_reader import FASTOutputFile
        df = FASTOutputFile(outb_path).toDataFrame()
    except Exception as e:
        return go.Figure().update_layout(
            title=f"Reader error: {type(e).__name__}", **DARK)

    time_col = "Time_[s]" if "Time_[s]" in df.columns else df.columns[0]
    t = df[time_col].to_numpy()
    fig = go.Figure()
    palette = ["#4aa3ff", "#f0e68c", "#7ad67a", "#ff6b6b",
               "#c792ea", "#ffab70", "#89ddff", "#ff6ac1"]
    plotted = 0
    for i, ch in enumerate(channels or []):
        if ch not in df.columns:
            continue
        y = df[ch].to_numpy()
        fig.add_scatter(x=t, y=y, mode="lines", name=ch,
                        line=dict(color=palette[plotted % len(palette)],
                                  width=1.4))
        plotted += 1
    name = Path(outb_path).parent.name
    fig.update_layout(
        title=f"OpenFAST DLC 1.1 | {name} | {plotted} channels",
        xaxis_title="time (s)", yaxis_title="value",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(size=10)),
        height=620, **DARK,
    )
    return fig
