import { Component, type ReactNode } from "react";
import { BrowserRouter, HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { SquadronViewProvider } from "./layout/SquadronViewContext";
import { isNational, isWing, isAuditor } from "./auth/permissions";
import { Dashboard } from "./routes/Dashboard";
import { Calendar } from "./routes/Calendar";
import { ParadeNights } from "./routes/ParadeNights";
import { WeeklyProgram } from "./routes/WeeklyProgram";
import { Curriculum } from "./routes/Curriculum";
import { Facilitators } from "./routes/Facilitators";
import { FacilitatorSchedule } from "./routes/FacilitatorSchedule";
import { Resources } from "./routes/Resources";
import { Cadets } from "./routes/Cadets";
import { Reports } from "./routes/Reports";
import { ActionItems } from "./routes/ActionItems";
import { Imports } from "./routes/Imports";
import { Audit } from "./routes/Audit";
import { Admin } from "./routes/Admin";
import { Accounts } from "./routes/Accounts";
import { Settings } from "./routes/Settings";
import { ReportCatalogue } from "./routes/ReportCatalogue";
import { WingOverview, NationalOverview } from "./routes/Overviews";
import { PlanningWorkspace } from "./routes/PlanningWorkspace";
import { ErrorBoundary } from "./components/ErrorBoundary";

// refetchOnWindowFocus/refetchOnReconnect: stale data (e.g. a Parade Night
// edited in the other frontend, or in another tab) should surface when the
// user comes back to this tab or the network returns, not require a manual
// reload -- matches the same freshness expectation Main TMS's own page
// Refresh buttons are built to satisfy.
const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: true, refetchOnReconnect: true } } });

const USE_HASH = import.meta.env.VITE_HASH_ROUTER === "true";
const BASENAME = USE_HASH ? "/" : (import.meta.env.BASE_URL || "/").replace(/\/$/, "") || "/";

const TMS_URL =
  (document.querySelector('meta[name="aafc-tms-base"]') as HTMLMetaElement | null)
    ?.content || "https://aafc-tms-frontend-production.up.railway.app";
const MODULE_MODE =
  (document.querySelector('meta[name="aafc-module-mode"]') as HTMLMetaElement | null)
    ?.content === "true";

// ── Module mode ───────────────────────────────────────────────────────────────
// Used when this app is opened as a standalone Planning Workspace preview tab
// (launched from the connected-frontend). AppShell is intentionally skipped so
// the full TMS layout/nav does not render. Auth comes from the shared backend
// session cookie (SameSite=None; Secure) — no login form is shown.

function NotAuthenticated() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f4f8fc" }}>
      <div style={{ background: "white", border: "1px solid #d1dce8", borderRadius: 10, padding: "36px 40px", maxWidth: 420, textAlign: "center", boxShadow: "0 4px 16px rgba(0,47,101,.10)" }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>🔒</div>
        <h1 style={{ fontSize: 17, fontWeight: 700, color: "#002f65", marginBottom: 10 }}>Session not found</h1>
        <p style={{ fontSize: 13, color: "#455560", lineHeight: 1.6, marginBottom: 24 }}>
          Please return to the Training Management System and log in first.
          Planning Workspace uses your existing TMS session.
        </p>
        <a href={TMS_URL} style={{ display: "inline-block", background: "#51b0e3", color: "white", fontWeight: 700, fontSize: 13, padding: "10px 24px", borderRadius: 6, textDecoration: "none" }}>
          Return to TMS
        </a>
      </div>
    </div>
  );
}

function ModuleLoading() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f4f8fc" }}>
      <div style={{ textAlign: "center", color: "#455560" }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Loading Planning Workspace…</div>
      </div>
    </div>
  );
}

function ModuleError({ onRetry }: { onRetry: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f4f8fc" }}>
      <div style={{ background: "white", border: "1px solid #d1dce8", borderRadius: 10, padding: "36px 40px", maxWidth: 480, textAlign: "center", boxShadow: "0 4px 16px rgba(0,47,101,.10)" }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⚠️</div>
        <h1 style={{ fontSize: 17, fontWeight: 700, color: "#002f65", marginBottom: 10 }}>Planning Workspace could not load</h1>
        <p style={{ fontSize: 13, color: "#455560", lineHeight: 1.6, marginBottom: 24 }}>
          The system could not load planning data. If this keeps happening, contact support.
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={onRetry} style={{ background: "#51b0e3", color: "white", fontWeight: 700, fontSize: 13, padding: "10px 20px", borderRadius: 6, border: 0, cursor: "pointer" }}>
            Retry
          </button>
          <a href={TMS_URL} style={{ display: "inline-block", background: "white", color: "#455560", fontWeight: 600, fontSize: 13, padding: "10px 20px", borderRadius: 6, textDecoration: "none", border: "1px solid #d1dce8" }}>
            Return to TMS
          </a>
        </div>
      </div>
    </div>
  );
}

class ModuleErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false };
  // WRITE-04: getDerivedStateFromError has no access to componentStack, so the
  // full error (message + stack) is logged here in componentDidCatch for
  // debugging -- the UI itself must never show operational users a raw JS
  // exception message (e.g. "Cannot read properties of undefined"), which is
  // what this previously rendered verbatim in a monospace <p>.
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error("[ModuleErrorBoundary]", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return <ModuleError onRetry={() => { this.setState({ hasError: false }); window.location.reload(); }} />;
    }
    return this.props.children;
  }
}

function ModuleEntry() {
  const { session, loading } = useAuth();
  if (loading) return <ModuleLoading />;
  if (!session) return <NotAuthenticated />;
  return (
    <ModuleErrorBoundary>
      <SquadronViewProvider>
        <Routes>
          <Route path="/planning" element={<PlanningWorkspace />} />
          <Route path="*" element={<Navigate to="/planning" replace />} />
        </Routes>
      </SquadronViewProvider>
    </ModuleErrorBoundary>
  );
}

// ── Normal full-app mode ──────────────────────────────────────────────────────

function Home() {
  const { session } = useAuth();
  if (isAuditor(session)) return <Navigate to="/audit" replace />;
  if (isNational(session)) return <Navigate to="/national-overview" replace />;
  if (isWing(session)) return <Navigate to="/wing-overview" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function App() {
  const Router = USE_HASH ? HashRouter : BrowserRouter;

  if (MODULE_MODE) {
    return (
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <BrowserRouter basename={BASENAME}>
            <ModuleEntry />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <Router basename={BASENAME}>
          <RequireAuth>
            <SquadronViewProvider>
            <AppShell>
              <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/calendar" element={<Calendar />} />
                <Route path="/parade-nights" element={<ParadeNights />} />
                <Route path="/weekly-program" element={<WeeklyProgram />} />
                <Route path="/curriculum" element={<Curriculum />} />
                <Route path="/facilitators" element={<Facilitators />} />
                <Route path="/facilitator-schedule" element={<FacilitatorSchedule />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/cadets" element={<Cadets />} />
                <Route path="/reports" element={<Reports />} />
                <Route path="/report-catalogue" element={<ReportCatalogue />} />
                <Route path="/action-items" element={<ActionItems />} />
                <Route path="/imports" element={<Imports />} />
                <Route path="/audit" element={<Audit />} />
                <Route path="/admin" element={<Admin />} />
                <Route path="/accounts" element={<Accounts />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/wing-overview" element={<WingOverview />} />
                <Route path="/national-overview" element={<NationalOverview />} />
                <Route path="/planning" element={<PlanningWorkspace />} />
                <Route path="*" element={<div className="empty">Page not found or access not permitted.</div>} />
              </Routes>
              </ErrorBoundary>
            </AppShell>
            </SquadronViewProvider>
          </RequireAuth>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
}
