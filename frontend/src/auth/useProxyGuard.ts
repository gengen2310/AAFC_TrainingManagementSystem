import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./AuthProvider";

/**
 * Attaches two proxy-mode guards when proxy / delegated-intervention is active:
 *
 *  1. Location watcher — exits proxy in the background when a SPA navigation
 *     changes the pathname. Non-blocking: navigation proceeds immediately and
 *     the backend scope is cleared asynchronously (best-effort). After exit,
 *     all cached queries are invalidated so any data that loaded during the
 *     race window is immediately refetched with the correct (non-proxy) scope.
 *     Note: useBlocker (blocking variant) requires a data router created with
 *     createBrowserRouter; BrowserRouter does not support it in RR v6.
 *
 *  2. beforeunload — browser native warning when the user closes the tab, forces
 *     a full-page reload, or follows an external link while proxy is active.
 *
 * Call this once from AppShell (which lives inside <BrowserRouter>).
 */
export function useProxyGuard(): void {
  const { session, exitProxy } = useAuth();
  const qc = useQueryClient();
  const proxyActive = !!session?.proxy;
  const location = useLocation();
  const prevPathRef = useRef(location.pathname);

  // Guard 1: SPA navigation — exit proxy when the pathname changes.
  useEffect(() => {
    const prev = prevPathRef.current;
    const next = location.pathname;
    if (proxyActive && prev !== next) {
      exitProxy()
        .then(() => qc.invalidateQueries())
        .catch(() => qc.invalidateQueries()); // best-effort: invalidate even on failure
    }
    prevPathRef.current = next;
  }, [location.pathname, proxyActive, exitProxy, qc]);

  // Guard 2: Hard navigation (tab close, reload, external link).
  useEffect(() => {
    if (!proxyActive) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [proxyActive]);
}
