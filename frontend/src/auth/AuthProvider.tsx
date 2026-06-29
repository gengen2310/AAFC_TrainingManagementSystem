import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { authApi, orgApi } from "../api";
import { tokenStore } from "../api/client";
import type { SessionInfo } from "../api/types";

interface AuthCtx {
  session: SessionInfo | null;
  loading: boolean;
  login: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  exitProxy: () => Promise<void>;
}
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try { const r = await authApi.me(); setSession(r.session); }
    catch { setSession(null); }
  }, []);

  useEffect(() => { (async () => { if (tokenStore.get()) await refresh(); setLoading(false); })(); }, [refresh]);

  const login = async (code: string) => {
    const r = await authApi.login(code);
    tokenStore.set(r.token);
    setSession(r.session);
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    tokenStore.clear();
    setSession(null);
  };

  // Exits proxy / delegated-intervention on the backend then refreshes the session.
  // Used by ProxyControls and by useProxyGuard (navigation guard).
  const exitProxy = useCallback(async () => {
    try { await orgApi.exitProxy(); } catch { /* best-effort; still refresh */ }
    await refresh();
  }, [refresh]);

  return <Ctx.Provider value={{ session, loading, login, logout, refresh, exitProxy }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
