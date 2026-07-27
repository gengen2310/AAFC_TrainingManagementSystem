import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { visibleRoutes } from "../auth/roleGuards";
import { isWing, isNational, isAuditor, isAdmin, isSystemAdmin, canManageAccounts } from "../auth/permissions";
import { ProxyControls } from "./ProxyControls";
import { useProxyGuard } from "../auth/useProxyGuard";
import { SquadronSelector } from "./SquadronSelector";

const TMS_URL =
  (document.querySelector('meta[name="aafc-tms-base"]') as HTMLMetaElement | null)
    ?.content || "https://aafc-tms-frontend-production.up.railway.app";

const THEMES = ["light", "dark", "hc"] as const;
type Theme = typeof THEMES[number];

export function AppShell({ children }: { children: ReactNode }) {
  useProxyGuard();
  const { session, logout } = useAuth();
  const [theme, setTheme] = useState<Theme>((localStorage.getItem("aafc_theme") as Theme) || "light");
  const applyTheme = (t: Theme) => { setTheme(t); localStorage.setItem("aafc_theme", t); document.documentElement.dataset.theme = t; };
  document.documentElement.dataset.theme = theme;
  const r = visibleRoutes(session);
  const proxy = session?.proxy;
  const wing = isWing(session), national = isNational(session), auditor = isAuditor(session);
  const squadron = !wing && !national && !auditor;
  const scope = auditor ? "Auditor · read-only" : national ? "National HQ" : wing ? "Wing HQ" : "Squadron";

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">AAFC · Training Management System</span>
        <div className="right">
          <span className="scope-pill">{scope}</span>
          <span className="role-pill">{session?.role}</span>
          <button className="btn out sm light" onClick={() => applyTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])}
            aria-label={`Theme, currently ${theme}`}>Theme: {theme}</button>
          <button className="btn out sm light" onClick={logout}>Sign out</button>
        </div>
      </header>

      {proxy && (
        <div className={`banner ${proxy.mode === "proxy" ? "proxy" : "intervention"}`} role="status" aria-live="polite">
          {proxy.mode === "proxy" ? "⚠ PROXY MODE ACTIVE" : "⚠ DELEGATED INTERVENTION ACTIVE"} —
          acting on squadron {proxy.acting_squadron_id}. All actions are audited.
        </div>
      )}

      <div className="body">
        <nav className="sidenav" aria-label="Main navigation">
          {/* SQUADRON — full operational workspace */}
          {squadron && <>
            <div className="nav-group">Operations</div>
            <NavItem to="/planning" label="Planning Workspace" />
            <NavItem to="/dashboard" label="Dashboard" />
            <NavItem to="/calendar" label="Calendar" />
            <NavItem to="/parade-nights" label="Parade Nights" />
            <NavItem to="/weekly-program" label="Weekly Program" />
            <NavItem to="/curriculum" label="Curriculum" />
            <div className="nav-group">Capability</div>
            <NavItem to="/facilitators" label="Facilitators" />
            <NavItem to="/facilitator-schedule" label="Facilitator Schedule" />
            <NavItem to="/resources" label="Resources" />
            {r.cadets && <NavItem to="/cadets" label="Cadets" />}
            <div className="nav-group">Assurance</div>
            <NavItem to="/reports" label="Reports" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/action-items" label="Action Items" />
            {r.imports && <NavItem to="/imports" label="Imports" />}
            <NavItem to="/audit" label="Audit" />
            {isAdmin(session) && <><div className="nav-group">Admin</div>
              <NavItem to="/accounts" label="Account Management" />
              <NavItem to="/admin" label="Admin / Settings" /></>}
          </>}

          {/* WING — retains the full Squadron function set (master transformation plan
              Block 8: "Wing users must retain the relevant Squadron pages/functions,
              then receive additional scope/analytics/governance capability" — not a
              separate, reduced page set). Viewing any squadron's pages below uses the
              Squadron selector and needs no Proxy Mode (viewing is broad by design);
              writing to that squadron still requires entering Proxy Mode. */}
          {wing && <>
            <div className="nav-group">Wing Assurance</div>
            <NavItem to="/wing-overview" label="Wing Dashboard" />
            <NavItem to="/reports" label="Reports" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/action-items" label="Action Items" />
            <NavItem to="/audit" label="Audit" />
            <NavItem to="/accounts" label="Account Management" />
            <div className="nav-group">Squadron Functions</div>
            <SquadronSelector />
            <NavItem to="/dashboard" label="Dashboard" />
            <NavItem to="/calendar" label="Calendar" />
            <NavItem to="/parade-nights" label="Parade Nights" />
            <NavItem to="/weekly-program" label="Weekly Program" />
            <NavItem to="/curriculum" label="Curriculum" />
            <NavItem to="/facilitators" label="Facilitators" />
            <NavItem to="/facilitator-schedule" label="Facilitator Schedule" />
            <NavItem to="/resources" label="Resources" />
            <NavItem to="/planning" label="Planning Workspace" />
            <div className="nav-group">Proxy Mode (required to edit a squadron)</div>
            <ProxyControls kind="proxy" />
          </>}

          {/* NATIONAL — cross-wing assurance; squadron editing only via Intervention.
              isNational() also returns true for the auditor role (matching the backend's
              NATIONAL_LEVEL grouping in permissions.py, which is correct for view-scope
              purposes elsewhere in the app) — excluded here so auditor sessions render only
              their own dedicated nav block below, not both. */}
          {national && !auditor && <>
            <div className="nav-group">National Assurance</div>
            <NavItem to="/national-overview" label="National Dashboard" />
            <NavItem to="/wing-overview" label="Wing Drill-down" />
            <NavItem to="/reports" label="Reports" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/action-items" label="Action Items" />
            <NavItem to="/audit" label="Audit" />
            {canManageAccounts(session) && <NavItem to="/accounts" label="Account Management" />}
            <div className="nav-group">Squadron Functions</div>
            <SquadronSelector />
            <NavItem to="/dashboard" label="Dashboard" />
            <NavItem to="/calendar" label="Calendar" />
            <NavItem to="/parade-nights" label="Parade Nights" />
            <NavItem to="/weekly-program" label="Weekly Program" />
            <NavItem to="/curriculum" label="Curriculum" />
            <NavItem to="/facilitators" label="Facilitators" />
            <NavItem to="/facilitator-schedule" label="Facilitator Schedule" />
            <NavItem to="/resources" label="Resources" />
            <NavItem to="/planning" label="Planning Workspace" />
            {(session?.role === "national_admin" || isSystemAdmin(session)) &&
              <><div className="nav-group">Intervention (required to edit a squadron)</div><ProxyControls kind="intervention" /></>}
            {isSystemAdmin(session) && <><div className="nav-group">System</div>
              <NavItem to="/admin" label="Admin / Settings" /></>}
          </>}

          {/* AUDITOR — read-only assurance, no write tools */}
          {auditor && <>
            <div className="nav-group">Audit</div>
            <NavItem to="/audit" label="Audit Log" />
            <NavItem to="/reports" label="Reports (read-only)" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/accounts" label="Account Management" />
          </>}

          {/* Account — visible to every authenticated user */}
          <div className="nav-group">Account</div>
          <NavItem to="/settings" label="Access Codes" />
          <a href={TMS_URL} className="nav-item nav-item-ext" rel="noopener noreferrer">&#8592; Main TMS</a>
        </nav>
        <main id="main" className="main" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
function NavItem({ to, label }: { to: string; label: string }) {
  return <NavLink to={to} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>{label}</NavLink>;
}
