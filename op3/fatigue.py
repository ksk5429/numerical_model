"""
Fatigue damage-equivalent load (DEL) computation module for Op^3.

Implements rainflow counting and DEL per DNV-RP-C203 / Hayman (2012).

DEL formula:
    DEL = (sum(n_i * S_i^m) / N_eq) ^ (1/m)

where:
    n_i   = cycle count for stress range S_i (half-cycles count as 0.5)
    S_i   = stress range (peak-to-valley amplitude, NOT half-amplitude)
    m     = inverse Woehler slope (3-5 for steel, 8-12 for composites)
    N_eq  = equivalent number of cycles (typically 1 Hz * T_lifetime)

References:
    - Hayman, G. (2012). MLife Theory Manual. NREL/TP-XXXX.
    - DNV-RP-C203 (2021). Fatigue design of offshore steel structures.
    - ASTM E1049-85. Standard practices for cycle counting in fatigue analysis.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np


def compute_del(
    signal: np.ndarray,
    m: float,
    n_eq: Optional[float] = None,
    dt: Optional[float] = None,
    f_eq: float = 1.0,
) -> float:
    """Compute the damage-equivalent load for a time series.

    Parameters
    ----------
    signal : array_like
        Load time series (e.g. TwrBsMyt in kN-m). 1-D array.
    m : float
        Inverse S-N slope (Woehler exponent). Typical values:
          - 3 for welded steel (DNV-RP-C203 detail categories)
          - 4 for base-metal steel
          - 10 for glass-fibre composites
    n_eq : float, optional
        Equivalent cycle count. If None, computed as ``f_eq * T`` where
        ``T = len(signal) * dt``.
    dt : float, optional
        Time step in seconds. Required if ``n_eq`` is None.
    f_eq : float
        Equivalent frequency in Hz (default 1.0).

    Returns
    -------
    del_value : float
        Damage-equivalent load in the same units as *signal*.

    Raises
    ------
    ValueError
        If neither ``n_eq`` nor ``dt`` is provided.
    """
    signal = np.asarray(signal, dtype=np.float64)
    if signal.size < 3:
        return 0.0

    # --- Equivalent cycle count ---
    if n_eq is None:
        if dt is None:
            raise ValueError("Either n_eq or dt must be provided.")
        duration = (signal.size - 1) * dt
        n_eq = f_eq * duration
    if n_eq <= 0:
        return 0.0

    # --- Rainflow counting ---
    ranges, counts = rainflow_count(signal)
    if len(ranges) == 0:
        return 0.0

    # --- DEL aggregation ---
    # ranges from rainflow are full cycle ranges (peak-to-valley)
    damage_sum = np.sum(counts * np.abs(ranges) ** m)
    del_value = (damage_sum / n_eq) ** (1.0 / m)
    return float(del_value)


def rainflow_count(signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Rainflow cycle counting using the ``rainflow`` package.

    Falls back to a built-in 4-point algorithm (ASTM E1049-85) if the
    package is unavailable.

    Parameters
    ----------
    signal : array_like
        1-D load time series.

    Returns
    -------
    ranges : ndarray
        Stress ranges (peak-to-valley, always positive).
    counts : ndarray
        Cycle counts (0.5 for half-cycles, 1.0 for full cycles).
    """
    signal = np.asarray(signal, dtype=np.float64)
    try:
        return _rainflow_package(signal)
    except ImportError:
        return _rainflow_astm(signal)


def _rainflow_package(signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Delegate to the ``rainflow`` PyPI package (v3.x API)."""
    import rainflow  # noqa: F811

    ranges_list = []
    counts_list = []
    for rng, mean, count, i_start, i_end in rainflow.extract_cycles(signal):
        ranges_list.append(rng)
        counts_list.append(count)
    return np.array(ranges_list), np.array(counts_list)


def _rainflow_astm(signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Minimal 4-point rainflow counter per ASTM E1049-85.

    This is a fallback implementation. It identifies turning points first,
    then applies the 4-point counting rule.
    """
    # --- Extract turning points ---
    tp = _turning_points(signal)
    if len(tp) < 2:
        return np.array([]), np.array([])

    ranges_list = []
    counts_list = []
    stack = list(tp)

    while len(stack) >= 4:
        s0, s1, s2, s3 = stack[-4], stack[-3], stack[-2], stack[-1]
        x = abs(s1 - s2)
        y = abs(s0 - s1)
        if x <= y:
            ranges_list.append(x)
            counts_list.append(1.0)
            del stack[-3]
            del stack[-2]  # remove s1 and s2
        else:
            break

    # Remaining stack: half-cycles
    for i in range(len(stack) - 1):
        rng = abs(stack[i + 1] - stack[i])
        if rng > 0:
            ranges_list.append(rng)
            counts_list.append(0.5)

    return np.array(ranges_list), np.array(counts_list)


def _turning_points(signal: np.ndarray) -> np.ndarray:
    """Extract local peaks and valleys from a signal."""
    if len(signal) < 3:
        return signal.copy()

    tp = [signal[0]]
    for i in range(1, len(signal) - 1):
        if (signal[i] - signal[i - 1]) * (signal[i + 1] - signal[i]) < 0:
            tp.append(signal[i])
    tp.append(signal[-1])
    return np.array(tp)


def compute_del_multi_slope(
    signal: np.ndarray,
    m_values: list[float],
    n_eq: Optional[float] = None,
    dt: Optional[float] = None,
    f_eq: float = 1.0,
) -> dict[float, float]:
    """Compute DEL for multiple Woehler exponents.

    Useful for comparing steel (m=3-5) vs composite (m=10) fatigue.

    Returns a dict mapping m -> DEL.
    """
    result = {}
    for m in m_values:
        result[m] = compute_del(signal, m=m, n_eq=n_eq, dt=dt, f_eq=f_eq)
    return result
