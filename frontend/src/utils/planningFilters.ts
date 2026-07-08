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
