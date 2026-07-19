"""
Tests for the rocket ascent simulator.  Run with:  pytest -q
"""
import math

import numpy as np

from rocket_sim import (
    Rocket, simulate, gravity, air_density, G0, RHO0, R_EARTH,
)


def sample_rocket():
    return Rocket(dry_mass=400.0, propellant_mass=1600.0, thrust=48_000.0,
                  isp=250.0, diameter=0.6)


# ---- environment models -----------------------------------------------------
def test_gravity_at_sea_level():
    assert gravity(0.0) == G0

def test_gravity_decreases_with_altitude():
    assert gravity(100_000) < gravity(0)
    # at one Earth radius up, gravity should be a quarter of surface value
    assert gravity(R_EARTH) == G0 / 4

def test_air_density_sea_level_and_decay():
    assert air_density(0.0) == RHO0
    assert air_density(8500.0) == RHO0 * math.exp(-1)   # one scale height
    assert air_density(50_000) < air_density(10_000)


# ---- rocket properties ------------------------------------------------------
def test_tsiolkovsky_delta_v():
    r = sample_rocket()
    expected = r.isp * G0 * math.log(r.wet_mass / r.dry_mass)
    assert math.isclose(r.ideal_delta_v, expected, rel_tol=1e-12)

def test_burn_time_matches_mass_flow():
    r = sample_rocket()
    # burning propellant at mdot for burn_time must consume exactly the propellant
    assert math.isclose(r.mass_flow_rate * r.burn_time, r.propellant_mass, rel_tol=1e-12)

def test_liftoff_thrust_exceeds_weight():
    # a rocket that can't beat its own weight never leaves the pad
    r = sample_rocket()
    assert r.thrust > r.wet_mass * G0


# ---- simulation -------------------------------------------------------------
def test_apogee_above_burnout():
    res = simulate(sample_rocket())
    assert res.apogee_altitude > res.burnout_altitude > 0

def test_apogee_velocity_near_zero():
    res = simulate(sample_rocket())
    # the run terminates at apogee, so the final velocity should be ~0
    assert abs(res.velocity[-1]) < 1.0

def test_real_losses_reduce_velocity():
    # actual burnout velocity must be LESS than the ideal (loss-free) delta-v,
    # because gravity and drag steal momentum during the climb
    res = simulate(sample_rocket())
    assert 0 < res.burnout_velocity < res.ideal_delta_v
    assert res.losses > 0

def test_mass_conserved_after_burnout():
    r = sample_rocket()
    res = simulate(r)
    # once the propellant is gone, mass holds at the dry mass
    assert math.isclose(res.mass[-1], r.dry_mass, rel_tol=1e-3)

def test_altitude_monotonic_until_apogee():
    res = simulate(sample_rocket())
    # on a purely vertical ascent, height never decreases before apogee
    assert np.all(np.diff(res.altitude) >= -1e-6)
