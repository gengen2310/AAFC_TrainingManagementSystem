import type { ReactNode } from "react";
import { Modal } from "./Modal";
// A drill-down panel: opens record-level detail behind a metric. Records come from the backend.
export function DrilldownPanel({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <Modal title={title} onClose={onClose}>{children}</Modal>;
}
