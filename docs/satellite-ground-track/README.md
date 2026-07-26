# Satellite Ground-Track Visualizer

A real-time two-body Keplerian orbit propagator with a live ground-track map, in a single self-contained HTML/CSS/JS file — no libraries, no build step, no network requests at runtime.

**Live demo:** [satellite-ground-track](https://waltermatagagweart-cmyk.github.io/Portfolio/projects/satellite-ground-track/)

---

## What it does

Pick a satellite (ISS, a sun-synchronous polar orbit, or geostationary), press play, and watch its ground track sweep across an equirectangular world graticule in real time — altitude, velocity, latitude/longitude, and an altitude-vs-time chart update continuously. Time can be accelerated up to 600× so a 90-minute LEO orbit or a 24-hour GEO orbit both become watchable in seconds.

This is the orbital-mechanics counterpart to the [flight-telemetry dashboard](../flight-telemetry-dashboard/README.md) — same Canvas-driven, self-contained approach, applied one level up: from an aircraft flying through the atmosphere to a satellite flying above it.

---

## The physics

Each animation frame re-solves the satellite's position from its classical orbital elements — this isn't a scripted animation, it's the same math a mission-planning tool uses:

1. **Mean anomaly** advances linearly with time: `M = M₀ + n·t`, where mean motion `n = √(μ/a³)`
2. **Kepler's equation** `M = E − e·sin(E)` is solved for eccentric anomaly `E` via Newton–Raphson
3. **True anomaly** and **radius** follow from standard conic-section relations
4. The position in the **perifocal frame** is rotated into the **Earth-Centered Inertial (ECI)** frame via the classical 3-1-3 Euler sequence (RAAN Ω, inclination i, argument of perigee ω)
5. ECI is rotated into **Earth-fixed** coordinates using Greenwich Mean Sidereal Time, accounting for Earth's sidereal rotation (`ω⊕ = 7.2921159×10⁻⁵ rad/s`)
6. Earth-fixed Cartesian coordinates convert to **latitude/longitude** (spherical Earth)
7. **Orbital velocity** comes from the vis-viva equation: `v = √(μ(2/r − 1/a))`

### Simplifications (stated honestly, not hidden)

- **Spherical Earth** (mean radius 6,371 km), not full WGS84 — fine for a visualization, wrong for a real ground-station pointing angle
- **GMST₀ = 0 at epoch** — a demo simplification; a real tool would compute GMST from the actual calendar date
- **No J2 oblateness perturbation** — real LEO orbits precess faster than this simple two-body model predicts (the ISS's actual orbital plane drifts about 4.5°/day from Earth's equatorial bulge; this model only captures the "orbit under a rotating Earth" component of that drift, not the perturbation itself)

These are the same category of trade-off as the [rocket ascent simulator](../rocket-ascent-sim/README.md)'s modeling choices — real physics, clearly scoped assumptions.

---

## Verification

Before writing a line of the visual page, the core propagator was checked against known values in a standalone Node.js script:

| Check | Computed | Expected |
|---|---|---|
| ISS orbital period | 92.41 min | ~92.68 min |
| ISS latitude range (51.6° inclination) | −51.60° to +51.60° | ±51.6° |
| ISS altitude range (near-circular) | 398.0–402.0 km | ~400 km |
| ISS orbital velocity | 7.675 km/s | ~7.66 km/s |
| GEO orbital period | 23.934 h | 23.934 h (one sidereal day) |
| GEO altitude | 35,789 km | ~35,786 km |
| Sun-sync max latitude (98.6° inclination) | 81.40° | 81.4° (= 180 − 98.6, a polar-crossing orbit) |
| ISS nodal drift per orbit | −23.17° | ~−23° westward (Earth rotating under a fixed orbital plane) |

Every check passed before the value was ever displayed on screen. The same verification-first discipline as the rocket simulator's pytest suite — just done once in Node instead of a checked-in test file, since there's no build pipeline here to run tests in.

The live page itself was also driven programmatically (stepping the simulation, switching satellite presets, sampling canvas pixel data to confirm the map actually renders, exercising the theme toggle and speed controls) with zero console errors, before shipping.

---

## Satellite presets

| Preset | Altitude | Inclination | Period | Use case |
|---|---|---|---|---|
| **ISS** | ~400 km | 51.6° | ~92.7 min | Low Earth orbit, crewed spaceflight |
| **Sun-Synchronous** | ~800 km | 98.6° | ~100.9 min | Earth observation — crosses every latitude, including the poles |
| **Geostationary** | ~35,786 km | ~0° | 23.934 h | Communications — appears fixed over one longitude |

---

## Files

- `index.html` — everything: orbital mechanics, Canvas rendering, UI, in one file. System fonts, zero network dependency at runtime.
