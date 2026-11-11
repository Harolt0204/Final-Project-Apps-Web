import { useEffect, useState } from "react";
import { api, STATUS_LABEL, type ThesisDetail, type WorkflowOption } from "../api";

const ACTOR_LABEL: Record<string, string> = { admin: "coordination", tutor: "the tutor" };

/** Next steps of the thesis: what is missing for each one, and buttons for those
 * the current user may perform. */
export default function WorkflowPanel({
  thesis,
  onChange,
}: {
  thesis: ThesisDetail;
  onChange: (t: ThesisDetail) => void;
}) {
  const [options, setOptions] = useState<WorkflowOption[] | null>(null);
  const [pending, setPending] = useState<WorkflowOption | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .workflow(thesis.thesis_id)
      .then((w) => setOptions(w.options))
      .catch((e: Error) => setError(e.message));
  }, [thesis]);

  if (!options || options.length === 0) {
    return error ? <p className="notice notice-error">{error}</p> : null;
  }

  async function apply(option: WorkflowOption, text: string) {
    setError(null);
    try {
      onChange(await api.changeStatus(thesis.thesis_id, option.to_status, text));
      setPending(null);
      setComment("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="workflow">
      <h2>Next steps</h2>
      <ul className="workflow-options">
        {options.map((o) => (
          <li key={o.to_status} className={o.blockers.length ? "blocked" : "ready"}>
            <div>
              <strong>{o.label}</strong>{" "}
              <span className="muted">
                → {STATUS_LABEL[o.to_status]} · by {o.actors.map((a) => ACTOR_LABEL[a] ?? a).join(" or ")}
              </span>
              {o.blockers.length > 0 ? (
                <ul className="blockers">
                  {o.blockers.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              ) : (
                <p className="ok-line">All prerequisites are met.</p>
              )}
            </div>
            {o.can_perform && pending?.to_status !== o.to_status && (
              <button
                type="button"
                className={`button button-small ${o.to_status === "REJECTED" ? "button-danger" : ""}`}
                onClick={() => setPending(o)}
              >
                {o.label}
              </button>
            )}
          </li>
        ))}
      </ul>

      {pending && (
        <form
          className="form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            apply(pending, comment);
          }}
        >
          <label className="full">
            Comment for the status history {pending.comment_required ? "(required)" : "(optional)"}
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              maxLength={2000}
              required={pending.comment_required}
            />
          </label>
          <div className="actions full">
            <button type="submit" className="button">
              Confirm: {pending.label}
            </button>
            <button type="button" className="button button-secondary" onClick={() => setPending(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {error && <p className="notice notice-error">{error}</p>}
    </div>
  );
}
