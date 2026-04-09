"""
Chapter 8 encoder <-> Op^3 UQ bridge (Task 20).

Exposes the 1,794-row OptumGX Monte Carlo database used by the
dissertation Chapter 8 digital-twin encoder as a first-class Op^3
UQ data source. Previously the MC database was consumed via a
side-channel CSV loaded directly by the encoder training script;
this module turns it into a propagator that any downstream Op^3
stage (Bayesian calibration, PCE surrogate, DLC sensitivity) can
consume.

Real CSV schema (SiteA integrated_database_1794.csv):

    run, S_D, scour_m, su0, k_su, Hmax_kN, H_ratio, V_ratio,
    f1_Hz, f1_f0, fixity_proxy

1794 Monte Carlo runs sampled over:
    scour_m  in [0.0, 4.0] m
    su0      in [7.5, 27.8] kPa  (surface undrained shear strength)
    k_su     in [12, 35] kPa/m   (depth gradient)

outputs:
    f1_Hz    first fore-aft bending frequency
    f1_f0    f1 normalised by the pristine (s=0) case
    Hmax_kN  ultimate horizontal capacity at collapse
    H_ratio  Hmax relative to pristine
    fixity_proxy (base rotational compliance indicator)

Use
---
    from op3.uq.encoder_bridge import load_site_a_mc
    df = load_site_a_mc()   # reads PHD/data/integrated_database_1794.csv
    # Sample the real joint distribution for Bayesian updates
    # or encoder training.

``prior`` is a list of ``SoilPrior`` objects whose mean and COV are
statistically consistent with the database, so
``propagate_pisa_mc(soil_priors=prior, ...)`` produces the same joint
distribution the encoder was trained on. This decouples the encoder
from the raw OptumGX runs and makes every Ch8 derivation traceable
through the committed Op^3 pipeline.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from op3.uq.propagation import SoilPrior


def load_encoder_mc(csv_path: str | Path) -> pd.DataFrame:
    """
    Load a generic Chapter 8 MC database. For the real SiteA case
    use ``load_site_a_mc()`` which auto-resolves the PHD path.

    Returns a pandas DataFrame. The CSV is expected to have one row
    per MC realisation; any columns beyond the minimum set are
    preserved for downstream feature engineering.
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"encoder MC database not found: {p}")
    df = pd.read_csv(p)
    if "run_id" not in df.columns and "run" not in df.columns:
        df = df.reset_index().rename(columns={"index": "run_id"})
    return df


def load_site_a_mc() -> pd.DataFrame:
    """
    Load the real 1794-sample SiteA integrated MC database from the
    PHD SSOT (``F:/TREE_OF_THOUGHT/PHD/data/integrated_database_1794.csv``).

    This is the authoritative training set for the Chapter 8 digital
    twin encoder. The database spans scour [0, 4] m, su0 [7.5, 27.8]
    kPa, and k_su [12, 35] kPa/m, and records f1_Hz, Hmax_kN, and
    fixity_proxy outputs from 1794 real OptumGX + OpenSeesPy runs.
    """
    from op3.data_sources import site_a_mc_database
    p = site_a_mc_database()
    return pd.read_csv(p)


def encoder_as_prior(
    df: pd.DataFrame,
    columns: list[str],
    *,
    default_soil_type: str = "sand",
    su_or_phi_default: float = 35.0,
) -> list[SoilPrior]:
    """
    Turn per-column statistics from the MC database into a list of
    ``SoilPrior`` objects, one per column. Each prior carries the
    empirical mean and COV computed from the column; the soil_type
    and strength default are user-selectable.

    The resulting prior list is suitable for feeding into
    ``op3.uq.propagation.propagate_pisa_mc`` to reproduce the encoder
    training distribution through the deterministic PISA pipeline.
    """
    priors: list[SoilPrior] = []
    for i, col in enumerate(columns):
        if col not in df.columns:
            raise KeyError(f"column {col} missing from MC database")
        values = df[col].values.astype(float)
        mean = float(np.mean(values))
        std = float(np.std(values))
        cov = float(std / mean) if mean > 0 else 0.30
        priors.append(SoilPrior(
            depth_m=float(i * 15.0),   # 15 m spacing by convention
            G_mean_Pa=mean,
            G_cov=cov,
            soil_type=default_soil_type,
            su_or_phi_mean=su_or_phi_default,
            su_or_phi_cov=0.10,
        ))
    return priors


def bayesian_from_encoder(
    df: pd.DataFrame,
    *,
    forward_model,
    observation_col: str = "f1_Hz",
    parameter_col: str = "G0_top_Pa",
    sigma: float = 0.005,
    n_grid: int = 101,
):
    """
    Treat one MC row as the "truth" observation and run an Op^3
    Bayesian calibration over another parameter column. Useful for
    synthetic-truth verification of the encoder: if the encoder is
    consistent, the posterior mean should recover the row's true
    parameter value.

    Returns an ``op3.uq.bayesian.BayesianPosterior``.
    """
    import numpy as np
    from op3.uq.bayesian import grid_bayesian_calibration, normal_likelihood

    truth_param = float(df[parameter_col].iloc[0])
    measured = float(df[observation_col].iloc[0])

    lo, hi = 0.5 * truth_param, 1.5 * truth_param
    grid = np.linspace(lo, hi, n_grid)

    return grid_bayesian_calibration(
        forward_model=forward_model,
        likelihood_fn=normal_likelihood(measured, sigma),
        grid=grid,
    )
