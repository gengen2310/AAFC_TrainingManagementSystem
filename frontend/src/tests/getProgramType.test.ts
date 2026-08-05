import { describe, it, expect } from "vitest";
import { getProgramType } from "../utils/planningFilters";

// Foundation/Extension/Optional must derive from the phase letter prefix,
// not the ambiguous CurriculumItem.core_status field (core|additional) --
// previously every "additional" item fell through to "Extension" regardless
// of its actual phase.
describe("getProgramType", () => {
  it("classifies A-E phases (Orientation..Senior) as foundation", () => {
    expect(getProgramType("A. Orientation")).toBe("foundation");
    expect(getProgramType("B. Initial")).toBe("foundation");
    expect(getProgramType("C. Junior")).toBe("foundation");
    expect(getProgramType("D. Intermediate")).toBe("foundation");
    expect(getProgramType("E. Senior")).toBe("foundation");
  });

  it("classifies I/J/K phases (Bronze/Silver/Gold) as extension", () => {
    expect(getProgramType("I. Bronze")).toBe("extension");
    expect(getProgramType("J. Silver")).toBe("extension");
    expect(getProgramType("K. Gold")).toBe("extension");
  });

  it("classifies a custom/unrecognised phase as optional", () => {
    expect(getProgramType("Z. Custom Squadron Phase")).toBe("optional");
    expect(getProgramType("")).toBe("optional");
    expect(getProgramType(null)).toBe("optional");
    expect(getProgramType(undefined)).toBe("optional");
  });
});
