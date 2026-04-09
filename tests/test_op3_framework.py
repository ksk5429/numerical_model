"""
Op^3 framework test suite.

These tests run in GitHub Actions on every push and assert the
structural integrity of the bundled reference models plus the
reproducibility of the headline numerical results.
"""
from __future__ import annotations

import re
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
NREL = REPO_ROOT / "nrel_reference"
SITE_A = REPO_ROOT / "site_a_ref4mw"


# ============================================================
# 1. NREL reference model presence
# ============================================================

class TestNRELReferencePresence:
    """Every model bundled in nrel_reference/ must have the expected files."""

    def test_oc3_monopile_exists(self):
        fst = NREL / "openfast_rtest" / "5MW_OC3Mnpl_DLL_WTurb_WavesIrr" / "5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst"
        assert fst.exists(), f"OC3 monopile .fst missing at {fst}"

    def test_5mw_baseline_data_exists(self):
        base = NREL / "openfast_rtest" / "5MW_Baseline"
        assert base.exists()
        assert any(base.rglob("*.dat"))

    def test_iea_scaled_models_exist(self):
        expected = ["NREL-1.72-103", "NREL-1.79-100", "NREL-2.3-116", "NREL-2.8-127"]
        for name in expected:
            d = NREL / "iea_scaled" / name
            assert d.exists(), f"Missing IEA-scaled model: {name}"
            assert any(d.rglob("*.fst")), f"No .fst in {d}"

    def test_vestas_v27_exists(self):
        d = NREL / "vestas" / "V27"
        assert d.exists()
        assert any(d.rglob("*.fst"))

    def test_site_a_openfast_deck_exists(self):
        fst = SITE_A / "openfast_deck" / "SiteA-Ref4MW.fst"
        assert fst.exists()


# ============================================================
# 2. NREL reference model .fst file parses
# ============================================================

class TestFSTParsing:
    """Every .fst file referenced by the benchmark table must parse."""

    FST_FILES = [
        "nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst",
        "nrel_reference/iea_scaled/NREL-1.72-103/OpenFAST/NREL-1p72-103.fst",
        "nrel_reference/iea_scaled/NREL-1.79-100/OpenFAST/NREL-1p79-100.fst",
        "nrel_reference/iea_scaled/NREL-2.3-116/OpenFAST/NREL-2p3-116.fst",
        "nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh87/NREL-2p8-127.fst",
        "nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh120/NREL-2p8-127-HH120.fst",
        "site_a_ref4mw/openfast_deck/SiteA-Ref4MW.fst",
    ]

    @pytest.mark.parametrize("fst_rel", FST_FILES)
    def test_fst_has_required_keys(self, fst_rel):
        fst = REPO_ROOT / fst_rel
        assert fst.exists(), f"File not found: {fst}"
        text = fst.read_text(errors="replace")
        for key in ["CompElast", "NRotors", "TMax"]:
            assert re.search(rf"\s{key}\b", text), f"{fst.name} missing {key}"

    def test_oc3_has_hydro_and_sub(self):
        fst = REPO_ROOT / self.FST_FILES[0]
        text = fst.read_text(errors="replace")
        # CompHydro and CompSub must both be enabled (non-zero)
        m_hydro = re.search(r"^\s*(\d+)\s+CompHydro\b", text, re.MULTILINE)
        m_sub = re.search(r"^\s*(\d+)\s+CompSub\b", text, re.MULTILINE)
        assert m_hydro and int(m_hydro.group(1)) > 0, "OC3 CompHydro not enabled"
        assert m_sub and int(m_sub.group(1)) > 0, "OC3 CompSub not enabled"


# ============================================================
# 3. OptumGX master database integrity
# ============================================================

class TestOptumGXMasterDatabase:
    """The 1,794-row master database must exist with the correct schema."""

    @classmethod
    def setup_class(cls):
        cls.db = pd.read_csv(DATA / "integrated_database_1794.csv")

    def test_row_count(self):
        assert len(self.db) == 1794

    def test_required_columns(self):
        required = {"run", "S_D", "su0", "k_su", "H_ratio", "f1_f0", "fixity_proxy"}
        assert required.issubset(set(self.db.columns))

    def test_scour_range(self):
        assert self.db["S_D"].min() >= 0
        assert self.db["S_D"].max() <= 1

    def test_soil_parameter_range(self):
        # From Chapter 6: su0 in [7.5, 27.8] kPa, k_su in [8.7, 43.0] kPa/m
        assert 7 <= self.db["su0"].min() <= 10
        assert 25 <= self.db["su0"].max() <= 30
        assert 8 <= self.db["k_su"].min() <= 12
        assert 40 <= self.db["k_su"].max() <= 45

    def test_capacity_power_law_fit(self):
        """Reproduce the dissertation's gamma = 0.61, delta = 1.31 fit."""
        from scipy.optimize import curve_fit
        grouped = self.db.groupby("S_D")["H_ratio"].mean().reset_index()

        def model(theta, gamma, delta):
            return 1 - gamma * np.power(np.clip(theta, 1e-9, None), delta)

        popt, _ = curve_fit(model, grouped["S_D"], grouped["H_ratio"], p0=[0.6, 1.3])
        gamma, delta = popt
        assert abs(gamma - 0.61) < 0.05, f"gamma = {gamma:.3f}, expected 0.61"
        assert abs(delta - 1.31) < 0.1, f"delta = {delta:.3f}, expected 1.31"


# ============================================================
# 4. Config file (SSOT) sanity
# ============================================================

class TestSSOTConfig:
    """The single source of truth YAML must have the expected keys."""

    def test_yaml_exists_and_parses(self):
        import yaml
        cfg = yaml.safe_load((REPO_ROOT / "op3" / "config" / "site_a_site.yaml").read_text())
        assert cfg is not None
        assert isinstance(cfg, dict)

    def test_ssot_txt_exists(self):
        assert (REPO_ROOT / "op3" / "config" / "SSOT_REAL_FINAL.txt").exists()


# ============================================================
# 5. Documentation integrity
# ============================================================

class TestDocumentationIntegrity:
    """The main documentation files must exist and be non-trivial."""

    REQUIRED_DOCS = [
        "README.md",
        "LICENSE",
        "CITATION.cff",
        "docs/FRAMEWORK.md",
        "docs/OPTUMGX_BOUNDARY.md",
        "validation/benchmarks/NREL_BENCHMARK.md",
        "validation/benchmarks/SITE_A_VS_NREL.md",
        "validation/benchmarks/FOUNDATION_MODE_STUDY.md",
    ]

    @pytest.mark.parametrize("doc", REQUIRED_DOCS)
    def test_doc_exists_and_substantial(self, doc):
        p = REPO_ROOT / doc
        assert p.exists(), f"Missing required doc: {doc}"
        assert p.stat().st_size > 500, f"Doc too small: {doc}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
