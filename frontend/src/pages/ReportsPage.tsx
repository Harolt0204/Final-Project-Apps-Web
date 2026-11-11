import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  api,
  localDate,
  STATUS_FLOW,
  STATUS_LABEL,
  type Overview,
  type Period,
  type RoomAvailability,
  type SchoolGrades,
  type WorkloadRow,
} from "../api";

export type ReportView = "overview" | "workload" | "grades" | "rooms";

/** Analytical reports for coordination (objective 5 of the proposal). Every chart has
 * its numbers in a table next to it, so nothing depends on color alone. */
export default function ReportsPage({ view }: { view: ReportView }) {
  return (
    <div className="viz-root">
      {view === "overview" && <OverviewReport />}
      {view === "workload" && <WorkloadReport />}
      {view === "grades" && <GradesReport />}
      {view === "rooms" && <RoomsReport />}
    </div>
  );
}

function useReport<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setError(null);
    load()
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, deps);
  return { data, error };
}

/** Horizontal single-series bar with its value labelled at the end. */
function Bar({ value, max, label }: { value: number; max: number; label: string }) {
  const width = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="hbar" title={label}>
      <div className="hbar-fill" style={{ width: `${width}%` }} />
      <span className="hbar-value">{label}</span>
    </div>
  );
}

// ------------------------------------------------------------------------- overview

function OverviewReport() {
  const { data, error } = useReport<Overview>(() => api.overview(), []);
  if (error) return <p className="notice notice-error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;
  const statuses = [...STATUS_FLOW, "REJECTED" as const];
  const max = Math.max(...statuses.map((s) => data.by_status[s]));
  return (
    <>
      <div className="stats">
        <Stat label="Theses registered" value={data.total_theses} />
        <Stat label="Active theses" value={data.active_theses} />
        <Stat label="Defended" value={data.by_status.DEFENDED} />
        <Stat label="Defenses in the next 30 days" value={data.upcoming_defenses_30_days} />
      </div>
      <section className="panel">
        <h2>Theses by status</h2>
        <table className="bar-table">
          <tbody>
            {statuses.map((s) => (
              <tr key={s}>
                <th scope="row">{STATUS_LABEL[s]}</th>
                <td>
                  <Bar value={data.by_status[s]} max={max} label={String(data.by_status[s])} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

// -------------------------------------------------------------------------- workload

const ROLES = [
  { key: "tutor_active", label: "Tutor", color: "var(--series-1)" },
  { key: "cotutor_active", label: "Co-tutor", color: "var(--series-2)" },
  { key: "president_active", label: "President", color: "var(--series-3)" },
  { key: "committee_active", label: "Committee", color: "var(--series-4)" },
] as const;

function WorkloadReport() {
  const [periods, setPeriods] = useState<Period[]>([]);
  const [periodId, setPeriodId] = useState("");
  const { data, error } = useReport<WorkloadRow[]>(
    () => api.workload(periodId ? Number(periodId) : undefined),
    [periodId],
  );
  useEffect(() => {
    api.periods().then(setPeriods).catch(() => setPeriods([]));
  }, []);

  const max = Math.max(1, ...(data ?? []).map((r) => r.total_active));

  return (
    <section className="panel">
      <div className="panel-title">
        <h1>Tutor workload</h1>
        <label className="inline-label">
          Academic period
          <select value={periodId} onChange={(e) => setPeriodId(e.target.value)}>
            <option value="">All periods</option>
            {periods.map((p) => (
              <option key={p.period_id} value={p.period_id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">Active theses per professor and role (defended and rejected theses excluded).</p>
      <ul className="legend" aria-label="Legend">
        {ROLES.map((r) => (
          <li key={r.key}>
            <span className="swatch" style={{ background: r.color }} />
            {r.label}
          </li>
        ))}
      </ul>
      {error && <p className="notice notice-error">{error}</p>}
      {data && (
        <div className="table-wrap">
          <table className="grid workload">
            <thead>
              <tr>
                <th>Professor</th>
                <th className="chart-col">Active load</th>
                {ROLES.map((r) => (
                  <th key={r.key} className="num">
                    {r.label}
                  </th>
                ))}
                <th className="num">Total</th>
                <th className="num" title="Theses supervised as main tutor that reached the defense">Defended</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.professor_id}>
                  <td>
                    {row.full_name}
                    {row.school && <span className="muted small"> · {row.school}</span>}
                  </td>
                  <td className="chart-col">
                    <div className="stack" style={{ width: `${(row.total_active / max) * 100}%` }}>
                      {ROLES.filter((r) => row[r.key] > 0).map((r) => (
                        <span
                          key={r.key}
                          className="stack-seg"
                          style={{ flexGrow: row[r.key], background: r.color }}
                          title={`${row.full_name} · ${r.label}: ${row[r.key]}`}
                        />
                      ))}
                    </div>
                  </td>
                  {ROLES.map((r) => (
                    <td key={r.key} className="num">
                      {row[r.key]}
                    </td>
                  ))}
                  <td className="num">
                    <strong>{row.total_active}</strong>
                  </td>
                  <td className="num">{row.supervised_defended}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------- grades

function GradesReport() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const { data, error } = useReport(() => api.gradesBySchool(from || undefined, to || undefined), [from, to]);
  const pass = data ? Number(data.min_passing_grade) : 0;

  return (
    <section className="panel">
      <div className="panel-title">
        <h1>Average defense grade by school</h1>
        <div className="filters compact-filters">
          <label className="inline-label">
            From
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="inline-label">
            To
            <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {data && data.schools.length === 0 && <p className="muted">No graded defenses in this range.</p>}
      {data && data.schools.length > 0 && (
        <>
          <p className="muted small">
            Scale 0–10 · pass mark {pass.toFixed(2)} (dashed line) · overall average{" "}
            <strong>{Number(data.overall_average).toFixed(2)}</strong>
          </p>
          <table className="bar-table">
            <tbody>
              {data.schools.map((s: SchoolGrades) => (
                <tr key={s.school_code}>
                  <th scope="row" title={s.school_name}>
                    {s.school_code}
                  </th>
                  <td>
                    <div className="hbar with-mark">
                      <div className="hbar-fill" style={{ width: `${Number(s.average_grade) * 10}%` }} />
                      <span className="pass-mark" style={{ left: `${pass * 10}%` }} aria-hidden="true" />
                      <span className="hbar-value">{Number(s.average_grade).toFixed(2)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="table-wrap spaced">
            <table className="grid compact">
              <thead>
                <tr>
                  <th>School</th>
                  <th className="num">Defenses</th>
                  <th className="num">Average</th>
                  <th className="num">Lowest</th>
                  <th className="num">Highest</th>
                  <th className="num">Pass rate</th>
                </tr>
              </thead>
              <tbody>
                {data.schools.map((s) => (
                  <tr key={s.school_code}>
                    <td>{s.school_name}</td>
                    <td className="num">{s.defenses}</td>
                    <td className="num">{Number(s.average_grade).toFixed(2)}</td>
                    <td className="num">{Number(s.min_grade).toFixed(2)}</td>
                    <td className="num">{Number(s.max_grade).toFixed(2)}</td>
                    <td className="num">
                      {Number(s.pass_rate).toFixed(0)}% ({s.passed}/{s.defenses})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

// ----------------------------------------------------------------------------- rooms

const OPEN_HOUR = 8;
const CLOSE_HOUR = 18;
const hours = (iso: string) => Number(iso.slice(11, 13)) + Number(iso.slice(14, 16)) / 60;
const position = (iso: string) => ((hours(iso) - OPEN_HOUR) / (CLOSE_HOUR - OPEN_HOUR)) * 100;
const dayName = (key: string) =>
  new Date(`${key}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short" });

function RoomsReport() {
  const [from, setFrom] = useState(localDate());
  const [days, setDays] = useState(7);
  const { data, error } = useReport<RoomAvailability>(() => api.roomAvailability(from, days), [from, days]);

  return (
    <section className="panel">
      <div className="panel-title">
        <h1>Defense room availability</h1>
        <div className="filters compact-filters">
          <label className="inline-label">
            From
            <input type="date" value={from} onChange={(e) => e.target.value && setFrom(e.target.value)} />
          </label>
          <label className="inline-label">
            Days
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[1, 7, 14, 31].map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      {data && (
        <>
          <p className="muted small">
            Working day {data.working_hours}. Blue blocks are booked defenses; the rest of the strip is free.
          </p>
          {data.rooms.map((room) => (
            <div key={room.room_id} className="room-block">
              <h3>
                {room.label}
                {room.capacity ? <span className="muted small"> · {room.capacity} seats</span> : null}
                <span className="room-occupancy">{Number(room.occupancy).toFixed(1)}% occupied</span>
              </h3>
              <div className="timeline-scale" aria-hidden="true">
                {Array.from({ length: CLOSE_HOUR - OPEN_HOUR + 1 }, (_, i) => (
                  <span key={i} style={{ left: `${(i / (CLOSE_HOUR - OPEN_HOUR)) * 100}%` }}>
                    {OPEN_HOUR + i}
                  </span>
                ))}
              </div>
              {room.days.map((d) => (
                <div key={d.day} className="timeline-row">
                  <span className="timeline-day">{dayName(d.day)}</span>
                  <div className="timeline" role="img" aria-label={`${dayName(d.day)}: ${d.bookings.length} bookings`}>
                    {d.bookings.map((b) => (
                      <Link
                        key={b.thesis_id}
                        to={`/theses/${b.thesis_id}`}
                        className="timeline-block"
                        style={{
                          left: `${Math.max(0, position(b.start))}%`,
                          width: `${Math.min(100, position(b.end)) - Math.max(0, position(b.start))}%`,
                        }}
                        title={`${b.start.slice(11, 16)}–${b.end.slice(11, 16)} · ${b.thesis_title}`}
                      />
                    ))}
                  </div>
                  <span className="timeline-free muted small">
                    {d.bookings.length === 0
                      ? "Free all day"
                      : `Free: ${d.free.map((w) => `${w.start.slice(11, 16)}–${w.end.slice(11, 16)}`).join(", ") || "—"}`}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </>
      )}
    </section>
  );
}
