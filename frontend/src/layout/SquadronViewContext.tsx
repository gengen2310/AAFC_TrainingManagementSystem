import { createContext, useContext, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";
import { isWing, isNational, isAuditor } from "../auth/permissions";

// Lets a Wing/National viewer pick which squadron's operational pages
// (Calendar/Curriculum/Parade Nights/Facilitators/Resources) they're looking at,
// without needing Proxy/Delegated Intervention Mode — viewing is broad by design
// (permissions.py's Principal.can_view_squadron); only writing is proxy-gated.
// See backend/app/routers/training.py's _view_squadron_id (master transformation
// plan Block 8) for the matching backend-side mechanism.
interface SquadronViewCtx {
  selectedSquadronId: string | null;
  setSelectedSquadronId: (id: string | null) => void;
}
const Ctx = createContext<SquadronViewCtx | null>(null);

export function SquadronViewProvider({ children }: { children: ReactNode }) {
  const [selectedSquadronId, setSelectedSquadronId] = useState<string | null>(null);
  return <Ctx.Provider value={{ selectedSquadronId, setSelectedSquadronId }}>{children}</Ctx.Provider>;
}

export function useSquadronView() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useSquadronView must be used within SquadronViewProvider");
  return c;
}

// Shared helper for Squadron-scoped pages (Calendar/Curriculum/Facilitators/Resources/
// Parade Nights/Dashboard) consumed at Wing/National scope. Squadron-role sessions need
// no selection — the backend infers their own squadron when no squadron_id is sent.
// Wing/National (excluding auditor, which has no operational nav block) must pick a
// squadron first; `scoped` is false until they do, so pages can render a prompt instead
// of querying with an undefined squadron_id.
export function useScopedSquadron() {
  const { session } = useAuth();
  const { selectedSquadronId } = useSquadronView();
  const needsSelection = (isWing(session) || isNational(session)) && !isAuditor(session);
  const squadronId = needsSelection ? (selectedSquadronId ?? undefined) : undefined;
  return { needsSelection, squadronId, scoped: !needsSelection || !!squadronId };
}
