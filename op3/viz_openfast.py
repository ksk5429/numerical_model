"""
Op3 OpenFAST Postprocessing via welib + pCrunch.

Advanced visualization and analysis of OpenFAST outputs:
  - Time series with channel overlay
  - Power spectral density (PSD)
  - Power curve from DLC sweep
  - Fatigue damage-equivalent loads (DEL)
  - DLC batch statistics (mean, std, min, max, DEL per wind speed)
  - Campbell diagram (from linearization files)

Usage::

    from op3.viz_openfast import (
        plot_time_series, plot_psd, plot_power_curve,
        plot_del_bar, compute_dlc_statistics,
    )
    stats = compute_dlc_statistics("validation/dlc11_partial/")
    plot_power_curve(stats, output_dir="validation/figures/")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _read_outb(path: str | Path):
    """Read OpenFAST .outb binary output into DataFrame."""
    try:
        from openfast_io.FAST_output_reader import FASTOutputFile
        return FASTOutputFile(str(path)).toDataFrame()
    except ImportError:
        raise ImportError("openfast_io required: pip install openfast-io")


def _save_or_show(fig, name: str, output_dir: Optional[str | Path]):
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{name}.png"
        fig.savefig(str(path), dpi=200, bbox_inches='tight',
                    facecolor='white')
        plt.close(fig)
        return str(path)
    plt.show()
    return None


# ============================================================
# Time series
# ============================================================

def plot_time_series(
    outb_path: str | Path,
    channels: list[str] = None,
    output_dir: Optional[str | Path] = None,
    title: str = "OpenFAST Time Series",
) -> Optional[str]:
    """Plot selected channels from a single OpenFAST output file."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")

    df = _read_outb(outb_path)

    if channels is None:
        # Auto-select interesting channels
        candidates = ['GenPwr_[kW]', 'RotSpeed_[rpm]', 'BldPitch1_[deg]',
                       'RootMyc1_[kN-m]', 'TwrBsMyt_[kN-m]',
                       'YawBrTDxt_[m]', '-ReactMYss_[kN-m]']
        channels = [c for c in candidates if c in df.columns]

    n = len(channels)
    if n == 0:
        return None

    fig, axes = plt.subplots(n, 1, figsize=(14, 3 * n), sharex=True)
    if n == 1:
        axes = [axes]

    time_col = [c for c in df.columns if 'time' in c.lower()][0]
    t = df[time_col].values

    colors = plt.cm.tab10(np.linspace(0, 1, n))
    for ax, ch, color in zip(axes, channels, colors):
        if ch in df.columns:
            ax.plot(t, df[ch].values, color=color, linewidth=0.5)
            ax.set_ylabel(ch, fontsize=10)
            mean_val = df[ch].mean()
            ax.axhline(mean_val, color='gray', linestyle='--', alpha=0.5)
            ax.text(0.98, 0.85, f'mean={mean_val:.1f}',
                    transform=ax.transAxes, ha='right', fontsize=9,
                    bbox=dict(facecolor='white', alpha=0.7))
        ax.grid(True, alpha=0.2)

    axes[-1].set_xlabel('Time (s)', fontsize=12)
    fig.suptitle(title, fontsize=14, fontweight='bold')
    fig.tight_layout()

    return _save_or_show(fig, "openfast_timeseries", output_dir)


# ============================================================
# Power Spectral Density
# ============================================================

def plot_psd(
    outb_path: str | Path,
    channel: str = None,
    output_dir: Optional[str | Path] = None,
    title: str = None,
) -> Optional[str]:
    """Plot PSD of a channel using Welch's method."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")

    df = _read_outb(outb_path)
    time_col = [c for c in df.columns if 'time' in c.lower()][0]
    dt = df[time_col].diff().median()

    if channel is None:
        for c in ['YawBrTDxt_[m]', '-ReactMYss_[kN-m]', 'TwrBsMyt_[kN-m]',
                  '-ReactMYss_[N*m]', 'YawBrMyp_[kN-m]', 'RootMyc1_[kN-m]']:
            if c in df.columns:
                channel = c
                break
    if channel is None or channel not in df.columns:
        return None

    from scipy.signal import welch
    fs = 1.0 / dt
    f, Pxx = welch(df[channel].values, fs=fs, nperseg=min(1024, len(df) // 2))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.semilogy(f, Pxx, 'b-', linewidth=1)
    ax.set_xlabel('Frequency (Hz)', fontsize=12)
    ax.set_ylabel(f'PSD ({channel})', fontsize=12)
    ax.set_xlim(0, 2.0)
    ax.grid(True, alpha=0.3, which='both')

    # Mark 1P and 3P
    rpm_col = [c for c in df.columns if 'RotSpeed' in c]
    if rpm_col:
        rpm = df[rpm_col[0]].mean()
        f_1P = rpm / 60
        f_3P = 3 * f_1P
        ax.axvline(f_1P, color='r', linestyle='--', alpha=0.5,
                   label=f'1P = {f_1P:.3f} Hz')
        ax.axvline(f_3P, color='orange', linestyle='--', alpha=0.5,
                   label=f'3P = {f_3P:.3f} Hz')
        ax.legend(fontsize=10)

    if title is None:
        title = f"PSD: {channel}"
    ax.set_title(title, fontsize=14, fontweight='bold')

    return _save_or_show(fig, "openfast_psd", output_dir)


# ============================================================
# DLC batch statistics
# ============================================================

def compute_dlc_statistics(
    dlc_dir: str | Path,
    channels: list[str] = None,
) -> dict:
    """Compute statistics from a DLC sweep directory.

    Returns dict with 'wind_speeds', 'stats' (DataFrame per channel).
    """
    import pandas as pd

    dlc_dir = Path(dlc_dir)
    outb_files = sorted(dlc_dir.glob("*.outb"))
    if not outb_files:
        return {"wind_speeds": [], "stats": {}}

    all_stats = []
    for f in outb_files:
        df = _read_outb(f)
        time_col = [c for c in df.columns if 'time' in c.lower()][0]

        # Extract wind speed from filename
        ws = None
        name = f.stem
        for part in name.split('_'):
            if 'mps' in part:
                try:
                    ws = float(part.replace('mps', '').replace('p', '.')) / 10
                    if ws > 50:
                        ws = ws / 10
                except ValueError:
                    pass

        # Skip first 30s for transient
        t = df[time_col].values
        mask = t > 30 if t.max() > 60 else t > 0
        df_ss = df[mask]

        row = {'file': f.name, 'wind_speed': ws}
        if channels is None:
            channels = [c for c in df.columns if c != time_col]

        for ch in channels:
            if ch in df_ss.columns:
                vals = df_ss[ch].values
                row[f'{ch}_mean'] = float(np.mean(vals))
                row[f'{ch}_std'] = float(np.std(vals))
                row[f'{ch}_min'] = float(np.min(vals))
                row[f'{ch}_max'] = float(np.max(vals))

        all_stats.append(row)

    stats_df = pd.DataFrame(all_stats).sort_values('wind_speed')
    return {
        "wind_speeds": stats_df['wind_speed'].tolist(),
        "stats_df": stats_df,
        "n_runs": len(outb_files),
    }


# ============================================================
# Power curve
# ============================================================

def plot_power_curve(
    stats: dict,
    output_dir: Optional[str | Path] = None,
    title: str = "Power Curve (DLC 1.1)",
) -> Optional[str]:
    """Plot power curve from DLC statistics."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")

    df = stats.get("stats_df")
    if df is None or df.empty:
        return None

    ws = df['wind_speed'].values
    pwr_col = [c for c in df.columns if 'GenPwr' in c and '_mean' in c]
    rpm_col = [c for c in df.columns if 'RotSpeed' in c and '_mean' in c]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    if pwr_col:
        pwr = df[pwr_col[0]].values
        axes[0].plot(ws, pwr, 'bo-', linewidth=2, markersize=8)
        axes[0].axhline(5000, color='r', linestyle='--', alpha=0.5,
                        label='Rated (5 MW)')
        axes[0].set_ylabel('Generator Power (kW)', fontsize=12)
        axes[0].legend(fontsize=10)
        axes[0].grid(True, alpha=0.3)
        axes[0].set_ylim(bottom=0)

    if rpm_col:
        rpm = df[rpm_col[0]].values
        axes[1].plot(ws, rpm, 'go-', linewidth=2, markersize=8)
        axes[1].axhline(12.1, color='r', linestyle='--', alpha=0.5,
                        label='Rated (12.1 rpm)')
        axes[1].set_ylabel('Rotor Speed (rpm)', fontsize=12)
        axes[1].set_xlabel('Wind Speed (m/s)', fontsize=12)
        axes[1].legend(fontsize=10)
        axes[1].grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=14, fontweight='bold')
    fig.tight_layout()

    return _save_or_show(fig, "openfast_power_curve", output_dir)


# ============================================================
# DEL bar chart
# ============================================================

def plot_del_bar(
    outb_paths: list[str | Path],
    channels: list[str] = None,
    m_values: list[float] = None,
    output_dir: Optional[str | Path] = None,
    title: str = "Damage-Equivalent Loads",
) -> Optional[str]:
    """Compute and plot DEL for multiple channels across runs."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")

    from op3.fatigue import compute_del

    if m_values is None:
        m_values = [3, 4, 10]
    if channels is None:
        channels = ['RootMyc1_[kN-m]', '-ReactMYss_[kN-m]']

    results = {}
    for path in outb_paths:
        df = _read_outb(path)
        time_col = [c for c in df.columns if 'time' in c.lower()][0]
        t = df[time_col].values
        dt = np.median(np.diff(t))

        for ch in channels:
            if ch not in df.columns:
                continue
            signal = df[ch].values
            for m in m_values:
                del_val = compute_del(signal, m=m, dt=dt)
                key = f"{ch} (m={m})"
                if key not in results:
                    results[key] = []
                results[key].append(del_val)

    if not results:
        return None

    # Average DEL across runs
    labels = list(results.keys())
    values = [np.mean(v) for v in results.values()]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=plt.cm.Set2(np.linspace(0, 1, len(labels))))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=9)
    ax.set_ylabel('DEL (same units as channel)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f'{val:.0f}', ha='center', va='bottom', fontsize=9)

    fig.tight_layout()
    return _save_or_show(fig, "openfast_del", output_dir)


# ============================================================
# pCrunch batch processing
# ============================================================

def run_pcrunch_batch(
    outb_files: list[str | Path],
    wind_speeds: list[float],
    m_values: list[float] = None,
) -> dict:
    """Run pCrunch batch statistics on a set of OpenFAST outputs.

    Returns dict with summary_stats and DELs DataFrames.
    """
    try:
        from pcrunch import AeroelasticOutput, Crunch
    except ImportError:
        return {"error": "pcrunch not installed: pip install pcrunch"}

    if m_values is None:
        m_values = [3, 4, 6, 8, 10]

    outputs = []
    for path, ws in zip(outb_files, wind_speeds):
        try:
            df = _read_outb(path)
            outputs.append(AeroelasticOutput(df, wind_speed=ws))
        except Exception as e:
            print(f"  Warning: failed to load {path}: {e}")

    if not outputs:
        return {"error": "no valid outputs"}

    crunch = Crunch(outputs, DEL_windspeed=11.4, m=m_values)

    return {
        "summary_stats": crunch.summary_stats,
        "DELs": crunch.DELs,
        "n_runs": len(outputs),
    }
