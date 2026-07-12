import { BrowserRouter, HashRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { isNational, isWing, isAuditor } from "./auth/permissions";
import { Dashboard } from "./routes/Dashboard";
import { Calendar } from "./routes/Calendar";
import { ParadeNights } from "./routes/ParadeNights";
import { WeeklyProgram } from "./routes/WeeklyProgram";
import { Curriculum } from "./routes/Curriculum";
import { Facilitators } from "./routes/Facilitators";
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
import { PlanningWorkspaceRoute } from "./routes/PlanningWorkspace";
import { ErrorBoundary } from "./components/ErrorBoundary";

const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });

// Single-file connected build uses HashRouter (/#/path) so it works with Python's simple HTTP
// server without SPA path-rewriting. All other builds keep BrowserRouter.
const USE_HASH = import.meta.env.VITE_HASH_ROUTER === "true";
// GitHub Pages serves project sites under /<repo>/. Vite sets BASE_URL from the `base` build
// option; strip trailing slash. Ignored when using HashRouter.
const BASENAME = USE_HASH ? "/" : (import.meta.env.BASE_URL || "/").replace(/\/$/, "") || "/";

function Home() {
  const { session } = useAuth();
  if (isAuditor(session)) return <Navigate to="/audit" replace />;
  if (isNational(session)) return <Navigate to="/national-overview" replace />;
  if (isWing(session)) return <Navigate to="/wing-overview" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function App() {
  const Router = USE_HASH ? HashRouter : BrowserRouter;
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <Router basename={BASENAME}>
          <RequireAuth>
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
                <Route path="/planning" element={<PlanningWorkspaceRoute />} />
                <Route path="*" element={<div className="empty">Page not found or access not permitted.</div>} />
              </Routes>
              </ErrorBoundary>
            </AppShell>
          </RequireAuth>
        </Router>
      </AuthProvider>
    </QueryClientProvider>
  );
}
