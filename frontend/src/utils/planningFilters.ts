import type { AnchorEvent } from "../api/types";

type AnchorPredicate = (a: AnchorEvent) => boolean;

const AUDIENCE_MATCH: Record<string, AnchorPredicate> = {
  "All Cadets":    (a) => a.audience_orientation || a.audience_initial || a.audience_junior || a.audience_intermediate || a.audience_senior,
  "Seniors":       (a) => a.audience_senior,
  "Juniors":       (a) => a.audience_junior,
  "First Years":   (a) => a.audience_orientation || a.audience_initial,
  "Staff":         (a) => a.audience_staff_only,
  "All Personnel": (_) => true,
};

// Priority chip label → backend importance value(s). Empty string = no restriction.
const PRIORITY_IMPORTANCE: Record<string, string> = {
  "Must Attend": "mandatory",
  "Key Event":   "key_event",
  "Home Parade": "",          // parade type, not an anchor importance — passes through
  "Optional":    "optional",
  "Noting":      "recommended",
};

// Foundation/Extension/Optional per the national phase catalogue, not the
// ambiguous 2-valued CurriculumItem.core_status field (core|additional) --
// core_status made every "additional" item fall through to "Extension"
// regardless of its actual phase. Derived instead from the governed phase
// name's letter prefix (A-E = Orientation/Initial/Junior/Intermediate/Senior
// = Foundation, I/J/K = Bronze/Silver/Gold = Extension), matching the
// national CurriculumPhase catalogue's sort order (backend training.py). A
// phase outside that set (a custom wing/squadron phase, or missing) is
// Optional -- "other programs added by squadrons," per spec. Shared between
// PlanningBottomDrawer.tsx and PlanningRightDrawer.tsx so the two can't
// drift back out of sync with each other the way core_status-based copies did.
const _FOUNDATION_PREFIXES = new Set(["A", "B", "C", "D", "E"]);
const _EXTENSION_PREFIXES = new Set(["I", "J", "K"]);
export function getProgramType(phase: string | null | undefined): "foundation" | "extension" | "optional" {
  const prefix = (phase || "").trim().charAt(0).toUpperCase();
  if (_FOUNDATION_PREFIXES.has(prefix)) return "foundation";
  if (_EXTENSION_PREFIXES.has(prefix)) return "extension";
  return "optional";
}

export function filterAnchors(
  anchors: AnchorEvent[],
  audience: Set<string>,
  priority: Set<string>,
): AnchorEvent[] {
  return anchors.filter((a) => {
    if (audience.size > 0) {
      const audienceMatch = [...audience].some((aud) => {
        const fn = AUDIENCE_MATCH[aud];
        return fn ? fn(a) : true;
      });
      if (!audienceMatch) return false;
    }

    if (priority.size > 0) {
      const priorityMatch = [...priority].some((p) => {
        const imp = PRIORITY_IMPORTANCE[p];
        return !imp || a.importance === imp;
      });
      if (!priorityMatch) return false;
    }

    return true;
  });
}
