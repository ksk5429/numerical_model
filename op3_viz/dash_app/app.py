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


def _tab_compliance() -> html.Div:
    """Compliance & Actions tab: run DNV/IEC audits + dispatch DLC sweeps.

    Wires the existing audit scripts under ``scripts/`` so the engineer
    can trigger a DNV-ST-0126 or IEC 61400-3 conformance check and a
    DLC 1.1 sweep from the web UI without touching the terminal.
    """
    return html.Div([
        html.Div([
            html.H3("Compliance audits",
                    style={"marginTop": "0", "color": "#d0d4dc"}),
            html.Button("Run DNV-ST-0126 audit", id="btn_dnv",
                        n_clicks=0,
                        style={"marginRight": "10px", "padding": "8px 14px",
                               "backgroundColor": "#2b7a78", "color": "#fff",
                               "border": "none", "borderRadius": "6px",
                               "cursor": "pointer"}),
            html.Button("Run IEC 61400-3 audit", id="btn_iec",
                        n_clicks=0,
                        style={"padding": "8px 14px",
                               "backgroundColor": "#2b7a78", "color": "#fff",
                               "border": "none", "borderRadius": "6px",
                               "cursor": "pointer"}),
            html.Pre(id="audit_out",
                     style={"marginTop": "12px", "padding": "10px",
                            "backgroundColor": "#1a1e27",
                            "color": "#d0d4dc",
                            "whiteSpace": "pre-wrap",
                            "fontSize": "11px", "maxHeight": "300px",
                            "overflowY": "auto"}),
        ], style={"padding": "14px"}),
        html.Hr(style={"borderColor": "#2a2f3a"}),
        html.Div([
            html.H3("DLC 1.1 sweep dispatch",
                    style={"color": "#d0d4dc"}),
            html.Div(
                "Launches the OpenFAST runner in the background against "
                "the 6-wind-speed DLC 1.1 grid. Watch the DLC 1.1 "
                "Time-series tab for results when the sweep completes.",
                style={"opacity": 0.7, "fontSize": "12px",
                       "marginBottom": "10px"},
            ),
            html.Button("Dispatch DLC 1.1 (6 wind speeds)",
                        id="btn_dlc_run", n_clicks=0,
                        style={"padding": "8px 14px",
                               "backgroundColor": "#c68b17", "color": "#fff",
                               "border": "none", "borderRadius": "6px",
                               "cursor": "pointer"}),
            html.Pre(id="dlc_dispatch_out",
                     style={"marginTop": "12px", "padding": "10px",
                            "backgroundColor": "#1a1e27",
                            "color": "#d0d4dc",
                            "whiteSpace": "pre-wrap",
                            "fontSize": "11px"}),
        ], style={"padding": "14px"}),
    ])


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


def _tab_sequential_bayes() -> html.Div:
    """Sequential Bayesian tracker tab: accumulate monitoring epochs
    and watch the posterior tighten over time."""
    return html.Div([
        html.Div([
            html.H3("Sequential Bayesian Tracker",
                    style={"marginTop": "0", "color": "#d0d4dc"}),
            html.Div(
                "Enter sensor readings for each monitoring epoch. "
                "The posterior from each epoch becomes the prior for "
                "the next, progressively tightening the diagnosis.",
                style={"opacity": 0.7, "fontSize": "12px",
                       "marginBottom": "12px"},
            ),
            html.Div([
                html.Div([
                    html.Label("Frequency ratio"),
                    dcc.Input(id="seq_freq", type="number", value=0.994,
                              step=0.001, style={"width": "120px",
                                                  "color": "#111"}),
                ], style={"marginRight": "16px"}),
                html.Div([
                    html.Label("Capacity ratio"),
                    dcc.Input(id="seq_cap", type="number", value=0.99,
                              step=0.01, style={"width": "120px",
                                                 "color": "#111"}),
                ], style={"marginRight": "16px"}),
                html.Div([
                    html.Label("Anomaly"),
                    dcc.RadioItems(
                        id="seq_anomaly",
                        options=[{"label": "no", "value": "no"},
                                 {"label": "yes", "value": "yes"}],
                        value="no", inline=True,
                        inputStyle={"marginRight": "4px",
                                    "marginLeft": "8px"}),
                ], style={"marginRight": "16px"}),
                html.Button("Add epoch", id="btn_seq_epoch", n_clicks=0,
                            style={"padding": "8px 16px",
                                   "backgroundColor": "#2b7a78",
                                   "color": "#fff", "border": "none",
                                   "borderRadius": "6px",
                                   "cursor": "pointer",
                                   "alignSelf": "flex-end"}),
                html.Button("Reset", id="btn_seq_reset", n_clicks=0,
                            style={"padding": "8px 16px",
                                   "backgroundColor": "#8b3a3a",
                                   "color": "#fff", "border": "none",
                                   "borderRadius": "6px",
                                   "cursor": "pointer",
                                   "marginLeft": "8px",
                                   "alignSelf": "flex-end"}),
            ], style={"display": "flex", "alignItems": "flex-end",
                      "gap": "4px"}),
        ], style={"padding": "14px"}),
        dcc.Graph(id="g_seq_trajectory"),
        html.Pre(id="seq_summary",
                 style={"padding": "10px 14px",
                        "backgroundColor": "#1a1e27",
                        "color": "#d0d4dc", "fontSize": "11px",
                        "whiteSpace": "pre-wrap", "maxHeight": "200px",
                        "overflowY": "auto"}),
    ])


def _tab_agent() -> html.Div:
    """Decision agent tab: run the full diagnostic pipeline and
    produce a natural-language report."""
    return html.Div([
        html.Div([
            html.H3("Diagnostic Agent",
                    style={"marginTop": "0", "color": "#d0d4dc"}),
            html.Div(
                "Enter sensor readings and click 'Run diagnosis' to "
                "produce a full natural-language maintenance report. "
                "Each click adds an epoch to the agent's sequential "
                "tracker.",
                style={"opacity": 0.7, "fontSize": "12px",
                       "marginBottom": "12px"},
            ),
            html.Div([
                html.Div([
                    html.Label("Frequency ratio"),
                    dcc.Input(id="agent_freq", type="number", value=0.985,
                              step=0.001, style={"width": "120px",
                                                  "color": "#111"}),
                ], style={"marginRight": "16px"}),
                html.Div([
                    html.Label("Capacity ratio"),
                    dcc.Input(id="agent_cap", type="number", value=0.92,
                              step=0.01, style={"width": "120px",
                                                 "color": "#111"}),
                ], style={"marginRight": "16px"}),
                html.Div([
                    html.Label("Anomaly"),
                    dcc.RadioItems(
                        id="agent_anomaly",
                        options=[{"label": "no", "value": "no"},
                                 {"label": "yes", "value": "yes"}],
                        value="yes", inline=True,
                        inputStyle={"marginRight": "4px",
                                    "marginLeft": "8px"}),
                ], style={"marginRight": "16px"}),
                html.Button("Run diagnosis", id="btn_agent_run",
                            n_clicks=0,
                            style={"padding": "8px 16px",
                                   "backgroundColor": "#c68b17",
                                   "color": "#fff", "border": "none",
                                   "borderRadius": "6px",
                                   "cursor": "pointer",
                                   "alignSelf": "flex-end"}),
            ], style={"display": "flex", "alignItems": "flex-end",
                      "gap": "4px"}),
        ], style={"padding": "14px"}),
        html.Div(id="agent_report",
                 style={"padding": "14px",
                        "backgroundColor": "#1a1e27",
                        "color": "#d0d4dc", "fontSize": "12px",
                        "whiteSpace": "pre-wrap",
                        "maxHeight": "500px", "overflowY": "auto",
                        "borderRadius": "6px", "margin": "10px 14px"}),
    ])


def create_app() -> Dash:
    try:
        scene = build_full_scene()
        scene_error = None
    except Exception as exc:
        scene = None
        scene_error = f"{type(exc).__name__}: {exc}"

    app = Dash(__name__)
    app.title = "Op^3 Viewer"

    if scene is None:
        app.layout = html.Div(
            style={"backgroundColor": "#0f1117", "color": "#d0d4dc",
                   "fontFamily": "system-ui, sans-serif",
                   "minHeight": "100vh", "padding": "24px"},
            children=[
                html.H2("Op^3 Interactive Viewer"),
                html.Div(
                    "Could not build the default scene. The viewer "
                    "requires a configured private data tree "
                    "(set OP3_PHD_ROOT) with tower_segments.csv and "
                    "tower_metadata.yaml.",
                    style={"opacity": 0.8, "marginBottom": "12px"},
                ),
                html.Pre(scene_error or "",
                         style={"backgroundColor": "#1a1e27",
                                "padding": "10px", "borderRadius": "6px",
                                "whiteSpace": "pre-wrap",
                                "color": "#ff6b6b",
                                "fontSize": "12px"}),
            ],
        )
        return app

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
                dcc.Tab(label="Compliance & Actions", value="compliance",
                        children=[_tab_compliance()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="Sequential Tracker", value="seq_bayes",
                        children=[_tab_sequential_bayes()],
                        style={"backgroundColor": "#1a1e27",
                               "color": "#d0d4dc"},
                        selected_style={"backgroundColor": "#0f1117",
                                        "color": "#4aa3ff",
                                        "borderTop": "2px solid #4aa3ff"}),
                dcc.Tab(label="Diagnostic Agent", value="agent",
                        children=[_tab_agent()],
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

    @app.callback(
        Output("audit_out", "children"),
        Input("btn_dnv", "n_clicks"),
        Input("btn_iec", "n_clicks"),
        prevent_initial_call=True,
    )
    def _run_audit(n_dnv, n_iec):
        import dash
        from ..compliance import run_dnv_audit, run_iec_audit
        trig = dash.callback_context.triggered_id
        if trig == "btn_dnv":
            result = run_dnv_audit()
        elif trig == "btn_iec":
            result = run_iec_audit()
        else:
            return ""
        import json as _json
        return _json.dumps(result, indent=2)[:3000]

    @app.callback(
        Output("dlc_dispatch_out", "children"),
        Input("btn_dlc_run", "n_clicks"),
        prevent_initial_call=True,
    )
    def _dispatch_dlc(n):
        from ..compliance import dispatch_dlc_run
        result = dispatch_dlc_run(
            family="1.1",
            wind_speeds=[6.0, 8.0, 11.4, 15.0, 19.0, 25.0],
            tmax_s=120.0,
        )
        import json as _json
        return _json.dumps(result, indent=2)

    # --- Sequential Bayesian tracker state (per-app instance) ---
    from op3.uq.sequential_bayesian import SequentialBayesianTracker
    _seq_tracker = SequentialBayesianTracker()

    @app.callback(
        Output("g_seq_trajectory", "figure"),
        Output("seq_summary", "children"),
        Input("btn_seq_epoch", "n_clicks"),
        Input("btn_seq_reset", "n_clicks"),
        Input("seq_freq", "value"),
        Input("seq_cap", "value"),
        Input("seq_anomaly", "value"),
        prevent_initial_call=True,
    )
    def _seq_update(n_epoch, n_reset, freq, cap, anom):
        import dash, json as _json
        trig = dash.callback_context.triggered_id
        if trig == "btn_seq_reset":
            _seq_tracker.reset()
            empty = go.Figure()
            empty.update_layout(
                paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
                font=dict(color="#d0d4dc"),
                title="tracker reset — add epochs to begin")
            return empty, "reset"
        if trig != "btn_seq_epoch":
            raise dash.exceptions.PreventUpdate
        _seq_tracker.update(
            freq_ratio=float(freq or 0.99),
            capacity_ratio=float(cap or 0.99),
            anomaly=(anom == "yes"),
        )
        traj = _seq_tracker.trajectory()
        epochs = [t["epoch"] for t in traj]
        means = [t["mean"] for t in traj]
        p05s = [t["p05"] for t in traj]
        p95s = [t["p95"] for t in traj]
        fig = go.Figure()
        fig.add_scatter(x=epochs, y=p95s, mode="lines",
                        line=dict(width=0), showlegend=False)
        fig.add_scatter(x=epochs, y=p05s, mode="lines",
                        fill="tonexty", fillcolor="rgba(74,163,255,0.2)",
                        line=dict(width=0), name="90% CI")
        fig.add_scatter(x=epochs, y=means, mode="lines+markers",
                        line=dict(color="#4aa3ff", width=2),
                        marker=dict(size=7), name="posterior mean")
        fig.add_hline(y=0.45, line_dash="dash", line_color="#ff6b6b",
                      annotation_text="critical")
        fig.update_layout(
            paper_bgcolor="#0f1117", plot_bgcolor="#0f1117",
            font=dict(color="#d0d4dc"),
            xaxis=dict(title="epoch", gridcolor="#2a2f3a"),
            yaxis=dict(title="scour depth (S/D)", gridcolor="#2a2f3a"),
            title=f"sequential posterior | {len(traj)} epochs | "
                  f"latest mean={means[-1]:.3f}",
            height=400, margin=dict(l=50, r=20, t=40, b=40),
        )
        summary = _json.dumps(_seq_tracker.summary(), indent=2)
        return fig, summary

    # --- Decision agent state ---
    from op3.agents.decision_agent import DecisionAgent
    _agent = DecisionAgent()

    @app.callback(
        Output("agent_report", "children"),
        Input("btn_agent_run", "n_clicks"),
        Input("agent_freq", "value"),
        Input("agent_cap", "value"),
        Input("agent_anomaly", "value"),
        prevent_initial_call=True,
    )
    def _agent_run(n, freq, cap, anom):
        import dash
        if dash.callback_context.triggered_id != "btn_agent_run":
            raise dash.exceptions.PreventUpdate
        report = _agent.run(
            freq_ratio=float(freq or 0.99),
            capacity_ratio=float(cap or 0.99),
            anomaly=(anom == "yes"),
        )
        return report.text

    return app


def main():
    app = create_app()
    app.run(debug=False, host="127.0.0.1", port=8050)


if __name__ == "__main__":
    main()
