import { useEffect, useState } from "react";
import { api, type Professor, type ThesisDetail, type User } from "../api";

const EDITABLE = ["TOPIC_APPROVED", "THESIS_I", "THESIS_II", "IN_REVIEW"];

/** Reviewer committee (3 reviewers, one president). Admins manage it; a reviewer
 * approves the manuscript or withdraws the approval. */
export default function CommitteePanel({
  thesis,
  user,
  onChange,
}: {
  thesis: ThesisDetail;
  user: User;
  onChange: (t: ThesisDetail) => void;
}) {
  const [professors, setProfessors] = useState<Professor[]>([]);
  const [candidate, setCandidate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const isAdmin = user.role === "admin";
  const canEdit = isAdmin && EDITABLE.includes(thesis.status);
  const me = thesis.reviewers.find((r) => r.professor.professor_id === user.professor_id);
  const hasPresident = thesis.reviewers.some((r) => r.role === "President");

  useEffect(() => {
    if (canEdit) api.people<Professor>("professors").then(setProfessors).catch(() => setProfessors([]));
  }, [canEdit]);

  async function run(action: () => Promise<ThesisDetail>) {
    setError(null);
    try {
      onChange(await action());
      setCandidate("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const busy = new Set([
    ...thesis.reviewers.map((r) => r.professor.professor_id),
    ...thesis.tutors.map((t) => t.professor.professor_id),
  ]);
  const sorted = [...thesis.reviewers].sort((a, b) => (a.role === "President" ? -1 : b.role === "President" ? 1 : 0));

  return (
    <div className="committee">
      <h3>Reviewer committee ({thesis.reviewers.length}/3)</h3>
      {sorted.length === 0 && <p className="muted">No reviewers assigned.</p>}
      <ul className="committee-list">
        {sorted.map((r) => (
          <li key={r.professor.professor_id}>
            <span>
              <strong>{r.professor.full_name}</strong> <span className="muted">· {r.role}</span>
              {thesis.status === "IN_REVIEW" || r.approved_at ? (
                <span className={r.approved_at ? "approval yes" : "approval no"}>
                  {r.approved_at ? "✓ approved" : "pending approval"}
                </span>
              ) : null}
              {r.grade !== null && <span className="approval yes">grade {Number(r.grade).toFixed(2)}</span>}
            </span>
            {canEdit && (
              <span className="row-actions">
                <button
                  type="button"
                  className="button button-small button-secondary"
                  disabled={r.role !== "President" && hasPresident}
                  title={r.role !== "President" && hasPresident ? "Demote the current president first" : ""}
                  onClick={() =>
                    run(() =>
                      api.setReviewer(
                        thesis.thesis_id,
                        r.professor.professor_id,
                        r.role === "President" ? "Committee" : "President",
                      ),
                    )
                  }
                >
                  {r.role === "President" ? "Make member" : "Make president"}
                </button>
                <button
                  type="button"
                  className="button button-small button-danger"
                  onClick={() => run(() => api.removeReviewer(thesis.thesis_id, r.professor.professor_id))}
                >
                  Remove
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>

      {canEdit && thesis.reviewers.length < 3 && (
        <div className="tutor-row">
          <label>
            Add reviewer
            <select value={candidate} onChange={(e) => setCandidate(e.target.value)}>
              <option value="">Select a professor…</option>
              {professors
                .filter((p) => !busy.has(p.professor_id))
                .map((p) => (
                  <option key={p.professor_id} value={p.professor_id}>
                    {p.full_name}
                  </option>
                ))}
            </select>
          </label>
          <button
            type="button"
            className="button button-small"
            disabled={!candidate}
            onClick={() =>
              run(() => api.setReviewer(thesis.thesis_id, Number(candidate), hasPresident ? "Committee" : "President"))
            }
          >
            Add as {hasPresident ? "member" : "president"}
          </button>
        </div>
      )}
      {isAdmin && !EDITABLE.includes(thesis.status) && thesis.status === "PROPOSED" && (
        <p className="muted">The committee can be assigned once the topic is approved.</p>
      )}

      {me && thesis.status === "IN_REVIEW" && (
        <div className="my-approval">
          {me.approved_at ? (
            <>
              <span>You approved the manuscript.</span>
              <button
                type="button"
                className="button button-small button-secondary"
                onClick={() => run(() => api.setApproval(thesis.thesis_id, false))}
              >
                Withdraw approval
              </button>
            </>
          ) : (
            <>
              <span>Approve the manuscript once all your observations are resolved.</span>
              <button
                type="button"
                className="button button-small"
                onClick={() => run(() => api.setApproval(thesis.thesis_id, true))}
              >
                Approve manuscript
              </button>
            </>
          )}
        </div>
      )}
      {error && <p className="notice notice-error">{error}</p>}
    </div>
  );
}
