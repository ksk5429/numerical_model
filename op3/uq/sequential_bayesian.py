"""
Sequential Bayesian updating for scour depth estimation.

Propagates the posterior from one monitoring epoch to the next,
so accumulated evidence progressively tightens the diagnosis.
The posterior from epoch t becomes the prior for epoch t+1.

Usage
-----
    from op3.uq.sequential_bayesian import SequentialBayesianTracker

    tracker = SequentialBayesianTracker(grid_resolution=200)

    # Epoch 1: first field measurement
    tracker.update(freq_ratio=0.994, capacity_ratio=0.99, anomaly=False)
    print(tracker.summary())

    # Epoch 2: six months later
    tracker.update(freq_ratio=0.991, capacity_ratio=0.97, anomaly=False)
    print(tracker.summary())

    # Epoch 3: anomaly detected
    tracker.update(freq_ratio=0.985, capacity_ratio=0.92, anomaly=True)
    print(tracker.summary())

    # Full trajectory
    trajectory = tracker.trajectory()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class EpochResult:
    """Diagnostic result at a single monitoring epoch."""
    epoch: int
    freq_ratio: float
    capacity_ratio: float
    anomaly: bool
    posterior_mean: float
    posterior_std: float
    p05: float
    p50: float
    p95: float
    recommended_action: str


class SequentialBayesianTracker:
    """Tracks the scour posterior across monitoring epochs.

    At each epoch the previous posterior becomes the new prior,
    and the incoming sensor observations sharpen the estimate.
    The trajectory of posterior means over time reveals the
    degradation rate and enables remaining-useful-life estimation.

    Parameters
    ----------
    grid_resolution : int
        Number of discrete scour-depth bins from 0 to 1 (S/D).
    freq_sensitivity : float
        Power-law coefficient for the frequency observation model.
    freq_exponent : float
        Power-law exponent for the frequency model.
    freq_sigma : float
        Gaussian likelihood width for the frequency channel.
    capacity_sigma : float
        Gaussian likelihood width for the capacity channel.
    anomaly_threshold : float
        Scour depth (S/D) above which the anomaly detector fires.
    anomaly_sharpness : float
        Steepness of the logistic step function for the anomaly channel.
    """

    def __init__(
        self,
        grid_resolution: int = 200,
        freq_sensitivity: float = 0.059,
        freq_exponent: float = 1.5,
        freq_sigma: float = 0.015,
        capacity_sigma: float = 0.05,
        anomaly_threshold: float = 0.39,
        anomaly_sharpness: float = 30.0,
    ):
        self.s_grid = np.linspace(0.0, 1.0, grid_resolution)
        self.ds = self.s_grid[1] - self.s_grid[0]

        # Observation model parameters
        self._freq_a = freq_sensitivity
        self._freq_b = freq_exponent
        self._freq_sigma = freq_sigma
        self._cap_sigma = capacity_sigma
        self._anom_thresh = anomaly_threshold
        self._anom_sharp = anomaly_sharpness

        # Initial prior: uniform over [0, 1]
        self._prior = np.ones_like(self.s_grid) / len(self.s_grid)
        self._history: List[EpochResult] = []

    @property
    def current_posterior(self) -> np.ndarray:
        return self._prior.copy()

    def _freq_model(self, s: np.ndarray) -> np.ndarray:
        """Predicted frequency ratio at scour depth s."""
        return 1.0 - self._freq_a * np.power(np.clip(s, 0, None), self._freq_b)

    def _capacity_model(self, s: np.ndarray) -> np.ndarray:
        """Predicted capacity ratio at scour depth s (linear approx)."""
        return np.clip(1.0 - 0.32 * s, 0.01, 1.0)

    def _likelihood_freq(self, obs: float) -> np.ndarray:
        predicted = self._freq_model(self.s_grid)
        return np.exp(-0.5 * ((obs - predicted) / self._freq_sigma) ** 2)

    def _likelihood_capacity(self, obs: float) -> np.ndarray:
        predicted = self._capacity_model(self.s_grid)
        return np.exp(-0.5 * ((obs - predicted) / self._cap_sigma) ** 2)

    def _likelihood_anomaly(self, detected: bool) -> np.ndarray:
        logistic = 1.0 / (1.0 + np.exp(
            -self._anom_sharp * (self.s_grid - self._anom_thresh)))
        if detected:
            return logistic
        return 1.0 - logistic

    def update(
        self,
        freq_ratio: float,
        capacity_ratio: float,
        anomaly: bool,
    ) -> EpochResult:
        """Process one monitoring epoch and update the posterior.

        The current posterior (from the previous epoch) is used as the
        prior, multiplied by the three channel likelihoods, and
        renormalised. The result becomes the prior for the next epoch.
        """
        L_a = self._likelihood_freq(freq_ratio)
        L_b = self._likelihood_capacity(capacity_ratio)
        L_c = self._likelihood_anomaly(anomaly)

        posterior = self._prior * L_a * L_b * L_c
        total = np.sum(posterior) * self.ds
        if total > 0:
            posterior /= total
        else:
            posterior = np.ones_like(self.s_grid) / len(self.s_grid)

        # Compute summary statistics
        mean = float(np.sum(self.s_grid * posterior * self.ds))
        var = float(np.sum((self.s_grid - mean) ** 2 * posterior * self.ds))
        std = float(np.sqrt(max(var, 0.0)))

        cdf = np.cumsum(posterior * self.ds)
        cdf /= cdf[-1] if cdf[-1] > 0 else 1.0
        p05 = float(np.interp(0.05, cdf, self.s_grid))
        p50 = float(np.interp(0.50, cdf, self.s_grid))
        p95 = float(np.interp(0.95, cdf, self.s_grid))

        # Action recommendation based on posterior mean
        if mean < 0.20:
            action = "continue_monitoring"
        elif mean < 0.45:
            action = "inspect"
        elif mean < 0.70:
            action = "mitigate"
        else:
            action = "emergency_replacement"

        epoch_num = len(self._history) + 1
        result = EpochResult(
            epoch=epoch_num,
            freq_ratio=freq_ratio,
            capacity_ratio=capacity_ratio,
            anomaly=anomaly,
            posterior_mean=round(mean, 4),
            posterior_std=round(std, 4),
            p05=round(p05, 4),
            p50=round(p50, 4),
            p95=round(p95, 4),
            recommended_action=action,
        )
        self._history.append(result)

        # Posterior becomes the prior for the next epoch
        self._prior = posterior.copy()

        return result

    def summary(self) -> dict:
        """Return the latest epoch's diagnostic summary."""
        if not self._history:
            return {"status": "no_epochs_processed"}
        r = self._history[-1]
        return {
            "epoch": r.epoch,
            "posterior_mean_SD": r.posterior_mean,
            "posterior_std_SD": r.posterior_std,
            "credible_interval_90": [r.p05, r.p95],
            "recommended_action": r.recommended_action,
            "n_epochs_accumulated": len(self._history),
        }

    def trajectory(self) -> List[dict]:
        """Return the full trajectory of posterior means over epochs."""
        return [
            {
                "epoch": r.epoch,
                "mean": r.posterior_mean,
                "std": r.posterior_std,
                "p05": r.p05,
                "p95": r.p95,
                "action": r.recommended_action,
            }
            for r in self._history
        ]

    def save(self, path: str | Path) -> None:
        """Save the full tracker state (trajectory + current posterior)."""
        state = {
            "trajectory": self.trajectory(),
            "current_posterior": self._prior.tolist(),
            "grid": self.s_grid.tolist(),
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def reset(self) -> None:
        """Reset to uniform prior and clear history."""
        self._prior = np.ones_like(self.s_grid) / len(self.s_grid)
        self._history.clear()
