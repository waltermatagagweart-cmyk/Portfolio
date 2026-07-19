"""
Demo run: launch a small sounding rocket, print a flight summary, and save a
four-panel ascent-profile chart to plots/ascent_profile.png.

    python run.py
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")            # headless backend — no display needed
import matplotlib.pyplot as plt

from rocket_sim import Rocket, simulate, KARMAN_LINE


def summary(result, rocket) -> str:
    def km(m): return f"{m/1000:,.1f} km"
    lines = [
        "=" * 56,
        " ROCKET ASCENT - FLIGHT SUMMARY",
        "=" * 56,
        f" Lift-off mass        : {rocket.wet_mass:,.0f} kg",
        f" Propellant           : {rocket.propellant_mass:,.0f} kg "
        f"({rocket.propellant_mass/rocket.wet_mass*100:.0f}% of lift-off mass)",
        f" Thrust / weight       : {rocket.thrust/(rocket.wet_mass*9.80665):.2f}",
        f" Burn time            : {rocket.burn_time:.1f} s",
        "-" * 56,
        f" Burnout altitude     : {km(result.burnout_altitude)}",
        f" Burnout velocity     : {result.burnout_velocity:,.0f} m/s "
        f"(Mach {result.burnout_velocity/343:.1f})",
        f" Apogee (max height)  : {km(result.apogee_altitude)}  at T+{result.apogee_time:.0f} s",
        f" Max-Q (peak load)    : {result.max_q/1000:,.1f} kPa  at {km(result.max_q_altitude)}",
        "-" * 56,
        f" Ideal dv (Tsiolkovsky): {result.ideal_delta_v:,.0f} m/s",
        f" Gravity + drag losses : {result.losses:,.0f} m/s "
        f"({result.losses/result.ideal_delta_v*100:.0f}% of ideal)",
        f" Reached space (100 km): {'YES' if result.reached_space else 'no'}",
        "=" * 56,
    ]
    return "\n".join(lines)


def make_plot(result, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t = result.t
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    fig.suptitle("Rocket ascent profile", fontsize=14, fontweight="bold")

    ax[0, 0].plot(t, result.altitude / 1000, color="#12707e")
    ax[0, 0].axhline(KARMAN_LINE / 1000, ls="--", color="#b96a1e", lw=1,
                     label="Kármán line (space)")
    ax[0, 0].axvline(result.burnout_time, ls=":", color="grey", lw=1, label="burnout")
    ax[0, 0].set(title="Altitude", xlabel="time (s)", ylabel="km"); ax[0, 0].legend(fontsize=8)

    ax[0, 1].plot(t, result.velocity, color="#12707e")
    ax[0, 1].axvline(result.burnout_time, ls=":", color="grey", lw=1)
    ax[0, 1].set(title="Velocity", xlabel="time (s)", ylabel="m/s")

    ax[1, 0].plot(t, result.acceleration / 9.80665, color="#12707e")
    ax[1, 0].axhline(0, color="grey", lw=0.6)
    ax[1, 0].set(title="Acceleration", xlabel="time (s)", ylabel="g")

    ax[1, 1].plot(t, result.dynamic_pressure / 1000, color="#b96a1e")
    ax[1, 1].set(title="Dynamic pressure (max-Q)", xlabel="time (s)", ylabel="kPa")

    for a in ax.flat:
        a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=130)
    print(f"saved {path}")


if __name__ == "__main__":
    # A small sub-orbital sounding rocket.
    rocket = Rocket(
        dry_mass=400.0,        # kg
        propellant_mass=1600.0,  # kg
        thrust=48_000.0,       # N
        isp=250.0,             # s
        diameter=0.6,          # m
        drag_coeff=0.4,
    )
    result = simulate(rocket)
    print(summary(result, rocket))
    make_plot(result, os.path.join("plots", "ascent_profile.png"))
