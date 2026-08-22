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
        position: "fixed", bottom: 20, right: 20, zIndex: 9999,
        display: "flex", flexDirection: "column", gap: 8, pointerEvents: "none",
      }}>
        {items.map((t) => (
          <div key={t.id} role="status" style={{
            background: t.isError ? "var(--red, #e51937)" : "var(--dark, #002f65)",
            color: "#fff", padding: "9px 16px", borderRadius: 7,
            fontSize: 'var(--fs-base)', fontWeight: 600, boxShadow: "0 4px 16px rgba(0,0,0,.22)",
            maxWidth: 340, pointerEvents: "auto", animation: "pw-toast-in .18s ease",
          }}>
            {t.text}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
