"""
Loader for canonical Op^3 / PhD result JSONs. Each function returns
Plotly-ready figures or small dicts of arrays for the Dash tabs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

REPO = Path(__file__).resolve().parents[1]

PATHS = {
    "bayes": REPO / "PHD/ch7/site_a_bayesian_scour_real_mc.json",
    "pce": REPO / "PHD/ch7/site_a_pce_surrogate.json",
    "mode_d": REPO / "PHD/ch6/site_a_mode_d_calibration.json",
}

DARK = dict(
    paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
    font=dict(color="#d0d4dc"),
    xaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
    yaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
    margin=dict(l=40, r=20, t=40, b=40),
)


def _load(key: str) -> dict | None:
    p = PATHS[key]
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def figure_bayes_scour() -> go.Figure:
    d = _load("bayes")
    if d is None:
        return go.Figure().update_layout(title="Bayesian scour (result not found)", **DARK)
    hist = d["scour_posterior_histogram"]
    edges = np.array(hist["bin_edges_m"])
    dens = np.array(hist["density"])
    centers = 0.5 * (edges[:-1] + edges[1:])
    post = d["posterior_marginal"]["scour_m"]
    fig = go.Figure()
    fig.add_bar(x=centers, y=dens, marker_color="#4aa3ff",
                name="posterior density")
    for p_key, color, dash in [("p05", "#ff6b6b", "dash"),
                               ("p50", "#f0e68c", "solid"),
                               ("p95", "#ff6b6b", "dash")]:
        fig.add_vline(x=post[p_key], line=dict(color=color, dash=dash),
                      annotation_text=p_key, annotation_position="top")
    ess = d["effective_sample_size"]
    fig.update_layout(
        title=f"Bayesian scour posterior | mean={post['mean']:.2f} m, "
              f"90% CI [{post['p05']:.2f}, {post['p95']:.2f}] | ESS={ess:.0f}",
        xaxis_title="scour depth (m)", yaxis_title="posterior density",
        **DARK,
    )
    return fig


def figure_pce() -> go.Figure:
    d = _load("pce")
    if d is None:
        return go.Figure().update_layout(title="PCE (result not found)", **DARK)
    verif = d.get("verification", {})
    coeffs = np.array(d.get("coefficients", []), dtype=float)
    idx = np.arange(len(coeffs))
    fig = go.Figure()
    fig.add_bar(x=idx, y=np.abs(coeffs), marker_color="#7ad67a",
                name="|c_alpha|")
    mean = d.get("closed_form_mean_hz", None)
    var = d.get("closed_form_var", None)
    ttl = f"PCE (order {d.get('pce_order','?')})"
    if mean is not None and var is not None:
        ttl += f" | mean f1 = {mean:.4f} Hz, std = {np.sqrt(var):.4f}"
    if verif:
        ttl += f" | verif r = {verif.get('correlation', float('nan')):.4f}"
    fig.update_layout(title=ttl, xaxis_title="coefficient index",
                      yaxis_title="|c|", yaxis_type="log", **DARK)
    return fig


def figure_mode_d() -> go.Figure:
    d = _load("mode_d")
    if d is None:
        return go.Figure().update_layout(title="Mode D (result not found)", **DARK)
    grid = d["grid"]
    alpha = np.array(grid["alpha"])
    beta = np.array(grid["beta"])
    post = np.array(d["posterior"])
    fig = go.Figure(
        data=go.Heatmap(z=post, x=alpha, y=beta, colorscale="Viridis",
                        colorbar=dict(title="p(alpha,beta|f1)")),
    )
    mp = d.get("MAP", {})
    if "alpha" in mp and "beta" in mp:
        fig.add_scatter(x=[mp["alpha"]], y=[mp["beta"]], mode="markers+text",
                        marker=dict(color="#ff6b6b", size=14, symbol="x"),
                        text=["MAP"], textposition="top center",
                        name="MAP")
    mm = d.get("marginal_means", {})
    fig.update_layout(
        title=f"Mode D 2D grid posterior | MAP alpha={mp.get('alpha','?')} "
              f"beta={mp.get('beta','?')} | mean alpha={mm.get('alpha','?')}"
              f" beta={mm.get('beta','?')}",
        xaxis_title="alpha", yaxis_title="beta", **DARK,
    )
    return fig
