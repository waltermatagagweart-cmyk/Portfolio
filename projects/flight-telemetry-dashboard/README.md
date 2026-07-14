# ✈️ Flight Telemetry Dashboard

A live **glass-cockpit (EFIS) style** telemetry dashboard, built as a single self-contained
HTML/CSS/JavaScript file — **no libraries, no build step, no network**. It simulates a
Nairobi → Mombasa flight and drives a navigation display, instrument readouts, a heading
compass, and two live-updating charts.

**Author:** Walter Matagagwe · **Live:** open `index.html` in any browser.

## What it shows

- **Navigation display** — a nav map (Canvas) with the planned route, named waypoints
  (HKJK · MTITO · VOI · HKMO), range rings, a moving aircraft marker rotated to its track,
  and a fading flight trail.
- **Instrument readouts** — altitude, ground speed, heading, vertical speed, distance
  remaining, and estimated time en route, all updating live.
- **Heading compass** — a rotating compass rose with the current heading.
- **Live charts** — altitude and ground speed plotted over the flight, drawing the real
  climb → cruise → descent profile as it flies.
- **Controls** — play/pause, reset, and 1× / 2× / 4× simulation speed.
- **Light & dark themes**, and it respects `prefers-reduced-motion` (starts paused).

## How it works

A single flight model maps flight **progress (0–1)** to altitude, speed and phase (taxi →
takeoff → climb → cruise → descent → approach → landed). Position is interpolated along the
route by **arc length**, and heading is derived from the route tangent. Everything renders
on `<canvas>` at device-pixel-ratio for crisp lines, driven by `requestAnimationFrame`;
charts sample by simulated time so they trace the whole flight profile. All colours come
from CSS custom properties, so the Canvas re-themes with the page.

The data is **simulated** (fake) by design — the point is the real-time visualisation and
instrument UI, the kind used in ground-control and avionics software.

> Nice detail: it flies **5Y-DHC (DHC-8-400)** — the same aircraft that appears in my
> [Aircraft Maintenance Database](../aircraft-maintenance-db/) project.

## Tech

`HTML` · `CSS` · `JavaScript (ES6)` · `Canvas 2D` · `requestAnimationFrame` — zero dependencies.
