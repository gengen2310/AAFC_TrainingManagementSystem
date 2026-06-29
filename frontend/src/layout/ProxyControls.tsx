import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { orgApi } from "../api";
import { useAuth } from "../auth/AuthProvider";
import { ApiError } from "../api/client";

// Proxy (Wing Admin) / Delegated Intervention (National Admin) entry/exit. Same backend route
// POST /api/proxy/enter/{squadron_id}; the backend chooses mode by role and requires a reason.
export function ProxyControls({ kind }: { kind: "proxy" | "intervention" }) {
  const { session, refresh, exitProxy } = useAuth();
  const qc = useQueryClient();
  const [sid, setSid] = useState("");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const squadrons = useQuery({ queryKey: ["squadrons"], queryFn: orgApi.squadrons });

  const enter = useMutation({
    mutationFn: () => orgApi.enterProxy(sid, reason),
    onSuccess: async () => {
      setErr(""); setReason("");
      await refresh();
      qc.invalidateQueries();
    },
    onError: (e) => setErr(e instanceof ApiError ? e.friendly : "Could not enter proxy mode."),
  });

  const exit = useMutation({
    mutationFn: exitProxy,
    onSuccess: () => qc.invalidateQueries(),
  });

  if (session?.proxy) {
    return <button className="btn danger sm" style={{ width: "100%" }} onClick={() => exit.mutate()}>{kind === "intervention" ? "Exit intervention" : "Exit proxy mode"}</button>;
  }
  return (
    <div className="proxy-box">
      <div className="nav-group" style={{ margin: "0 0 6px" }}>{kind === "intervention" ? "Intervention" : "Proxy mode"}</div>
      <label className="vis-hidden" htmlFor="proxy-sqn">Squadron</label>
      <select id="proxy-sqn" value={sid} onChange={(e) => setSid(e.target.value)}>
        <option value="">Select squadron…</option>
        {(squadrons.data ?? []).map((s) => <option key={s.squadron_id} value={s.squadron_id}>{s.short_name}</option>)}
      </select>
      <label className="vis-hidden" htmlFor="proxy-reason">Reason</label>
      <input id="proxy-reason" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
      {err && <div className="err" role="alert">{err}</div>}
      <button className="btn sm" style={{ width: "100%" }} disabled={!sid || !reason.trim() || enter.isPending}
        onClick={() => enter.mutate()}>{kind === "intervention" ? "Enter intervention" : "Enter proxy mode"}</button>
    </div>
  );
}
