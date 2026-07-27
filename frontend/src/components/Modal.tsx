import type { ReactNode } from "react";
import { useEffect } from "react";

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    // The backdrop's onClick is a mouse-only convenience; Escape (above) and the Close
    // button below are the full keyboard-equivalent paths, so this div doesn't need its
    // own keyboard handler/focus stop.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div className="modal-overlay" onClick={onClose}>
      {/* onClick here only stops the backdrop's click-to-close from firing when the
          click originated inside the dialog — not itself a user-facing interaction. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events */}
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h2>{title}</h2><button className="btn out sm" onClick={onClose} aria-label="Close">✕</button></div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
