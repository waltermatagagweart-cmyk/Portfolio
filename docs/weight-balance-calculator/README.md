# Weight & Balance / CG Calculator

A single-file HTML/JS tool that computes an aircraft's center of gravity from its loaded stations and checks it against a certified CG envelope — no libraries, no build step, no network requests at runtime.

**Live demo:** [weight-balance-calculator](https://waltermatagagweart-cmyk.github.io/Portfolio/projects/weight-balance-calculator/)

---

## What it does

Enter (or pick a preset scenario for) the weight at each loading station — basic empty weight, front seats, rear seats, baggage, fuel — and the tool computes the total weight, total moment, and resulting CG arm, then checks that CG against the aircraft's certified envelope at that weight. A status banner says plainly whether the loading is within limits and, if not, which limit it violates (forward, aft, or over max gross weight). An envelope chart plots the shaded certified region with the current loading marked as a dot, and a separate check flags baggage that exceeds its placarded structural limit — independent of the CG calculation, exactly as it works in a real POH.

This is the practical-operations counterpart to the [aircraft maintenance database](../aircraft-maintenance-db/README.md) and [maintenance API](../aircraft-maintenance-api/README.md) — same aviation-MRO/ops theme, but a tool a pilot or dispatcher would actually use before a flight rather than a maintenance record system.

---

## The method

Standard FAA weight & balance procedure, from the **FAA Aircraft Weight and Balance Handbook (FAA-H-8083-1)**:

1. **Moment** = weight × arm, for every station (arm = distance from a fixed reference datum)
2. **CG arm** = (Σ moment) / (Σ weight)
3. The **certified envelope** is a forward limit line and an aft limit line, each defined as a handful of (weight, arm) breakpoints from the type's POH loading chart. At any given weight, the allowed CG range is found by linearly interpolating between the two breakpoints bracketing that weight — exactly how a pilot reads a paper loading chart.
4. A loading is **in limits** when the total weight is at or under the max gross weight *and* the CG arm falls on or between the forward and aft limits at that weight (the boundary itself counts as in limits, matching how "at the limit" is treated in practice).

The core math (`computeTotals`, `interpLimit`, `checkEnvelope`) lives in `wb-core.js`, kept separate from the page's DOM code specifically so it can be required and tested directly under Node — see Verification below.

---

## Assumptions and limitations (stated honestly, not hidden)

- **The example aircraft is illustrative, not real POH data.** The station arms (basic empty weight 85.0 in, front seats 70.0 in, rear seats 118.0 in, baggage 140.0 in, fuel 95.0 in), the max gross weight (2,300 lb), and the envelope breakpoints are loosely modeled on the general shape of a typical 4-seat single-engine trainer's loading chart — invented for this demo so the calculation could be exercised and verified, **not** a reproduction of any specific type's certified type-certificate data sheet or POH. Real flight dispatch must use the actual airframe's own current weight-and-balance data.
- **Fuel is a single station with a fixed arm**, entered directly as total weight (≈6 lb/US gallon for avgas; Jet A is closer to 6.7–6.8 lb/gal — the tool doesn't do the gallon→pound conversion itself, by design, so it isn't silently wrong for the wrong fuel type). Real aircraft with multiple tanks can see a small CG shift as fuel burns unevenly between tanks; this tool treats fuel as one lumped station, the same simplification most single-tank/simple-system POHs make.
- **The envelope is piecewise-linear between chart breakpoints.** A real POH envelope can have curved or additional stepped boundaries between the points actually published; this tool would miss a boundary detail that falls strictly between two breakpoints and isn't a straight line in reality.
- **This checks the loading as entered, once.** A full flight-planning tool would also re-check the envelope at the estimated landing weight, since burning fuel shifts both total weight and CG. This calculator doesn't project that — it's a snapshot check, not a full flight envelope analysis.
- **Weights below the chart's lowest breakpoint or above its highest are clamped** to the nearest end of the chart rather than extrapolated — a real aircraft's envelope simply doesn't extend past what's published, so clamping (and not silently extrapolating a line past where it's certified) is the honest behavior.

---

## Verification

The underlying arithmetic (weighted sum → CG, piecewise-linear interpolation, boundary comparisons) is simple enough to verify by hand rather than needing an external literature cross-check the way the rocket sim or airfoil analyzer's physics did. Even so, the same discipline was followed: **before writing the final page**, a throwaway Node script computed four hand-checked loading scenarios and confirmed the algorithm's output matched hand arithmetic exactly, then was deleted once confirmed.

Those four scenarios became the persisted, real test suite in `test-core.js` (run with `node test-core.js` — no dependency, just Node's built-in `assert`):

| Scenario | Total weight | CG arm | Envelope at that weight | Result |
|---|---|---|---|---|
| Typical loading | 2,180 lb | 86.43 in | 84.05–89.85 in | **In limits** |
| Heavy front seats, empty rear/baggage/fuel | 1,840 lb | 82.23 in | 82.85–89.28 in | **Forward of limit** |
| Heavy rear seats + baggage | 2,150 lb | 91.36 in | 83.94–89.81 in | **Aft of limit** |
| Full seats + full baggage + full fuel | 2,540 lb | — | max gross 2,300 lb | **Over max gross weight** |

14 tests in total, also covering: empty-station-list (no divide-by-zero), non-numeric input handled as zero, exact-breakpoint interpolation, clamping above/below the chart's range, and CG landing *exactly* on a limit line counting as in-limits (boundary inclusive) in both directions.

The live page itself was also driven directly (not just "loads without exceptions"): served locally, each of the four scenario buttons clicked and the resulting weight/CG/status banner read back and checked against the table above, a manual station-weight edit exercised to confirm live recalculation, the baggage-placard warning triggered by entering baggage over 120 lb, the theme toggle exercised, and the envelope SVG chart's rendered polygon and CG-marker coordinates read back to confirm it draws real geometry rather than an empty shape. Zero console errors throughout.

---

## Files

- `index.html` — UI: station table, live totals, status banner, SVG envelope chart, theme toggle. Loads `wb-core.js` as a plain local `<script>` — no CDN, no framework.
- `wb-core.js` — pure calculation functions (`computeTotals`, `interpLimit`, `checkEnvelope`), written with no DOM dependency specifically so it works both in the browser and under Node.
- `test-core.js` — 14 assertions against `wb-core.js`, run with `node test-core.js`.
