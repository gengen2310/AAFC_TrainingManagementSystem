import { describe, it, expect } from "vitest";
import html from "../../../connected-frontend/index.html?raw";

// Extract the body of `@media print{ ... }` by matching braces, so a rule can be
// tested for which side of it it lives on. The whole defect this file guards
// against is a rule sitting INSIDE that block when it was meant to apply on
// screen, and a plain `toContain` cannot tell the difference.
function printMediaBlock(src: string): string {
  const start = src.indexOf("@media print{");
  if (start < 0) throw new Error("@media print block not found");
  let depth = 0;
  for (let i = src.indexOf("{", start); i < src.length; i++) {
    if (src[i] === "{") depth++;
    else if (src[i] === "}") { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error("@media print block never closed");
}
const PRINT = printMediaBlock(html);
const SCREEN = html.replace(PRINT, "");

describe("the print block still owns only paper concerns", () => {
  it("keeps @page, the 8pt type and the page breaks inside @media print", () => {
    expect(PRINT).toContain("@page { size: landscape; margin: 12mm; }");
    expect(PRINT).toContain("font-size: 8pt");
    expect(PRINT).toContain("page-break-after: always");
  });
});

describe("Weekly Program is legible on screen, not only on paper", () => {
  // Nine nights rendered as one continuous unstyled table, because every rule
  // that separated them lived in @media print. The only thing dividing one
  // night from the next on screen was a 12px regular row with no background
  // and no rule above it.
  it("gives each night a banner that applies on screen", () => {
    expect(SCREEN).toContain(".night-header");
    expect(SCREEN).toMatch(/\.night-header[^}]*background:\s*#002f65/);
  });

  it("separates the nights structurally on screen", () => {
    // .print-pn-block already wraps each night for the page break; on screen it
    // has to carry the separation itself.
    expect(SCREEN).toMatch(/\.print-pn-block\{[^}]*margin-bottom/);
  });

  it("draws the table gridlines on screen", () => {
    expect(SCREEN).toMatch(/\.print-schedule-table\s+(th|td)[^{]*\{[^}]*border:/);
  });
});

describe("the night row and the phase columns are no longer the same class", () => {
  // .group-header styled both the night row (a td spanning the table) and the
  // phase column headers (th). One class doing two jobs meant neither could be
  // styled without disturbing the other.
  it("renders the night row with its own class", () => {
    expect(html).toMatch(/<td colspan="\$\{totalCols\+2\}" class="night-header"/);
  });

  it("leaves the phase column headers on group-header", () => {
    expect(html).toMatch(/<th colspan="\$\{gc\.cols\.length\}" class="group-header"/);
  });
});

describe("an empty night says so", () => {
  it("has an explicit empty state rather than a bare grid", () => {
    expect(html).toContain("No sessions planned");
  });
});
