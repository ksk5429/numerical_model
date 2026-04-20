"""
Centralised reference-frequency and field-measurement constants for Op³.

This module is the single source of truth for every "0.244 Hz"-like
literal that previously appeared sprinkled across visualisation and
validation code, each labelled inconsistently as "field measurement",
"design target", or "SSOT baseline".

Provenance (as of 2026-04-20, committed in op3/config/site_a.yaml):

    baselines.soft.frequency_hz   = 0.24016 Hz   design target (soft soil)
    baselines.stiff.frequency_hz  = 0.24358 Hz   design target (stiff soil)
    baselines.field_measured_hz   = None         (not yet populated;
                                                  field OMA baseline TBD)

Source: F:/PROJ_A_PRIVATE/ProjA_사이트A_하부구조물_1구조계산서.pdf
         (SiteA 4 MW OWT structural calculation report; proprietary).

The rounded aggregate value ``0.244 Hz`` used historically as
"field-measured f1" is actually the midpoint of the two design
targets, **not** an OMA measurement on the Gunsan tower. Any
legacy code or figure caption that said "field measured" was wrong;
callers of this module must use ``DESIGN_TARGET_F1_HZ`` (a range)
until a real OMA record is published.

Usage
-----

    from op3.field_reference import (
        DESIGN_TARGET_F1_SOFT_HZ,   # 0.24016
        DESIGN_TARGET_F1_STIFF_HZ,  # 0.24358
        DESIGN_TARGET_F1_HZ,        # rounded mean (0.244)
        FIELD_MEASURED_F1_HZ,       # None until OMA baseline published
        field_reference_freq,       # helper with source disclosure
    )

When plotting, use the helper:

    freq_hz, source_label = field_reference_freq()
    ax.axhline(freq_hz, label=source_label)

The returned label is either ``"Design target, stiff soil (0.24358 Hz)"``
or, once a real field measurement is available, ``"Field OMA 2026-xx-xx
(<value> Hz)"``. This forces every figure to disclose what the
reference line actually represents.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Optional, Tuple


# -- Design-report targets (VERIFIED from ProjA structural calc, 2026-01-07) --
DESIGN_TARGET_F1_SOFT_HZ: float = 0.24016
DESIGN_TARGET_F1_STIFF_HZ: float = 0.24358
# Rounded aggregate used by legacy viz / comparison code. This is
# NOT a field measurement; it is the (stiff + soft) / 2 rounded to 3 dp.
DESIGN_TARGET_F1_HZ: float = round(
    0.5 * (DESIGN_TARGET_F1_SOFT_HZ + DESIGN_TARGET_F1_STIFF_HZ), 3
)

# -- Field OMA measurement (TBD — populate when the baseline record is
# archived in op3/config/site_a.yaml under baselines.field_measured_hz).
FIELD_MEASURED_F1_HZ: Optional[float] = None
FIELD_MEASURED_F1_DATE: Optional[str] = None


def field_reference_freq(
    prefer: str = "stiff",
    allow_env_override: bool = True,
) -> Tuple[float, str]:
    """Return ``(frequency_hz, source_label)`` for plotting / validation.

    Precedence:

    1. If ``FIELD_MEASURED_F1_HZ`` is set (and ``prefer != "design"``),
       return that with a field-OMA label.
    2. If ``allow_env_override`` and ``OP3_FIELD_F1_HZ`` env var is set,
       return that value with a user-override label. Useful when the
       caller knows the field value but it is not yet in the SSOT.
    3. Otherwise return the design target (soft / stiff / mean
       depending on ``prefer``).

    ``prefer`` options: ``"soft"``, ``"stiff"``, ``"mean"``, ``"design"``.
    """
    if prefer == "design":
        # force design target regardless of field availability
        return DESIGN_TARGET_F1_STIFF_HZ, (
            f"Design target, stiff soil ({DESIGN_TARGET_F1_STIFF_HZ:.5f} Hz)"
        )

    if FIELD_MEASURED_F1_HZ is not None:
        date_suffix = f" {FIELD_MEASURED_F1_DATE}" if FIELD_MEASURED_F1_DATE else ""
        return FIELD_MEASURED_F1_HZ, (
            f"Field OMA{date_suffix} ({FIELD_MEASURED_F1_HZ:.5f} Hz)"
        )

    if allow_env_override:
        override = os.environ.get("OP3_FIELD_F1_HZ")
        if override is not None:
            try:
                v = float(override)
                return v, f"OP3_FIELD_F1_HZ override ({v:.5f} Hz)"
            except ValueError:
                warnings.warn(
                    f"OP3_FIELD_F1_HZ='{override}' is not a float; "
                    "falling back to design target"
                )

    if prefer == "soft":
        return DESIGN_TARGET_F1_SOFT_HZ, (
            f"Design target, soft soil ({DESIGN_TARGET_F1_SOFT_HZ:.5f} Hz)"
        )
    if prefer == "mean":
        return DESIGN_TARGET_F1_HZ, (
            f"Design target, mean of soft/stiff ({DESIGN_TARGET_F1_HZ:.3f} Hz)"
        )
    # default: stiff
    return DESIGN_TARGET_F1_STIFF_HZ, (
        f"Design target, stiff soil ({DESIGN_TARGET_F1_STIFF_HZ:.5f} Hz)"
    )


def load_field_measured_hz_from_yaml(
    site_a_yaml: Optional[Path] = None,
) -> Optional[float]:
    """Attempt to read ``baselines.field_measured_hz`` from
    ``op3/config/site_a.yaml``.

    Returns ``None`` if the YAML is missing, PyYAML is not installed,
    or the key is null.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return None
    if site_a_yaml is None:
        site_a_yaml = Path(__file__).resolve().parent / "config" / "site_a.yaml"
    if not site_a_yaml.exists():
        return None
    try:
        with open(site_a_yaml, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception:
        return None
    baselines = (cfg or {}).get("baselines", {})
    val = baselines.get("field_measured_hz")
    return float(val) if val is not None else None
