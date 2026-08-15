import { useCallback, useRef, useState } from "react";
import type { SaveStatus } from "../components/ui";

// AUTO-01: React hook that wraps the Class A autosave pattern.
// saveFn: async function that persists the current value; must return a Promise.
// debounceMs: milliseconds to wait after last keystroke before saving (default 1400).
//
// Returns { onChange, status } where:
//   onChange — pass directly to an input/textarea's onChange prop
//   status   — current SaveStatus; feed into <SaveIndicator status={status} />
//
// Prevents duplicate concurrent writes via an inflight flag.
export function useAutoSave(saveFn: (value: string) => Promise<void>, debounceMs = 1400) {
  const [status, setStatus] = useState<SaveStatus>("ready");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useRef(false);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const val = e.target.value;
      setStatus("dirty");
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(async () => {
        if (inflight.current) return;
        inflight.current = true;
        setStatus("saving");
        try {
          await saveFn(val);
          setStatus("saved");
          setTimeout(() => setStatus("ready"), 3000);
        } catch {
          setStatus("failed");
        } finally {
          inflight.current = false;
        }
      }, debounceMs);
    },
    [saveFn, debounceMs]
  );

  return { onChange, status };
}
