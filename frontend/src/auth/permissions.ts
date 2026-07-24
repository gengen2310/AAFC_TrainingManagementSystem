import type { SessionInfo } from "../api/types";
// Frontend gating only reduces confusion; the backend remains the security authority.
export const isNational = (s: SessionInfo | null) =>
  !!s && ["national_viewer", "national_admin", "system_admin", "auditor"].includes(s.role);
export const isWing = (s: SessionInfo | null) => !!s && ["wing_viewer", "wing_admin"].includes(s.role);
export const isAdmin = (s: SessionInfo | null) =>
  !!s && ["sqn_admin", "wing_admin", "national_admin", "system_admin"].includes(s.role);
// Matches backend/app/permissions.py's require_can_write_squadron exactly: sqn_admin
// can always write its own squadron; wing_admin/national_admin/system_admin can only
// write a squadron while their Proxy/Delegated-Intervention mode is ACTIVE. Previously
// this checked role only, so a wing/national admin who hadn't yet entered proxy mode
// saw every write control (buttons, quick-status icons, dropdowns) fully enabled and
// only discovered the 403 after clicking — this is the confirmed root cause of the
// "unexplained 403 while editing" report, not a backend bug (the backend's own gate
// was already correct).
export const canWriteSquadron = (s: SessionInfo | null) => {
  if (!s) return false;
  if (s.role === "sqn_admin") return true;
  if (s.role === "wing_admin") return s.proxy?.mode === "proxy";
  if (s.role === "national_admin" || s.role === "system_admin") return s.proxy?.mode === "delegated_intervention";
  return false;
};
export const canViewCadets = (s: SessionInfo | null) => !!s && s.role !== "sqn_general";
export const isAuditor = (s: SessionInfo | null) => !!s && s.role === "auditor";
export const isSystemAdmin = (s: SessionInfo | null) => !!s && s.role === "system_admin";
// Account Management page is visible to any admin, viewer, or auditor — just not sqn_general
export const canManageAccounts = (s: SessionInfo | null) =>
  !!s && s.role !== "sqn_general";
