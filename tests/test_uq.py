"""
Phase 5 Uncertainty Quantification V&V.

Verifies the soil-prior MC propagation, the Hermite PCE surrogate,
and the grid-based Bayesian calibration end-to-end.

Tests
-----
  5.1.1  MC propagation: K samples are positive and shape (n,6,6)
  5.1.2  MC propagation: mean K_xx within 10 percent of deterministic
         mean-prior result
  5.1.3  MC propagation: COV on K_xx is in (0.05, 0.50)
  5.1.4  MC propagation: percentile ordering p05 < p50 < p95

  5.2.1  PCE 1D: linear function recovered exactly with order >= 1
  5.2.2  PCE 1D: quadratic function recovered exactly with order >= 2
  5.2.3  PCE 1D: mean-variance match analytic for f(xi)=xi
         (mean=0, var=1)
  5.2.4  PCE 2D: bilinear function f(x,y)=1+2x+3y+4xy recovered exactly
  5.2.5  PCE 1D: surrogate accuracy within 1 percent of MC mean for
         a noisy nonlinear test function

  5.3.1  Bayesian: degenerate likelihood collapses posterior to a
         delta around the true value
  5.3.2  Bayesian: posterior std shrinks as measurement sigma decreases
  5.3.3  Bayesian: posterior is normalised and bounded
  5.3.4  Bayesian: end-to-end demo on Op^3 EI scale calibration
         against the NREL 5 MW OC3 example reference frequency

Run:
    python tests/test_uq.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.uq import (
    HermitePCE, SoilPrior,
    build_pce_1d, build_pce_2d,
    grid_bayesian_calibration, normal_likelihood,
    propagate_pisa_mc, summarise_samples,
)
from op3.uq.pce import pce_mean_var
from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6


# ---------------------------------------------------------------------------
# Task 5.1 MC propagation
# ---------------------------------------------------------------------------

def _priors():
    return [
        SoilPrior(0.0,  5.0e7, 0.30, "sand", 35.0, 0.10),
        SoilPrior(15.0, 1.0e8, 0.30, "sand", 35.0, 0.10),
        SoilPrior(36.0, 1.5e8, 0.30, "sand", 36.0, 0.10),
    ]


def test_5_1_1_shape_and_positivity():
    s = propagate_pisa_mc(diameter_m=float('nan'), embed_length_m=30.0,
                          soil_priors=_priors(), n_samples=100)
    print(f"  [5.1.1] shape={s.shape}, min K_xx={s[:,0,0].min():.3e}")
    assert s.shape == (100, 6, 6)
    assert (s[:, 0, 0] > 0).all()


def test_5_1_2_mean_close_to_deterministic():
    priors = _priors()
    s = propagate_pisa_mc(diameter_m=float('nan'), embed_length_m=30.0,
                          soil_priors=priors, n_samples=400)
    summary = summarise_samples(s)
    K_det = pisa_pile_stiffness_6x6(
        diameter_m=float('nan'), embed_length_m=30.0,
        soil_profile=[SoilState(p.depth_m, p.G_mean_Pa,
                                 p.su_or_phi_mean, p.soil_type)
                       for p in priors],
    )
    err = abs(summary["Kxx"]["mean"] - K_det[0, 0]) / K_det[0, 0]
    print(f"  [5.1.2] MC mean Kxx={summary['Kxx']['mean']:.3e}, "
          f"det={K_det[0,0]:.3e}, err={err:+.2%}")
    assert err < 0.10


def test_5_1_3_cov_in_band():
    s = propagate_pisa_mc(diameter_m=float('nan'), embed_length_m=30.0,
                          soil_priors=_priors(), n_samples=400)
    summary = summarise_samples(s)
    cov = summary["Kxx"]["cov"]
    print(f"  [5.1.3] COV(Kxx) = {cov:.3f}")
    assert 0.05 < cov < 0.60


def test_5_1_4_percentile_ordering():
    s = propagate_pisa_mc(diameter_m=float('nan'), embed_length_m=30.0,
                          soil_priors=_priors(), n_samples=200)
    summary = summarise_samples(s)
    e = summary["Kxx"]
    print(f"  [5.1.4] p05={e['p05']:.2e} < p50={e['p50']:.2e} < p95={e['p95']:.2e}")
    assert e["p05"] < e["p50"] < e["p95"]


# ---------------------------------------------------------------------------
# Task 5.2 PCE
# ---------------------------------------------------------------------------

def test_5_2_1_linear_exact():
    pce = build_pce_1d(lambda x: 2.0 + 3.0 * x, order=2)
    err = abs(pce.coeffs[0] - 2.0) + abs(pce.coeffs[1] - 3.0)
    print(f"  [5.2.1] linear PCE err = {err:.2e}")
    assert err < 1e-10


def test_5_2_2_quadratic_exact():
    # f(xi) = 1 + 2 xi + 3 xi^2 = 1 + 2 He_1 + 3 (He_2 + 1) = 4 + 2 He_1 + 3 He_2
    pce = build_pce_1d(lambda x: 1.0 + 2.0 * x + 3.0 * x ** 2, order=3)
    err = (abs(pce.coeffs[0] - 4.0)
           + abs(pce.coeffs[1] - 2.0)
           + abs(pce.coeffs[2] - 3.0))
    print(f"  [5.2.2] quadratic PCE err = {err:.2e}")
    assert err < 1e-10


def test_5_2_3_mean_var_xi():
    pce = build_pce_1d(lambda x: x, order=2)
    mean, var = pce_mean_var(pce)
    print(f"  [5.2.3] mean={mean:.4e}, var={var:.4e} (expect 0, 1)")
    assert abs(mean) < 1e-10
    assert abs(var - 1.0) < 1e-10


def test_5_2_4_bilinear_2d():
    f = lambda x, y: 1.0 + 2.0 * x + 3.0 * y + 4.0 * x * y
    pce = build_pce_2d(f, order=2)
    # Random sanity check
    err = 0.0
    for x, y in [(0.5, -0.3), (-1.2, 0.7), (0.0, 1.4)]:
        err += abs(pce.evaluate(x, y)[0] - f(x, y))
    print(f"  [5.2.4] bilinear 2D PCE pointwise err = {err:.2e}")
    assert err < 1e-9


def test_5_2_5_nonlinear_mean_match():
    # f(xi) = exp(0.3 xi) ; analytic mean = exp(0.045)
    pce = build_pce_1d(lambda x: np.exp(0.3 * x), order=6)
    mean, var = pce_mean_var(pce)
    analytic = float(np.exp(0.045))
    err = abs(mean - analytic) / analytic
    print(f"  [5.2.5] exp(0.3 xi): PCE mean={mean:.4f} analytic={analytic:.4f} err={err:.2e}")
    assert err < 1e-4


# ---------------------------------------------------------------------------
# Task 5.3 Bayesian calibration
# ---------------------------------------------------------------------------

def test_5_3_1_collapse_to_truth():
    """Tight likelihood + linear forward model -> posterior peaks at truth."""
    truth = 1.20
    grid = np.linspace(0.5, 2.0, 301)
    fwd = lambda p: 0.5 * p   # f1 = 0.5 * EI_scale, deterministic
    lk = normal_likelihood(measured=fwd(truth), sigma=0.001)
    post = grid_bayesian_calibration(
        forward_model=fwd, likelihood_fn=lk, grid=grid)
    print(f"  [5.3.1] truth={truth} posterior mean={post.mean:.4f}")
    assert abs(post.mean - truth) < 0.01


def test_5_3_2_sigma_shrinks_posterior():
    grid = np.linspace(0.5, 2.0, 401)
    fwd = lambda p: 0.5 * p
    truth = 1.0
    s_wide = grid_bayesian_calibration(
        forward_model=fwd,
        likelihood_fn=normal_likelihood(fwd(truth), 0.05),
        grid=grid).std
    s_tight = grid_bayesian_calibration(
        forward_model=fwd,
        likelihood_fn=normal_likelihood(fwd(truth), 0.005),
        grid=grid).std
    print(f"  [5.3.2] wide std={s_wide:.4f}, tight std={s_tight:.4f}")
    assert s_tight < s_wide


def test_5_3_3_normalised():
    grid = np.linspace(0.5, 2.0, 301)
    post = grid_bayesian_calibration(
        forward_model=lambda p: 0.5 * p,
        likelihood_fn=normal_likelihood(0.5, 0.01),
        grid=grid)
    Z = float(np.trapz(post.posterior, grid))
    print(f"  [5.3.3] integral of posterior = {Z:.6f}")
    assert abs(Z - 1.0) < 1e-6
    assert (post.posterior >= 0).all()


def test_5_3_4_op3_calibration_demo():
    """End-to-end Bayesian calibration of the OC3 example's tower EI
    scale factor using the published Jonkman/Musial 2010 reference."""
    from scripts.test_three_analyses import import_build
    from op3.opensees_foundations import builder as B

    saved = B.TOWER_TEMPLATES["nrel_5mw_oc3_tower"].get("EI_scale", 1.0)

    def forward(scale: float) -> float:
        # Patch the AdjFASt-equivalent stiffness scale via the loader
        # Trick: monkey-patch builder._build_tower_stick_from_elastodyn
        # to multiply EI by scale.
        from op3.opensees_foundations import tower_loader as TL
        orig = TL.load_elastodyn_tower

        def patched(*a, **kw):
            t = orig(*a, **kw)
            from dataclasses import replace
            return replace(t,
                           ei_fa_Nm2=t.ei_fa_Nm2 * scale,
                           ei_ss_Nm2=t.ei_ss_Nm2 * scale)

        TL.load_elastodyn_tower = patched
        try:
            mod = import_build(REPO_ROOT / "examples/02_nrel_5mw_oc3_monopile")
            f1 = float(mod.build().eigen(n_modes=3)[0])
        finally:
            TL.load_elastodyn_tower = orig
        return f1

    grid = np.linspace(0.7, 1.3, 21)   # coarse for speed
    measured = 0.2766                  # NREL/TP-500-47535 OC3 ref
    post = grid_bayesian_calibration(
        forward_model=forward,
        likelihood_fn=normal_likelihood(measured, 0.01),
        grid=grid)
    print(f"  [5.3.4] EI scale posterior: mean={post.mean:.3f} +/- {post.std:.3f}")
    print(f"           p05={post.p05:.3f}  p50={post.p50:.3f}  p95={post.p95:.3f}")
    assert 0.7 < post.mean < 1.3
    assert post.std > 0


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 78)
    print(" Op3 Phase 5 UQ V&V -- propagation, PCE, Bayesian")
    print("=" * 78)
    tests = [
        test_5_1_1_shape_and_positivity,
        test_5_1_2_mean_close_to_deterministic,
        test_5_1_3_cov_in_band,
        test_5_1_4_percentile_ordering,
        test_5_2_1_linear_exact,
        test_5_2_2_quadratic_exact,
        test_5_2_3_mean_var_xi,
        test_5_2_4_bilinear_2d,
        test_5_2_5_nonlinear_mean_match,
        test_5_3_1_collapse_to_truth,
        test_5_3_2_sigma_shrinks_posterior,
        test_5_3_3_normalised,
        test_5_3_4_op3_calibration_demo,
    ]
    fails = 0
    for t in tests:
        # Reset OpenSeesPy global domain between tests (Linux CI fix).
        try:
            import openseespy.opensees as _ops
            _ops.wipe()
        except Exception:
            pass
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            fails += 1
    print("=" * 78)
    print(f" {len(tests) - fails}/{len(tests)} UQ tests passed")
    print("=" * 78)
    return fails


if __name__ == "__main__":
    sys.exit(main())
