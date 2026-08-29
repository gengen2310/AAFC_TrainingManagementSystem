import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

interface ToastMsg { id: number; text: string; isError?: boolean; }

interface ToastCtx { toast: (text: string, isError?: boolean) => void; }

const Ctx = createContext<ToastCtx>({ toast: () => {} });

export function useToast() { return useContext(Ctx); }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastMsg[]>([]);
  const seq = useRef(0);

  const toast = useCallback((text: string, isError = false) => {
    const id = ++seq.current;
    setItems((prev) => [...prev, { id, text, isError }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 3500);
  }, []);

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div aria-live="polite" aria-atomic="false" style={{
        // Same spacing contract as connected-frontend's .toast-region, so the
        // two implementations stay in step rather than drifting apart. The
        // fallbacks are the shared token values, not new numbers.
        position: "fixed",
        bottom: "var(--toast-edge, 20px)",
        right: "var(--toast-edge, 20px)",
        left: "var(--toast-edge, 20px)",
        zIndex: 9999,
        display: "flex", flexDirection: "column", alignItems: "flex-end",
        gap: "var(--toast-gap, 10px)", pointerEvents: "none",
      }}>
        {items.map((t) => (
          <div key={t.id} role="status" style={{
            background: t.isError ? "var(--red, #e51937)" : "var(--dark, #002f65)",
            color: "#fff",
            // 9px vertical read as cramped against the border; 14/18 matches the
            // connected-frontend toast exactly.
            padding: "var(--toast-pad-y, 14px) var(--toast-pad-x, 18px)",
            borderRadius: 7, lineHeight: 1.45,
            fontSize: 'var(--fs-base)', fontWeight: 600, boxShadow: "0 4px 16px rgba(0,0,0,.22)",
            maxWidth: "var(--toast-max-w, 400px)",
            pointerEvents: "auto", animation: "pw-toast-in .18s ease",
          }}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
