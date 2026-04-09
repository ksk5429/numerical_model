"""
Runtime loader for a project-specific tapered-tubular tower.

The numeric segment table (id, thickness, length, top/bottom OD) is
**proprietary** and must never be committed to this public repository.
Instead, it is loaded at runtime from a CSV whose location is
resolved through ``op3.data_sources``. The CSV schema is:

    id,thickness_mm,length_mm,OD_top_mm,OD_bot_mm

Rows are ordered from the base of the tower upward.

Environment
-----------
Set ``OP3_PHD_ROOT`` (or otherwise configure ``op3.data_sources``) to
point at the private data tree. If the CSV cannot be located, every
public function in this module raises ``RuntimeError`` with a clear
message -- we never silently fall back to synthetic values.

Public API (unchanged)
----------------------
  * ``SITE_A_SEGMENTS``        list[tuple]  -- lazy-loaded
  * ``section_properties()``    -> list[dict]
  * ``SITE_A_REAL_TOWER_TEMPLATE``  dict
"""
from __future__ import annotations

import os
from typing import List, Tuple

import numpy as np


# --- Material + global parameters (non-proprietary, published
# conventions) ---------------------------------------------------------
E_STEEL_PA = 210e9
G_STEEL_PA = 80.8e9
RHO_EFFECTIVE_KG_M3 = 8500.0   # inflated per NREL / DTU convention


def _load_metadata() -> dict:
    """Load site metadata (base elev, hub height) from a private
    YAML alongside the segment CSV. Returns a dict with safe
    defaults if the file cannot be resolved."""
    try:
        import yaml
        from op3.data_sources import find_phd_data
        rel = os.environ.get(
            "OP3_TOWER_METADATA_YAML",
            "data/private/tower_metadata.yaml",
        )
        p = find_phd_data(rel)
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


_meta = _load_metadata()
BASE_ELEV_M = float(
    os.environ.get("OP3_TOWER_BASE_ELEV_M",
                   _meta.get("base_elev_m", 0.0))
)
HUB_HEIGHT_M = float(
    os.environ.get("OP3_TOWER_HUB_HEIGHT_M",
                   _meta.get("hub_height_m", 0.0))
)


# --- Lazy loader ------------------------------------------------------

_SEGMENTS_CACHE: List[Tuple[str, float, float, float, float]] | None = None


def _load_segments() -> List[Tuple[str, float, float, float, float]]:
    """Read the proprietary segment CSV through ``op3.data_sources``."""
    global _SEGMENTS_CACHE
    if _SEGMENTS_CACHE is not None:
        return _SEGMENTS_CACHE

    try:
        import pandas as pd
        from op3.data_sources import find_phd_data
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "op3.data_sources unavailable -- cannot load tower segments"
        ) from exc

    rel = os.environ.get(
        "OP3_TOWER_SEGMENTS_CSV",
        "data/private/tower_segments.csv",
    )
    try:
        csv_path = find_phd_data(rel)
    except Exception as exc:
        raise RuntimeError(
            f"tower segment CSV not found at '{rel}'. "
            "Set OP3_PHD_ROOT (or OP3_TOWER_SEGMENTS_CSV) to the private "
            "data tree, or provide a non-proprietary substitute."
        ) from exc

    df = pd.read_csv(csv_path)
    required = {"id", "thickness_mm", "length_mm", "OD_top_mm", "OD_bot_mm"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"{csv_path}: missing columns {sorted(missing)}")

    _SEGMENTS_CACHE = [
        (str(r.id),
         float(r.thickness_mm),
         float(r.length_mm),
         float(r.OD_top_mm),
         float(r.OD_bot_mm))
        for r in df.itertuples(index=False)
    ]
    return _SEGMENTS_CACHE


class _SegmentsProxy:
    """Module-level object that acts like a list but lazy-loads the
    proprietary segment data on first access. Preserves the legacy
    ``SITE_A_SEGMENTS`` API without committing any numeric values.
    """

    def __iter__(self):
        return iter(_load_segments())

    def __len__(self):
        return len(_load_segments())

    def __getitem__(self, idx):
        return _load_segments()[idx]


SITE_A_SEGMENTS = _SegmentsProxy()


def section_properties():
    """Return per-segment ``(z_bot, z_top, A, I, m_per_L)`` from the
    base upward. All units SI.

    Raises ``RuntimeError`` if the private segment CSV cannot be
    resolved. This is intentional -- no synthetic fallback.
    """
    segs = _load_segments()
    out = []
    z = BASE_ELEV_M
    for seg_id, t_mm, h_mm, od_top_mm, od_bot_mm in segs:
        t = t_mm / 1000.0
        h = h_mm / 1000.0
        od_avg = 0.5 * (od_top_mm + od_bot_mm) / 1000.0
        ro = od_avg / 2.0
        ri = ro - t
        A = np.pi * (ro ** 2 - ri ** 2)
        I = np.pi * (ro ** 4 - ri ** 4) / 4.0
        m_per_L = RHO_EFFECTIVE_KG_M3 * A
        out.append({
            "id": seg_id,
            "z_bot": z,
            "z_top": z + h,
            "length_m": h,
            "OD_m": od_avg,
            "t_m": t,
            "A_m2": A,
            "I_m4": I,
            "m_per_L_kg_m": m_per_L,
        })
        z += h
    return out


SITE_A_REAL_TOWER_TEMPLATE = {
    "base_elev_m": BASE_ELEV_M,
    "hub_height_m": HUB_HEIGHT_M,
    "E_Pa": E_STEEL_PA,
    "G_Pa": G_STEEL_PA,
    "density_kg_m3": RHO_EFFECTIVE_KG_M3,
    "source": "runtime-loaded from op3.data_sources (private CSV)",
}


if __name__ == "__main__":
    try:
        props = section_properties()
        print(f"Loaded {len(props)} segments from private data store.")
    except RuntimeError as e:
        print(f"[proprietary data unavailable] {e}")
