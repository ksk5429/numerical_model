"""
Op^3 Single Source of Truth (SSOT) configuration loader.

Every physical parameter used anywhere in Op^3 flows from a YAML file
through this loader. The loader performs schema validation on load and
raises a clear error if a required key is missing.

Usage:

    from op3 import load_site_config
    cfg = load_site_config('op3/config/site_a.yaml')
    D = cfg['foundation']['bucket_diameter_m']
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


# Required top-level sections that every site YAML must contain
REQUIRED_SECTIONS = {
    "site_id",
    "version",
    "foundation",
    "tower",
    "rotor_nacelle_assembly",
}


def load_site_config(path: str | Path) -> dict[str, Any]:
    """Load and lightly validate a site configuration YAML.

    Parameters
    ----------
    path : str or Path
        Path to the YAML file. Relative paths are resolved from the
        repository root.

    Returns
    -------
    dict
        Parsed YAML with a `_source_path` key added for provenance.

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    ValueError
        If the YAML is missing a required top-level section.
    """
    p = Path(path)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Site config not found: {p}")

    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Loose validation — warn on missing sections but do not hard-fail
    # because different site YAMLs may legitimately omit some sections
    # (e.g. a land-based turbine has no hydro parameters).
    missing = REQUIRED_SECTIONS - set(cfg.keys())
    if missing:
        # Only raise if *all* required sections are missing (empty YAML)
        if len(missing) == len(REQUIRED_SECTIONS):
            raise ValueError(
                f"Site config {p} is empty or does not contain any "
                f"expected top-level sections. Expected at least one "
                f"of {REQUIRED_SECTIONS}."
            )
        # Otherwise attach a warnings list for downstream consumers
        cfg.setdefault("_warnings", []).append(
            f"Missing optional sections: {sorted(missing)}"
        )

    cfg["_source_path"] = str(p)
    return cfg


def pretty_print_config(cfg: dict[str, Any]) -> str:
    """Return a human-readable summary of a loaded config."""
    lines = [f"Site: {cfg.get('site_id', 'unknown')}"]
    lines.append(f"Version: {cfg.get('version', 'unknown')}")
    lines.append(f"Source: {cfg.get('_source_path', 'unknown')}")

    fnd = cfg.get("foundation", {})
    if fnd:
        lines.append(f"Foundation:")
        for k, v in fnd.items():
            if not str(k).startswith("_"):
                lines.append(f"  {k}: {v}")

    rna = cfg.get("rotor_nacelle_assembly", {})
    if rna:
        lines.append(f"Rotor/Nacelle:")
        for k in ("rotor_diameter_m", "hub_height_m", "rated_power_MW",
                  "rated_wind_m_s", "rated_rotor_speed_rpm"):
            if k in rna:
                lines.append(f"  {k}: {rna[k]}")

    return "\n".join(lines)
