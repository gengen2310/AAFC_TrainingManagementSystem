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
