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

describe("button classes consume the scale", () => {
  it(".btn uses --ctl-h, not a literal height", () => {
    const rule = html.slice(html.indexOf(".btn{"), html.indexOf(".btn{") + 400);
    expect(rule).toContain("min-height:var(--ctl-h)");
    expect(rule).not.toContain("min-height:28px");
  });

  it(".btn-xs keeps both axes at the floor -- a visual variant, not a smaller target", () => {
    const rule = html.slice(html.indexOf(".btn-xs{"), html.indexOf(".btn-xs{") + 260);
    expect(rule).toContain("min-height:var(--ctl-min)");
    expect(rule).toContain("min-width:var(--ctl-min)");
  });
});

describe("fields sit at the larger height", () => {
  it("bare inputs, selects and textareas use --ctl-h-lg", () => {
    const i = html.indexOf("input[type=date],input[type=search]");
    expect(html.slice(i, i + 220)).toContain("min-height:var(--ctl-h-lg)");
  });

  it("checkbox and radio keep an 18px box -- the box is not the target", () => {
    expect(html).toContain("input[type=checkbox],input[type=radio]{width:18px;height:18px;}");
  });
});
