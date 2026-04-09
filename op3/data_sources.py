"""
PHD dissertation data source resolver (single source of truth).

The Op^3 framework is the *computational engine* for the Kim 2026
PhD dissertation, but the dissertation's authoritative data (field
OMA, raw OptumGX output, the 1794-sample MC encoder database, the
SiteA site characterisation) lives at

    F:/TREE_OF_THOUGHT/PHD/

which is a much larger working directory than the Op^3 repo can or
should mirror. This module is the **single point of access** to the
PHD data from inside Op^3. It exposes:

* ``get_phd_root()``     -- returns the PHD root directory, or None
                            if not present (CI / reviewer machines)
* ``get_phd_path(rel)``  -- resolves a PHD-relative path to an
                            absolute Path, verifying existence
* ``find_phd_data(*candidates)`` -- tries each candidate path in
                                    order (PHD first, then Op^3's
                                    committed snapshot) and returns
                                    the first one that exists

Environment variable
--------------------
Set ``OP3_PHD_ROOT`` to override the default PHD location:

    export OP3_PHD_ROOT=/home/reviewer/dissertation/PHD

If the env var is unset, the default is
``F:/TREE_OF_THOUGHT/PHD`` (the author's development machine).

Reproducibility policy
----------------------
The author's machine has PHD present; scripts that call
``find_phd_data`` will pick up the live dissertation data.
Reviewer machines without PHD get a graceful fallback to the
committed v0.3.2 snapshots under ``data/fem_results/site_a_real_*``
so the V&V suite and the calibration regression still pass.

Never maintain two authoritative copies of the same file. If a
file exists in PHD, Op^3 links to it; Op^3 keeps only the
dated snapshots needed for reviewer reproducibility.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_DEFAULT_PHD_ROOT = Path("F:/TREE_OF_THOUGHT/PHD")


def get_phd_root() -> Optional[Path]:
    """
    Return the PHD root directory if it exists, else None.

    Resolution order:
      1. ``OP3_PHD_ROOT`` environment variable
      2. Default location ``F:/TREE_OF_THOUGHT/PHD``
      3. None if neither exists
    """
    env = os.environ.get("OP3_PHD_ROOT")
    if env:
        p = Path(env)
        if p.exists():
            return p
    if _DEFAULT_PHD_ROOT.exists():
        return _DEFAULT_PHD_ROOT
    return None


def get_phd_path(relative: str) -> Path:
    """
    Resolve a PHD-relative path. Raises ``FileNotFoundError`` if the
    PHD root cannot be located or the file does not exist.

    Example
    -------
    >>> get_phd_path("data/optumgx/dissipation/spring_params_v4_dissipation.csv")
    PosixPath('/.../PHD/data/optumgx/dissipation/spring_params_v4_dissipation.csv')
    """
    root = get_phd_root()
    if root is None:
        raise FileNotFoundError(
            "PHD dissertation root not found. Set OP3_PHD_ROOT or "
            "ensure F:/TREE_OF_THOUGHT/PHD exists."
        )
    p = root / relative
    if not p.exists():
        raise FileNotFoundError(f"PHD file not found: {p}")
    return p


def find_phd_data(*candidates: str, op3_fallback: Optional[str] = None) -> Path:
    """
    Try each candidate path in order and return the first that
    exists. Candidates are checked under the PHD root first; if none
    exist and ``op3_fallback`` is provided, the fallback is checked
    relative to the Op^3 repo root.

    This is the recommended entry point for scripts that should work
    both on the author's development machine (PHD available) and on
    reviewer machines (only committed Op^3 snapshots).

    Parameters
    ----------
    *candidates : str
        Paths relative to the PHD root, tried in order.
    op3_fallback : str, optional
        Path relative to the Op^3 repo root, used if no PHD
        candidate exists.

    Returns
    -------
    pathlib.Path
        First existing path.

    Raises
    ------
    FileNotFoundError
        If no candidate exists anywhere.
    """
    root = get_phd_root()
    if root is not None:
        for rel in candidates:
            p = root / rel
            if p.exists():
                return p

    if op3_fallback is not None:
        op3_root = Path(__file__).resolve().parent.parent
        p = op3_root / op3_fallback
        if p.exists():
            return p

    tried = list(candidates)
    if op3_fallback:
        tried.append(f"op3:{op3_fallback}")
    raise FileNotFoundError(
        f"None of the data candidates exist: {tried}. "
        f"PHD root: {root or '<not set>'}"
    )


# ---------------------------------------------------------------------------
# Canonical PHD data paths (the SSOT contract)
# ---------------------------------------------------------------------------

def site_a_spring_params() -> Path:
    """Real OptumGX SiteA spring parameters (v4 dissipation pipeline).

    Proprietary -- no public fallback. Configure ``OP3_PHD_ROOT`` to
    point at the private data tree. Raises ``FileNotFoundError``
    otherwise.
    """
    return find_phd_data(
        "data/optumgx/dissipation/spring_params_v4_dissipation.csv",
    )


def site_a_dissipation_skirt() -> Path:
    """Real OptumGX SiteA dissipation field (Vmax case, skirt-only).

    Proprietary -- no public fallback.
    """
    return find_phd_data(
        "data/optumgx/dissipation/dissipation_skirt_Vmax.csv",
    )


def site_a_fn_vs_scour() -> Path:
    """Real OptumGX SiteA f1 vs scour sweep (9 scour depths).

    Proprietary -- no public fallback.
    """
    return find_phd_data(
        "data/optumgx/dissipation/fn_vs_scour_v4_dissipation.csv",
    )


def site_a_mc_database() -> Path:
    """
    Real 1794-sample OptumGX MC database used by the Ch8 digital
    twin encoder. Authoritative at PHD/data/integrated_database_1794.csv;
    no Op^3 fallback because it is too large (~80 MB) to commit.
    """
    return find_phd_data(
        "data/integrated_database_1794.csv",
        "data/mc_combined_1800.csv",
    )


def site_a_field_oma() -> Path:
    """
    SiteA 20039-RANSAC-window field operational modal analysis
    database (Ch. 5).
    """
    return find_phd_data(
        "data/field/site_a_ransac_windows.csv",
        "data/field/site_a_ransac_windows.parquet",
    )


def phd_optumgx_raw_plates_dir() -> Path:
    """Directory containing the 128 raw OptumGX plate export .xlsx files."""
    root = get_phd_root()
    if root is None:
        raise FileNotFoundError("PHD root not set")
    p = root / "data/optumgx/raw_plates"
    if not p.exists():
        raise FileNotFoundError(f"raw_plates directory missing: {p}")
    return p


def phd_optumgx_vh_envelopes_dir() -> Path:
    """Directory containing the 11 scour-dependent VH envelope .xlsx files."""
    root = get_phd_root()
    if root is None:
        raise FileNotFoundError("PHD root not set")
    p = root / "data/optumgx/VH_envelopes"
    if not p.exists():
        raise FileNotFoundError(f"VH_envelopes directory missing: {p}")
    return p
