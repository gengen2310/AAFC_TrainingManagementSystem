import { describe, it, expect } from "vitest";
import { isNational, isWing, isAdmin, canViewCadets, canWriteSquadron } from "../auth/permissions";
import { visibleRoutes } from "../auth/roleGuards";
import type { SessionInfo } from "../api/types";

const mk = (role: string, proxy?: SessionInfo["proxy"]): SessionInfo => ({
  user_id: "u", display_name: "x", role, wing_id: null, squadron_id: null,
  national_id: null, is_wing: false, is_national: false, proxy: proxy ?? null,
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
  describe("canWriteSquadron — proxy/intervention awareness (Block 7)", () => {
    it("sqn_admin can always write, no proxy needed", () => {
      expect(canWriteSquadron(mk("sqn_admin"))).toBe(true);
    });
    it("wing_admin cannot write without an active proxy session", () => {
      expect(canWriteSquadron(mk("wing_admin"))).toBe(false);
      expect(canWriteSquadron(mk("wing_admin", { mode: "delegated_intervention", acting_squadron_id: "s1", acting_wing_id: null, proxy_session_id: "p1" }))).toBe(false);
    });
    it("wing_admin can write once proxy mode is active", () => {
      expect(canWriteSquadron(mk("wing_admin", { mode: "proxy", acting_squadron_id: "s1", acting_wing_id: null, proxy_session_id: "p1" }))).toBe(true);
    });
    it("national_admin cannot write without delegated intervention", () => {
      expect(canWriteSquadron(mk("national_admin"))).toBe(false);
      expect(canWriteSquadron(mk("national_admin", { mode: "proxy", acting_squadron_id: "s1", acting_wing_id: null, proxy_session_id: "p1" }))).toBe(false);
    });
    it("national_admin can write once delegated intervention is active", () => {
      expect(canWriteSquadron(mk("national_admin", { mode: "delegated_intervention", acting_squadron_id: "s1", acting_wing_id: null, proxy_session_id: "p1" }))).toBe(true);
    });
    it("system_admin follows the same delegated-intervention rule as national_admin", () => {
      expect(canWriteSquadron(mk("system_admin"))).toBe(false);
      expect(canWriteSquadron(mk("system_admin", { mode: "delegated_intervention", acting_squadron_id: "s1", acting_wing_id: null, proxy_session_id: "p1" }))).toBe(true);
    });
    it("sqn_general and viewer roles never gain write access regardless of proxy", () => {
      expect(canWriteSquadron(mk("sqn_general"))).toBe(false);
      expect(canWriteSquadron(mk("wing_viewer"))).toBe(false);
      expect(canWriteSquadron(mk("national_viewer"))).toBe(false);
      expect(canWriteSquadron(mk("auditor"))).toBe(false);
    });
  });
});
