import { describe, it, expect } from "vitest";
import html from "../../../connected-frontend/index.html?raw";

// The control scale is CSS in a single-file SPA, so the cheap, fast guard is a
// text assertion on the stylesheet. It cannot prove a rendered height -- that is
// tools/design-audit/lab-gates.mjs -- but it catches a token being renamed,
// deleted, or quietly given a different value, which is how a scale drifts.
describe("control scale tokens", () => {
  it("declares the six control tokens with their agreed values", () => {
    expect(html).toContain("--ctl-min:       44px");
    expect(html).toContain("--ctl-h:         44px");
    expect(html).toContain("--ctl-h-lg:      52px");
    expect(html).toContain("--ctl-pad-x:     16px");
    expect(html).toContain("--ctl-pad-x-sm:  12px");
    expect(html).toContain("--ctl-gap:        8px");
  });
});

import lab from "../../../connected-frontend/component-lab.html?raw";

describe("component lab", () => {
  it("pulls the SPA's own style block rather than copying it", () => {
    // A copied stylesheet drifts silently. Fetching index.html and injecting its
    // <style> means drift shows up as a visibly broken lab instead.
    expect(lab).toContain('fetch("index.html")');
    expect(lab).not.toContain("--ctl-min:");   // no token may be redeclared here
  });

  it("renders every control class the scale governs", () => {
    // The attributes are applied via setAttribute at runtime, so assert on the
    // CLASSES table that drives them rather than on rendered markup. Only the
    // adjacency block carries literal data-lab-* attributes.
    for (const cls of ["btn", "btn-sm", "btn-xs", "tb-btn", "tab-btn",
                       "lh-btn", "btn-lnk", "ff-ro", "input", "select"]) {
      expect(lab).toContain(`cls: "${cls}"`);
    }
    expect(lab).toContain('ctl.setAttribute("data-lab-class", spec.cls)');
  });

  it("covers the states that were never measured on a live screen", () => {
    expect(lab).toContain(
      'const STATES  = ["resting", "hover", "focus", "disabled", "active"];');
    expect(lab).toContain('ctl.setAttribute("data-lab-state", state)');
  });

  it("exercises long labels, which is where a fixed height clips", () => {
    expect(lab).toContain('long: "A considerably longer control label than usual"');
  });
});
