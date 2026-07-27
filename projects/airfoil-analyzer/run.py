"""
Demo: analyze NACA 0012 (symmetric) and NACA 2412 (cambered), compare thin
airfoil theory against the discrete vortex panel method across an angle-of-
attack sweep, and plot the airfoil shapes and lift curves.
"""

import numpy as np
import matplotlib.pyplot as plt

from airfoil import parse_naca4, naca4_surface
from aero import thin_airfoil_theory, vortex_panel_method

AIRFOILS = ["0012", "2412"]
ALPHA_SWEEP = np.arange(-4, 12.1, 1.0)


def analyze(code):
    m, p, _ = parse_naca4(code)
    tat_cl = [thin_airfoil_theory(m, p, a)["Cl"] for a in ALPHA_SWEEP]
    panel_cl = [vortex_panel_method(m, p, a, N=60)["Cl"] for a in ALPHA_SWEEP]
    alpha_L0 = thin_airfoil_theory(m, p, 0)["alpha_L0_deg"]
    return {"code": code, "tat_cl": tat_cl, "panel_cl": panel_cl, "alpha_L0": alpha_L0}


def main():
    results = {code: analyze(code) for code in AIRFOILS}

    for code, r in results.items():
        print(f"\nNACA {code}")
        print(f"  Zero-lift angle: {r['alpha_L0']:.2f} deg")
        print(f"  Lift-curve slope: 2*pi/rad = {2*np.pi:.4f} (universal, thin airfoil theory)")
        i5 = list(ALPHA_SWEEP).index(5.0)
        print(f"  At alpha=5deg: Cl (thin airfoil theory) = {r['tat_cl'][i5]:.4f}, "
              f"Cl (panel method) = {r['panel_cl'][i5]:.4f}")

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))

    # Airfoil shapes
    ax = axes[0, 0]
    for code in AIRFOILS:
        surf = naca4_surface(code, n_points=100)
        ax.plot(surf["xu"], surf["yu"], label=f"NACA {code} upper")
        ax.plot(surf["xl"], surf["yl"], linestyle="--", color=ax.lines[-1].get_color(), label=f"NACA {code} lower")
        ax.plot(surf["x"], surf["camber"], linestyle=":", color=ax.lines[-1].get_color(), alpha=0.6)
    ax.set_title("Airfoil shapes")
    ax.set_xlabel("x/c"); ax.set_ylabel("y/c")
    ax.axis("equal"); ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # Cl vs alpha, both methods
    ax = axes[0, 1]
    for code, r in results.items():
        ax.plot(ALPHA_SWEEP, r["tat_cl"], label=f"NACA {code}, thin airfoil theory")
        ax.plot(ALPHA_SWEEP, r["panel_cl"], linestyle="--", marker="o", markersize=3,
                 color=ax.lines[-1].get_color(), label=f"NACA {code}, vortex panel method")
    ax.axhline(0, color="gray", linewidth=0.7)
    ax.axvline(0, color="gray", linewidth=0.7)
    ax.set_title("Lift coefficient vs angle of attack")
    ax.set_xlabel("alpha (deg)"); ax.set_ylabel("Cl")
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    # Circulation (loading proxy) distribution at alpha=5 for NACA 2412
    ax = axes[1, 0]
    m, p, _ = parse_naca4("2412")
    panel = vortex_panel_method(m, p, alpha_deg=5, N=60)
    ax.plot(panel["x_stations"], panel["gamma"], color="tab:orange")
    ax.set_title("NACA 2412 circulation distribution, alpha=5deg")
    ax.set_xlabel("x/c"); ax.set_ylabel("panel circulation Gamma_i")
    ax.grid(alpha=0.3)

    # Convergence of panel method to thin airfoil theory as N increases
    ax = axes[1, 1]
    tat5 = thin_airfoil_theory(m, p, 5)["Cl"]
    Ns = [5, 10, 20, 40, 80, 160]
    diffs = [abs(vortex_panel_method(m, p, 5, N=n)["Cl"] - tat5) for n in Ns]
    ax.plot(Ns, diffs, marker="o")
    ax.set_title("Panel method convergence (NACA 2412, alpha=5deg)")
    ax.set_xlabel("Number of panels N"); ax.set_ylabel("|Cl_panel - Cl_TAT|")
    ax.set_xscale("log"); ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig("plots/airfoil_analysis.png", dpi=140)
    print("\nSaved plots/airfoil_analysis.png")


if __name__ == "__main__":
    main()
