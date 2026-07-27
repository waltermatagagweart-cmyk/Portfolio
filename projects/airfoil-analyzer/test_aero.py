"""
Tests check the two independent lift-prediction methods against known
textbook/literature values, and against each other.
"""

import numpy as np
import pytest

from airfoil import parse_naca4, naca4_surface, naca4_camber
from aero import thin_airfoil_theory, vortex_panel_method


def test_flat_plate_zero_lift_angle_is_zero():
    """A symmetric airfoil (zero camber) has no zero-lift angle offset."""
    result = thin_airfoil_theory(m=0, p=0, alpha_deg=0)
    assert abs(result["alpha_L0_deg"]) < 1e-9


@pytest.mark.parametrize("alpha_deg", [0, 3, 5, 10])
def test_flat_plate_matches_classical_2pi_alpha(alpha_deg):
    """Thin airfoil theory for a flat plate must reduce to Cl = 2*pi*alpha (alpha in radians)."""
    result = thin_airfoil_theory(m=0, p=0, alpha_deg=alpha_deg)
    expected = 2 * np.pi * np.radians(alpha_deg)
    assert result["Cl"] == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("alpha_deg", [0, 5, 10])
def test_panel_method_matches_thin_airfoil_theory_for_flat_plate(alpha_deg):
    tat = thin_airfoil_theory(m=0, p=0, alpha_deg=alpha_deg)
    panel = vortex_panel_method(m=0, p=0, alpha_deg=alpha_deg, N=60)
    assert panel["Cl"] == pytest.approx(tat["Cl"], abs=0.01)


def test_naca2412_zero_lift_angle_matches_literature():
    """NACA 2412's zero-lift angle is well documented as approximately -2.0 to -2.1 degrees."""
    m, p, _ = parse_naca4("2412")
    result = thin_airfoil_theory(m, p, alpha_deg=0)
    assert -2.3 < result["alpha_L0_deg"] < -1.8


def test_naca2412_lift_slope_is_two_pi_per_radian():
    """Thin airfoil theory predicts a universal lift-curve slope of 2*pi/rad, independent of camber."""
    m, p, _ = parse_naca4("2412")
    cl_0 = thin_airfoil_theory(m, p, 0)["Cl"]
    cl_1 = thin_airfoil_theory(m, p, 1)["Cl"]
    slope_per_rad = (cl_1 - cl_0) * 180 / np.pi
    assert slope_per_rad == pytest.approx(2 * np.pi, abs=0.01)


def test_naca2412_panel_and_tat_agree_across_alpha_sweep():
    m, p, _ = parse_naca4("2412")
    for alpha_deg in [-2, 0, 5, 10]:
        tat = thin_airfoil_theory(m, p, alpha_deg)
        panel = vortex_panel_method(m, p, alpha_deg, N=60)
        assert panel["Cl"] == pytest.approx(tat["Cl"], abs=0.02)


def test_panel_method_converges_as_panel_count_increases():
    """More panels should bring the discrete method closer to (or stably near) the analytic result."""
    m, p, _ = parse_naca4("2412")
    tat_cl = thin_airfoil_theory(m, p, 5)["Cl"]
    diffs = []
    for N in [5, 10, 20, 40, 80]:
        panel_cl = vortex_panel_method(m, p, 5, N=N)["Cl"]
        diffs.append(abs(panel_cl - tat_cl))
    # Should stabilize to a small, bounded discrepancy rather than diverge.
    assert diffs[-1] < 0.01
    assert max(diffs) < 0.02


def test_cl_increases_monotonically_with_alpha_in_linear_range():
    m, p, _ = parse_naca4("2412")
    alphas = [-2, 0, 2, 4, 6, 8]
    cls_tat = [thin_airfoil_theory(m, p, a)["Cl"] for a in alphas]
    cls_panel = [vortex_panel_method(m, p, a, N=60)["Cl"] for a in alphas]
    assert all(b > a for a, b in zip(cls_tat, cls_tat[1:]))
    assert all(b > a for a, b in zip(cls_panel, cls_panel[1:]))


def test_naca4_surface_upper_above_lower_for_cambered_airfoil():
    """Sanity check on the geometry: the upper surface should sit above the lower surface everywhere."""
    surf = naca4_surface("2412", n_points=50)
    # Compare at matching x-stations only where the airfoil has real thickness (skip the very tip points)
    assert np.all(surf["yu"][2:-2] > surf["yl"][2:-2])


def test_symmetric_airfoil_camber_is_zero_everywhere():
    m, p, _ = parse_naca4("0012")
    zc, dzdx = naca4_camber(m, p, np.linspace(0, 1, 50))
    assert np.allclose(zc, 0)
    assert np.allclose(dzdx, 0)
