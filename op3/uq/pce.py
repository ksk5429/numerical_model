"""
Polynomial Chaos Expansion surrogate (Phase 5 / Task 5.2).

A minimal Hermite-polynomial PCE for surrogate modelling of expensive
Op^3 responses (eigenvalue, DLC outputs) as a function of one or two
standard-normal input parameters. The surrogate is built by
pseudo-spectral projection over a Gauss-Hermite quadrature grid:

    f(xi) ~ sum_{k=0}^{p} c_k H_k(xi)

where H_k are the probabilist Hermite polynomials and the
coefficients are obtained as

    c_k = E[ f * H_k ] / E[ H_k^2 ]

with the expectation taken over the standard-normal density.
Hermite polynomial orthogonality gives ``E[H_k^2] = k!``.

For 2D inputs the basis is the tensor product of 1D Hermite
polynomials and the quadrature is a tensor product of 1D Gauss-Hermite
nodes.

References
----------
Wiener, N. (1938). "The Homogeneous Chaos". Am. J. Math. 60(4),
    897-936.
Xiu, D., & Karniadakis, G. E. (2002). "The Wiener-Askey polynomial
    chaos for stochastic differential equations". SIAM J. Sci.
    Comput. 24(2), 619-644.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.polynomial.hermite_e import hermegauss, hermeval


@dataclass
class HermitePCE:
    coeffs: np.ndarray              # 1D: shape (p+1,) ; 2D: shape (p1+1, p2+1)
    order: int
    n_dim: int

    def evaluate(self, xi: float | np.ndarray,
                 xi2: float | np.ndarray | None = None) -> np.ndarray:
        if self.n_dim == 1:
            return hermeval(np.asarray(xi), self.coeffs)
        if self.n_dim == 2:
            if xi2 is None:
                raise ValueError("2D PCE requires both xi and xi2")
            x = np.atleast_1d(np.asarray(xi))
            y = np.atleast_1d(np.asarray(xi2))
            out = np.zeros_like(x, dtype=float)
            for i in range(self.coeffs.shape[0]):
                for j in range(self.coeffs.shape[1]):
                    e_i = np.zeros(i + 1); e_i[i] = 1.0
                    e_j = np.zeros(j + 1); e_j[j] = 1.0
                    out += self.coeffs[i, j] * hermeval(x, e_i) * hermeval(y, e_j)
            return out
        raise NotImplementedError(f"n_dim={self.n_dim} not supported")


def _factorial(n: int) -> int:
    out = 1
    for k in range(2, n + 1):
        out *= k
    return out


def build_pce_1d(
    f: Callable[[float], float],
    order: int = 4,
    n_quad: int | None = None,
) -> HermitePCE:
    """
    Pseudo-spectral 1D Hermite PCE built on Gauss-Hermite quadrature.
    The input is the standard normal coordinate xi ~ N(0, 1); callers
    are responsible for mapping back to the physical parameter space.
    """
    if n_quad is None:
        n_quad = 2 * order + 1   # exact for polynomials of degree 4*order+1
    nodes, weights = hermegauss(n_quad)
    # hermegauss returns weights for INT f(x) exp(-x^2/2) dx, missing
    # the 1/sqrt(2 pi) normalisation of the standard normal density.
    weights = weights / np.sqrt(2.0 * np.pi)
    f_vals = np.array([f(float(x)) for x in nodes])
    coeffs = np.zeros(order + 1)
    for k in range(order + 1):
        e_k = np.zeros(k + 1); e_k[k] = 1.0
        H_k = hermeval(nodes, e_k)
        coeffs[k] = float(np.sum(weights * f_vals * H_k) / _factorial(k))
    return HermitePCE(coeffs=coeffs, order=order, n_dim=1)


def build_pce_2d(
    f: Callable[[float, float], float],
    order: int = 3,
    n_quad: int | None = None,
) -> HermitePCE:
    if n_quad is None:
        n_quad = 2 * order + 1
    nodes, weights = hermegauss(n_quad)
    weights = weights / np.sqrt(2.0 * np.pi)
    coeffs = np.zeros((order + 1, order + 1))
    f_vals = np.array([[f(float(x), float(y)) for y in nodes] for x in nodes])
    for i in range(order + 1):
        e_i = np.zeros(i + 1); e_i[i] = 1.0
        H_i = hermeval(nodes, e_i)
        for j in range(order + 1):
            e_j = np.zeros(j + 1); e_j[j] = 1.0
            H_j = hermeval(nodes, e_j)
            inner = 0.0
            for a in range(n_quad):
                for b in range(n_quad):
                    inner += (weights[a] * weights[b] * f_vals[a, b]
                              * H_i[a] * H_j[b])
            coeffs[i, j] = inner / (_factorial(i) * _factorial(j))
    return HermitePCE(coeffs=coeffs, order=order, n_dim=2)


def pce_sobol_2d(pce: HermitePCE) -> dict:
    """
    First-order and total Sobol indices from a 2D Hermite PCE.

    For the tensor-product basis :math:`\\Psi_{ij}(\\xi_1, \\xi_2) = H_i(\\xi_1) H_j(\\xi_2)`
    the total variance decomposes as

    .. math::
        V = \\sum_{(i,j) \\neq (0,0)} i!\\,j!\\,c_{ij}^2

    with partial variances grouped by which input is active:

    - :math:`V_1 = \\sum_{i \\geq 1, j = 0} i!\\,c_{i0}^2`
    - :math:`V_2 = \\sum_{i = 0, j \\geq 1} j!\\,c_{0j}^2`
    - :math:`V_{12} = \\sum_{i \\geq 1, j \\geq 1} i!\\,j!\\,c_{ij}^2`

    First-order Sobol: :math:`S_i = V_i / V`. Total Sobol:
    :math:`S_i^T = (V_i + V_{12}) / V`.
    """
    if pce.n_dim != 2:
        raise ValueError("pce_sobol_2d requires a 2D PCE")
    V = 0.0
    V1 = 0.0
    V2 = 0.0
    V12 = 0.0
    for i in range(pce.coeffs.shape[0]):
        for j in range(pce.coeffs.shape[1]):
            if i == 0 and j == 0:
                continue
            contrib = _factorial(i) * _factorial(j) * pce.coeffs[i, j] ** 2
            V += contrib
            if i >= 1 and j == 0:
                V1 += contrib
            elif i == 0 and j >= 1:
                V2 += contrib
            else:
                V12 += contrib
    if V == 0:
        return {"S1": 0.0, "S2": 0.0, "S1_total": 0.0, "S2_total": 0.0,
                "V": 0.0, "V1": 0.0, "V2": 0.0, "V12": 0.0}
    return {
        "S1": V1 / V,
        "S2": V2 / V,
        "S1_total": (V1 + V12) / V,
        "S2_total": (V2 + V12) / V,
        "V": V, "V1": V1, "V2": V2, "V12": V12,
    }


def pce_mean_var(pce: HermitePCE) -> tuple[float, float]:
    """Closed-form mean and variance from Hermite PCE coefficients.
    Mean = c_0; Variance = sum_{k>=1} k! * c_k^2 ."""
    if pce.n_dim == 1:
        mean = float(pce.coeffs[0])
        var = 0.0
        for k in range(1, pce.coeffs.size):
            var += _factorial(k) * pce.coeffs[k] ** 2
        return mean, var
    if pce.n_dim == 2:
        mean = float(pce.coeffs[0, 0])
        var = 0.0
        for i in range(pce.coeffs.shape[0]):
            for j in range(pce.coeffs.shape[1]):
                if i == 0 and j == 0:
                    continue
                var += (_factorial(i) * _factorial(j)
                        * pce.coeffs[i, j] ** 2)
        return mean, var
    raise NotImplementedError
