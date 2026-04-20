"""
Validation + contract tests for the Gunsan 4.2 MW OWT tripod
dossier (:mod:`op3.models.gunsan_4mw_tripod`).

Scope of PR #4:
- Confirm :class:`op3.foundations.types.Tripod` builds from the
  dossier YAMLs and exposes the expected geometry.
- Confirm the back-compat bridge (``as_legacy_foundation``) with
  the legacy composer.
- Confirm the **rigid-SSI UPPER BOUND** eigen (f1 ≈ 0.317 Hz on
  site_a_rt1_tower + ref_4mw_owt).

Out of scope for PR #4 (deferred to PR #5):
- Spine-with-ribs topology-aware SSI (ports legacy v1 physics).
- Validation against design-report coupled target 0.240-0.244 Hz.
- Scour-sensitivity validation against Jeong 2021 centrifuge data.
- Field OMA baseline (data pending archival).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openseespy.opensees")


GUNSAN_F1_RIGID_UPPER_BOUND_HZ = 0.317
"""Op^3 built-in fixed-base f1 for site_a_rt1_tower + ref_4mw_owt."""
GUNSAN_F1_DESIGN_REPORT_RANGE_HZ = (0.24016, 0.24358)
"""ProjA design-report soft / stiff soil envelope (PR #5 validation target)."""


# ---------------------------------------------------------------------------
# Dossier structure
# ---------------------------------------------------------------------------


def test_dossier_files_exist():
    from op3.models.gunsan_4mw_tripod import DOSSIER_DIR

    for f in ("site.yaml", "geometry.yaml", "soil.yaml", "vvc.yaml", "build.py"):
        assert (DOSSIER_DIR / f).exists(), f"missing {f} in dossier"


# ---------------------------------------------------------------------------
# (1) Tripod factory
# ---------------------------------------------------------------------------


class TestTripodFactory:

    def test_from_gunsan_4mw_spec(self):
        from op3.foundations.types import Tripod

        t = Tripod.from_gunsan_4mw_spec()
        assert t.type_name == "tripod"
        assert t.n_buckets == 3
        assert t.bucket_diameter_m == pytest.approx(8.0)
        assert t.bucket_skirt_thickness_m == pytest.approx(0.020)
        assert t.tripod_radial_distance_m == pytest.approx(11.58)
        assert t.tripod_angular_spacing_deg == pytest.approx(120.0)
        assert t.mudline_z_m == pytest.approx(-8.2)
        assert t.transition_piece_z_m == pytest.approx(23.6)
        assert t.num_ribs_per_bucket == 4
        assert t.ssi is None

    def test_from_yaml_matches_dossier(self):
        from op3.foundations.types import Tripod
        from op3.models.gunsan_4mw_tripod import DOSSIER_DIR

        t = Tripod.from_yaml(DOSSIER_DIR)
        assert t.n_buckets == 3
        assert t.bucket_diameter_m == pytest.approx(8.0)
        assert t.tripod_radial_distance_m == pytest.approx(11.58)
        # Soil profile public summary: 3 layers
        assert len(t.soil_profile) == 3

    def test_topology_summary_and_positions(self):
        from op3.foundations.types import Tripod

        t = Tripod.from_gunsan_4mw_spec()
        summary = t.topology_summary()
        assert summary["n_buckets"] == 3
        assert summary["tripod_radial_distance_m"] == pytest.approx(11.58)
        # 3-bucket symmetric: bucket spacing = 2 R sin(60) = R sqrt(3)
        expected_spacing = 11.58 * np.sqrt(3)
        assert summary["bucket_spacing_m"] == pytest.approx(expected_spacing, rel=1e-6)

        positions = t.bucket_positions()
        assert positions.shape == (3, 3)
        # Sum of x and y positions must be zero (symmetric 3-bucket)
        assert abs(positions[:, 0].sum()) < 1e-9
        assert abs(positions[:, 1].sum()) < 1e-9
        # All buckets at the mudline elevation
        np.testing.assert_allclose(positions[:, 2], -8.2)

    def test_head_stiffness_without_ssi_raises(self):
        from op3.foundations.types import Tripod

        t = Tripod.from_gunsan_4mw_spec()
        with pytest.raises(RuntimeError, match="no SSI strategy"):
            t.head_stiffness_6x6()


# ---------------------------------------------------------------------------
# (2) Legacy bridge
# ---------------------------------------------------------------------------


class TestLegacyBridge:

    def test_as_legacy_foundation(self):
        from op3.foundations import FoundationMode
        from op3.foundations.types import Tripod
        from op3.ssi import Stiffness6x6

        t = Tripod.from_gunsan_4mw_spec().with_ssi(Stiffness6x6.rigid())
        legacy = t.as_legacy_foundation()
        assert legacy.mode is FoundationMode.STIFFNESS_6X6
        assert legacy.stiffness_matrix.shape == (6, 6)
        assert "tripod" in legacy.source


# ---------------------------------------------------------------------------
# (3) Composer integration
# ---------------------------------------------------------------------------


class TestComposerIntegration:

    def test_build_tower_model(self):
        from op3.models.gunsan_4mw_tripod import build_tower_model

        model = build_tower_model()
        assert model.rotor_name == "ref_4mw_owt"
        assert model.tower_name == "site_a_rt1_tower"
        assert model.foundation.mode.value == "stiffness_6x6"


# ---------------------------------------------------------------------------
# (4) Validation: rigid upper-bound eigen
# ---------------------------------------------------------------------------


class TestValidationEigen:

    def test_f1_rigid_upper_bound(self):
        """Rigid SSI on the Gunsan tower + RNA gives f1 ~ 0.317 Hz.
        This is the UPPER BOUND only — real Gunsan coupled f1 with
        SSI is 0.240-0.244 Hz per the design report (PR #5 target)."""
        from op3.models.gunsan_4mw_tripod import build_tower_model

        model = build_tower_model()
        freqs = model.eigen(n_modes=3)
        f1 = float(freqs[0])
        tolerance_pct = 3.0
        err_pct = abs(f1 - GUNSAN_F1_RIGID_UPPER_BOUND_HZ) / \
                  GUNSAN_F1_RIGID_UPPER_BOUND_HZ * 100
        assert err_pct < tolerance_pct, (
            f"Rigid-SSI f1 = {f1:.4f} Hz vs op3 built-in upper-bound "
            f"{GUNSAN_F1_RIGID_UPPER_BOUND_HZ:.4f} Hz; error {err_pct:.2f}% "
            f"exceeds {tolerance_pct}% tolerance"
        )

    def test_f1_above_design_report_range(self):
        """The rigid-SSI f1 MUST be above the design-report coupled
        range (0.240-0.244 Hz). Adding foundation flexibility can
        only lower f1, so the rigid result is the upper bound."""
        from op3.models.gunsan_4mw_tripod import build_tower_model

        model = build_tower_model()
        f1 = float(model.eigen(n_modes=1)[0])
        soft, stiff = GUNSAN_F1_DESIGN_REPORT_RANGE_HZ
        assert f1 > stiff, (
            f"Rigid-SSI f1 = {f1:.4f} Hz must be ABOVE the design-report "
            f"stiff-soil coupled target {stiff:.5f} Hz. If not, the tower "
            "template or RNA mass is out of calibration."
        )


# ---------------------------------------------------------------------------
# (5) Cross-type contract sanity
# ---------------------------------------------------------------------------


class TestCrossTypeSanity:

    def test_all_three_types_are_foundation_protocol(self):
        from op3.foundations.base import FoundationProtocol
        from op3.foundations.types import Jacket, Monopile, Tripod
        from op3.ssi import Stiffness6x6

        m = Monopile.from_oc3_spec().with_ssi(Stiffness6x6.rigid())
        j = Jacket.from_oc4_phase1_spec().with_ssi(Stiffness6x6.rigid())
        t = Tripod.from_gunsan_4mw_spec().with_ssi(Stiffness6x6.rigid())

        assert isinstance(m, FoundationProtocol)
        assert isinstance(j, FoundationProtocol)
        assert isinstance(t, FoundationProtocol)

    def test_all_three_types_bridge_to_legacy(self):
        from op3.foundations import FoundationMode
        from op3.foundations.types import Jacket, Monopile, Tripod
        from op3.ssi import Stiffness6x6

        for type_cls, factory in [
            (Monopile, lambda: Monopile.from_oc3_spec()),
            (Jacket, lambda: Jacket.from_oc4_phase1_spec()),
            (Tripod, lambda: Tripod.from_gunsan_4mw_spec()),
        ]:
            instance = factory().with_ssi(Stiffness6x6.rigid())
            legacy = instance.as_legacy_foundation()
            assert legacy.mode is FoundationMode.STIFFNESS_6X6, (
                f"{type_cls.__name__}.as_legacy_foundation() bridge broken"
            )
            assert legacy.stiffness_matrix.shape == (6, 6)


# ---------------------------------------------------------------------------
# (6) PR #5 roadmap sentinel
# ---------------------------------------------------------------------------


class TestPR5RoadmapSentinel:
    """These tests pass trivially today but document the PR #5
    targets so the sentinel surfaces in test reports. They do NOT
    fail; they emit xfail markers so the CI dashboard tracks them."""

    @pytest.mark.xfail(
        reason="PR #5 target: coupled f1 matches design-report 0.240-0.244 Hz "
               "via spine-with-ribs SSI (not yet implemented)",
        strict=False,
    )
    def test_coupled_f1_matches_design_report(self):
        from op3.models.gunsan_4mw_tripod import build_tower_model

        model = build_tower_model()
        f1 = float(model.eigen(n_modes=1)[0])
        soft, stiff = GUNSAN_F1_DESIGN_REPORT_RANGE_HZ
        # Expected to FAIL under PR #4 rigid SSI (f1 = 0.317 > 0.244).
        assert soft - 0.01 <= f1 <= stiff + 0.01, (
            f"f1 = {f1} outside design-report envelope {soft}-{stiff}"
        )

    @pytest.mark.xfail(
        reason="PR #5 target: Jeong 2021 centrifuge scour sensitivity match "
               "(requires scour-swept SSI)",
        strict=False,
    )
    def test_scour_sensitivity_matches_jeong_2021(self):
        # Placeholder — PR #5 will populate when TripodSpineRibs SSI lands.
        raise NotImplementedError("scour sweep pending PR #5")
