import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api, localDate, type CalendarItem } from "../api";
import { useAuth } from "../auth";

const dayKey = (iso: string) => iso.slice(0, 10);
const dayLabel = (key: string) =>
  new Date(`${key}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

/** Defense calendar: upcoming and past defenses the user takes part in. */
export default function DefensesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<CalendarItem[] | null>(null);
  const [showPast, setShowPast] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .calendar()
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, []);

  const today = localDate();
  const groups = useMemo(() => {
    const visible = (items ?? []).filter((d) => (showPast ? dayKey(d.scheduled_at) < today : dayKey(d.scheduled_at) >= today));
    const ordered = showPast ? [...visible].reverse() : visible;
    const map = new Map<string, CalendarItem[]>();
    for (const d of ordered) map.set(dayKey(d.scheduled_at), [...(map.get(dayKey(d.scheduled_at)) ?? []), d]);
    return [...map.entries()];
  }, [items, showPast, today]);

  return (
    <section className="panel">
      <div className="panel-title">
        <h1>{user?.role === "admin" ? "Defense calendar" : "My defenses"}</h1>
        <div className="segmented" role="group" aria-label="Period">
          <button type="button" className={showPast ? "" : "active"} onClick={() => setShowPast(false)}>
            Upcoming
          </button>
          <button type="button" className={showPast ? "active" : ""} onClick={() => setShowPast(true)}>
            Past
          </button>
        </div>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {items && groups.length === 0 && (
        <p className="muted">{showPast ? "No past defenses." : "No upcoming defenses."}</p>
      )}
      {groups.map(([key, list]) => (
        <div key={key} className="calendar-day">
          <h3>{dayLabel(key)}</h3>
          <ul className="calendar-list">
            {list.map((d) => (
              <li key={d.defense_id}>
                <span className="calendar-time">
                  {d.scheduled_at.slice(11, 16)}–{d.ends_at.slice(11, 16)}
                </span>
                <div>
                  <Link to={`/theses/${d.thesis_id}`}>
                    <strong>{d.thesis_title}</strong>
                  </Link>
                  <div className="small">
                    {d.student_name} · {d.modality === "In-person" ? d.room?.label : "Virtual"}
                  </div>
                  <div className="muted small">Jury: {d.jury.join(", ")}</div>
                </div>
                <span>
                  {d.final_grade !== null ? (
                    <span className={`badge ${d.passed ? "badge-defended" : "badge-rejected"}`}>
                      {Number(d.final_grade).toFixed(2)}
                    </span>
                  ) : (
                    <span className="badge">{d.grades_recorded}/3 grades</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
