import { useEffect, useState, type FormEvent } from "react";
import { api, localDate, type DefenseInput, type Room, type ThesisDetail, type User } from "../api";

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
const formatTime = (iso: string) => iso.slice(11, 16);

/** Oral defense: schedule (admin), details for everyone, grades (jury). */
export default function DefensePanel({
  thesis,
  user,
  onChange,
}: {
  thesis: ThesisDetail;
  user: User;
  onChange: (t: ThesisDetail) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defense = thesis.defense;
  const isAdmin = user.role === "admin";
  const waiting = thesis.status === "READY_FOR_DEFENSE";
  const graded = (defense?.grades_recorded ?? 0) > 0;

  if (!waiting && !defense) return null;

  async function run(action: () => Promise<ThesisDetail>) {
    setError(null);
    try {
      onChange(await action());
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const me = thesis.reviewers.find((r) => r.professor.professor_id === user.professor_id);
  const started = defense ? new Date(defense.scheduled_at) <= new Date() : false;

  return (
    <section className="panel defense-panel">
      <div className="panel-title">
        <h2>Oral defense</h2>
        {isAdmin && waiting && !graded && !editing && (
          <span className="row-actions">
            <button type="button" className="button button-small" onClick={() => setEditing(true)}>
              {defense ? "Reschedule" : "Schedule defense"}
            </button>
            {defense && (
              <button
                type="button"
                className="button button-small button-danger"
                onClick={() => window.confirm("Cancel this defense?") && run(() => api.cancelDefense(thesis.thesis_id))}
              >
                Cancel
              </button>
            )}
          </span>
        )}
      </div>

      {editing && (
        <ScheduleForm thesis={thesis} onCancel={() => setEditing(false)} onSubmit={(d) => run(() => api.scheduleDefense(thesis.thesis_id, d))} />
      )}

      {!defense && !editing && <p className="muted">The thesis is approved for defense; no date has been set yet.</p>}

      {defense && (
        <>
          <dl className="facts">
            <dt>Date</dt>
            <dd>
              {formatDateTime(defense.scheduled_at)} – {formatTime(defense.ends_at)}
              <span className="muted"> ({defense.duration_minutes} min)</span>
            </dd>
            <dt>Place</dt>
            <dd>
              {defense.modality === "In-person" ? (
                defense.room?.label
              ) : defense.meeting_url?.startsWith("http") ? (
                <a href={defense.meeting_url} target="_blank" rel="noreferrer noopener">
                  Virtual meeting link
                </a>
              ) : (
                `Virtual (${defense.meeting_url})`
              )}
            </dd>
            <dt>Jury</dt>
            <dd>{thesis.reviewers.map((r) => `${r.professor.full_name}${r.role === "President" ? " (president)" : ""}`).join(", ")}</dd>
            <dt>Grades</dt>
            <dd>
              {defense.final_grade !== null ? (
                <span className={`final-grade ${defense.passed ? "ok" : "bad"}`}>
                  {Number(defense.final_grade).toFixed(2)} / 10 · {defense.passed ? "Passed" : "Failed"}
                </span>
              ) : (
                `${defense.grades_recorded} of 3 jury grades recorded`
              )}
              {defense.min_passing_grade && (
                <span className="muted small"> (pass mark {Number(defense.min_passing_grade).toFixed(2)})</span>
              )}
            </dd>
          </dl>

          {me && waiting && (
            <GradeForm
              current={me.grade}
              started={started}
              onSubmit={(g) => run(() => api.recordGrade(thesis.thesis_id, g))}
            />
          )}
        </>
      )}
      {error && <p className="notice notice-error">{error}</p>}
    </section>
  );
}

function GradeForm({
  current,
  started,
  onSubmit,
}: {
  current: string | null;
  started: boolean;
  onSubmit: (grade: string) => void;
}) {
  const [grade, setGrade] = useState(current ? String(Number(current)) : "");
  if (!started) {
    return <p className="notice">You can record your grade once the defense has started.</p>;
  }
  return (
    <form
      className="grade-form"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(grade);
      }}
    >
      <label>
        Your grade (0–10)
        <input type="number" min={0} max={10} step="0.01" value={grade} onChange={(e) => setGrade(e.target.value)} required />
      </label>
      <button type="submit" className="button">
        {current ? "Update my grade" : "Record my grade"}
      </button>
      <span className="muted small">The final grade is the average of the three jury grades.</span>
    </form>
  );
}

function ScheduleForm({
  thesis,
  onCancel,
  onSubmit,
}: {
  thesis: ThesisDetail;
  onCancel: () => void;
  onSubmit: (data: DefenseInput) => void;
}) {
  const current = thesis.defense;
  const [rooms, setRooms] = useState<Room[]>([]);
  const [date, setDate] = useState(current?.scheduled_at.slice(0, 10) ?? "");
  const [time, setTime] = useState(current?.scheduled_at.slice(11, 16) ?? "10:00");
  const [duration, setDuration] = useState(String(current?.duration_minutes ?? 60));
  const [modality, setModality] = useState<"In-person" | "Virtual">(current?.modality ?? "In-person");
  const [roomId, setRoomId] = useState(current?.room ? String(current.room.room_id) : "");
  const [url, setUrl] = useState(current?.meeting_url ?? "");
  const [bookings, setBookings] = useState<{ thesis_id: number; starts_at: string; ends_at: string }[]>([]);

  useEffect(() => {
    api.rooms().then(setRooms).catch(() => setRooms([]));
  }, []);

  // Show the room's other bookings that day, so a free slot is easy to pick.
  useEffect(() => {
    if (modality === "In-person" && roomId && date) {
      api
        .roomBookings(Number(roomId), date)
        .then((all) => setBookings(all.filter((b) => b.thesis_id !== thesis.thesis_id)))
        .catch(() => setBookings([]));
    } else {
      setBookings([]);
    }
  }, [modality, roomId, date, thesis.thesis_id]);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      scheduled_at: `${date}T${time}:00`,
      duration_minutes: Number(duration),
      modality,
      ...(modality === "In-person" ? { room_id: Number(roomId) } : { meeting_url: url }),
    });
  }

  const tomorrow = localDate(1);

  return (
    <form className="form-grid inline-form" onSubmit={submit}>
      <label>
        Date
        <input type="date" value={date} min={tomorrow} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <label>
        Start time
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} required />
      </label>
      <label>
        Duration
        <select value={duration} onChange={(e) => setDuration(e.target.value)}>
          {[45, 60, 90, 120].map((m) => (
            <option key={m} value={m}>
              {m} minutes
            </option>
          ))}
        </select>
      </label>
      <label>
        Modality
        <select value={modality} onChange={(e) => setModality(e.target.value as "In-person" | "Virtual")}>
          <option value="In-person">In person</option>
          <option value="Virtual">Virtual</option>
        </select>
      </label>
      {modality === "In-person" ? (
        <label className="full">
          Room
          <select value={roomId} onChange={(e) => setRoomId(e.target.value)} required>
            <option value="">Select a room…</option>
            {rooms.map((r) => (
              <option key={r.room_id} value={r.room_id}>
                {r.label}
                {r.capacity ? ` · ${r.capacity} seats` : ""}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="full">
          Meeting link
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" maxLength={255} required />
        </label>
      )}
      {bookings.length > 0 && (
        <p className="notice full">
          Room already booked that day:{" "}
          {bookings.map((b) => `${formatTime(b.starts_at)}–${formatTime(b.ends_at)}`).join(", ")}
        </p>
      )}
      <p className="muted small full">
        The system rejects the date if the room or any jury member has another defense at that time.
      </p>
      <div className="actions full">
        <button type="submit" className="button">
          Save schedule
        </button>
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
