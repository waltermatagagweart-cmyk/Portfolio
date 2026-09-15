/*
 * wb-core.js — Aircraft Weight & Balance / CG core math.
 * Pure functions, no DOM. Loaded by index.html as a plain <script>, and
 * required directly by test-core.js under Node for automated testing.
 *
 * Method: standard FAA Weight & Balance procedure (FAA-H-8083-1,
 * "Aircraft Weight and Balance Handbook") —
 *   moment = weight x arm
 *   CG arm = (sum of moments) / (sum of weights)
 * The certified envelope is a set of forward/aft limit lines, each a
 * piecewise-linear function of gross weight (exactly how a POH loading
 * chart is read) — the loading is "in limits" if the CG arm falls on or
 * between the forward and aft limit at that weight, and the weight itself
 * is at or under the max gross weight.
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) {
    module.exports = factory();
  } else {
    root.WB = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /**
   * @param {Array<{weight:number, arm:number}>} stations
   * @returns {{totalWeight:number, totalMoment:number, cg:number}}
   */
  function computeTotals(stations) {
    let totalWeight = 0;
    let totalMoment = 0;
    for (const s of stations) {
      const w = Number(s.weight) || 0;
      const a = Number(s.arm) || 0;
      totalWeight += w;
      totalMoment += w * a;
    }
    const cg = totalWeight > 0 ? totalMoment / totalWeight : 0;
    return { totalWeight, totalMoment, cg };
  }

  /**
   * Piecewise-linear interpolation of a limit-arm curve at a given weight.
   * Points must be sorted ascending by weight. Weights outside the chart's
   * range are clamped to the nearest end point (the chart simply doesn't
   * extend further — this is a modeling limitation, not extrapolation).
   * @param {Array<{weight:number, arm:number}>} points
   * @param {number} weight
   * @returns {number}
   */
  function interpLimit(points, weight) {
    if (!points || points.length === 0) return NaN;
    if (points.length === 1) return points[0].arm;
    if (weight <= points[0].weight) return points[0].arm;
    const last = points[points.length - 1];
    if (weight >= last.weight) return last.arm;
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      if (weight >= a.weight && weight <= b.weight) {
        const frac = (weight - a.weight) / (b.weight - a.weight);
        return a.arm + frac * (b.arm - a.arm);
      }
    }
    return last.arm;
  }

  /**
   * @param {{maxWeight:number, minWeight?:number, forward:Array, aft:Array}} envelope
   * @param {number} totalWeight
   * @param {number} cg
   * @returns {{status:string, message:string, forwardLimit:number|null, aftLimit:number|null}}
   */
  function checkEnvelope(envelope, totalWeight, cg) {
    if (envelope.maxWeight != null && totalWeight > envelope.maxWeight) {
      return {
        status: "over-max-weight",
        message:
          "Total weight " +
          totalWeight.toFixed(1) +
          " lb exceeds max gross weight of " +
          envelope.maxWeight.toFixed(1) +
          " lb.",
        forwardLimit: null,
        aftLimit: null,
      };
    }
    if (envelope.minWeight != null && totalWeight < envelope.minWeight) {
      return {
        status: "under-min-weight",
        message:
          "Total weight " +
          totalWeight.toFixed(1) +
          " lb is below the chart's minimum weight of " +
          envelope.minWeight.toFixed(1) +
          " lb.",
        forwardLimit: null,
        aftLimit: null,
      };
    }
    const fwd = interpLimit(envelope.forward, totalWeight);
    const aft = interpLimit(envelope.aft, totalWeight);
    if (cg < fwd) {
      return {
        status: "forward-of-limit",
        message:
          "CG at " +
          cg.toFixed(2) +
          " in is forward of the limit (" +
          fwd.toFixed(2) +
          " in) at this weight.",
        forwardLimit: fwd,
        aftLimit: aft,
      };
    }
    if (cg > aft) {
      return {
        status: "aft-of-limit",
        message:
          "CG at " +
          cg.toFixed(2) +
          " in is aft of the limit (" +
          aft.toFixed(2) +
          " in) at this weight.",
        forwardLimit: fwd,
        aftLimit: aft,
      };
    }
    return {
      status: "in-limits",
      message: "Within the certified CG envelope.",
      forwardLimit: fwd,
      aftLimit: aft,
    };
  }

  return { computeTotals, interpLimit, checkEnvelope };
});
