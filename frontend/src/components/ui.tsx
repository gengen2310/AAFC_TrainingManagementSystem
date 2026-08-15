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
      style={{ fontSize: 11, fontWeight: 600, marginLeft: 8, color }}
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
export function ErrorNote({ error, variant = "load" }: { error: unknown; variant?: "load" | "action" }) {
  const msg = friendlyMessage(error, "Unknown error");
  if (variant === "action") {
    return <div className="errnote" role="alert">{msg}</div>;
  }
  return (
    <div className="errnote" role="alert">
      <div style={{ fontWeight: 700 }}>Could not load this data</div>
      <div style={{ fontSize: 12, opacity: .85, marginTop: 2 }}>{msg}</div>
      <div style={{ fontSize: 11, marginTop: 4 }}>Check your connection, then reload the page.</div>
    </div>
  );
}
export function Button({ children, onClick, variant = "primary", type = "button", disabled, title }:
  { children: ReactNode; onClick?: () => void; variant?: "primary" | "out" | "danger"; type?: "button" | "submit"; disabled?: boolean; title?: string }) {
  return <button className={`btn ${variant === "out" ? "out" : variant === "danger" ? "danger" : ""}`} onClick={onClick} type={type} disabled={disabled} title={title}>{children}</button>;
}
