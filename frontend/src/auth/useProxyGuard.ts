import { useEffect } from "react";
import { useAuth } from "./AuthProvider";

// useBlocker requires a data router (createBrowserRouter) which this app uses BrowserRouter for.
// Guard 1 (SPA nav blocker) is omitted; Guard 2 (beforeunload) covers the primary proxy-exit case.
export function useProxyGuard(): void {
  const { session } = useAuth();
  const proxyActive = !!session?.proxy;

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
