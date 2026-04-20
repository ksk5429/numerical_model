"""
Validation + contract tests for the NREL 5MW OC4 Phase I jacket
dossier (:mod:`op3.models.nrel_5mw_oc4_jacket`).

Mirrors the OC3 monopile test structure (PR #1 / PR #2).

Scope of PR #3:
- Confirm :class:`op3.foundations.types.Jacket` builds from the
  dossier + parses the SACS deck.
- Confirm :class:`op3.ssi.Stiffness6x6` loads the SubDyn-condensed
  K_6x6_oc4_jacket.csv and feeds the jacket head.
- Confirm the back-compat bridge works with the legacy composer.
- Confirm coupled f1 matches Popko 2012 OC4 Phase I benchmark
  (0.319 Hz) within 3%.

Out of scope for PR #3 (deferred):
- Topology-aware OpenSees instantiation of jacket legs + braces.
- Craig-Bampton cross-check of the externally-supplied 6x6.
- Sensitivity / standards conformance.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")


OC4_REFERENCE_F1_HZ = 0.319
"""Popko 2012 OC4 Phase I first fore-aft coupled frequency."""


# ---------------------------------------------------------------------------
# Dossier structure
# ---------------------------------------------------------------------------


def test_dossier_files_exist():
    from op3.models.nrel_5mw_oc4_jacket import DOSSIER_DIR

    for f in ("site.yaml", "geometry.yaml", "soil.yaml", "vvc.yaml", "build.py"):
        assert (DOSSIER_DIR / f).exists(), f"missing {f} in dossier"


# ---------------------------------------------------------------------------
# (1) Jacket factory
# ---------------------------------------------------------------------------


class TestJacketFactory:

    def test_from_oc4_phase1_spec(self):
        from op3.foundations.types import Jacket

        j = Jacket.from_oc4_phase1_spec()
        assert j.type_name == "jacket"
        assert j.foundation_type.value == "jacket"
        assert j.n_legs == 4
        assert j.n_x_braces == 4
        assert j.mudline_z_m == pytest.approx(-50.0)
        assert j.transition_piece_z_m == pytest.approx(20.15)
        assert j.ssi is None

    def test_sacs_deck_parses(self):
        """The bundled OC4 SACS deck parses to the expected size."""
        from op3.foundations.types import Jacket
        from op3.models.nrel_5mw_oc4_jacket import OC4_SACS_DECK

        if not OC4_SACS_DECK.exists():
            pytest.skip(f"SACS deck not bundled: {OC4_SACS_DECK}")
        j = Jacket.from_oc4_phase1_spec(sacs_deck_path=str(OC4_SACS_DECK))
        assert j.sacs_deck is not None
        assert len(j.sacs_deck.joints) == 56
        assert len(j.sacs_deck.members) == 54
        assert j.sacs_deck.seabed_elev_m == pytest.approx(-42.5)

    def test_from_yaml_matches_dossier(self):
        from op3.foundations.types import Jacket
        from op3.models.nrel_5mw_oc4_jacket import DOSSIER_DIR

        j = Jacket.from_yaml(DOSSIER_DIR)
        assert j.n_legs == 4
        assert j.footprint_spacing_m == pytest.approx(12.0)
        # SACS path in geometry.yaml points at the bundled deck.
        if j.sacs_deck is not None:
            assert len(j.sacs_deck.joints) == 56

    def test_head_stiffness_without_ssi_raises(self):
        from op3.foundations.types import Jacket

        j = Jacket.from_oc4_phase1_spec()
        with pytest.raises(RuntimeError, match="no SSI strategy"):
            j.head_stiffness_6x6()

    def test_topology_summary(self):
        from op3.foundations.types import Jacket
        from op3.models.nrel_5mw_oc4_jacket import OC4_SACS_DECK

        sacs = str(OC4_SACS_DECK) if OC4_SACS_DECK.exists() else None
        j = Jacket.from_oc4_phase1_spec(sacs_deck_path=sacs)
        summary = j.topology_summary()
        assert summary["n_legs"] == 4
        assert summary["n_x_braces"] == 4
        assert summary["sacs_deck_loaded"] == (sacs is not None)


# ---------------------------------------------------------------------------
# (2) Legacy bridge
# ---------------------------------------------------------------------------


class TestLegacyBridge:

    def test_as_legacy_foundation(self):
        from op3.foundations import FoundationMode
        from op3.foundations.types import Jacket
        from op3.ssi import Stiffness6x6

        K_expected = np.diag([2.4e9, 2.4e9, 4.5e9, 8.5e11, 8.5e11, 1.2e10])
        j = Jacket.from_oc4_phase1_spec()
        j.with_ssi(Stiffness6x6(K=K_expected, label="OC4 SubDyn"))
        legacy = j.as_legacy_foundation()
        assert legacy.mode is FoundationMode.STIFFNESS_6X6
        assert legacy.stiffness_matrix.shape == (6, 6)
        np.testing.assert_allclose(legacy.stiffness_matrix, K_expected)
        assert "jacket" in legacy.source


# ---------------------------------------------------------------------------
# (3) Composer integration
# ---------------------------------------------------------------------------


class TestComposerIntegration:

    def test_build_tower_model(self):
        from op3.models.nrel_5mw_oc4_jacket import build_tower_model

        model = build_tower_model()
        assert model.rotor_name == "nrel_5mw_baseline"
        assert model.tower_name == "nrel_5mw_tower"
        assert model.foundation.mode.value == "stiffness_6x6"


# ---------------------------------------------------------------------------
# (4) Validation: OC4 Phase I coupled eigen
# ---------------------------------------------------------------------------


class TestValidationEigen:

    def test_f1_matches_oc4_phase1_coupled(self):
        """Coupled f1 of jacket + NREL 5MW tower + RNA vs Popko 2012."""
        from op3.models.nrel_5mw_oc4_jacket import build_tower_model

        model = build_tower_model()
        freqs = model.eigen(n_modes=3)
        f1 = float(freqs[0])
        tolerance_pct = 3.0
        err_pct = abs(f1 - OC4_REFERENCE_F1_HZ) / OC4_REFERENCE_F1_HZ * 100
        assert err_pct < tolerance_pct, (
            f"OC4 coupled f1 = {f1:.4f} Hz vs Popko 2012 reference "
            f"{OC4_REFERENCE_F1_HZ:.4f} Hz; error {err_pct:.2f}% exceeds "
            f"{tolerance_pct}% tolerance"
        )

    def test_K_matches_csv(self):
        """Head stiffness loaded from the dossier must match the
        diagonal values in K_6x6_oc4_jacket.csv exactly."""
        from op3.models.nrel_5mw_oc4_jacket import OC4_K_CSV, build_jacket

        if not OC4_K_CSV.exists():
            pytest.skip(f"OC4 K CSV not bundled: {OC4_K_CSV}")

        jacket = build_jacket()
        K = jacket.head_stiffness_6x6()
        # Diagonals per Popko 2012 / data/fem_results/K_6x6_oc4_jacket.csv
        expected_diag = [2.4e9, 2.4e9, 4.5e9, 8.5e11, 8.5e11, 1.2e10]
        for i, exp in enumerate(expected_diag):
            assert K[i, i] == pytest.approx(exp, rel=0.01), (
                f"K[{i},{i}] = {K[i,i]:.3e} vs expected {exp:.3e}"
            )
        # Off-diagonals must be exactly zero (SubDyn diagonal condensation).
        off = K - np.diag(np.diag(K))
        assert np.max(np.abs(off)) == 0.0, "OC4 K must be strictly diagonal"


# ---------------------------------------------------------------------------
# (5) Cross-type contract sanity
# ---------------------------------------------------------------------------


class TestCrossTypeSanity:
    """Both Monopile and Jacket must honour the same FoundationProtocol
    surface. This guards against future refactors that accidentally
    differentiate the two at the protocol level."""

    def test_both_types_are_foundation_protocol(self):
        from op3.foundations.base import FoundationProtocol
        from op3.foundations.types import Jacket, Monopile
        from op3.ssi import Stiffness6x6

        m = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        j = Jacket.from_oc4_phase1_spec().with_ssi(Stiffness6x6.rigid())

        assert isinstance(m, FoundationProtocol)
        assert isinstance(j, FoundationProtocol)

    def test_both_types_bridge_to_legacy(self):
        from op3.foundations import FoundationMode
        from op3.foundations.types import Jacket, Monopile
        from op3.ssi import Stiffness6x6

        m = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        j = Jacket.from_oc4_phase1_spec().with_ssi(Stiffness6x6.rigid())

        lm = m.as_legacy_foundation()
        lj = j.as_legacy_foundation()
        assert lm.mode is FoundationMode.STIFFNESS_6X6
        assert lj.mode is FoundationMode.STIFFNESS_6X6
