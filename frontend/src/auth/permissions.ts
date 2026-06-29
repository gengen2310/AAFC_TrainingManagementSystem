import type { SessionInfo } from "../api/types";
// Frontend gating only reduces confusion; the backend remains the security authority.
export const isNational = (s: SessionInfo | null) =>
  !!s && ["national_viewer", "national_admin", "system_admin", "auditor"].includes(s.role);
export const isWing = (s: SessionInfo | null) => !!s && ["wing_viewer", "wing_admin"].includes(s.role);
export const isAdmin = (s: SessionInfo | null) =>
  !!s && ["sqn_admin", "wing_admin", "national_admin", "system_admin"].includes(s.role);
export const canWriteSquadron = (s: SessionInfo | null) =>
  !!s && ["sqn_admin", "wing_admin", "national_admin", "system_admin"].includes(s.role);
export const canViewCadets = (s: SessionInfo | null) => !!s && s.role !== "sqn_general";
export const isAuditor = (s: SessionInfo | null) => !!s && s.role === "auditor";
export const isSystemAdmin = (s: SessionInfo | null) => !!s && s.role === "system_admin";
// Account Management page is visible to any admin, viewer, or auditor — just not sqn_general
export const canManageAccounts = (s: SessionInfo | null) =>
  !!s && s.role !== "sqn_general";
