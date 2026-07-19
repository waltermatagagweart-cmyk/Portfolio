# 🚀 Rocket Ascent Simulator

A physics-based simulation of a rocket launch, written in Python. It integrates the
equations of motion of a vertically-launched rocket and reports the flight profile —
altitude, velocity, acceleration, and aerodynamic load — from lift-off to apogee.

**Author:** Walter Matagagwe · **Stack:** Python · NumPy · SciPy · Matplotlib

![Ascent profile](plots/ascent_profile.png)

## What it models

A real ascent is more than "thrust minus gravity." This simulator captures the three
effects that actually shape the trajectory:

1. **Variable mass** — the rocket burns propellant, so it continuously gets lighter. That's
   why acceleration *climbs* during the burn (constant thrust ÷ shrinking mass) and peaks at
   burnout, as you can see in the acceleration plot above.
2. **Altitude-dependent gravity** — gravity weakens with height following the inverse-square
   law, `g(h) = g₀ · (Rₑ / (Rₑ + h))²`.
3. **Atmospheric drag** — an exponential-atmosphere density model, `ρ(h) = ρ₀ · e^(−h/H)`,
   feeding a standard drag term `½ ρ v² C_d A`. This produces the classic **max-Q** hump —
   the point of maximum aerodynamic stress — early in the flight.

The equations of motion are integrated with **SciPy's adaptive RK45** (`solve_ivp`), and a
**terminal event** stops the run exactly at apogee (when vertical velocity reaches zero).

## The physics, briefly

The **Tsiolkovsky rocket equation** gives the ideal velocity change a rocket *could* achieve
in empty space with no losses:

```
Δv = vₑ · ln(m_wet / m_dry)      where  vₑ = Isp · g₀
```

The simulator computes this ideal Δv and then compares it to the velocity the rocket
*actually* gains — the difference is the real-world **gravity + drag losses**, which for the
demo rocket come to ~27% of the ideal Δv. That gap is exactly why launching to orbit is hard.

## Sample run

The demo (`run.py`) launches a small sub-orbital sounding rocket (2,000 kg lift-off, 80%
propellant). It prints:

```
========================================================
 ROCKET ASCENT - FLIGHT SUMMARY
========================================================
 Lift-off mass         : 2,000 kg
 Propellant            : 1,600 kg (80% of lift-off mass)
 Thrust / weight       : 2.45
 Burn time             : 81.7 s
--------------------------------------------------------
 Burnout altitude      : 77.0 km
 Burnout velocity      : 2,900 m/s (Mach 8.5)
 Apogee (max height)   : 548.2 km  at T+415 s
 Max-Q (peak load)     : 68.0 kPa  at 9.9 km
--------------------------------------------------------
 Ideal dv (Tsiolkovsky): 3,946 m/s
 Gravity + drag losses : 1,046 m/s (27% of ideal)
 Reached space (100 km): YES
========================================================
```

(The rocket crosses the 100 km Kármán line — the boundary of space — but stays sub-orbital:
a purely vertical shot has no horizontal velocity, so it falls back down instead of orbiting.)

## Run it yourself

```bash
pip install -r requirements.txt
python run.py          # prints the summary and writes plots/ascent_profile.png
pytest -q              # 11 tests
```

Change the rocket in `run.py` — thrust, propellant, Isp, diameter — and watch the whole
profile respond.

## Tests

`pytest` runs **11 tests** covering the environment models (gravity and air-density behaviour),
the rocket properties (Tsiolkovsky Δv, burn time, thrust-to-weight), and the simulation itself
(apogee above burnout, velocity ~0 at apogee, real losses below ideal Δv, mass conservation
after burnout). All passing.

## Files

| File | Purpose |
|---|---|
| `rocket_sim.py` | Core: the `Rocket` model, environment models, and the `simulate()` integrator |
| `run.py` | Demo scenario — prints the summary and generates the plot |
| `test_rocket_sim.py` | The 11-test suite |
| `plots/ascent_profile.png` | Generated four-panel ascent chart |

## Why I built it

Part of a portfolio bridging my Computer Science diploma toward aerospace. Where my
[aircraft-maintenance database](../aircraft-maintenance-db/) shows data modelling and my
[flight-telemetry dashboard](../flight-telemetry-dashboard/) shows real-time visualisation,
this one shows **numerical methods and physical modelling** — the maths behind flight.
