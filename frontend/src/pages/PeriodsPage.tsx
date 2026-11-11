import { useEffect, useState, type FormEvent } from "react";
import { api, localDate, type Period } from "../api";

const today = localDate();

export default function PeriodsPage() {
  const [periods, setPeriods] = useState<Period[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Period | "new" | null>(null);

  const load = () =>
    api
      .periods()
      .then(setPeriods)
      .catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function remove(p: Period) {
    if (!window.confirm(`Delete period ${p.name}?`)) return;
    try {
      await api.deletePeriod(p.period_id);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      {editing && (
        <PeriodForm
          key={editing === "new" ? "new" : editing.period_id}
          period={editing === "new" ? undefined : editing}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
      <section className="panel">
        <div className="panel-title">
          <h1>Academic periods</h1>
          {editing !== "new" && (
            <button type="button" className="button" onClick={() => setEditing("new")}>
              New period
            </button>
          )}
        </div>
        {error && <p className="notice notice-error">{error}</p>}
        {periods?.length === 0 && <p className="muted">No academic periods yet.</p>}
        {periods && periods.length > 0 && (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Start</th>
                  <th>End</th>
                  <th />
                  <th />
                </tr>
              </thead>
              <tbody>
                {periods.map((p) => {
                  const current = p.start_date && p.end_date && p.start_date <= today && today <= p.end_date;
                  return (
                    <tr key={p.period_id}>
                      <td>
                        <strong>{p.name}</strong>
                      </td>
                      <td>{p.start_date ?? "—"}</td>
                      <td>{p.end_date ?? "—"}</td>
                      <td>{current && <span className="badge badge-defended">In course</span>}</td>
                      <td className="row-actions">
                        <button
                          type="button"
                          className="button button-small button-secondary"
                          onClick={() => setEditing(p)}
                        >
                          Edit
                        </button>
                        <button type="button" className="button button-small button-danger" onClick={() => remove(p)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function PeriodForm({ period, onCancel, onSaved }: { period?: Period; onCancel: () => void; onSaved: () => void }) {
  const [name, setName] = useState(period?.name ?? "");
  const [start, setStart] = useState(period?.start_date ?? "");
  const [end, setEnd] = useState(period?.end_date ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const data = { name, start_date: start, end_date: end };
    try {
      if (period) await api.updatePeriod(period.period_id, data);
      else await api.createPeriod(data);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>{period ? `Edit ${period.name}` : "New academic period"}</h2>
      <form className="form-grid" onSubmit={submit}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="2027-I" required maxLength={100} />
        </label>
        <label>
          Start date
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} required />
        </label>
        <label>
          End date
          <input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required />
        </label>
        {error && <p className="notice notice-error full">{error}</p>}
        <div className="actions full">
          <button type="submit" className="button">
            Save
          </button>
          <button type="button" className="button button-secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
