"""
NACA 4-digit airfoil geometry: camber line, thickness distribution, and full
upper/lower surface coordinates for plotting.
"""

import numpy as np


def parse_naca4(code):
    """'2412' -> (m=0.02, p=0.4, t=0.12): max camber, camber position, thickness (fractions of chord)."""
    code = str(code)
    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    t = int(code[2:4]) / 100.0
    return m, p, t


def naca4_camber(m, p, x_over_c):
    """Camber line z/c and its slope dz/dx at station(s) x/c, for a NACA4 airfoil.

    Standard piecewise-parabolic camber line definition:
    front of max-camber point (x < p): one parabola; aft (x >= p): another,
    joined with continuous slope at x = p*c.
    """
    x = np.asarray(x_over_c, dtype=float)
    zc = np.zeros_like(x)
    dzdx = np.zeros_like(x)
    if m == 0 or p == 0:
        return zc, dzdx  # symmetric airfoil: zero camber everywhere
    front = x < p
    zc[front] = m / p**2 * (2 * p * x[front] - x[front] ** 2)
    dzdx[front] = 2 * m / p**2 * (p - x[front])
    back = ~front
    zc[back] = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x[back] - x[back] ** 2)
    dzdx[back] = 2 * m / (1 - p) ** 2 * (p - x[back])
    return zc, dzdx


def naca4_thickness(t, x_over_c):
    """Half-thickness distribution y_t/c at station(s) x/c (standard open-trailing-edge NACA4 form)."""
    x = np.asarray(x_over_c, dtype=float)
    return 5 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1015 * x**4
    )


def naca4_surface(code, n_points=100):
    """Full upper/lower surface coordinates (for plotting the airfoil shape),
    using cosine spacing so points cluster near the leading and trailing edges
    where curvature is highest."""
    m, p, t = parse_naca4(code)
    beta = np.linspace(0, np.pi, n_points)
    x = 0.5 * (1 - np.cos(beta))  # cosine spacing, 0..1

    zc, dzdx = naca4_camber(m, p, x)
    yt = naca4_thickness(t, x)
    theta = np.arctan(dzdx)

    xu = x - yt * np.sin(theta)
    yu = zc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = zc - yt * np.cos(theta)

    return {"x": x, "camber": zc, "xu": xu, "yu": yu, "xl": xl, "yl": yl}
