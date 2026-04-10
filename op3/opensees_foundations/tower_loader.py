"""
Tower template loader: parse OpenFAST ElastoDyn tower input files and
return distributed tower properties suitable for assembling an
OpenSeesPy stick model with byte-identical NREL section properties.

This is Phase 1 / Task 1.1 of the Op^3 Track C industry-grade plan:
replace the hand-tuned ``TOWER_TEMPLATES`` dict in
``op3/opensees_foundations/builder.py`` with values read directly from
the canonical NREL ``*_ElastoDyn*Tower.dat`` files. The expected
outcome is that examples 1, 2, 3, 7, 8 frequency errors fall from
10-30% to <2% on the fixed-base configuration.

Usage
-----
>>> from op3.opensees_foundations.tower_loader import load_elastodyn_tower
>>> tpl = load_elastodyn_tower(
...     ed_main="nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/"
...             "NRELOffshrBsline5MW_OC3Monopile_ElastoDyn.dat",
... )
>>> tpl.tower_height_m, len(tpl.ht_fract)
(87.6, 11)

Schema
------
Returned ``TowerTemplate`` exposes:

- ``tower_height_m``      : TowerHt from ElastoDyn main file
- ``tower_base_z_m``      : TowerBsHt (offset from MSL or ground)
- ``ht_fract``            : array of fractional heights along tower (0..1)
- ``mass_density_kg_m``   : array of TMassDen at each station
- ``ei_fa_Nm2``           : array of TwFAStif (fore-aft EI)
- ``ei_ss_Nm2``           : array of TwSSStif (side-side EI)
- ``damping_ratio_fa``    : (TwrFADmp1, TwrFADmp2) percent of critical
- ``damping_ratio_ss``    : (TwrSSDmp1, TwrSSDmp2)
- ``adj_tower_mass``      : AdjTwMa scalar
- ``adj_fa_stiff``        : AdjFASt scalar
- ``adj_ss_stiff``        : AdjSSSt scalar
- ``source_files``        : provenance for V&V records
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class TowerTemplate:
    """Distributed tower properties parsed from an ElastoDyn deck."""

    tower_height_m: float
    tower_base_z_m: float
    ht_fract: np.ndarray
    mass_density_kg_m: np.ndarray
    ei_fa_Nm2: np.ndarray
    ei_ss_Nm2: np.ndarray
    damping_ratio_fa: tuple[float, float] = (1.0, 1.0)
    damping_ratio_ss: tuple[float, float] = (1.0, 1.0)
    adj_tower_mass: float = 1.0
    adj_fa_stiff: float = 1.0
    adj_ss_stiff: float = 1.0
    source_files: list[str] = field(default_factory=list)

    @property
    def n_stations(self) -> int:
        return int(self.ht_fract.size)

    def station_elevations_m(self) -> np.ndarray:
        """Absolute z-coordinates of stations (base + ht_fract * height)."""
        return self.tower_base_z_m + self.ht_fract * self.tower_height_m

    def section_at(self, ht_fract: float) -> dict:
        """Linearly interpolated section properties at a given height fraction."""
        return {
            "mass_kg_m": float(np.interp(ht_fract, self.ht_fract, self.mass_density_kg_m)),
            "EI_fa_Nm2": float(np.interp(ht_fract, self.ht_fract, self.ei_fa_Nm2)),
            "EI_ss_Nm2": float(np.interp(ht_fract, self.ht_fract, self.ei_ss_Nm2)),
        }


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_NUM = r"[-+]?\d+(?:\.\d*)?(?:[EeDd][-+]?\d+)?"


def _read_text(path: Path) -> str:
    return path.read_text(errors="replace")


def _scan_scalar(text: str, key: str) -> float | None:
    """Find ``<value> <key>`` style scalar parameter."""
    # Use a word-boundary only when the key ends in a word char, since
    # OpenFAST uses keys like ``TwFAM1Sh(2)`` whose trailing ``)`` is
    # non-word and would block \b from matching.
    suffix = r"\b" if key[-1].isalnum() or key[-1] == "_" else r"(?=\s|$)"
    m = re.search(rf"^\s*({_NUM})\s+{re.escape(key)}{suffix}", text, re.MULTILINE)
    if not m:
        return None
    raw = m.group(1).replace("D", "E").replace("d", "e")
    try:
        return float(raw)
    except ValueError:
        return None


def _scan_distributed_block(text: str) -> np.ndarray:
    """
    Locate the DISTRIBUTED TOWER PROPERTIES table and return an
    (n, 4) array with columns [HtFract, TMassDen, TwFAStif, TwSSStif].

    Some NREL files include extra columns (TwGJStif, TwEAStif, ...) — we
    keep only the first four because that is what ElastoDyn requires
    for FE bending mode synthesis.
    """
    # Find header line that starts the block
    m = re.search(
        r"DISTRIBUTED\s+TOWER\s+PROPERTIES.*?\n"
        r"\s*HtFract.*?\n"               # column header
        r"\s*\(-\).*?\n",                # units line
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        raise ValueError("DISTRIBUTED TOWER PROPERTIES block not found")

    tail = text[m.end():]
    rows: list[list[float]] = []
    for line in tail.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("-") or s.startswith("="):
            break
        # require leading numeric token
        first = s.split()[0].replace("D", "E").replace("d", "e")
        try:
            float(first)
        except ValueError:
            break
        toks = [t.replace("D", "E").replace("d", "e") for t in s.split()]
        try:
            vals = [float(t) for t in toks[:4]]
        except ValueError:
            break
        if len(vals) < 4:
            break
        rows.append(vals)
    if not rows:
        raise ValueError("No distributed tower stations parsed")
    return np.asarray(rows, dtype=float)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_elastodyn_tower(
    ed_main: str | Path,
    ed_tower: str | Path | None = None,
) -> TowerTemplate:
    """
    Parse an OpenFAST ElastoDyn deck and return a ``TowerTemplate``.

    Parameters
    ----------
    ed_main
        Path to the ElastoDyn primary input file (the one referenced by
        ``EDFile`` in the top-level ``.fst``). Provides ``TowerHt`` and
        ``TowerBsHt`` plus the path to the tower file via ``TwrFile``.
    ed_tower
        Optional explicit override for the tower properties file. If
        omitted, the loader resolves it from ``TwrFile`` in ``ed_main``.

    Notes
    -----
    Some NREL decks (the OC3 monopile in particular) embed the
    distributed properties directly in the main ElastoDyn file rather
    than in a separate ``*_Tower.dat``. We handle both layouts.
    """
    ed_main_path = Path(ed_main)
    main_text = _read_text(ed_main_path)

    tower_height = _scan_scalar(main_text, "TowerHt")
    tower_base = _scan_scalar(main_text, "TowerBsHt") or 0.0
    if tower_height is None:
        raise ValueError(f"TowerHt not found in {ed_main_path}")

    # Try to resolve a separate tower file
    twr_path: Path | None = None
    if ed_tower is not None:
        twr_path = Path(ed_tower)
    else:
        m = re.search(r'^\s*"([^"]+)"\s+TwrFile\b', main_text, re.MULTILINE)
        if m:
            cand = (ed_main_path.parent / m.group(1)).resolve()
            if cand.exists():
                twr_path = cand
            else:
                # Fall back: search same directory for *tower*.dat
                basename = Path(m.group(1)).name
                local = ed_main_path.parent / basename
                if local.exists():
                    twr_path = local
                else:
                    matches = sorted(ed_main_path.parent.glob("*[Tt]ower*.dat"))
                    matches = [p for p in matches if p != ed_main_path]
                    if matches:
                        twr_path = matches[0]

    if twr_path is not None and twr_path.exists():
        twr_text = _read_text(twr_path)
        block_source = twr_path
    else:
        twr_text = main_text
        block_source = ed_main_path

    table = _scan_distributed_block(twr_text)

    fa_dmp1 = _scan_scalar(twr_text, "TwrFADmp(1)") or 1.0
    fa_dmp2 = _scan_scalar(twr_text, "TwrFADmp(2)") or 1.0
    ss_dmp1 = _scan_scalar(twr_text, "TwrSSDmp(1)") or 1.0
    ss_dmp2 = _scan_scalar(twr_text, "TwrSSDmp(2)") or 1.0
    adj_mass = _scan_scalar(twr_text, "AdjTwMa") or 1.0
    adj_fa = _scan_scalar(twr_text, "AdjFASt") or 1.0
    adj_ss = _scan_scalar(twr_text, "AdjSSSt") or 1.0

    return TowerTemplate(
        tower_height_m=float(tower_height),
        tower_base_z_m=float(tower_base),
        ht_fract=table[:, 0],
        mass_density_kg_m=table[:, 1],
        ei_fa_Nm2=table[:, 2],
        ei_ss_Nm2=table[:, 3],
        damping_ratio_fa=(float(fa_dmp1), float(fa_dmp2)),
        damping_ratio_ss=(float(ss_dmp1), float(ss_dmp2)),
        adj_tower_mass=float(adj_mass),
        adj_fa_stiff=float(adj_fa),
        adj_ss_stiff=float(adj_ss),
        source_files=[str(ed_main_path), str(block_source)],
    )


# ---------------------------------------------------------------------------
# RNA (rotor + nacelle assembly) loader
# ---------------------------------------------------------------------------

@dataclass
class RNAProperties:
    """Mass + inertia of the rotor-nacelle assembly parsed from ElastoDyn."""

    hub_mass_kg: float
    nac_mass_kg: float
    blade_mass_kg: float          # per blade, integrated from blade .dat
    n_blades: int
    hub_iner_kgm2: float          # rotor-axis inertia
    nac_yiner_kgm2: float         # nacelle yaw-axis inertia
    nac_cm_xn_m: float            # downwind offset tower-top -> nacelle CM
    nac_cm_zn_m: float            # vertical offset tower-top -> nacelle CM
    twr2shft_m: float             # tower-top to rotor shaft vertical offset
    tip_rad_m: float
    hub_rad_m: float
    source_files: list[str] = field(default_factory=list)

    @property
    def total_rna_mass_kg(self) -> float:
        return self.hub_mass_kg + self.nac_mass_kg + self.n_blades * self.blade_mass_kg


def published_mode_shape(twr_text: str, mode: str = "TwFAM1Sh") -> np.ndarray | None:
    """
    Return the 5 polynomial coefficients [c2, c3, c4, c5, c6] for one of
    the NREL ElastoDyn tower mode shapes
    (TwFAM1Sh, TwFAM2Sh, TwSSM1Sh, TwSSM2Sh).

    Mode shape is psi(eta) = sum_{i=2..6} c_i * eta^i where eta in [0,1].
    """
    coeffs = []
    for i in range(2, 7):
        v = _scan_scalar(twr_text, f"{mode}({i})")
        if v is None:
            return None
        coeffs.append(v)
    return np.asarray(coeffs, dtype=float)


def evaluate_mode_shape(coeffs: np.ndarray, eta: np.ndarray) -> np.ndarray:
    """Sample psi(eta) given the [c2..c6] polynomial coefficients."""
    eta = np.asarray(eta, dtype=float)
    psi = np.zeros_like(eta)
    for i, c in enumerate(coeffs, start=2):
        psi += c * eta ** i
    return psi


def _integrate_blade_mass(blade_path: Path, span_m: float) -> float:
    """Trapezoidal integration of BMassDen over the blade span."""
    text = _read_text(blade_path)
    hm = re.search(
        r"DISTRIBUTED\s+BLADE\s+PROPERTIES.*?\n(\s*BlFract[^\n]*)\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not hm:
        return 0.0
    header_tokens = hm.group(1).split()
    try:
        bm_idx = header_tokens.index("BMassDen")
        bf_idx = header_tokens.index("BlFract")
    except ValueError:
        return 0.0
    # Skip units line after header
    after = text[hm.end():]
    units_match = re.match(r"\s*\([^\n]*\n", after)
    tail = after[units_match.end():] if units_match else after
    rows: list[list[float]] = []
    for line in tail.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("-") or s.startswith("="):
            break
        toks = [t.replace("D", "E").replace("d", "e") for t in s.split()]
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            break
        if len(vals) <= max(bf_idx, bm_idx):
            break
        rows.append(vals)
    if not rows:
        return 0.0
    arr = np.asarray(rows)
    bl_fract = arr[:, bf_idx]
    bmass = arr[:, bm_idx]
    s = bl_fract * span_m
    return float(np.trapezoid(bmass, s))


def load_elastodyn_rna(ed_main: str | Path) -> RNAProperties:
    ed_main_path = Path(ed_main)
    text = _read_text(ed_main_path)

    def must(key: str) -> float:
        v = _scan_scalar(text, key)
        if v is None:
            raise ValueError(f"{key} not found in {ed_main_path.name}")
        return v

    hub_mass = must("HubMass")
    nac_mass = must("NacMass")
    hub_iner = must("HubIner")
    nac_yiner = must("NacYIner")
    nac_cm_xn = _scan_scalar(text, "NacCMxn") or 0.0
    nac_cm_zn = _scan_scalar(text, "NacCMzn") or 0.0
    twr2shft = _scan_scalar(text, "Twr2Shft") or 0.0
    tip_rad = must("TipRad")
    hub_rad = must("HubRad")
    n_blades = int(_scan_scalar(text, "NumBl") or 3)

    # Locate blade file (BldFile(1)) and integrate BMassDen
    blade_mass = 0.0
    sources = [str(ed_main_path)]
    bm = re.search(r'^\s*"([^"]+)"\s+BldFile[\(]?1[\)]?', text, re.MULTILINE)
    if bm:
        cand = (ed_main_path.parent / bm.group(1)).resolve()
        if not cand.exists():
            basename = Path(bm.group(1)).name
            # Search recursively under ed parent and grandparent
            for root in [ed_main_path.parent, ed_main_path.parent.parent]:
                hits = list(root.rglob(basename))
                if hits:
                    cand = hits[0]
                    break
        if cand.exists():
            blade_mass = _integrate_blade_mass(cand, tip_rad - hub_rad)
            sources.append(str(cand))

    return RNAProperties(
        hub_mass_kg=float(hub_mass),
        nac_mass_kg=float(nac_mass),
        blade_mass_kg=float(blade_mass),
        n_blades=n_blades,
        hub_iner_kgm2=float(hub_iner),
        nac_yiner_kgm2=float(nac_yiner),
        nac_cm_xn_m=float(nac_cm_xn),
        nac_cm_zn_m=float(nac_cm_zn),
        twr2shft_m=float(twr2shft),
        tip_rad_m=float(tip_rad),
        hub_rad_m=float(hub_rad),
        source_files=sources,
    )


# ---------------------------------------------------------------------------
# Convenience: build OpenSeesPy stick segments from a template
# ---------------------------------------------------------------------------

def discretise(
    tpl: TowerTemplate,
    n_segments: int = 20,
) -> list[dict]:
    """
    Subdivide the tower into ``n_segments`` equal-length elements and
    return per-element section properties (interpolated at the element
    midpoint). The resulting list is what
    ``opensees_foundations.builder._build_tower_stick`` consumes.

    Each entry has keys: ``z_bot``, ``z_top``, ``length``, ``mass_kg_m``,
    ``EI_fa_Nm2``, ``EI_ss_Nm2``, ``EI_avg_Nm2``.
    """
    if n_segments < 1:
        raise ValueError("n_segments must be >= 1")

    z0 = tpl.tower_base_z_m
    H = tpl.tower_height_m
    edges = np.linspace(0.0, 1.0, n_segments + 1)
    elements: list[dict] = []
    for i in range(n_segments):
        f_lo, f_hi = edges[i], edges[i + 1]
        f_mid = 0.5 * (f_lo + f_hi)
        sec = tpl.section_at(f_mid)
        ei_avg = 0.5 * (sec["EI_fa_Nm2"] + sec["EI_ss_Nm2"])
        elements.append(
            {
                "z_bot": z0 + f_lo * H,
                "z_top": z0 + f_hi * H,
                "length": (f_hi - f_lo) * H,
                "mass_kg_m": sec["mass_kg_m"] * tpl.adj_tower_mass,
                "EI_fa_Nm2": sec["EI_fa_Nm2"] * tpl.adj_fa_stiff,
                "EI_ss_Nm2": sec["EI_ss_Nm2"] * tpl.adj_ss_stiff,
                "EI_avg_Nm2": ei_avg * 0.5 * (tpl.adj_fa_stiff + tpl.adj_ss_stiff),
            }
        )
    return elements


# ---------------------------------------------------------------------------
# Self-test entry point
# ---------------------------------------------------------------------------

def _selftest(paths: Iterable[str | Path]) -> None:
    for p in paths:
        try:
            tpl = load_elastodyn_tower(p)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {p}: {exc}")
            continue
        print(
            f"[OK]   {Path(p).name}: H={tpl.tower_height_m:.1f} m, "
            f"stations={tpl.n_stations}, "
            f"m_base={tpl.mass_density_kg_m[0]:.0f} kg/m, "
            f"EI_base={tpl.ei_fa_Nm2[0]:.2e} Nm^2"
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        _selftest(sys.argv[1:])
    else:
        repo = Path(__file__).resolve().parents[2]
        candidates = [
            repo / "nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr"
                   "/NRELOffshrBsline5MW_OC3Monopile_ElastoDyn.dat",
            repo / "nrel_reference/iea_15mw/OpenFAST_monopile"
                   "/IEA-15-240-RWT-Monopile_ElastoDyn.dat",
        ]
        _selftest([c for c in candidates if c.exists()])
