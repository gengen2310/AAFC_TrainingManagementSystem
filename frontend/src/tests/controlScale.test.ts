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

describe("the remaining control classes", () => {
  for (const [cls, token] of [["tb-btn", "--ctl-min"], ["tab-btn", "--ctl-h"],
                              ["lh-btn", "--ctl-min"], ["btn-lnk", "--ctl-min"]] as const) {
    it(`.${cls} consumes ${token} and keeps no literal fallback`, () => {
      const i = html.indexOf(`.${cls}{`);
      expect(i, `.${cls} rule not found`).toBeGreaterThan(-1);
      const rule = html.slice(i, html.indexOf("}", i));
      expect(rule).toContain(`min-height:var(${token})`);
      // A rule may declare min-height twice; the LAST one wins. .btn-lnk carried
      // a trailing min-height:28px that silently beat the token, and an
      // assertion that only checked the token was present did not catch it.
      expect(rule).not.toContain("min-height:28px");
      expect(rule).not.toContain("min-width:28px");
    });
  }
});

describe("adjacent targets are separated", () => {
  it("declares .ctl-group with --ctl-gap", () => {
    // NOTE ON WHY THIS EXISTS. The original justification was 23 controls that
    // measured large enough and still failed the hit probe. That was at 28px,
    // where a probe reaching +-21px from centre lands OUTSIDE the box and onto
    // the neighbour. At 44px it lands inside, and the lab now passes flush
    // buttons without any gap.
    //
    // The rule is kept as design judgement, not as a gate result: a finger's
    // contact patch is wider than a 1px probe, and Apple treats spacing between
    // targets as a separate concern from target size.
    expect(html).toContain(".ctl-group{display:inline-flex;gap:var(--ctl-gap);");
  });
});

describe("border contrast", () => {
  it("--border meets WCAG 1.4.11 at 3:1", () => {
    // #7d8ea8 measures 3.33:1 on #ffffff and 3.12:1 on --bg #f4f8fc -- the first
    // candidate clearing 3:1 against BOTH surfaces the app paints on.
    expect(html).toContain("--border:       #7d8ea8;");
  });

  it("--border-light is left alone -- decoration is outside 1.4.11", () => {
    // 1.4.11 covers information identifying components and states, not
    // decorative graphics. Darkening hairline dividers would be styling.
    expect(html).toContain("--border-light: #e4edf5;");
  });
});
