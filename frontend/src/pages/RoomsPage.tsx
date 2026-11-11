import { useEffect, useState, type FormEvent } from "react";
import { api, type Room } from "../api";

/** Defense rooms catalog (administrators). */
export default function RoomsPage() {
  const [rooms, setRooms] = useState<Room[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [building, setBuilding] = useState("");
  const [capacity, setCapacity] = useState("");

  const load = () =>
    api
      .rooms(true)
      .then(setRooms)
      .catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    await run(() => api.createRoom({ name, building, capacity: capacity ? Number(capacity) : null }));
    setName("");
    setCapacity("");
  }

  return (
    <section className="panel">
      <h1>Defense rooms</h1>
      {error && <p className="notice notice-error">{error}</p>}
      {rooms && (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Room</th>
                <th>Building</th>
                <th>Capacity</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.room_id} className={r.is_active ? "" : "inactive"}>
                  <td>{r.name}</td>
                  <td>{r.building}</td>
                  <td>{r.capacity ?? "—"}</td>
                  <td>{r.is_active ? "Active" : "Inactive"}</td>
                  <td className="row-actions">
                    <button
                      type="button"
                      className="button button-small button-secondary"
                      onClick={() => run(() => api.updateRoom(r.room_id, { is_active: !r.is_active }))}
                    >
                      {r.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="spaced">Add room</h3>
      <form className="form-grid" onSubmit={add}>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </label>
        <label>
          Building
          <input value={building} onChange={(e) => setBuilding(e.target.value)} maxLength={100} required />
        </label>
        <label>
          Capacity
          <input type="number" min={1} max={2000} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
        </label>
        <div className="actions align-end">
          <button type="submit" className="button">
            Add room
          </button>
        </div>
      </form>
    </section>
  );
}
