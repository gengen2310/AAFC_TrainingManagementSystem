import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

interface ConfirmState {
  message: string;
  title?: string;
  confirmLabel?: string;
  danger?: boolean;
  resolve: (ok: boolean) => void;
}

interface ConfirmCtx {
  confirm: (message: string, opts?: { title?: string; confirmLabel?: string; danger?: boolean }) => Promise<boolean>;
}

const Ctx = createContext<ConfirmCtx>({ confirm: async () => false });

export function useConfirm() { return useContext(Ctx); }

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConfirmState | null>(null);
  const resolveRef = useRef<((ok: boolean) => void) | null>(null);

  const confirm = useCallback(
    (message: string, opts: { title?: string; confirmLabel?: string; danger?: boolean } = {}) =>
      new Promise<boolean>((resolve) => {
        resolveRef.current = resolve;
        setState({ message, ...opts, resolve });
      }),
    []
  );

  function close(ok: boolean) {
    setState(null);
    const cb = resolveRef.current;
    resolveRef.current = null;
    if (cb) cb(ok);
  }

  return (
    <Ctx.Provider value={{ confirm }}>
      {children}
      {state && (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div
          className="modal-overlay"
          onClick={() => close(false)}
          style={{ zIndex: 9900 }}
        >
          {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events */}
          <div
            className="modal"
            role="alertdialog"
            aria-modal="true"
            aria-label={state.title ?? "Confirm"}
            style={{ maxWidth: 420 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <h2>{state.title ?? "Confirm"}</h2>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, fontSize: 14, whiteSpace: "pre-line" }}>{state.message}</p>
            </div>
            <div className="modal-foot" style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn out sm" onClick={() => close(false)}>
                Cancel
              </button>
              <button
                className={`btn sm ${state.danger ? "danger" : ""}`}
                onClick={() => close(true)}
                autoFocus
              >
                {state.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </Ctx.Provider>
  );
}
