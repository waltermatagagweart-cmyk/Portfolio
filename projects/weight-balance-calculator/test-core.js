/*
 * test-core.js — assertion-based tests for wb-core.js.
 * Plain Node + the built-in assert module (no test framework/dependency,
 * matching the zero-library spirit of the rest of this project).
 * Run with: node test-core.js
 */
const assert = require("assert");
const { computeTotals, interpLimit, checkEnvelope } = require("./wb-core.js");

let passed = 0;
function test(name, fn) {
  try {
    fn();
    console.log("PASS " + name);
    passed++;
  } catch (err) {
    console.error("FAIL " + name);
    console.error("  " + err.message);
    process.exitCode = 1;
  }
}

const approx = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

// The example envelope used by the calculator's default aircraft profile.
// See docs/weight-balance-calculator/README.md for what these numbers do
// and do not represent.
const envelope = {
  maxWeight: 2300,
  forward: [
    { weight: 1500, arm: 82.0 },
    { weight: 1900, arm: 83.0 },
    { weight: 2300, arm: 84.5 },
  ],
  aft: [
    { weight: 1500, arm: 88.0 },
    { weight: 1900, arm: 89.5 },
    { weight: 2300, arm: 90.0 },
  ],
};

// ---- computeTotals ----

test("computeTotals: sums weight and moment correctly", () => {
  const t = computeTotals([
    { weight: 1500, arm: 85.0 },
    { weight: 340, arm: 70.0 },
  ]);
  assert.strictEqual(t.totalWeight, 1840);
  assert.strictEqual(t.totalMoment, 1500 * 85 + 340 * 70);
  assert.ok(approx(t.cg, (1500 * 85 + 340 * 70) / 1840));
});

test("computeTotals: empty station list gives zero weight and zero CG (no divide-by-zero)", () => {
  const t = computeTotals([]);
  assert.strictEqual(t.totalWeight, 0);
  assert.strictEqual(t.totalMoment, 0);
  assert.strictEqual(t.cg, 0);
});

test("computeTotals: ignores non-numeric weight/arm as zero rather than NaN", () => {
  const t = computeTotals([{ weight: "abc", arm: 50 }, { weight: 100, arm: 40 }]);
  assert.strictEqual(t.totalWeight, 100);
  assert.strictEqual(t.totalMoment, 4000);
});

// ---- interpLimit ----

test("interpLimit: exact breakpoint returns the breakpoint's arm", () => {
  assert.strictEqual(interpLimit(envelope.forward, 1900), 83.0);
});

test("interpLimit: below range clamps to the first point", () => {
  assert.strictEqual(interpLimit(envelope.forward, 100), 82.0);
});

test("interpLimit: above range clamps to the last point", () => {
  assert.strictEqual(interpLimit(envelope.forward, 9999), 84.5);
});

test("interpLimit: linear midpoint between two breakpoints", () => {
  // Halfway between (1500, 82.0) and (1900, 83.0) is weight 1700 -> arm 82.5
  assert.strictEqual(interpLimit(envelope.forward, 1700), 82.5);
});

// ---- checkEnvelope: hand-verified loading scenarios ----
// Each scenario's totalWeight/totalMoment/cg was independently confirmed
// by hand and in a throwaway scratch script before this file was written.

test("checkEnvelope: typical balanced loading is in-limits", () => {
  const stations = [
    { weight: 1500, arm: 85.0 }, // basic empty weight
    { weight: 340, arm: 70.0 }, // front seats (2 occupants)
    { weight: 170, arm: 118.0 }, // rear seat (1 occupant)
    { weight: 20, arm: 140.0 }, // baggage
    { weight: 150, arm: 95.0 }, // fuel, 25 gal @ 6 lb/gal
  ];
  const t = computeTotals(stations);
  assert.strictEqual(t.totalWeight, 2180);
  assert.strictEqual(t.totalMoment, 188410);
  assert.ok(approx(t.cg, 188410 / 2180));
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "in-limits");
  assert.ok(approx(r.forwardLimit, 84.05));
  assert.ok(approx(r.aftLimit, 89.85));
});

test("checkEnvelope: heavy front seats + empty fuel/rear/baggage is forward-of-limit", () => {
  const stations = [
    { weight: 1500, arm: 85.0 },
    { weight: 340, arm: 70.0 },
    { weight: 0, arm: 118.0 },
    { weight: 0, arm: 140.0 },
    { weight: 0, arm: 95.0 },
  ];
  const t = computeTotals(stations);
  assert.strictEqual(t.totalWeight, 1840);
  assert.strictEqual(t.totalMoment, 151300);
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "forward-of-limit");
  assert.ok(t.cg < r.forwardLimit);
});

test("checkEnvelope: heavy rear seats + baggage is aft-of-limit", () => {
  const stations = [
    { weight: 1500, arm: 85.0 },
    { weight: 170, arm: 70.0 },
    { weight: 340, arm: 118.0 },
    { weight: 80, arm: 140.0 },
    { weight: 60, arm: 95.0 },
  ];
  const t = computeTotals(stations);
  assert.strictEqual(t.totalWeight, 2150);
  assert.strictEqual(t.totalMoment, 196420);
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "aft-of-limit");
  assert.ok(t.cg > r.aftLimit);
});

test("checkEnvelope: fully loaded aircraft exceeds max gross weight", () => {
  const stations = [
    { weight: 1500, arm: 85.0 },
    { weight: 340, arm: 70.0 },
    { weight: 340, arm: 118.0 },
    { weight: 120, arm: 140.0 },
    { weight: 240, arm: 95.0 },
  ];
  const t = computeTotals(stations);
  assert.strictEqual(t.totalWeight, 2540);
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "over-max-weight");
  assert.strictEqual(r.forwardLimit, null);
});

test("checkEnvelope: CG exactly on the forward limit line counts as in-limits (boundary inclusive)", () => {
  // At weight 1900 the forward limit is exactly 83.0 -> construct a loading with that CG.
  // weight*arm total must give cg = 83.0 at totalWeight = 1900.
  const stations = [{ weight: 1900, arm: 83.0 }];
  const t = computeTotals(stations);
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "in-limits");
});

test("checkEnvelope: CG exactly on the aft limit line counts as in-limits (boundary inclusive)", () => {
  const stations = [{ weight: 1900, arm: 89.5 }];
  const t = computeTotals(stations);
  const r = checkEnvelope(envelope, t.totalWeight, t.cg);
  assert.strictEqual(r.status, "in-limits");
});

test("checkEnvelope: weight below minWeight is flagged when minWeight is set", () => {
  const withMin = Object.assign({}, envelope, { minWeight: 1600 });
  const r = checkEnvelope(withMin, 1550, 85.0);
  assert.strictEqual(r.status, "under-min-weight");
});

console.log("\n" + passed + " test(s) passed.");
if (process.exitCode) {
  console.error("Some tests FAILED.");
} else {
  console.log("All tests passed.");
}
