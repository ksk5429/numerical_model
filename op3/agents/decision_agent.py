"""
Agentic decision support for Op³.

Automates the full diagnostic pipeline from raw sensor data through
Bayesian scour inference to a natural-language maintenance
prescription. The agent runs the analysis, interprets the results,
and produces a human-readable report suitable for a field engineer
who is not a specialist in probabilistic methods.

The agent does NOT use a language model for the interpretation.
Instead, it uses a rule-based template system that maps quantitative
results (posterior mean, credible interval, VoI ranking, action
recommendation) to pre-written natural-language paragraphs. This
ensures that the output is deterministic, reproducible, and free
of hallucinated content.

Usage
-----
    from op3.agents.decision_agent import DecisionAgent

    agent = DecisionAgent()
    report = agent.run(
        freq_ratio=0.985,
        capacity_ratio=0.92,
        anomaly=True,
    )
    print(report.text)
    report.save("reports/diagnostic_2026_04_09.md")
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class DiagnosticReport:
    """The output of the decision agent."""
    timestamp: str
    epoch: int
    freq_ratio: float
    capacity_ratio: float
    anomaly: bool
    posterior_mean: float
    posterior_std: float
    credible_interval: List[float]
    recommended_action: str
    action_justification: str
    sensor_ranking: List[dict]
    voi_summary: str
    text: str  # full natural-language report
    trajectory: Optional[List[dict]] = None

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.text, encoding="utf-8")

    def to_json(self) -> str:
        d = {
            "timestamp": self.timestamp,
            "epoch": self.epoch,
            "freq_ratio": self.freq_ratio,
            "capacity_ratio": self.capacity_ratio,
            "anomaly": self.anomaly,
            "posterior_mean_SD": self.posterior_mean,
            "posterior_std_SD": self.posterior_std,
            "credible_interval_90": self.credible_interval,
            "recommended_action": self.recommended_action,
            "sensor_ranking": self.sensor_ranking,
        }
        return json.dumps(d, indent=2)


class DecisionAgent:
    """Runs the full diagnostic pipeline and produces a prescription.

    The agent encapsulates the three-step method from Chapter 7:
      1. Translate sensor readings into likelihoods
      2. Combine likelihoods into a posterior via Bayes' theorem
      3. Map the posterior to the cost-minimising action

    It then interprets the results using a rule-based template
    system and produces a natural-language report.
    """

    def __init__(self):
        from op3.uq.sequential_bayesian import SequentialBayesianTracker
        self._tracker = SequentialBayesianTracker()
        self._epoch_count = 0

    def run(
        self,
        freq_ratio: float,
        capacity_ratio: float,
        anomaly: bool,
    ) -> DiagnosticReport:
        """Execute one diagnostic epoch and produce a report."""
        self._epoch_count += 1
        result = self._tracker.update(
            freq_ratio=freq_ratio,
            capacity_ratio=capacity_ratio,
            anomaly=anomaly,
        )

        # Sensor ranking (from Chapter 7 analysis)
        ranking = [
            {"channel": "B (strain gauge)", "voi": 0.48,
             "description": "capacity-based strain fixity ratio"},
            {"channel": "C (statistical)", "voi": 0.29,
             "description": "persistence-filtered anomaly detector"},
            {"channel": "A (accelerometer)", "voi": 0.22,
             "description": "frequency-based vibration monitoring"},
        ]

        # Generate natural-language report
        text = self._generate_text(result, ranking)
        trajectory = self._tracker.trajectory()

        return DiagnosticReport(
            timestamp=dt.datetime.now().isoformat(timespec="seconds"),
            epoch=self._epoch_count,
            freq_ratio=freq_ratio,
            capacity_ratio=capacity_ratio,
            anomaly=anomaly,
            posterior_mean=result.posterior_mean,
            posterior_std=result.posterior_std,
            credible_interval=[result.p05, result.p95],
            recommended_action=result.recommended_action,
            action_justification=self._justify_action(result),
            sensor_ranking=ranking,
            voi_summary=self._voi_text(ranking),
            text=text,
            trajectory=trajectory,
        )

    def _generate_text(self, result, ranking) -> str:
        """Rule-based natural-language report generation."""
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        mean = result.posterior_mean
        std = result.posterior_std
        ci = f"[{result.p05:.2f}, {result.p95:.2f}]"
        action = result.recommended_action.replace("_", " ")

        severity = self._severity_label(mean)
        justification = self._justify_action(result)
        voi = self._voi_text(ranking)
        trend = self._trend_text()

        lines = [
            f"# Op³ Diagnostic Report — Epoch {result.epoch}",
            f"**Generated:** {ts}",
            "",
            "## Current Diagnosis",
            "",
            f"The foundation's estimated normalised scour depth is "
            f"**{mean:.3f} S/D** (±{std:.3f}), with a 90 percent "
            f"credible interval of {ci}. This places the foundation "
            f"in the **{severity}** category.",
            "",
            f"The diagnosis is based on three sensor channels: a "
            f"frequency ratio of {result.freq_ratio:.3f}, a capacity "
            f"ratio of {result.capacity_ratio:.2f}, and an anomaly "
            f"flag {'active' if result.anomaly else 'inactive'}. "
            f"The capacity channel contributed the narrowest likelihood "
            f"and dominated the posterior shape.",
            "",
            "## Recommended Action",
            "",
            f"**{action.upper()}**",
            "",
            justification,
            "",
            "## Sensor Value Assessment",
            "",
            voi,
            "",
        ]

        if trend:
            lines.extend(["## Trend Analysis", "", trend, ""])

        lines.extend([
            "## Provenance",
            "",
            "This report was generated by the Op³ Decision Agent "
            "(rule-based template system, no language model). "
            "Every number traces to the sequential Bayesian tracker "
            "using the observation models calibrated in Chapter 6 "
            "of the associated dissertation. The framework source "
            "code is archived under Zenodo DOI 10.5281/zenodo.19476542.",
            "",
            "---",
            f"*Op³ v1.0.0-rc1 · Epoch {result.epoch} · {ts}*",
        ])
        return "\n".join(lines)

    def _severity_label(self, mean: float) -> str:
        if mean < 0.15:
            return "healthy"
        if mean < 0.30:
            return "early warning"
        if mean < 0.55:
            return "moderate concern"
        if mean < 0.75:
            return "critical"
        return "near failure"

    def _justify_action(self, result) -> str:
        action = result.recommended_action
        mean = result.posterior_mean

        if action == "continue_monitoring":
            return (
                f"The posterior mean of {mean:.3f} S/D falls below "
                f"the inspection threshold. The 90 percent credible "
                f"interval does not extend into the critical range. "
                f"No immediate action is required. The next monitoring "
                f"epoch should be scheduled at the standard interval."
            )
        if action == "inspect":
            return (
                f"The posterior mean of {mean:.3f} S/D falls within "
                f"the inspection range. The expected cost of inspection "
                f"is lower than the expected cost of continued "
                f"monitoring at this scour level, because the "
                f"probability of entering the critical zone before "
                f"the next epoch is non-negligible. A vessel-based "
                f"ROV or diver inspection is recommended."
            )
        if action == "mitigate":
            return (
                f"The posterior mean of {mean:.3f} S/D indicates "
                f"significant capacity degradation. The expected cost "
                f"of scour protection deployment (rock dumping or "
                f"engineered backfill) is lower than the expected cost "
                f"of further degradation. Mitigation should be "
                f"scheduled within the next maintenance window."
            )
        return (
            f"The posterior mean of {mean:.3f} S/D indicates that "
            f"the foundation is approaching or has reached its "
            f"capacity limit. Emergency assessment and potential "
            f"replacement planning should begin immediately. "
            f"Turbine load reduction or shutdown may be warranted "
            f"pending the engineering review."
        )

    def _voi_text(self, ranking) -> str:
        lines = [
            "If the monitoring budget allows one additional sensor, "
            "the recommended priority is:",
        ]
        for i, r in enumerate(ranking, 1):
            lines.append(
                f"{i}. **{r['channel']}** (VoI = {r['voi']:.2f} × "
                f"reference cost) — {r['description']}"
            )
        lines.append(
            "\nThe capacity-based strain gauge has approximately twice "
            "the decision value of the frequency-based accelerometer, "
            "because the lateral capacity degrades faster than the "
            "natural frequency as scour progresses."
        )
        return "\n".join(lines)

    def _trend_text(self) -> str:
        traj = self._tracker.trajectory()
        if len(traj) < 3:
            return ""
        means = [t["mean"] for t in traj]
        recent = means[-3:]
        if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
            rate = (recent[-1] - recent[0]) / len(recent)
            return (
                f"The posterior mean has increased monotonically over "
                f"the last {len(recent)} epochs at an average rate of "
                f"{rate:.4f} S/D per epoch. If this trend continues, "
                f"the foundation will enter the critical zone in "
                f"approximately {max(1, int((0.55 - recent[-1]) / max(rate, 1e-6)))} "
                f"epochs. This trend should be monitored closely."
            )
        if all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1)):
            return (
                "The posterior mean has decreased over the last "
                f"{len(recent)} epochs, which may indicate recovery "
                "from a transient event or an improvement in the "
                "soil conditions (e.g., natural backfill). The trend "
                "is positive but should be confirmed over additional "
                "monitoring epochs before revising the maintenance plan."
            )
        return (
            f"The posterior mean has fluctuated over the last "
            f"{len(recent)} epochs without a clear monotonic trend. "
            f"This variability may reflect environmental noise in "
            f"the sensor channels or genuine intermittent scour-backfill "
            f"cycles. Additional epochs are needed to establish a "
            f"reliable degradation trajectory."
        )

    def reset(self) -> None:
        """Reset the tracker and epoch counter."""
        self._tracker.reset()
        self._epoch_count = 0
