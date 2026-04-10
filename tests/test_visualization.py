"""
Tests for op3.visualization -- smoke tests for import and basic calls.

These are lightweight checks that do not require a running OpenSees model
or the opsvis package (unless available). The goal is to verify:
  - All public functions import without error
  - _check_deps raises ImportError when opsvis is missing (mocked)
  - plot_pushover_curve and plot_moment_rotation handle empty data
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

# Check if matplotlib is available
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# Check if OpenSeesPy is available for full integration tests
try:
    import openseespy.opensees as ops
    HAS_OPENSEES = True
except ImportError:
    HAS_OPENSEES = False


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------

class TestImports:
    """All visualization functions should import without error."""

    def test_import_module(self):
        import op3.visualization  # noqa: F401

    def test_import_plot_model(self):
        from op3.visualization import plot_model  # noqa: F401

    def test_import_plot_mode_shapes(self):
        from op3.visualization import plot_mode_shapes  # noqa: F401

    def test_import_plot_deformed(self):
        from op3.visualization import plot_deformed  # noqa: F401

    def test_import_plot_section_forces(self):
        from op3.visualization import plot_section_forces  # noqa: F401

    def test_import_plot_pushover_curve(self):
        from op3.visualization import plot_pushover_curve  # noqa: F401

    def test_import_plot_moment_rotation(self):
        from op3.visualization import plot_moment_rotation  # noqa: F401

    def test_import_plot_all(self):
        from op3.visualization import plot_all  # noqa: F401


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

class TestCheckDeps:

    def test_raises_when_opsvis_missing(self):
        """When HAS_OPSVIS is False, _check_deps should raise ImportError."""
        from op3 import visualization as viz
        original = viz.HAS_OPSVIS
        try:
            viz.HAS_OPSVIS = False
            with pytest.raises(ImportError, match="opsvis"):
                viz._check_deps()
        finally:
            viz.HAS_OPSVIS = original

    def test_raises_when_matplotlib_missing(self):
        from op3 import visualization as viz
        original_mpl = viz.HAS_MPL
        try:
            viz.HAS_MPL = False
            with pytest.raises(ImportError, match="matplotlib"):
                viz._check_deps()
        finally:
            viz.HAS_MPL = original_mpl


# ---------------------------------------------------------------------------
# Pushover curve with dummy data (no OpenSees needed)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_MPL, reason="matplotlib not installed")
class TestPushoverCurve:

    def test_empty_data_returns_none(self):
        from op3.visualization import plot_pushover_curve
        result = plot_pushover_curve({})
        assert result is None

    def test_produces_png(self, tmp_path):
        from op3.visualization import plot_pushover_curve
        data = {
            "displacement_m": [0.0, 0.01, 0.02, 0.03],
            "reaction_kN": [0.0, 500.0, 900.0, 1200.0],
        }
        path = plot_pushover_curve(data, output_dir=str(tmp_path))
        assert path is not None
        assert Path(path).exists()
        assert path.endswith(".png")


# ---------------------------------------------------------------------------
# Moment-rotation curve with dummy data (no OpenSees needed)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_MPL, reason="matplotlib not installed")
class TestMomentRotationCurve:

    def test_empty_data_returns_none(self):
        from op3.visualization import plot_moment_rotation
        result = plot_moment_rotation({})
        assert result is None

    def test_produces_png(self, tmp_path):
        from op3.visualization import plot_moment_rotation
        data = {
            "rotation_deg": [0.0, 0.1, 0.2, 0.3],
            "moment_MNm": [0.0, 5.0, 9.0, 12.0],
        }
        path = plot_moment_rotation(data, output_dir=str(tmp_path))
        assert path is not None
        assert Path(path).exists()
        assert path.endswith(".png")

    def test_with_reference_markers(self, tmp_path):
        from op3.visualization import plot_moment_rotation
        data = {
            "rotation_deg": [0.0, 0.1, 0.2, 0.3],
            "moment_MNm": [0.0, 5.0, 9.0, 12.0],
        }
        path = plot_moment_rotation(
            data,
            output_dir=str(tmp_path),
            ref_My=10.0,
            ref_theta_y=0.15,
        )
        assert path is not None
        assert Path(path).exists()


# ---------------------------------------------------------------------------
# Integration: full plot_model if OpenSees + opsvis available
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (HAS_OPENSEES and HAS_MPL),
    reason="Requires OpenSeesPy and matplotlib",
)
class TestFullVisualization:
    """Only run when both OpenSeesPy and matplotlib are installed."""

    def test_plot_model_after_eigen(self, tmp_path):
        try:
            import opsvis  # noqa: F401
        except ImportError:
            pytest.skip("opsvis not installed")

        from op3.foundations import build_foundation
        from op3.composer import compose_tower_model
        from op3.visualization import plot_model

        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        model.eigen(n_modes=3)
        path = plot_model(output_dir=str(tmp_path))
        assert path is not None
        assert Path(path).exists()
        assert path.endswith(".png")
