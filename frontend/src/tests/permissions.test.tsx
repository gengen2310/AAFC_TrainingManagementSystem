import { describe, it, expect } from "vitest";
import { isNational, isWing, isAdmin, canViewCadets, canWriteSquadron } from "../auth/permissions";
import { visibleRoutes } from "../auth/roleGuards";
import type { SessionInfo } from "../api/types";

const mk = (role: string): SessionInfo => ({
  user_id: "u", display_name: "x", role, wing_id: null, squadron_id: null,
  national_id: null, is_wing: false, is_national: false,
});

describe("permission helpers", () => {
  it("classifies roles", () => {
    expect(isNational(mk("national_admin"))).toBe(true);
    expect(isWing(mk("wing_admin"))).toBe(true);
    expect(isAdmin(mk("sqn_admin"))).toBe(true);
    expect(canWriteSquadron(mk("sqn_general"))).toBe(false);
    expect(canViewCadets(mk("sqn_general"))).toBe(false);
  });
  it("gates routes by role", () => {
    expect(visibleRoutes(mk("sqn_general")).imports).toBe(false);
    expect(visibleRoutes(mk("sqn_general")).cadets).toBe(false);
    expect(visibleRoutes(mk("sqn_admin")).imports).toBe(true);
    expect(visibleRoutes(mk("wing_admin")).wingOverview).toBe(true);
    expect(visibleRoutes(mk("sqn_admin")).nationalOverview).toBe(false);
  });
});
