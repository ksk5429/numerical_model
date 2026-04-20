"""
Validation + contract tests for the NREL 5MW OC3 Phase I monopile
dossier (:mod:`op3.models.nrel_5mw_oc3_monopile`).

Scope of PR #1:
- Confirm the new :mod:`op3.foundations.types.Monopile` API builds
  from the dossier YAMLs.
- Confirm the back-compat bridge
  (``Monopile.as_legacy_foundation()``) produces a valid
  ``FoundationMode.STIFFNESS_6X6`` Foundation.
- Confirm :func:`op3.composer.compose_tower_model` accepts the
  bridged Foundation and runs an eigen analysis.
- Confirm the fixed-base eigen hits the NREL 5MW onshore reference
  within the vvc.yaml acceptance tolerance.

Out of scope for PR #1 (deferred to later PRs):
- PISA-derived SSI validation against OC3 Phase II soil.
- Physical distributed BNWF variant.
- Grid-convergence / Sobol / standards-conformance metrics.

These tests enforce the portion of the ``vvc.yaml`` dossier that is
GREEN at PR #1 land; the rest stays RED until its PR.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")


# ---------------------------------------------------------------------------
# Dossier loading
# ---------------------------------------------------------------------------


def test_dossier_files_exist():
    from op3.models.nrel_5mw_oc3_monopile import DOSSIER_DIR

    for f in ("site.yaml", "geometry.yaml", "soil.yaml", "vvc.yaml", "build.py"):
        assert (DOSSIER_DIR / f).exists(), f"missing {f} in dossier"


# ---------------------------------------------------------------------------
# (1) Monopile factory
# ---------------------------------------------------------------------------


class TestMonopileFactory:

    def test_from_oc3_spec(self):
        from op3.foundations.types import Monopile

        mono = Monopile.from_oc3_spec()
        assert mono.type_name == "monopile"
        assert mono.foundation_type.value == "monopile"
        assert mono.diameter_m == pytest.approx(6.0)
        assert mono.wall_thickness_m == pytest.approx(0.06)
        assert mono.embed_length_m == pytest.approx(36.0)
        assert mono.stub_length_m == pytest.approx(30.0)
        assert mono.ssi is None, "SSI must not auto-attach"

    def test_from_yaml_matches_dossier(self):
        from op3.foundations.types import Monopile
        from op3.models.nrel_5mw_oc3_monopile import DOSSIER_DIR

        mono = Monopile.from_yaml(DOSSIER_DIR)
        assert mono.diameter_m == pytest.approx(6.0)
        assert mono.wall_thickness_m == pytest.approx(0.06)
        assert mono.embed_length_m == pytest.approx(36.0)
        assert mono.stub_length_m == pytest.approx(30.0)
        # soil.yaml ships the Zaaijer-consistent 4-layer dense-sand profile.
        assert len(mono.soil_profile) == 4, "expected 4 soil layers from soil.yaml"
        assert mono.soil_profile[0].depth_m == 0.0
        assert mono.soil_profile[-1].depth_m == 36.0

    def test_head_stiffness_without_ssi_raises(self):
        from op3.foundations.types import Monopile

        mono = Monopile.from_oc3_spec()
        with pytest.raises(RuntimeError, match="no SSI strategy"):
            mono.head_stiffness_6x6()

    def test_with_ssi_returns_self_for_chaining(self):
        from op3.foundations.types import Monopile
        from op3.ssi import Stiffness6x6

        mono = Monopile.from_oc3_spec()
        returned = mono.with_ssi(Stiffness6x6.rigid())
        assert returned is mono

    def test_rigid_ssi_gives_rigid_K(self):
        from op3.foundations.types import Monopile
        from op3.ssi import Stiffness6x6

        mono = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        K = mono.head_stiffness_6x6()
        assert K.shape == (6, 6)
        assert np.all(np.diag(K) >= 1e19), "rigid SSI should give >=1e20 diagonal"


# ---------------------------------------------------------------------------
# (2) Back-compat bridge
# ---------------------------------------------------------------------------


class TestLegacyFoundationBridge:

    def test_as_legacy_foundation_returns_STIFFNESS_6X6(self):
        from op3.foundations import FoundationMode
        from op3.foundations.types import Monopile
        from op3.ssi import Stiffness6x6

        mono = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        legacy = mono.as_legacy_foundation()
        assert legacy.mode is FoundationMode.STIFFNESS_6X6
        assert legacy.stiffness_matrix is not None
        assert legacy.stiffness_matrix.shape == (6, 6)
        assert "monopile" in legacy.source
        assert "stiffness_6x6" in legacy.source

    def test_bridge_no_deprecation_noise(self):
        """The Monopile back-compat bridge builds Foundation directly —
        it must NOT emit the ``build_foundation`` DeprecationWarning."""
        from op3.foundations.types import Monopile
        from op3.ssi import Stiffness6x6

        mono = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            _ = mono.as_legacy_foundation()

    def test_legacy_build_foundation_emits_deprecation(self):
        """Direct calls to the legacy factory MUST emit the deprecation."""
        from op3.foundations import build_foundation

        with pytest.warns(DeprecationWarning, match="frozen at v1.0"):
            build_foundation(mode="fixed")


# ---------------------------------------------------------------------------
# (3) Composer integration
# ---------------------------------------------------------------------------


class TestComposerIntegration:
    """The legacy composer pipeline must accept a Monopile-derived
    Foundation unchanged. This is the whole point of the back-compat
    bridge — PR #1 does not modify composer.py at all."""

    def test_compose_tower_model_accepts_monopile(self):
        from op3.models.nrel_5mw_oc3_monopile import build_tower_model

        model = build_tower_model()
        # Composer returns a TowerModel dataclass; build happens lazily.
        assert model.rotor_name == "nrel_5mw_baseline"
        assert model.tower_name == "nrel_5mw_oc3_tower"
        assert model.foundation.mode.value == "stiffness_6x6"


# ---------------------------------------------------------------------------
# (4) Validation metric: f1 vs NREL onshore baseline
# ---------------------------------------------------------------------------


OC3_REFERENCE_F1_HZ = 0.276
"""Passon 2008 / OC3 Phase I first fore-aft coupled frequency."""


class TestValidationEigen:
    """f1 validation metrics from vvc.yaml. Each SSI variant (rigid
    Stiffness6x6, PISA on soil.yaml, legacy CSV) must reproduce the
    OC3 Phase I coupled benchmark 0.276 Hz.

    Why 0.276 Hz and not the onshore 0.324 Hz? The Op^3 legacy
    ``_attach_stiffness_6x6`` attaches the rigid 6x6 element between
    the tower base (at z=+10 m) and a ground node at (0,0,0). The
    resulting geometry is the OC3 coupled system (monopile stub +
    tower + RNA), not a fixed base at the tower foot. The OC3 Phase I
    f1 is the right reference for this geometry (Passon 2008)."""

    def test_f1_matches_oc3_phase1_coupled(self):
        """Rigid Stiffness6x6 SSI — PR #2 acceptance 3% (was 5% in PR #1)."""
        from op3.models.nrel_5mw_oc3_monopile import build_tower_model

        model = build_tower_model()
        freqs = model.eigen(n_modes=1)
        f1 = float(freqs[0])
        tolerance_pct = 3.0
        err_pct = abs(f1 - OC3_REFERENCE_F1_HZ) / OC3_REFERENCE_F1_HZ * 100
        assert err_pct < tolerance_pct, (
            f"rigid-SSI f1 = {f1:.4f} Hz vs OC3 ref {OC3_REFERENCE_F1_HZ:.4f} Hz; "
            f"error {err_pct:.2f}% exceeds {tolerance_pct}% tolerance"
        )

    def test_f1_pisa_matches_oc3_phase1_coupled(self):
        """PISA SSI using the soil.yaml dense-sand profile (Byrne 2020
        coefficients). Acceptance 5% because PISA head stiffness ends
        up diagonal-attached (coupling lost) in Mode B — see vvc.yaml
        limitations.diagonal_only_Mode_B_attachment."""
        import warnings as _w
        from op3.composer import compose_tower_model
        from op3.models.nrel_5mw_oc3_monopile import build_monopile_pisa

        mono = build_monopile_pisa()
        # The audit-pass UserWarning about off-diagonal coupling is
        # expected here (PISA K[0,4] is large). Silence it for the test.
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            legacy = mono.as_legacy_foundation()
            model = compose_tower_model(
                rotor="nrel_5mw_baseline",
                tower="nrel_5mw_oc3_tower",
                foundation=legacy,
            )
            f1 = float(model.eigen(n_modes=1)[0])

        tolerance_pct = 5.0
        err_pct = abs(f1 - OC3_REFERENCE_F1_HZ) / OC3_REFERENCE_F1_HZ * 100
        assert err_pct < tolerance_pct, (
            f"PISA-SSI f1 = {f1:.4f} Hz vs OC3 ref {OC3_REFERENCE_F1_HZ:.4f} Hz; "
            f"error {err_pct:.2f}% exceeds {tolerance_pct}% tolerance"
        )

    def test_f1_legacy_csv_matches(self):
        """Reproduce the v1.0 op³ result by loading the legacy
        K_6x6_oc3_monopile.csv via the new Stiffness6x6 strategy. This
        is a back-compat regression — the new-API pipeline must give
        the same f1 as the legacy pipeline when fed the same K."""
        from op3.composer import compose_tower_model
        from op3.models.nrel_5mw_oc3_monopile import (
            LEGACY_K_CSV,
            build_monopile_legacy_csv,
        )

        if not LEGACY_K_CSV.exists():
            pytest.skip(f"Legacy CSV not available: {LEGACY_K_CSV}")

        mono = build_monopile_legacy_csv()
        legacy = mono.as_legacy_foundation()
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_oc3_tower",
            foundation=legacy,
        )
        f1 = float(model.eigen(n_modes=1)[0])
        tolerance_pct = 3.0
        err_pct = abs(f1 - OC3_REFERENCE_F1_HZ) / OC3_REFERENCE_F1_HZ * 100
        assert err_pct < tolerance_pct, (
            f"legacy-CSV-SSI f1 = {f1:.4f} Hz vs OC3 ref "
            f"{OC3_REFERENCE_F1_HZ:.4f} Hz; error {err_pct:.2f}% > {tolerance_pct}%"
        )


# ---------------------------------------------------------------------------
# (5) PISA strategy contract
# ---------------------------------------------------------------------------


class TestPisaStrategy:

    def test_pisa_produces_valid_6x6(self):
        """The PISA SSI strategy must produce a symmetric 6x6 with
        positive diagonals and the Op^3 sign convention
        (K[0,4] <= 0, K[1,3] >= 0)."""
        import warnings as _w
        from op3.models.nrel_5mw_oc3_monopile import build_monopile_pisa

        mono = build_monopile_pisa()
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            K = mono.head_stiffness_6x6()
        assert K.shape == (6, 6)
        assert np.all(np.diag(K) > 0), "PISA diagonal must be positive"
        assert np.max(np.abs(K - K.T)) < 1e-3 * np.max(np.abs(K)), (
            "PISA K must be symmetric"
        )
        assert K[0, 4] <= 0, f"PISA K[0,4] should be <= 0 (got {K[0,4]})"
        assert K[1, 3] >= 0, f"PISA K[1,3] should be >= 0 (got {K[1,3]})"

    def test_pisa_K_in_expected_range(self):
        """PISA head stiffness for the OC3 dense-sand profile should
        give K[0,0] ≈ 1.9e10 N/m within 10% — the vvc.yaml
        internal-consistency metric."""
        import warnings as _w
        from op3.models.nrel_5mw_oc3_monopile import build_monopile_pisa

        mono = build_monopile_pisa()
        with _w.catch_warnings():
            _w.simplefilter("ignore", UserWarning)
            K = mono.head_stiffness_6x6()
        K_00 = float(K[0, 0])
        expected = 1.9e10
        err_pct = abs(K_00 - expected) / expected * 100
        assert err_pct < 10.0, (
            f"PISA K[0,0] = {K_00:.3e} N/m vs expected {expected:.3e}; "
            f"drift {err_pct:.1f}% exceeds 10% internal-consistency band"
        )

    def test_three_variants_build_successfully(self):
        """rigid / PISA / legacy-CSV all produce Monopile instances."""
        from op3.models.nrel_5mw_oc3_monopile import (
            LEGACY_K_CSV,
            build_monopile,
            build_monopile_legacy_csv,
            build_monopile_pisa,
        )
        m_rigid = build_monopile()
        assert m_rigid.ssi.name == "stiffness_6x6"

        m_pisa = build_monopile_pisa()
        assert m_pisa.ssi.name == "pisa"

        if LEGACY_K_CSV.exists():
            m_csv = build_monopile_legacy_csv()
            assert m_csv.ssi.name == "stiffness_6x6"

    def test_pisa_without_soil_raises(self, tmp_path):
        """If soil.yaml is missing / empty, build_monopile_pisa raises."""
        from op3.foundations.types import Monopile
        from op3.ssi import PISA

        # Build a Monopile with empty soil and try to use PISA directly.
        mono = Monopile.from_oc3_spec(soil_profile=[])
        with pytest.raises((RuntimeError, ValueError)):
            mono.with_ssi(PISA(soil_profile=[]))

    def test_pisa_rejects_foundation_without_geometry(self):
        """PISA requires diameter_m + embed_length_m on the foundation."""
        from op3.ssi import PISA
        from op3.standards.pisa import SoilState

        class DummyFoundation:
            pass

        strategy = PISA(
            soil_profile=[
                SoilState(depth_m=0.0, G_Pa=50e6, su_or_phi=35.0, soil_type="sand"),
            ],
        )
        with pytest.raises(TypeError, match="diameter_m"):
            strategy.compute_head_stiffness(DummyFoundation())
