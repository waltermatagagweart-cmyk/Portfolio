"""
Rocket ascent simulator
========================

Simulates the vertical launch of a rocket, integrating the equations of motion
with three physical effects that matter for a real ascent:

  * variable mass          — the rocket burns propellant, so it gets lighter
  * altitude-dependent g   — gravity weakens with height, g(h) = g0 (Re/(Re+h))^2
  * atmospheric drag       — an exponential-atmosphere density model, rho(h)

The equations are integrated with SciPy's adaptive RK45 (`solve_ivp`), and a
terminal event stops the run at apogee (the moment vertical velocity hits zero).

Author: Walter Matagagwe
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

# ---- physical constants -----------------------------------------------------
G0 = 9.80665            # standard gravity at sea level, m/s^2
R_EARTH = 6.371e6       # mean Earth radius, m
RHO0 = 1.225            # sea-level air density, kg/m^3
SCALE_HEIGHT = 8500.0   # exponential-atmosphere scale height, m
KARMAN_LINE = 100_000.0 # the 100 km boundary of space, m


@dataclass
class Rocket:
    """A single-stage rocket with a constant thrust during the burn."""
    dry_mass: float          # kg — structure + payload, no propellant
    propellant_mass: float   # kg
    thrust: float            # N — constant while the motor burns
    isp: float               # s — specific impulse (engine efficiency)
    diameter: float          # m
    drag_coeff: float = 0.4  # dimensionless

    @property
    def wet_mass(self) -> float:
        """Lift-off mass (dry + propellant)."""
        return self.dry_mass + self.propellant_mass

    @property
    def exhaust_velocity(self) -> float:
        """Effective exhaust velocity, ve = Isp * g0 (m/s)."""
        return self.isp * G0

    @property
    def mass_flow_rate(self) -> float:
        """Propellant burn rate, mdot = thrust / ve (kg/s)."""
        return self.thrust / self.exhaust_velocity

    @property
    def burn_time(self) -> float:
        """How long the motor burns (s)."""
        return self.propellant_mass / self.mass_flow_rate

    @property
    def frontal_area(self) -> float:
        """Cross-sectional area presented to the airflow (m^2)."""
        return np.pi * (self.diameter / 2.0) ** 2

    @property
    def ideal_delta_v(self) -> float:
        """
        The Tsiolkovsky rocket equation: the velocity a rocket *could* gain in
        empty space with no gravity or drag losses.  dv = ve * ln(m_wet / m_dry).
        """
        return self.exhaust_velocity * np.log(self.wet_mass / self.dry_mass)


# ---- environment models -----------------------------------------------------
def gravity(h: float) -> float:
    """Gravitational acceleration at altitude h (m/s^2)."""
    return G0 * (R_EARTH / (R_EARTH + h)) ** 2


def air_density(h: float) -> float:
    """Air density at altitude h using an exponential atmosphere (kg/m^3)."""
    return RHO0 * np.exp(-max(h, 0.0) / SCALE_HEIGHT)


# ---- simulation -------------------------------------------------------------
@dataclass
class AscentResult:
    """Time-series and summary metrics from a simulated ascent."""
    t: np.ndarray            # s
    altitude: np.ndarray     # m
    velocity: np.ndarray     # m/s
    acceleration: np.ndarray # m/s^2
    mass: np.ndarray         # kg
    dynamic_pressure: np.ndarray  # Pa
    burnout_time: float
    burnout_altitude: float
    burnout_velocity: float
    apogee_time: float
    apogee_altitude: float
    max_q: float
    max_q_altitude: float
    ideal_delta_v: float
    losses: float            # ideal delta-v minus velocity actually gained (m/s)
    reached_space: bool


def simulate(rocket: Rocket, max_time: float = 2000.0, dt: float = 0.05) -> AscentResult:
    """Integrate the vertical ascent from lift-off to apogee."""
    tb = rocket.burn_time

    def derivatives(t, y):
        h, v, m = y
        thrust = rocket.thrust if t < tb else 0.0
        mdot = -rocket.mass_flow_rate if t < tb else 0.0
        rho = air_density(h)
        # v*|v| keeps drag opposing the direction of motion
        drag = 0.5 * rho * v * abs(v) * rocket.drag_coeff * rocket.frontal_area
        acc = (thrust - drag - m * gravity(h)) / m
        return [v, acc, mdot]

    def apogee_event(t, y):
        return y[1]          # trigger when vertical velocity == 0
    apogee_event.terminal = True
    apogee_event.direction = -1   # only when velocity is decreasing through zero

    y0 = [0.0, 0.0, rocket.wet_mass]
    t_eval = np.arange(0.0, max_time, dt)
    sol = solve_ivp(
        derivatives, (0.0, max_time), y0, t_eval=t_eval, events=apogee_event,
        max_step=0.25, rtol=1e-9, atol=1e-9,
    )

    t, altitude, velocity, mass = sol.t, sol.y[0], sol.y[1], sol.y[2]

    # recompute acceleration and dynamic pressure along the solution
    acceleration = np.gradient(velocity, t)
    rho = RHO0 * np.exp(-np.clip(altitude, 0, None) / SCALE_HEIGHT)
    dynamic_pressure = 0.5 * rho * velocity ** 2

    # burnout = state at the end of the burn
    bi = int(np.searchsorted(t, tb))
    bi = min(bi, len(t) - 1)

    # apogee = the terminal event (fall back to last sample if it never fired)
    if sol.t_events[0].size:
        apogee_time = float(sol.t_events[0][0])
        apogee_altitude = float(sol.y_events[0][0][0])
    else:
        apogee_time = float(t[-1])
        apogee_altitude = float(altitude[-1])

    mq_idx = int(np.argmax(dynamic_pressure))

    return AscentResult(
        t=t, altitude=altitude, velocity=velocity, acceleration=acceleration,
        mass=mass, dynamic_pressure=dynamic_pressure,
        burnout_time=tb,
        burnout_altitude=float(altitude[bi]),
        burnout_velocity=float(velocity[bi]),
        apogee_time=apogee_time,
        apogee_altitude=apogee_altitude,
        max_q=float(dynamic_pressure[mq_idx]),
        max_q_altitude=float(altitude[mq_idx]),
        ideal_delta_v=float(rocket.ideal_delta_v),
        losses=float(rocket.ideal_delta_v - velocity[bi]),
        reached_space=bool(apogee_altitude >= KARMAN_LINE),
    )
