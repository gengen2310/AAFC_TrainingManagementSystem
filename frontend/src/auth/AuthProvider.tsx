import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { authApi, orgApi } from "../api";
import { tokenStore } from "../api/client";
import type { SessionInfo } from "../api/types";

interface AuthCtx {
  session: SessionInfo | null;
  loading: boolean;
  login: (code: string, user_id?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  exitProxy: () => Promise<void>;
}
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  // React Query's cache is keyed by query name only, with no per-user/session
  // dimension (e.g. ["dashboard-charts", win]) — without an explicit clear here,
  // switching accounts in the same tab (login → logout → different login) leaves
  // the previous user's cached data visible until each query's own staleTime
  // expires, which for a role-branching page like Dashboard can show one role's
  // tactical data inside another role's shell. Clearing on every login/logout
  // transition closes that gap regardless of any single query's staleTime.
  const queryClient = useQueryClient();

  const refresh = useCallback(async () => {
    try { const r = await authApi.me(); setSession(r.session); }
    catch { setSession(null); }
  }, []);

  // Always try /api/me on mount — cookie auth works even when sessionStorage token is absent
  // (e.g. when opened in a new tab from the connected-frontend).
  useEffect(() => { (async () => { await refresh(); setLoading(false); })(); }, [refresh]);

  const login = async (code: string, user_id?: string) => {
    queryClient.clear();
    const r = await authApi.login(code, user_id);
    tokenStore.set(r.token);
    setSession(r.session);
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    tokenStore.clear();
    setSession(null);
    queryClient.clear();
  };

  // Exits proxy / delegated-intervention on the backend then refreshes the session
  // and clears the React Query cache.  Cache clear is essential: without it, queries
  // fetched under the proxy scope remain cached and are served to the post-exit page,
  // showing the proxied squadron's data.  Both the ProxyControls button and the
  // navigation guard (useProxyGuard) flow through this function.
  const exitProxy = useCallback(async () => {
    try { await orgApi.exitProxy(); } catch { /* best-effort; still refresh */ }
    queryClient.clear();
    await refresh();
  }, [refresh, queryClient]);

  return <Ctx.Provider value={{ session, loading, login, logout, refresh, exitProxy }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
