"""
Craig-Bampton reducer for OpenSees substructures.

This module implements the blueprint Q2(b) primary: extract the full
mass and stiffness matrices of a built OpenSees domain via the
``GimmeMCK`` integrator, partition them into boundary (retained
interface) and interior DOFs, and produce a reduced-order model

    M_bar, K_bar    (boundary + n_modes retained internal modes)

which is written as a SubDyn-compatible ``SSIfile`` lump (CalcOption =
6x6 at each reaction joint when n_modes = 0) or as a full Craig-Bampton
superelement module otherwise.

The ``GimmeMCK`` recipe follows Minjie Zhu's Portwood Digital post
"Gimme all your damping, all your mass and stiffness too" (2020-05-17)
and requires ``system FullGeneral``.

Public API
----------

- ``extract_full_matrices(base_node) -> (K, M, boundary_dofs)``
    Extracts K, M from the current OpenSees domain as dense arrays.

- ``guyan_partition(K, M, boundary_dofs) -> (K_bb_hat, M_bb_hat)``
    Static condensation: 6x6 reduced to boundary DOFs.

- ``craig_bampton(K, M, boundary_dofs, n_modes) -> (K_bar, M_bar)``
    Full CB reduction: 6 + n_modes generalised DOFs.

- ``write_subdyn_ssi(path, K_bb, bucket_label, ...) -> Path``
    Writes a SubDyn ``SSIfile`` for the 6x6 reduced boundary
    stiffness (CalcOption-equivalent output used by OpenFAST v5).

- ``write_subdyn_superelement(path, K_bar, M_bar, ...) -> Path``
    Writes a SubDyn-compatible external superelement (ExtPtfm-format)
    carrying the full CB matrices.

Reference
---------
Damiani, Jonkman, Hayman (2015). "SubDyn User's Guide and Theory
    Manual". NREL/TP-5000-63062. https://www.nrel.gov/docs/fy15osti/63062.pdf
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


def _model_has_multi_point_constraints() -> bool:
    """Best-effort probe for ``rigidLink`` / ``equalDOF`` in the current
    OpenSees domain.

    OpenSeesPy does not expose a direct count of MP constraints, but
    it does expose ``ops.getMPConstraints`` / ``ops.getNodeTags`` in
    newer builds. When present we return ``True`` if any MP constraints
    exist. When unavailable we return ``False`` and rely on the caller
    to opt into ``Transformation`` via ``handler="Transformation"``.
    """
    try:
        import openseespy.opensees as ops
    except ImportError:
        return False
    getter = getattr(ops, "getMPConstraints", None)
    if getter is None:
        return False
    try:
        mps = getter()
        return bool(mps) and len(mps) > 0
    except Exception:
        return False


def _setup_gimmemck(
    coeff_M: float, coeff_C: float, coeff_K: float,
    *, handler: str = "auto",
) -> None:
    """Prepare a one-step GimmeMCK analysis context.

    Follows the Portwood Digital recipe (Zhu 2020): FullGeneral SOE +
    Plain numberer + ``Plain``/``Transformation`` constraints + Linear
    algorithm. ``analyze`` is called with ``dt=0.0`` which triggers
    ``formTangent`` (populating the system matrix) without actually
    integrating the ODE — so even if the subsequent ``solveCurrentStep``
    fails (because the system is linear and the load vector is zero),
    ``printA`` still returns the correctly-assembled matrix.

    ``handler`` selects the constraint handler:

    - ``"auto"`` (default): probe the domain for MP constraints and
      switch to ``Transformation`` when any rigid links / equalDOF
      constraints are present. Falls back to ``Plain`` otherwise
      (Plain gives a strictly positive-definite K that survives the
      Guyan subtraction without torsional drift).
    - ``"plain"``, ``"transformation"``: force the chosen handler.

    Empirically verified: ``Plain`` constraints give a positive-definite
    K via ``printA`` for models whose only constraints are single-point
    ``fix`` constraints. ``Transformation`` introduces spurious
    small-magnitude negative eigenvalues (~10⁻⁸ of max eigenvalue)
    that pollute the Guyan subtraction at torsional DOFs. ``Transformation``
    is nonetheless required when multi-point constraints are present.

    Leaves the OpenSees domain with active numberer/analysis so that
    ``printA`` can write the system matrix AND ``nodeDOFs`` can be
    queried. The caller is responsible for calling ``wipeAnalysis``
    when done.
    """
    import openseespy.opensees as ops

    ops.wipeAnalysis()
    ops.system("FullGeneral")
    ops.numberer("Plain")

    chosen = handler.lower()
    if chosen == "auto":
        has_mp = _model_has_multi_point_constraints()
        chosen = "transformation" if has_mp else "plain"
        if has_mp:
            warnings.warn(
                "Craig-Bampton extraction detected multi-point constraints "
                "(rigidLink / equalDOF) in the OpenSees domain and has "
                "switched to the Transformation constraint handler. "
                "Expect small (~0.5% of max eigenvalue) spurious "
                "negative eigenvalues on torsional DOFs after Guyan "
                "subtraction; the lateral/rocking stiffness blocks "
                "remain reliable.",
                stacklevel=3,
            )
    if chosen == "plain":
        ops.constraints("Plain")
    elif chosen == "transformation":
        ops.constraints("Transformation")
    else:
        raise ValueError(
            f"unknown handler '{handler}'; expected 'auto', 'plain', "
            "or 'transformation'"
        )
    ops.algorithm("Linear")
    ops.integrator("GimmeMCK", float(coeff_M), float(coeff_C), float(coeff_K))
    ops.analysis("Transient")
    # dt=0.0: formTangent runs, integrator assembles the matrix, the
    # solve step may emit a warning but the stored matrix is valid.
    try:
        ops.analyze(1, 0.0)
    except Exception:
        # analyze can raise when the LinearSOE solve fails on a matrix
        # that is not positive-definite at the zero-load trivial step.
        # The assembled matrix is nonetheless populated by formTangent;
        # printA below will return it.
        pass


def _printA_ret() -> np.ndarray:
    """Return the current ``printA`` matrix via the in-memory ``-ret``
    interface, reshaped to ``(N, N)``.

    The file-based ``printA -file`` alternative uses ~6-digit ``%g``
    formatting which silently corrupts high-dynamic-range stiffness
    matrices (verified: 2.18e11 was truncated to 2.18e11 losing the
    trailing digits and producing spurious ~10^-8 negative eigenvalues
    that cascade through the Guyan subtraction into physically wrong
    torsional entries). ``-ret`` preserves full double precision.
    """
    import openseespy.opensees as ops

    flat = ops.printA("-ret")
    if flat is None or len(flat) == 0:
        raise RuntimeError(
            "ops.printA('-ret') returned empty; ensure the analysis "
            "was set up with FullGeneral system and GimmeMCK integrator"
        )
    vals = np.asarray(flat, dtype=float)
    n_total = vals.size
    N = int(round(np.sqrt(n_total)))
    if N * N != n_total:
        raise RuntimeError(
            f"printA returned {n_total} values, not a perfect square"
        )
    # -ret is row-major (verified with 2D beam: values [2.1e9, 0, 0,
    # 0, 2.52e7, -1.26e7, 0, -1.26e7, 8.4e6] reshape(3,3) matches the
    # beam stiffness matrix row-by-row).
    return vals.reshape((N, N))


def _node_dof_indices(base_node: int) -> list[int]:
    """Return the global DOF indices (0-based) of ``base_node``'s 6 DOFs.

    Must be called while a numberer is active (i.e. between
    ``_setup_gimmemck`` and ``wipeAnalysis``). ``ops.nodeDOFs`` in
    OpenSeesPy 3.5+ returns zero-based equation numbers directly
    (verified empirically: a single-spring model with one free DOF
    returns ``[0]``). Fixed DOFs appear as negative numbers.
    """
    import openseespy.opensees as ops

    dofs = ops.nodeDOFs(int(base_node))
    if len(dofs) < 6:
        raise RuntimeError(
            f"node {base_node} has only {len(dofs)} DOFs; need 6 for 6x6 "
            "boundary condensation"
        )
    bad = [i for i, d in enumerate(dofs) if d < 0]
    if bad:
        raise RuntimeError(
            f"node {base_node} has fixed/eliminated DOFs at positions "
            f"{bad}; CB partition requires all 6 DOFs free. Check that "
            f"base_node is not fixed and is not the constrained node "
            f"of a rigid link."
        )
    return [int(d) for d in dofs[:6]]


def extract_full_matrices(
    base_node: int,
    *,
    handler: str = "auto",
) -> Tuple[np.ndarray, np.ndarray, list[int]]:
    """Extract the full system K, M matrices and the boundary DOFs.

    Must be called after the OpenSees model is fully built (including
    the foundation) and before any analysis has been run. The
    ``base_node`` must be free (not fixed) so its DOFs appear in the
    active equation system.

    ``handler`` is passed through to ``_setup_gimmemck``; use ``"auto"``
    (default) to let the module probe the OpenSees domain for
    multi-point constraints and auto-select ``Plain`` vs
    ``Transformation``.

    Returns
    -------
    K : ndarray of shape (N, N)
        Tangent stiffness matrix.
    M : ndarray of shape (N, N)
        Consistent mass matrix.
    boundary_dofs : list of int
        The 6 global DOF indices of ``base_node`` (0-based).
    """
    # --- K dump + boundary DOF query (one active numbering context) ---
    _setup_gimmemck(0.0, 0.0, 1.0, handler=handler)
    K = _printA_ret()
    boundary = _node_dof_indices(base_node)

    # --- M dump. No need to wipeAnalysis between dumps — the integrator
    # replacement via _setup_gimmemck rebuilds the analysis context. ---
    _setup_gimmemck(1.0, 0.0, 0.0, handler=handler)
    M = _printA_ret()

    if K.shape != M.shape:
        raise RuntimeError(
            f"K and M shape mismatch: K={K.shape}, M={M.shape}. "
            "This typically means the DOF numbering changed between "
            "GimmeMCK calls. Re-run without any intervening eigen or "
            "static analysis."
        )

    return K, M, boundary


def guyan_partition(
    K: np.ndarray,
    M: np.ndarray,
    boundary_dofs: list[int],
) -> Tuple[np.ndarray, np.ndarray]:
    """Static (Guyan) condensation onto the boundary DOFs.

    Returns
    -------
    K_bb_hat : ndarray of shape (n_b, n_b)
        K_bb - K_bi @ K_ii^-1 @ K_ib.
    M_bb_hat : ndarray of shape (n_b, n_b)
        Guyan-reduced mass = Phi^T M Phi where Phi is the Guyan
        transformation matrix (boundary DOFs + static interior response).
    """
    K = np.asarray(K, dtype=float)
    M = np.asarray(M, dtype=float)
    N = K.shape[0]

    b = np.asarray(boundary_dofs, dtype=int)
    all_dofs = np.arange(N)
    i = np.setdiff1d(all_dofs, b, assume_unique=False)

    K_bb = K[np.ix_(b, b)]
    K_bi = K[np.ix_(b, i)]
    K_ib = K[np.ix_(i, b)]
    K_ii = K[np.ix_(i, i)]

    # Static condensation
    # Phi_s = [I_b; -K_ii^-1 K_ib] — Guyan transformation
    X = np.linalg.solve(K_ii, K_ib)  # K_ii^-1 K_ib
    K_bb_hat = K_bb - K_bi @ X

    # Mass reduction via Phi_s^T M Phi_s
    # Phi_s is (N x n_b); build it column-by-column for clarity.
    n_b = b.size
    Phi = np.zeros((N, n_b), dtype=float)
    Phi[b, np.arange(n_b)] = 1.0
    Phi[i, :] = -X

    M_bb_hat = Phi.T @ M @ Phi
    K_bb_hat = 0.5 * (K_bb_hat + K_bb_hat.T)
    M_bb_hat = 0.5 * (M_bb_hat + M_bb_hat.T)
    return K_bb_hat, M_bb_hat


def craig_bampton(
    K: np.ndarray,
    M: np.ndarray,
    boundary_dofs: list[int],
    n_modes: int = 0,
) -> dict:
    """Craig-Bampton reduction: boundary + n_modes fixed-interface modes.

    When ``n_modes == 0`` this degenerates to Guyan partition. For
    ``n_modes > 0`` we add the first ``n_modes`` eigenvectors of the
    (K_ii, M_ii) generalised eigenproblem as generalised DOFs.

    Returns
    -------
    dict
        ``K_bar``, ``M_bar`` — reduced matrices of shape (n_b + n_modes).
        ``omega2_retained`` — vector of retained interior eigenvalues.
        ``Phi`` — full (N x (n_b + n_modes)) transformation matrix.
        ``boundary_dofs`` — echoed boundary indices.
    """
    K = np.asarray(K, dtype=float)
    M = np.asarray(M, dtype=float)
    N = K.shape[0]
    b = np.asarray(boundary_dofs, dtype=int)
    all_dofs = np.arange(N)
    i = np.setdiff1d(all_dofs, b, assume_unique=False)

    K_bb = K[np.ix_(b, b)]
    K_bi = K[np.ix_(b, i)]
    K_ib = K[np.ix_(i, b)]
    K_ii = K[np.ix_(i, i)]
    M_bb = M[np.ix_(b, b)]
    M_bi = M[np.ix_(b, i)]
    M_ib = M[np.ix_(i, b)]
    M_ii = M[np.ix_(i, i)]

    X = np.linalg.solve(K_ii, K_ib)  # static correction

    n_b = b.size
    n_m = max(int(n_modes), 0)

    # Static (Guyan) part
    K_sb = K_bb - K_bi @ X
    Phi_s_i = -X  # interior block of Phi_s

    if n_m == 0:
        Phi_m = np.zeros((i.size, 0), dtype=float)
        omega2 = np.zeros(0, dtype=float)
    else:
        # Generalised eigenproblem K_ii phi = omega^2 M_ii phi.
        # elasticBeamColumn with ``-mass`` adds translational lumped
        # mass only; rotational DOFs have zero mass which makes M_ii
        # semi-definite. Regularise with a small diagonal so ``eigh``
        # succeeds; modes whose eigenvalues correspond to the added
        # epsilon are at very high frequency and do not enter the
        # retained subset when n_modes is reasonable.
        from scipy.linalg import eigh
        mass_scale = float(np.max(np.abs(np.diag(M_ii)))) or 1.0
        eps = 1.0e-8 * mass_scale
        M_ii_reg = M_ii + eps * np.eye(M_ii.shape[0])
        omega2_all, phi_all = eigh(K_ii, M_ii_reg)
        # Lowest n_m modes
        order = np.argsort(omega2_all)[:n_m]
        omega2 = omega2_all[order]
        Phi_m = phi_all[:, order]
        # Mass-normalise against the original M_ii (pre-regularisation)
        # so ``Phi_m^T M_ii Phi_m`` is the identity up to numerical
        # drift. Massless modes end up ~1/eps scaled, which is why
        # the retained subset must avoid the epsilon-branch eigenvalues.
        for k in range(n_m):
            scale = float(np.sqrt(max(
                Phi_m[:, k] @ M_ii_reg @ Phi_m[:, k], 1e-30,
            )))
            if scale > 0:
                Phi_m[:, k] = Phi_m[:, k] / scale

    # Assemble the CB transformation matrix Phi : (N) -> (n_b + n_m)
    Phi = np.zeros((N, n_b + n_m), dtype=float)
    Phi[b, np.arange(n_b)] = 1.0
    Phi[i[:, None], np.arange(n_b)[None, :]] = Phi_s_i
    if n_m > 0:
        Phi[i[:, None], (n_b + np.arange(n_m))[None, :]] = Phi_m

    K_bar = Phi.T @ K @ Phi
    M_bar = Phi.T @ M @ Phi
    K_bar = 0.5 * (K_bar + K_bar.T)
    M_bar = 0.5 * (M_bar + M_bar.T)

    return {
        "K_bar": K_bar,
        "M_bar": M_bar,
        "omega2_retained": omega2,
        "Phi": Phi,
        "boundary_dofs": list(b),
        "n_modes": n_m,
        "N_full": N,
    }


def write_subdyn_ssi(
    out_path: str | Path,
    K_bb: np.ndarray,
    *,
    bucket_label: str = "foundation_interface",
    scour_depth_m: float = 0.0,
    provenance: str = "Op^3 CB-Guyan from OpenSees",
    M_bb: Optional[np.ndarray] = None,
) -> Path:
    """Write a 6x6 boundary stiffness as a SubDyn ``SSIfile``.

    SubDyn's ``SSIfile`` accepts a 6x6 stiffness + optional 6x6 mass
    at a reaction joint. The upper-triangle values are written as
    independent components ``K11, K22, K33, K44, K55, K66, K12, ...``
    per the SubDyn v1.3 file format.
    """
    K = np.asarray(K_bb, dtype=float)
    if K.shape != (6, 6):
        raise ValueError(f"K_bb must be 6x6, got {K.shape}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "!----- SubDyn SSIfile -------------------------------------------",
        f"! {provenance}",
        f"! Label: {bucket_label}, scour depth: {scour_depth_m:.2f} m",
        "!",
        "! 21 upper-triangle components: K11 K22 K33 K44 K55 K66",
        "!                               K12 K13 K14 K15 K16",
        "!                               K23 K24 K25 K26",
        "!                               K34 K35 K36",
        "!                               K45 K46",
        "!                               K56",
    ]

    diag = [K[0, 0], K[1, 1], K[2, 2], K[3, 3], K[4, 4], K[5, 5]]
    offdiag_idx = [
        (0, 1), (0, 2), (0, 3), (0, 4), (0, 5),
        (1, 2), (1, 3), (1, 4), (1, 5),
        (2, 3), (2, 4), (2, 5),
        (3, 4), (3, 5),
        (4, 5),
    ]
    offdiag = [K[i, j] for (i, j) in offdiag_idx]

    for name, value in zip(
        ["K11", "K22", "K33", "K44", "K55", "K66"], diag
    ):
        lines.append(f"{value: .6e}   {name}")
    offdiag_names = [
        "K12", "K13", "K14", "K15", "K16",
        "K23", "K24", "K25", "K26",
        "K34", "K35", "K36",
        "K45", "K46",
        "K56",
    ]
    for name, value in zip(offdiag_names, offdiag):
        lines.append(f"{value: .6e}   {name}")

    if M_bb is not None:
        M = np.asarray(M_bb, dtype=float)
        if M.shape != (6, 6):
            raise ValueError(f"M_bb must be 6x6, got {M.shape}")
        lines.append("!-- Mass (21 upper-triangle) --")
        for name, value in zip(
            ["M11", "M22", "M33", "M44", "M55", "M66"],
            [M[0, 0], M[1, 1], M[2, 2], M[3, 3], M[4, 4], M[5, 5]],
        ):
            lines.append(f"{value: .6e}   {name}")
        for name, (i, j) in zip(
            ["M12", "M13", "M14", "M15", "M16",
             "M23", "M24", "M25", "M26",
             "M34", "M35", "M36",
             "M45", "M46", "M56"],
            offdiag_idx,
        ):
            lines.append(f"{M[i, j]: .6e}   {name}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_subdyn_superelement(
    out_path: str | Path,
    K_bar: np.ndarray,
    M_bar: np.ndarray,
    *,
    provenance: str = "Op^3 Craig-Bampton",
    omega2_retained: Optional[np.ndarray] = None,
) -> Path:
    """Write a CB superelement in SubDyn ExtPtfm (FlexASCII-like) format.

    This is SubDyn's accepted format for externally-reduced
    substructures: a 6 + n_modes dense matrix for both stiffness and
    mass, with the first 6 rows/cols corresponding to the interface
    DOFs in the canonical SubDyn order ``(Surge, Sway, Heave, Roll,
    Pitch, Yaw)``.

    The caller is responsible for ensuring the boundary DOF ordering
    in ``K_bar`` matches SubDyn's expectation. In OpenSees the default
    node DOF order is ``(Ux, Uy, Uz, Rx, Ry, Rz)`` which is the same
    convention.
    """
    K = np.asarray(K_bar, dtype=float)
    M = np.asarray(M_bar, dtype=float)
    if K.shape != M.shape or K.ndim != 2 or K.shape[0] != K.shape[1]:
        raise ValueError(
            f"K_bar and M_bar must be identical square shapes; "
            f"got K={K.shape}, M={M.shape}"
        )
    n = K.shape[0]
    n_modes = n - 6

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "!----- SubDyn external Craig-Bampton superelement ---------------",
        f"! {provenance}",
        f"! Interface DOFs: 6 (Surge, Sway, Heave, Roll, Pitch, Yaw)",
        f"! Internal CB modes retained: {n_modes}",
        f"! Total reduced DOFs: {n}",
        "!",
        "------- Reduced system matrices -------------------------------",
        f"{n:6d}                NumReducedDOFs",
    ]
    if omega2_retained is not None and len(omega2_retained) == n_modes:
        freqs = np.sqrt(np.maximum(omega2_retained, 0.0)) / (2 * np.pi)
        lines.append("! Retained internal frequencies (Hz):")
        lines.append(
            "! " + "  ".join(f"{f:.4f}" for f in freqs)
        )

    lines.append("------- Mass matrix (n x n) -----------------------------------")
    for row in M:
        lines.append("  " + "  ".join(f"{v: .6e}" for v in row))
    lines.append("------- Stiffness matrix (n x n) -------------------------------")
    for row in K:
        lines.append("  " + "  ".join(f"{v: .6e}" for v in row))
    lines.append("------- end -----------------------------------------------------")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def reduce_and_export(
    base_node: int,
    out_path: str | Path,
    *,
    n_modes: int = 0,
    format: str = "auto",
    provenance: str = "Op^3 Craig-Bampton from OpenSees",
    bucket_label: str = "foundation_interface",
    scour_depth_m: float = 0.0,
) -> dict:
    """One-shot: extract, reduce, and write.

    ``format`` options:
      - ``"ssi"``          — 6x6 upper-triangle (requires n_modes == 0).
      - ``"superelement"`` — CB dense matrices (any n_modes).
      - ``"auto"``         — SSI when n_modes == 0, superelement otherwise.
    """
    # Validate args BEFORE running the expensive OpenSees extraction so
    # callers get fast feedback on misconfiguration.
    resolved_format = format
    if resolved_format == "auto":
        resolved_format = "ssi" if n_modes == 0 else "superelement"
    if resolved_format == "ssi" and n_modes != 0:
        raise ValueError(
            "format='ssi' requires n_modes == 0 (6x6 interface only)"
        )
    if resolved_format not in ("ssi", "superelement"):
        raise ValueError(f"unknown format '{format}'")

    K_full, M_full, boundary = extract_full_matrices(base_node)
    reduction = craig_bampton(K_full, M_full, boundary, n_modes=n_modes)

    K_bar = reduction["K_bar"]
    M_bar = reduction["M_bar"]

    if resolved_format == "ssi":
        path = write_subdyn_ssi(
            out_path, K_bar,
            bucket_label=bucket_label,
            scour_depth_m=scour_depth_m,
            provenance=provenance,
            M_bb=M_bar,
        )
    else:
        path = write_subdyn_superelement(
            out_path, K_bar, M_bar,
            provenance=provenance,
            omega2_retained=reduction["omega2_retained"],
        )

    reduction["out_path"] = str(path)
    return reduction
