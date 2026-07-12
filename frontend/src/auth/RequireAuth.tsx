import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";
import { LoginPage } from "./LoginPage";
import { Loading } from "../components/ui";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  if (loading) return <Loading />;
  if (!session) return <LoginPage />;
  return <>{children}</>;
}
