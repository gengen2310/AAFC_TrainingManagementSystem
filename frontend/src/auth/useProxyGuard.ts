import { useEffect } from "react";
import { useBlocker } from "react-router-dom";
import { useAuth } from "./AuthProvider";

/**
 * Attaches two proxy-mode guards when proxy / delegated-intervention is active:
 *
 *  1. React Router blocker — silently exits proxy on any SPA navigation so the
 *     backend scope is cleared before the next page renders. The navigation is
 *     held until the exit call resolves; it proceeds regardless of whether the
 *     call succeeds (best-effort).
 *
 *  2. beforeunload — browser native warning when the user closes the tab, forces
 *     a full-page reload, or follows an external link while proxy is active.
 *
 * Call this once from AppShell (which lives inside <BrowserRouter>).
 */
export function useProxyGuard(): void {
  const { session, exitProxy } = useAuth();
  const proxyActive = !!session?.proxy;

  // Guard 1: SPA navigation via React Router.
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      proxyActive && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    exitProxy()
      .catch(() => { /* proceed even if the server call fails */ })
      .finally(() => blocker.proceed());
  }, [blocker, exitProxy]);

  // Guard 2: Hard navigation (tab close, reload, external link).
  useEffect(() => {
    if (!proxyActive) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Chrome requires returnValue to be set to trigger the native dialog.
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [proxyActive]);
}
