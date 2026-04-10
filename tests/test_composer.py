"""
Tests for op3.composer -- Tower model composition and analysis dispatch.

Covers:
  - compose_tower_model() with valid rotor/tower returns TowerModel
  - Invalid rotor raises ValueError
  - Invalid tower raises ValueError
  - model.eigen() returns frequencies (requires OpenSeesPy)
  - model.pushover() returns expected keys (requires OpenSeesPy)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from op3.foundations import build_foundation, Foundation, FoundationMode
from op3.composer import compose_tower_model, TowerModel

# Check if OpenSeesPy is available for integration tests
try:
    import openseespy.opensees as ops
    HAS_OPENSEES = True
except ImportError:
    HAS_OPENSEES = False

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "fem_results"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fixed_foundation():
    return build_foundation(mode="fixed")


@pytest.fixture
def stiffness_foundation():
    K = np.diag([1e9, 1e9, 1e9, 1e8, 1e8, 1e8])
    return build_foundation(mode="stiffness_6x6", stiffness_matrix=K)


# ---------------------------------------------------------------------------
# Composition: valid inputs
# ---------------------------------------------------------------------------

class TestComposeValid:

    def test_returns_tower_model(self, fixed_foundation):
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fixed_foundation,
        )
        assert isinstance(model, TowerModel)

    def test_model_attributes(self, fixed_foundation):
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fixed_foundation,
        )
        assert model.rotor_name == "nrel_5mw_baseline"
        assert model.tower_name == "nrel_5mw_tower"
        assert model.foundation is fixed_foundation
        assert model._built is False

    def test_all_valid_rotors(self, fixed_foundation):
        valid_rotors = [
            "nrel_5mw_baseline", "iea_15mw_rwt", "ref_4mw_owt",
            "nrel_1.72_103", "nrel_2.8_127", "vestas_v27",
        ]
        for rotor in valid_rotors:
            model = compose_tower_model(
                rotor=rotor,
                tower="nrel_5mw_tower",
                foundation=fixed_foundation,
            )
            assert model.rotor_name == rotor

    def test_all_valid_towers(self, fixed_foundation):
        valid_towers = [
            "nrel_5mw_tower", "nrel_5mw_oc3_tower", "iea_15mw_tower",
            "site_a_rt1_tower", "iea_land_onshore_tower",
        ]
        for tower in valid_towers:
            model = compose_tower_model(
                rotor="nrel_5mw_baseline",
                tower=tower,
                foundation=fixed_foundation,
            )
            assert model.tower_name == tower

    def test_with_stiffness_foundation(self, stiffness_foundation):
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=stiffness_foundation,
        )
        assert model.foundation.mode == FoundationMode.STIFFNESS_6X6


# ---------------------------------------------------------------------------
# Composition: invalid inputs
# ---------------------------------------------------------------------------

class TestComposeInvalid:

    def test_invalid_rotor_raises(self, fixed_foundation):
        with pytest.raises(ValueError, match="Unknown rotor template"):
            compose_tower_model(
                rotor="nonexistent_rotor",
                tower="nrel_5mw_tower",
                foundation=fixed_foundation,
            )

    def test_invalid_tower_raises(self, fixed_foundation):
        with pytest.raises(ValueError, match="Unknown tower template"):
            compose_tower_model(
                rotor="nrel_5mw_baseline",
                tower="nonexistent_tower",
                foundation=fixed_foundation,
            )

    def test_both_invalid(self, fixed_foundation):
        with pytest.raises(ValueError):
            compose_tower_model(
                rotor="bad_rotor",
                tower="bad_tower",
                foundation=fixed_foundation,
            )


# ---------------------------------------------------------------------------
# Integration tests requiring OpenSeesPy
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_OPENSEES, reason="OpenSeesPy not installed")
class TestEigenAnalysis:
    """Eigen analysis requires a fully built OpenSees model."""

    def test_eigen_returns_frequencies(self):
        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        freqs = model.eigen(n_modes=3)
        assert isinstance(freqs, np.ndarray)
        assert len(freqs) == 3
        # All natural frequencies must be positive
        assert np.all(freqs > 0), f"Frequencies must be positive, got {freqs}"
        # First frequency of NREL 5MW is ~0.32 Hz (fixed base)
        assert freqs[0] < 5.0, f"First frequency {freqs[0]} Hz seems too high"

    @pytest.mark.parametrize("n_modes", [1, 3, 6])
    def test_eigen_n_modes(self, n_modes):
        """Each n_modes value needs a fresh model (OpenSees global state)."""
        import openseespy.opensees as ops
        ops.wipe()
        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        freqs = model.eigen(n_modes=n_modes)
        assert len(freqs) == n_modes

    def test_model_marked_built_after_eigen(self):
        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        assert model._built is False
        model.eigen(n_modes=1)
        assert model._built is True


@pytest.mark.skipif(not HAS_OPENSEES, reason="OpenSeesPy not installed")
class TestPushoverAnalysis:
    """Pushover requires a built model."""

    def test_pushover_returns_dict(self):
        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        result = model.pushover(target_disp_m=0.1, n_steps=10)
        assert isinstance(result, dict)
        assert "displacement_m" in result
        assert "reaction_kN" in result

    def test_pushover_arrays_same_length(self):
        fnd = build_foundation(mode="fixed")
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_tower",
            foundation=fnd,
        )
        result = model.pushover(target_disp_m=0.1, n_steps=10)
        disp = result["displacement_m"]
        force = result["reaction_kN"]
        assert len(disp) == len(force)
        assert len(disp) > 0
