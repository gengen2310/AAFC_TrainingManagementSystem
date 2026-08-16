import type { SessionInfo } from "../api/types";
import { isNational, isWing, isAdmin, isAuditor } from "./permissions";
// Which sidebar routes a role should SEE (backend still enforces access).
export function visibleRoutes(s: SessionInfo | null) {
  return {
    dashboard: true, calendar: true, paradeNights: true, weeklyProgram: true,
    curriculum: true, facilitators: true, resources: true,
    cadets: !!s && s.role !== "sqn_general",
    reports: true, actionItems: true, imports: isAdmin(s),
    // audit: sqn_general must not access audit log (includes access-code reset events).
    audit: isAdmin(s) || isAuditor(s),
    admin: isAdmin(s), wingOverview: isWing(s) || isNational(s), nationalOverview: isNational(s),
  };
}
