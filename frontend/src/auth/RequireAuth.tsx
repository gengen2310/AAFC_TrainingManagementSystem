import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { LoginPage } from "./LoginPage";
import { Loading } from "../components/ui";

const TMS_URL = "https://aafc-tms-frontend-production.up.railway.app";
const MODULE_MODE =
  (document.querySelector('meta[name="aafc-module-mode"]') as HTMLMetaElement | null)
    ?.content === "true";

function NotAuthenticated() {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--bg, #f4f8fc)" }}>
      <div style={{ background: "white", border: "1px solid #d1dce8", borderRadius: 10, padding: "36px 40px", maxWidth: 420, textAlign: "center", boxShadow: "0 4px 16px rgba(0,47,101,.10)" }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>🔒</div>
        <h1 style={{ fontSize: 17, fontWeight: 700, color: "#002f65", marginBottom: 10 }}>Session not found</h1>
        <p style={{ fontSize: 13, color: "#455560", lineHeight: 1.6, marginBottom: 24 }}>
          Please return to the Training Management System and log in first. Planning Workspace uses your existing TMS session.
        </p>
        <a
          href={TMS_URL}
          style={{ display: "inline-block", background: "#51b0e3", color: "white", fontWeight: 700, fontSize: 13, padding: "10px 24px", borderRadius: 6, textDecoration: "none" }}
        >
          Return to TMS
        </a>
      </div>
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <Loading />;
  if (!session) return MODULE_MODE ? <NotAuthenticated /> : <LoginPage />;
  return <>{children}</>;
}
