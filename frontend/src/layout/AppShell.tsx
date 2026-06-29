import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { visibleRoutes } from "../auth/roleGuards";
import { isWing, isNational, isAuditor, isAdmin, isSystemAdmin, canManageAccounts } from "../auth/permissions";
import { ProxyControls } from "./ProxyControls";
import { useProxyGuard } from "../auth/useProxyGuard";

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
            <NavItem to="/dashboard" label="Dashboard" />
            <NavItem to="/calendar" label="Calendar" />
            <NavItem to="/parade-nights" label="Parade Nights" />
            <NavItem to="/weekly-program" label="Weekly Program" />
            <NavItem to="/curriculum" label="Curriculum" />
            <div className="nav-group">Capability</div>
            <NavItem to="/facilitators" label="Facilitators" />
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

          {/* WING — assurance & comparison first; squadron editing only via Proxy Mode */}
          {wing && <>
            <div className="nav-group">Wing Assurance</div>
            <NavItem to="/wing-overview" label="Wing Dashboard" />
            <NavItem to="/reports" label="Reports" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/action-items" label="Action Items" />
            <NavItem to="/audit" label="Audit" />
            <NavItem to="/accounts" label="Account Management" />
            <div className="nav-group">Squadron support</div>
            <NavItem to="/dashboard" label="Squadron Drill-down" />
            <ProxyControls kind="proxy" />
          </>}

          {/* NATIONAL — cross-wing assurance; squadron editing only via Intervention */}
          {national && <>
            <div className="nav-group">National Assurance</div>
            <NavItem to="/national-overview" label="National Dashboard" />
            <NavItem to="/wing-overview" label="Wing Drill-down" />
            <NavItem to="/reports" label="Reports" />
            <NavItem to="/report-catalogue" label="Report Catalogue" />
            <NavItem to="/action-items" label="Action Items" />
            <NavItem to="/audit" label="Audit" />
            {canManageAccounts(session) && <NavItem to="/accounts" label="Account Management" />}
            {(session?.role === "national_admin" || isSystemAdmin(session)) &&
              <><div className="nav-group">Intervention</div><ProxyControls kind="intervention" /></>}
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
        </nav>
        <main id="main" className="main" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
function NavItem({ to, label }: { to: string; label: string }) {
  return <NavLink to={to} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>{label}</NavLink>;
}
