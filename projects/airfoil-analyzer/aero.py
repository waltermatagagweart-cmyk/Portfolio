"""
Two independent methods for predicting an airfoil's lift, cross-checked against
each other:

1. Classical thin airfoil theory (analytic, Fourier/Glauert integral on the
   camber-line slope) — the textbook closed-form result.
2. A discrete vortex panel method on the camber line (the "1/4-3/4 rule" /
   Weissinger method): each panel's bound vortex sits at its quarter-chord
   point, flow tangency is enforced at its three-quarter-chord point, and
   lift comes from the Kutta-Joukowski theorem applied to total circulation.

Both operate on the camber line only (thin-airfoil assumption) — neither
captures thickness effects on the pressure distribution. See README.md for
what that does and doesn't cost in accuracy.
"""

import numpy as np
from airfoil import naca4_camber


def thin_airfoil_theory(m, p, alpha_deg, n_theta=200):
    """Classical thin airfoil theory: zero-lift angle, lift coefficient, and
    quarter-chord moment coefficient via the Glauert Fourier-series solution."""
    alpha = np.radians(alpha_deg)
    theta = np.linspace(1e-6, np.pi - 1e-6, n_theta)
    x_over_c = 0.5 * (1 - np.cos(theta))
    _, dzdx = naca4_camber(m, p, x_over_c)

    alpha_L0 = -1 / np.pi * np.trapezoid(dzdx * (np.cos(theta) - 1), theta)
    Cl = 2 * np.pi * (alpha - alpha_L0)

    A1 = 2 / np.pi * np.trapezoid(dzdx * np.cos(theta), theta)
    A2 = 2 / np.pi * np.trapezoid(dzdx * np.cos(2 * theta), theta)
    Cm_c4 = (np.pi / 4) * (A2 - A1)

    return {"alpha_L0_deg": np.degrees(alpha_L0), "Cl": Cl, "Cm_c4": Cm_c4}


def vortex_panel_method(m, p, alpha_deg, N=60, Vinf=1.0):
    """Discrete vortex panel method on the camber line (1/4-3/4 rule).

    Returns total Cl, the per-panel circulation distribution (useful as an
    approximate spanwise-loading proxy), and the panel vortex-point stations.
    """
    alpha = np.radians(alpha_deg)
    theta_edges = np.linspace(0, np.pi, N + 1)
    x_edges = 0.5 * (1 - np.cos(theta_edges))

    x1, x2 = x_edges[:-1], x_edges[1:]
    xv = x1 + 0.25 * (x2 - x1)  # bound-vortex point, 1/4 panel
    xc = x1 + 0.75 * (x2 - x1)  # control point, 3/4 panel

    zv, _ = naca4_camber(m, p, xv)
    zc, dzdx_c = naca4_camber(m, p, xc)

    norm = np.sqrt(1 + dzdx_c**2)
    nx = -dzdx_c / norm
    nz = 1.0 / norm

    A = np.zeros((N, N))
    for i in range(N):
        dx = xc[i] - xv
        dz = zc[i] - zv
        r2 = dx**2 + dz**2
        r2 = np.where(r2 < 1e-12, 1e-12, r2)
        # Unit-strength 2D point-vortex induced velocity (u, w).
        u = dz / (2 * np.pi * r2)
        w = -dx / (2 * np.pi * r2)
        A[i, :] = u * nx[i] + w * nz[i]

    b = -Vinf * (np.cos(alpha) * nx + np.sin(alpha) * nz)
    gamma = np.linalg.solve(A, b)

    Gamma_total = np.sum(gamma)
    Cl = 2 * Gamma_total / Vinf  # chord normalized to 1

    return {"Cl": Cl, "gamma": gamma, "x_stations": xv}
