import { useEffect, useState } from "react";
import { api, type RequirementItem, type RequirementState, type StudentRequirements } from "../api";

const STATE_LABEL: Record<RequirementState, string> = {
  PENDING: "Pending",
  CERTIFIED: "Certified",
  REJECTED: "Rejected",
};
const STATE_BADGE: Record<RequirementState, string> = {
  PENDING: "badge",
  CERTIFIED: "badge badge-defended",
  REJECTED: "badge badge-rejected",
};

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

/** Administrative graduation requirements of a student (FR-10).
 * Loaded through the thesis (any participant) or the student (admin or the student). */
export default function RequirementsPanel({
  thesisId,
  studentId,
  canEdit,
  onChanged,
  title = "Administrative requirements",
}: {
  thesisId?: number;
  studentId?: number;
  canEdit: boolean;
  onChanged?: () => void;
  title?: string;
}) {
  const [data, setData] = useState<StudentRequirements | null>(null);
  const [editing, setEditing] = useState<{ item: RequirementItem; mode: "CERTIFIED" | "REJECTED" } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = thesisId ? api.thesisRequirements(thesisId) : api.studentRequirements(studentId!);
    load.then(setData).catch((e: Error) => setError(e.message));
  }, [thesisId, studentId]);

  async function run(action: () => Promise<StudentRequirements>) {
    setError(null);
    try {
      setData(await action());
      setEditing(null);
      onChanged?.();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (!data) return error ? <p className="notice notice-error">{error}</p> : null;
  const done = data.items.filter((i) => i.status === "CERTIFIED").length;

  return (
    <section className="panel">
      <h2>
        {title}{" "}
        <span className={`badge ${data.complete ? "badge-defended" : ""}`}>
          {done}/{data.items.length} certified
        </span>
      </h2>
      {data.items.length === 0 && <p className="muted">No requirements are configured.</p>}
      <ul className="requirements">
        {data.items.map((item) => (
          <li key={item.requirement_type.requirement_type_id} className={`req req-${item.status.toLowerCase()}`}>
            <div className="req-main">
              <span className={STATE_BADGE[item.status]}>{STATE_LABEL[item.status]}</span>
              <div>
                <strong>{item.requirement_type.name}</strong>
                {item.requirement_type.description && (
                  <div className="muted small">{item.requirement_type.description}</div>
                )}
                {item.certified_at && (
                  <div className="muted small">
                    {STATE_LABEL[item.status]} {formatDate(item.certified_at)}
                    {item.certified_by_name ? ` by ${item.certified_by_name}` : ""}
                    {item.evidence_url && (
                      <>
                        {" · "}
                        <a href={item.evidence_url} target="_blank" rel="noreferrer noopener">
                          evidence
                        </a>
                      </>
                    )}
                  </div>
                )}
                {item.notes && <div className="small req-note">{item.notes}</div>}
              </div>
            </div>
            {canEdit && editing?.item !== item && (
              <div className="row-actions">
                {item.status !== "CERTIFIED" && (
                  <button type="button" className="button button-small" onClick={() => setEditing({ item, mode: "CERTIFIED" })}>
                    Certify
                  </button>
                )}
                {item.status === "PENDING" && (
                  <button
                    type="button"
                    className="button button-small button-danger"
                    onClick={() => setEditing({ item, mode: "REJECTED" })}
                  >
                    Reject
                  </button>
                )}
                {item.status !== "PENDING" && (
                  <button
                    type="button"
                    className="button button-small button-secondary"
                    onClick={() =>
                      run(() => api.clearRequirement(data.student_id, item.requirement_type.requirement_type_id))
                    }
                  >
                    Reset
                  </button>
                )}
              </div>
            )}
            {editing?.item === item && (
              <DecisionForm
                mode={editing.mode}
                onCancel={() => setEditing(null)}
                onSubmit={(evidence, notes) =>
                  run(() =>
                    api.setRequirement(data.student_id, item.requirement_type.requirement_type_id, {
                      status: editing.mode,
                      evidence_url: evidence || undefined,
                      notes: notes || undefined,
                    }),
                  )
                }
              />
            )}
          </li>
        ))}
      </ul>
      {error && <p className="notice notice-error">{error}</p>}
    </section>
  );
}

function DecisionForm({
  mode,
  onCancel,
  onSubmit,
}: {
  mode: "CERTIFIED" | "REJECTED";
  onCancel: () => void;
  onSubmit: (evidence: string, notes: string) => void;
}) {
  const [evidence, setEvidence] = useState("");
  const [notes, setNotes] = useState("");
  return (
    <form
      className="form-grid inline-form full-row"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(evidence, notes);
      }}
    >
      {mode === "CERTIFIED" && (
        <label>
          Evidence URL (optional)
          <input type="url" value={evidence} onChange={(e) => setEvidence(e.target.value)} maxLength={500} />
        </label>
      )}
      <label className={mode === "REJECTED" ? "full" : ""}>
        {mode === "REJECTED" ? "Reason (required)" : "Notes (optional)"}
        <input value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} required={mode === "REJECTED"} />
      </label>
      <div className="actions full">
        <button type="submit" className={`button button-small ${mode === "REJECTED" ? "button-danger" : ""}`}>
          {mode === "CERTIFIED" ? "Confirm certification" : "Confirm rejection"}
        </button>
        <button type="button" className="button button-small button-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
