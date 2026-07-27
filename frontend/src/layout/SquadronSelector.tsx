import { useQuery } from "@tanstack/react-query";
import { reportApi } from "../api";
import { useSquadronView } from "./SquadronViewContext";

// Wing scope: reportApi.wingOverview() already returns only that wing's squadrons.
// National scope: the same endpoint returns squadrons across every wing (backend's
// wing_overview only filters by wing_id when the caller IS wing-scoped) — one
// selector serves both, per master transformation plan Block 8's requirement that
// Wing gets a Squadron selector and National gets Wing+Squadron selectors (the
// wing code shown alongside each squadron here gives National viewers the wing
// context without a separate control).
export function SquadronSelector() {
  const { selectedSquadronId, setSelectedSquadronId } = useSquadronView();
  const q = useQuery({ queryKey: ["wing-overview-for-selector"], queryFn: reportApi.wingOverview, staleTime: 5 * 60 * 1000 });
  const squadrons = q.data?.squadrons ?? [];

  return (
    <div className="nav-group-sqn-selector">
      <label htmlFor="sqn-view-select" style={{ fontSize: 11, fontWeight: 700, display: "block", marginBottom: 4 }}>
        Viewing squadron
      </label>
      <select
        id="sqn-view-select"
        value={selectedSquadronId ?? ""}
        onChange={(e) => setSelectedSquadronId(e.target.value || null)}
        style={{ width: "100%", fontSize: 12, padding: "5px 7px" }}
      >
        <option value="">— Select a squadron —</option>
        {squadrons.map((s) => (
          <option key={s.squadron_id} value={s.squadron_id}>{s.short_name ?? s.code}</option>
        ))}
      </select>
    </div>
  );
}
