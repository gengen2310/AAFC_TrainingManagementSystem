import type { ReactNode } from "react";
import { friendlyMessage } from "../api/client";

// AUTO-01: save-state indicator. status values:
//   'ready'  — no unsaved changes
//   'dirty'  — user has typed; debounce pending
//   'saving' — API call in flight
//   'saved'  — last save succeeded
//   'failed' — last save failed
export type SaveStatus = 'ready' | 'dirty' | 'saving' | 'saved' | 'failed';

export function SaveIndicator({ status }: { status: SaveStatus }) {
  if (status === 'ready') return null;
  const map: Record<SaveStatus, { label: string; color: string }> = {
    ready:  { label: '',                         color: 'inherit'       },
    dirty:  { label: 'Unsaved',                  color: 'var(--muted)'  },
    saving: { label: 'Saving…',                  color: 'var(--muted)'  },
    saved:  { label: 'Saved',                    color: 'var(--ok)'     },
    failed: { label: 'Could not save — Try again', color: 'var(--red)'  },
  };
  const { label, color } = map[status];
  return (
    <span
      style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, marginLeft: 8, color }}
      aria-live="polite"
      aria-atomic="true"
    >
      {label}
    </span>
  );
}

export function Card({ title, action, children }: { title?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || action) && <div className="card-head"><div className="ctitle">{title}</div>{action}</div>}
      {children}
    </section>
  );
}
export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return <div className="stat"><div className="lbl">{label}</div><div className="val">{value}</div>{hint && <div className="hint">{hint}</div>}</div>;
}
export function Empty({ msg }: { msg: string }) { return <div className="empty" role="status">{msg}</div>; }
export function Loading() { return <div className="empty" role="status" aria-live="polite">Loading…</div>; }
export function Bar({ pct, label }: { pct: number; label?: string }) {
  return (
    <div
      className="bar"
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? `${pct}% complete`}
    >
      <span style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </div>
  );
}
// "load" (default): a whole page/section's data query failed -- the user has
// no other context on the page, so name what failed and suggest reloading.
// "action" (opt in): a save/create/submit action inside a still-open form
// failed -- suggesting "reload the page" here would be wrong (it would
// discard whatever the user was typing), so this variant shows just the
// reason, matching the form's own still-visible Save/Cancel buttons as the
// implicit next step.
// Same resolution as App.tsx / AppShell.tsx: the PW has no sign-in of its own.
const TMS_BASE =
  (document.querySelector('meta[name="aafc-tms-base"]') as HTMLMetaElement | null)
    ?.content || "https://aafc-tms-frontend-production.up.railway.app";
// SESSION-04: the one place that decides what to tell the user to DO about an
// error. Five view components each hard-coded "check your internet connection",
// which is wrong for an expired session and for a server error.
export function ErrorRemedy({ error }: { error: unknown }) {
  const status = (error as { status?: number } | null)?.status;
  const isNetwork = !!(error as { isNetwork?: boolean } | null)?.isNetwork;
  if (status === 401) return (
    <div style={{ fontSize: 'var(--fs-xs)', marginTop: 6, color: "var(--muted-text)" }}>
      <a href={TMS_BASE}>Sign in again</a> to continue. Planning Workspace uses your TMS session.
    </div>
  );
  if (isNetwork) return (
    <div style={{ fontSize: 'var(--fs-xs)', marginTop: 6, color: "var(--muted-text)" }}>
      Check that you have an internet connection, then reload the page.
    </div>
  );
  return null;
}
export function ErrorNote({ error, variant = "load" }: { error: unknown; variant?: "load" | "action" }) {
  const msg = friendlyMessage(error, "Unknown error");
  if (variant === "action") {
    return <div className="errnote" role="alert">{msg}</div>;
  }
  // SESSION-04: the connectivity line used to print under EVERY error, so an
  // expired session read "Your session has expired. Please log in again. Check
  // your connection, then reload the page." -- two different causes in one
  // message, only one of them true, and a remedy the user cannot act on.
  // Defence Writing UI standard §2.14 (Accuracy): state exactly what is true.
  const status = (error as { status?: number } | null)?.status;
  const isNetwork = !!(error as { isNetwork?: boolean } | null)?.isNetwork;
  const expired = status === 401;
  return (
    <div className="errnote" role="alert">
      <div style={{ fontWeight: 700 }}>Could not load this data</div>
      <div style={{ fontSize: 'var(--fs-sm)', opacity: .85, marginTop: 2 }}>{msg}</div>
      {expired ? (
        <div style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>
          <a href={TMS_BASE}>Sign in again</a> to continue. Planning Workspace uses your TMS session.
        </div>
      ) : isNetwork ? (
        <div style={{ fontSize: 'var(--fs-xs)', marginTop: 4 }}>Check your connection, then reload the page.</div>
      ) : null}
    </div>
  );
}
export function Button({ children, onClick, variant = "primary", type = "button", disabled, title }:
  { children: ReactNode; onClick?: () => void; variant?: "primary" | "out" | "danger"; type?: "button" | "submit"; disabled?: boolean; title?: string }) {
  return <button className={`btn ${variant === "out" ? "out" : variant === "danger" ? "danger" : ""}`} onClick={onClick} type={type} disabled={disabled} title={title}>{children}</button>;
}
