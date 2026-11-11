import { useEffect, useState, type FormEvent } from "react";
import { api, type Observation, type ObservationStatus, type ThesisDetail, type User } from "../api";

const STATUS_TEXT: Record<ObservationStatus, string> = {
  OPEN: "Open",
  ADDRESSED: "Answered",
  RESOLVED: "Resolved",
};

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

/** Review observations (FR-08): reviewer → student → reviewer. */
export default function ObservationsPanel({
  thesis,
  user,
  onChanged,
}: {
  thesis: ThesisDetail;
  user: User;
  onChanged: () => void;
}) {
  const [items, setItems] = useState<Observation[] | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .observations(thesis.thesis_id)
      .then(setItems)
      .catch((e: Error) => setError(e.message));
  }, [thesis]);

  const inReview = thesis.status === "IN_REVIEW";
  const isReviewer = thesis.reviewers.some((r) => r.professor.professor_id === user.professor_id);
  const isStudent = user.role === "student";

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      onChanged(); // reloads the thesis, which reloads this list and the workflow
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    await run(() => api.addObservation(thesis.thesis_id, text));
    setText("");
  }

  if (!items) return null;
  if (items.length === 0 && !(inReview && isReviewer)) return null;

  const open = items.filter((o) => o.status !== "RESOLVED").length;

  return (
    <section className="panel">
      <h2>
        Review observations{" "}
        <span className="muted small">
          {items.length} total · {open} pending
        </span>
      </h2>

      {items.length === 0 && <p className="muted">No observations yet.</p>}
      <ol className="observations">
        {items.map((o) => (
          <li key={o.observation_id} className={`obs obs-${o.status.toLowerCase()}`}>
            <div className="obs-head">
              <span className={`badge obs-badge-${o.status.toLowerCase()}`}>{STATUS_TEXT[o.status]}</span>
              <strong>{o.author_name}</strong>
              <span className="muted">· {formatDate(o.created_at)}</span>
            </div>
            <p className="prewrap">{o.text}</p>
            {o.response && (
              <blockquote className="prewrap">
                <span className="muted">Student response{o.responded_at ? ` · ${formatDate(o.responded_at)}` : ""}:</span>
                <br />
                {o.response}
              </blockquote>
            )}
            {inReview && isStudent && o.status === "OPEN" && (
              <ResponseForm onSubmit={(r) => run(() => api.respondObservation(thesis.thesis_id, o.observation_id, r))} />
            )}
            {inReview && o.status === "ADDRESSED" && o.professor_id === user.professor_id && (
              <div className="actions">
                <button
                  type="button"
                  className="button button-small"
                  onClick={() => run(() => api.resolveObservation(thesis.thesis_id, o.observation_id, true))}
                >
                  Accept response
                </button>
                <button
                  type="button"
                  className="button button-small button-secondary"
                  onClick={() => run(() => api.resolveObservation(thesis.thesis_id, o.observation_id, false))}
                >
                  Reopen
                </button>
              </div>
            )}
          </li>
        ))}
      </ol>

      {inReview && isReviewer && (
        <form className="form-grid" onSubmit={add}>
          <label className="full">
            New observation
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={5000} required />
          </label>
          <div className="actions full">
            <button type="submit" className="button">
              Add observation
            </button>
            <span className="muted small">Adding an observation withdraws your approval.</span>
          </div>
        </form>
      )}
      {error && <p className="notice notice-error">{error}</p>}
    </section>
  );
}

function ResponseForm({ onSubmit }: { onSubmit: (response: string) => Promise<void> }) {
  const [response, setResponse] = useState("");
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button type="button" className="button button-small" onClick={() => setOpen(true)}>
        Respond
      </button>
    );
  }
  return (
    <form
      className="form-grid"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(response);
      }}
    >
      <label className="full">
        Your response (what you changed)
        <textarea value={response} onChange={(e) => setResponse(e.target.value)} rows={3} maxLength={5000} required />
      </label>
      <div className="actions full">
        <button type="submit" className="button button-small">
          Send response
        </button>
        <button type="button" className="button button-small button-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
