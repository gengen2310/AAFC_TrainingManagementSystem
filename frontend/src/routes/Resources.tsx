import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { trainingApi } from "../api";
import { Card, Empty, Loading, ErrorNote, Button } from "../components/ui";

export function Resources() {
  const areas = useQuery({ queryKey: ["training-areas"], queryFn: trainingApi.trainingAreas });
  const equip = useQuery({ queryKey: ["equipment"], queryFn: trainingApi.equipment });
  const [date, setDate] = useState("");
  const clashes = useQuery({ queryKey: ["clashes", date], queryFn: () => trainingApi.clashes(date), enabled: !!date });

  return (
    <div>
      <h1>Resources</h1>
      <Card title="Training areas">
        {areas.isLoading ? <Loading /> : areas.error ? <ErrorNote error={areas.error} /> :
          (areas.data ?? []).length === 0 ? <Empty msg="No training areas." /> : (
            <table><caption className="vis-hidden">Training areas</caption>
              <thead><tr><th>Name</th><th>Type</th><th>Capacity</th></tr></thead>
              <tbody>{(areas.data ?? []).map((a) => <tr key={a.training_area_id}><td>{a.name}</td><td>{a.type ?? "—"}</td><td>{a.capacity ?? "—"}</td></tr>)}</tbody></table>
          )}
      </Card>
      <Card title="Equipment">
        {equip.isLoading ? <Loading /> : equip.error ? <ErrorNote error={equip.error} /> :
          (equip.data ?? []).length === 0 ? <Empty msg="No equipment." /> : (
            <table><caption className="vis-hidden">Equipment</caption>
              <thead><tr><th>Name</th><th>Type</th><th>Qty</th></tr></thead>
              <tbody>{(equip.data ?? []).map((e) => <tr key={e.equipment_id}><td>{e.name}</td><td>{e.type ?? "—"}</td><td>{e.quantity ?? "—"}</td></tr>)}</tbody></table>
          )}
      </Card>
      <Card title="Resource clashes">
        <div className="filter-bar">
          <label htmlFor="cl-date">Date</label>
          <input id="cl-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <Button variant="out" onClick={() => clashes.refetch()} disabled={!date}>Check</Button>
        </div>
        {!date ? <Empty msg="Pick a date to check for room/facilitator clashes." /> :
          clashes.isLoading ? <Loading /> :
          (clashes.data?.clashes.length ? (
            <table><thead><tr><th>Type</th><th>Resource</th><th>Severity</th></tr></thead>
              <tbody>{clashes.data!.clashes.map((c, i) => (
                <tr key={i}><td>{c.type.replace(/_/g, " ")}</td><td>{c.resource_id}</td>
                  <td><span className="badge red">▲ Hard clash</span></td></tr>))}</tbody></table>
          ) : <Empty msg="No clashes on this date." />)}
      </Card>
    </div>
  );
}
