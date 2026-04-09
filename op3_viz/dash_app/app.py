"""
Op^3 standalone Dash demo (tabbed).

Tabs:
  1. 3D Viewer       -- reference tower + foundation with live overlays
  2. Bayesian Scour  -- real 1794-MC importance-sampling posterior
  3. Mode D          -- real 2D alpha/beta posterior heatmap
  4. PCE Surrogate   -- closed-form PCE coefficients + verification

Run:
    python -m op3_viz.dash_app.app
    # then browse http://localhost:8050
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from ..geometry import Mesh, build_full_scene
from ..op3_results import (
    real_mode_shape,
    real_dissipation_weight_on_tripod,
    bending_stress_proxy,
)
from ..results_loader import figure_bayes_scour, figure_mode_d, figure_pce
from ..dlc_loader import (
    discover_runs,
    figure_dlc,
    PRIMARY_CHANNELS,
)


FIELD_CHOICES = [
    {"label": "Eigenmode 1 sqrt(ux^2+uy^2) (live OpenSees)",
     "value": "real_mode_1"},
    {"label": "Eigenmode 2 sqrt(ux^2+uy^2) (live OpenSees)",
     "value": "real_mode_2"},
    {"label": "sigma(z) [MPa] on tower (real I(z), c(z), cantilever)",
     "value": "real_stress"},
    {"label": "w_dissip(depth) on buckets (OptumGX spring_params_v4)",
     "value": "real_wz"},
]


def _compute_field(tower: Mesh, tripod: Mesh, key: str
                   ) -> tuple[str, np.ndarray]:
    """Return (target_mesh_name, intensity) for a given field key.
    target_mesh_name is 'tower' or 'tripod'."""
    if key == "real_mode_1":
        return "tower", real_mode_shape(tower, mode_index=1)
    if key == "real_mode_2":
        return "tower", real_mode_shape(tower, mode_index=2)
    if key == "real_stress":
        return "tower", bending_stress_proxy(tower, F_hub_kN=1000.0)
    if key == "real_wz":
        return "tripod", real_dissipation_weight_on_tripod(tripod)
    raise ValueError(f"unknown field key: {key}")


def _mesh3d(mesh: Mesh, *, intensity=None, colorscale="Viridis",
            name="", opacity=1.0, color=None, showscale=False) -> go.Mesh3d:
    kwargs = dict(
        x=mesh.x, y=mesh.y, z=mesh.z,
        i=mesh.i, j=mesh.j, k=mesh.k,
        name=name, opacity=opacity, flatshading=True,
        lighting=dict(ambient=0.55, diffuse=0.8, specular=0.3, roughness=0.5),
        lightposition=dict(x=100, y=200, z=400),
    )
    if intensity is not None:
        kwargs.update(
            intensity=intensity, colorscale=colorscale, showscale=showscale,
            intensitymode="vertex",
            colorbar=dict(title=name, thickness=14, len=0.6),
        )
    elif color is not None:
        kwargs["color"] = color
    return go.Mesh3d(**kwargs)


def _mudline_disk(radius: float = 22.0, z: float = 0.0) -> go.Mesh3d:
    n = 48
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xs = np.concatenate([[0.0], radius * np.cos(theta)])
    ys = np.concatenate([[0.0], radius * np.sin(theta)])
    zs = np.full_like(xs, z)
    ii = np.zeros(n, dtype=int)
    jj = np.arange(1, n + 1)
    kk = np.roll(jj, -1); kk[-1] = 1
    return go.Mesh3d(x=xs, y=ys, z=zs, i=ii, j=jj, k=kk,
                     color="#c2a26b", opacity=0.35, name="mudline",
                     showscale=False)


def make_3d_figure(scene: dict, field_key: str, scour_m: float) -> go.Figure:
    tower, tripod, nacelle = scene["tower"], scene["tripod"], scene["nacelle"]
    rotor = scene["rotor"]
    target, field = _compute_field(tower, tripod, field_key)
    label = {c["value"]: c["label"] for c in FIELD_CHOICES}[field_key]

    tower_trace = (
        _mesh3d(tower, intensity=field, colorscale="Viridis",
                name=label, showscale=True)
        if target == "tower" else
        _mesh3d(tower, color="#b7c0cc", name="tower", opacity=0.85)
    )
    tripod_trace = (
        _mesh3d(tripod, intensity=field, colorscale="Viridis",
                name=label, showscale=True)
        if target == "tripod" else
        _mesh3d(tripod, color="#6c7a89", name="tripod")
    )

    traces = [
        _mudline_disk(z=-scour_m),     # mudline visual offset (cosmetic)
        _mudline_disk(z=0.0),          # original seabed (ghost)
        tripod_trace,
        _mesh3d(nacelle, color="#f0e6d2", name="RNA"),
        _mesh3d(rotor, color="#8a9eaf", name="rotor disk", opacity=0.35),
        tower_trace,
    ]
    fig = go.Figure(data=traces)
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis_title="x (m)", yaxis_title="y (m)", zaxis_title="z (m)",
            bgcolor="#0f1117",
            xaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
            yaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
            zaxis=dict(color="#d0d4dc", gridcolor="#2a2f3a"),
        ),
        paper_bgcolor="#0f1117", font=dict(color="#d0d4dc"),
        margin=dict(l=0, r=0, t=30, b=0), showlegend=False, height=680,
        title=dict(
            text=(f"Op^3 reference tower | mudline visual offset "
                  f"{scour_m:.2f} m (cosmetic)"),
            x=0.5, xanchor="center",
        ),
    )
    return fig


# ------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------

def _tab_viewer() -> html.Div:
    return html.Div([
        html.Div([
            html.Div([
                html.Label("Field overlay"),
                dcc.RadioItems(
                    id="field", options=FIELD_CHOICES, value="real_stress",
                    inputStyle={"marginRight": "4px", "marginLeft": "12px"},
                ),
            ]),
            html.Div([
                html.Label("Mudline visual offset (m) -- cosmetic only; "
                           "does not rebuild springs"),
                dcc.Slider(id="scour", min=0.0, max=4.0, step=0.25, value=0.0,
                           marks={i: str(i) for i in range(5)},
                           tooltip={"always_visible": False}),
            ], style={"marginTop": "12px"}),
        ], style={"padding": "10px 14px"}),
        dcc.Graph(id="viewer"),
        html.Div(
            "Overlays are computed from Op^3 artefacts at runtime: "
            "tower section properties via ``section_properties()``, "
            "a live OpenSeesPy eigen run, and the dissipation spring "
            "table resolved through ``op3.data_sources``. Any "
            "project-specific numeric values stay in the private "
            "data store and are never hard-coded here.",
            style={"opacity": 0.7, "fontSize": "12px", "padding": "4px 14px"},
        ),
    ])


def _tab_bayes() -> html.Div:
    return html.Div([dcc.Graph(figure=figure_bayes_scour(), id="g_bayes")],
                    style={"padding": "10px 14px"})


def _tab_mode_d() -> html.Div:
    return html.Div([dcc.Graph(figure=figure_mode_d(), id="g_mode_d")],
                    style={"padding": "10px 14px"})


def _tab_pce() -> html.Div:
    return html.Div([dcc.Graph(figure=figure_pce(), id="g_pce")],
                    style={"padding": "10px 14px"})


def _tab_dlc() -> html.Div:
    runs = discover_runs()
    default_run = runs[0]["value"] if runs else None
    return html.Div([
        html.Div([
            html.Div([
                html.Label("DLC 1.1 run"),
                dcc.Dropdown(
                    id="dlc_run",
                    options=[{"label": r["label"], "value": r["value"]}
                             for r in runs],
                    value=default_run,
                    clearable=False,
                    style={"color": "#111"},
                ),
            ], style={"flex": "1 1 45%"}),
            html.Div([
                html.Label("Channels"),
                dcc.Dropdown(
                    id="dlc_channels",
                    options=[{"label": c, "value": c} for c in PRIMARY_CHANNELS],
                    value=["RootMyb1_[kN-m]", "TwrBsMyt_[kN-m]",
                           "Wind1VelX_[m/s]"],
                    multi=True,
                    style={"color": "#111"},
                ),
            ], style={"flex": "1 1 45%", "marginLeft": "16px"}),
        ], style={"display": "flex", "gap": "12px", "padding": "10px 14px"}),
        dcc.Graph(id="g_dlc"),
        html.Div(
            f"Source: {len(runs)} runs discovered under "
            "validation/dlc11_partial/ (latest sweep).",
            style={"opacity": 0.7, "fontSize": "12px", "padding": "4px 14px"},
        ),
    ])


def create_app() -> Dash:
    scene = build_full_scene()
    app = Dash(__name__)
    app.title = "Op^3 Viewer"

    app.layout = html.Div(
        style={"backgroundColor": "#0f1117", "color": "#d0d4dc",
               "fontFamily": "system-ui, sans-serif", "minHeight": "100vh"},
        children=[
            html.Div([
                html.H2("Op^3 Interactive Viewer",
                        style={"margin": "0 0 4px 0"}),
                html.Div("OptumGX - OpenSeesPy - OpenFAST",
                         style={"opacity": 0.7, "fontSize": "13px"}),
            ], style={"padding": "16px 18px 8px 18px"}),
            dcc.Tabs(id="tabs", value="viewer", children=[
                dcc.Tab(label="3D Viewer", value="viewer",
                        children=[_tab_viewer()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="Bayesian Scour", value="bayes",
                        children=[_tab_bayes()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="Mode D (alpha, beta)", value="mode_d",
                        children=[_tab_mode_d()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="PCE Surrogate", value="pce",
                        children=[_tab_pce()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="DLC 1.1 Time-series", value="dlc",
                        children=[_tab_dlc()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
            ]),
        ],
    )

    @app.callback(
        Output("viewer", "figure"),
        Input("field", "value"),
        Input("scour", "value"),
    )
    def _update(field_key, scour_m):
        return make_3d_figure(scene, field_key, float(scour_m or 0.0))

    @app.callback(
        Output("g_dlc", "figure"),
        Input("dlc_run", "value"),
        Input("dlc_channels", "value"),
    )
    def _update_dlc(run_path, channels):
        return figure_dlc(run_path, channels or [])

    return app


def main():
    app = create_app()
    app.run(debug=False, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
