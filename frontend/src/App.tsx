import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { SquadronViewProvider } from "./layout/SquadronViewContext";
import { PlanningWorkspace } from "./routes/PlanningWorkspace";
import { ToastProvider } from "./components/Toast";
import { ConfirmProvider } from "./components/ConfirmDialog";

// refetchOnWindowFocus/refetchOnReconnect: stale data (e.g. a Parade Night
// edited in the other frontend, or in another tab) should surface when the
// user comes back to this tab or the network returns, not require a manual
// reload -- matches the same freshness expectation Main TMS's own page
// Refresh buttons are built to satisfy.
const qc = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: true, refetchOnReconnect: true } } });

const BASENAME = (import.meta.env.BASE_URL || "/").replace(/\/$/, "") || "/";

const TMS_URL =
  (document.querySelector('meta[name="aafc-tms-base"]') as HTMLMetaElement | null)
    ?.content || "https://aafc-tms-frontend-production.up.railway.app";

// Planning Workspace is MODULE-ONLY by architecture — it is always opened
// as a standalone tab from the connected-frontend TMS, never as a full app
// with its own shell and nav. Auth comes from the shared backend session
// cookie (SameSite=None; Secure) — no login form is shown.

function NotAuthenticated() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f4f8fc" }}>
      <div style={{ background: "white", border: "1px solid #d1dce8", borderRadius: 10, padding: "36px 40px", maxWidth: 420, textAlign: "center", boxShadow: "0 4px 16px rgba(0,47,101,.10)" }}>
        <div style={{ fontSize: '2rem', marginBottom: 16 }}>🔒</div>
        <h1 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, color: "#002f65", marginBottom: 10 }}>Session not found</h1>
        <p style={{ fontSize: 'var(--fs-base)', color: "#455560", lineHeight: 1.6, marginBottom: 24 }}>
          Please return to the Training Management System and log in first.
          Planning Workspace uses your existing TMS session.
        </p>
        <a href={TMS_URL} style={{ display: "inline-block", background: "var(--royal)", color: "white", fontWeight: 700, fontSize: 'var(--fs-base)', padding: "10px 24px", borderRadius: 6, textDecoration: "none" }}>
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
        <div style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>Loading Planning Workspace…</div>
      </div>
    </div>
  );
}

function ModuleError({ onRetry }: { onRetry: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f4f8fc" }}>
      <div style={{ background: "white", border: "1px solid #d1dce8", borderRadius: 10, padding: "36px 40px", maxWidth: 480, textAlign: "center", boxShadow: "0 4px 16px rgba(0,47,101,.10)" }}>
        <div style={{ fontSize: '2rem', marginBottom: 16 }}>⚠️</div>
        <h1 style={{ fontSize: 'var(--fs-xl)', fontWeight: 700, color: "#002f65", marginBottom: 10 }}>Planning Workspace could not load</h1>
        <p style={{ fontSize: 'var(--fs-base)', color: "#455560", lineHeight: 1.6, marginBottom: 24 }}>
          The system could not load planning data. If this keeps happening, contact support.
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <button onClick={onRetry} style={{ background: "var(--royal)", color: "white", fontWeight: 700, fontSize: 'var(--fs-base)', padding: "10px 20px", borderRadius: 6, border: 0, cursor: "pointer" }}>
            Retry
          </button>
          <a href={TMS_URL} style={{ display: "inline-block", background: "white", color: "#455560", fontWeight: 600, fontSize: 'var(--fs-base)', padding: "10px 20px", borderRadius: 6, textDecoration: "none", border: "1px solid #d1dce8" }}>
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

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ConfirmProvider>
          <AuthProvider>
            <BrowserRouter basename={BASENAME}>
              <ModuleEntry />
            </BrowserRouter>
          </AuthProvider>
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
