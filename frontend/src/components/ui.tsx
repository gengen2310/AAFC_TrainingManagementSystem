import type { ReactNode } from "react";
import { ApiError } from "../api/client";

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
export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof ApiError ? error.friendly : "Something went wrong.";
  return <div className="errnote" role="alert">{msg}</div>;
}
export function Button({ children, onClick, variant = "primary", type = "button", disabled, title }:
  { children: ReactNode; onClick?: () => void; variant?: "primary" | "out" | "danger"; type?: "button" | "submit"; disabled?: boolean; title?: string }) {
  return <button className={`btn ${variant === "out" ? "out" : variant === "danger" ? "danger" : ""}`} onClick={onClick} type={type} disabled={disabled} title={title}>{children}</button>;
}
