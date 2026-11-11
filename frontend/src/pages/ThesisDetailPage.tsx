import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, ApiError, STATUS_LABEL, type Professor, type ThesisDetail } from "../api";
import { useAuth } from "../auth";
import CommitteePanel from "../components/CommitteePanel";
import DefensePanel from "../components/DefensePanel";
import ObservationsPanel from "../components/ObservationsPanel";
import RequirementsPanel from "../components/RequirementsPanel";
import SimilarityPanel from "../components/SimilarityPanel";
import { StatusBadge, StatusStepper } from "../components/Status";
import WorkflowPanel from "../components/WorkflowPanel";

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

const CLOSED = ["DEFENDED", "REJECTED"];

export default function ThesisDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [thesis, setThesis] = useState<ThesisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = () =>
    api
      .thesis(Number(id))
      .then(setThesis)
      .catch((e: Error) =>
        setError(e instanceof ApiError && e.status === 404 ? "Thesis not found, or you do not take part in it." : e.message),
      );

  useEffect(() => {
    setThesis(null);
    setError(null);
    load();
  }, [id]);

  if (error) {
    return (
      <section className="panel">
        <p className="notice notice-error">{error}</p>
        <Link to="/theses">Back to theses</Link>
      </section>
    );
  }
  if (!thesis || !user) return <p className="muted">Loading…</p>;

  const isAdmin = user.role === "admin";
  const canEdit = isAdmin || (user.role === "student" && thesis.status === "PROPOSED");

  return (
    <>
      <section className="panel">
        <p className="breadcrumb">
          <Link to="/theses">Theses</Link> › #{thesis.thesis_id}
        </p>
        {editing ? (
          <EditTopicForm
            thesis={thesis}
            isAdmin={isAdmin}
            onCancel={() => setEditing(false)}
            onSaved={(t) => {
              setThesis(t);
              setEditing(false);
            }}
          />
        ) : (
          <>
            <div className="panel-title">
              <h1>{thesis.title}</h1>
              {canEdit && (
                <button type="button" className="button button-secondary" onClick={() => setEditing(true)}>
                  Edit topic
                </button>
              )}
            </div>
            <p>
              <StatusBadge status={thesis.status} />
              {thesis.my_roles.length > 0 && <span className="muted"> · Your role: {thesis.my_roles.join(", ")}</span>}
            </p>
          </>
        )}
        <StatusStepper status={thesis.status} />
        <WorkflowPanel thesis={thesis} onChange={setThesis} />
      </section>

      <DefensePanel thesis={thesis} user={user} onChange={setThesis} />

      <div className="two-col">
        <section className="panel">
          <h2>General information</h2>
          <dl className="facts">
            <dt>Student</dt>
            <dd>
              {thesis.student.full_name}
              <br />
              <span className="muted">{thesis.student.email}</span>
            </dd>
            <dt>School</dt>
            <dd>{thesis.student.school?.name ?? "—"}</dd>
            <dt>Academic periods</dt>
            <dd>{thesis.periods.map((p) => p.name).join(", ") || "—"}</dd>
            <dt>Abstract</dt>
            <dd className="prewrap">{thesis.abstract ?? "—"}</dd>
          </dl>
        </section>

        <section className="panel">
          <h2>Tutors and committee</h2>
          {isAdmin && !CLOSED.includes(thesis.status) ? (
            <TutorManager thesis={thesis} onChange={setThesis} />
          ) : (
            <dl className="facts">
              <dt>Tutor</dt>
              <dd>{thesis.tutors.find((t) => t.role === "Tutor")?.professor.full_name ?? "Not assigned"}</dd>
              <dt>Co-tutor</dt>
              <dd>{thesis.tutors.find((t) => t.role === "Co-Tutor")?.professor.full_name ?? "—"}</dd>
            </dl>
          )}
          <CommitteePanel thesis={thesis} user={user} onChange={setThesis} />
        </section>
      </div>

      <ObservationsPanel thesis={thesis} user={user} onChanged={load} />

      <SimilarityPanel thesis={thesis} user={user} onChanged={load} />
      <RequirementsPanel thesisId={thesis.thesis_id} canEdit={isAdmin} onChanged={load} />

      <section className="panel">
        <h2>Status history</h2>
        {thesis.status_history.length === 0 ? (
          <p className="muted">No status changes recorded.</p>
        ) : (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Change</th>
                  <th>By</th>
                  <th>Comment</th>
                </tr>
              </thead>
              <tbody>
                {[...thesis.status_history].reverse().map((h, i) => (
                  <tr key={i}>
                    <td>{formatDate(h.changed_at)}</td>
                    <td>
                      {h.from_status ? `${STATUS_LABEL[h.from_status]} → ` : ""}
                      {STATUS_LABEL[h.to_status]}
                    </td>
                    <td>{h.changed_by_name}</td>
                    <td>{h.comment ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function EditTopicForm({
  thesis,
  isAdmin,
  onCancel,
  onSaved,
}: {
  thesis: ThesisDetail;
  isAdmin: boolean;
  onCancel: () => void;
  onSaved: (t: ThesisDetail) => void;
}) {
  const [title, setTitle] = useState(thesis.title);
  const [abstract, setAbstract] = useState(thesis.abstract ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      onSaved(await api.updateThesis(thesis.thesis_id, { title, abstract: abstract || null }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <label className="full">
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} minLength={5} maxLength={255} required />
      </label>
      <label className="full">
        Abstract
        <textarea value={abstract} onChange={(e) => setAbstract(e.target.value)} rows={6} maxLength={5000} />
      </label>
      {!isAdmin && <p className="muted full">You can edit the topic until it is approved.</p>}
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
  );
}

/** Admin control to assign, replace or remove the tutor and co-tutor (DEC-03). */
function TutorManager({ thesis, onChange }: { thesis: ThesisDetail; onChange: (t: ThesisDetail) => void }) {
  const [professors, setProfessors] = useState<Professor[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.people<Professor>("professors").then(setProfessors).catch((e: Error) => setError(e.message));
  }, []);

  const current = (role: "Tutor" | "Co-Tutor") => thesis.tutors.find((t) => t.role === role)?.professor.professor_id;
  const reviewerIds = new Set(thesis.reviewers.map((r) => r.professor.professor_id));

  async function run(action: () => Promise<ThesisDetail>) {
    setError(null);
    try {
      onChange(await action());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const slots = [
    { role: "Tutor" as const, slot: "tutor" as const, label: "Tutor" },
    { role: "Co-Tutor" as const, slot: "co-tutor" as const, label: "Co-tutor" },
  ];

  return (
    <div className="tutor-manager">
      {slots.map(({ role, slot, label }) => {
        const assigned = current(role);
        const disabled = role === "Co-Tutor" && !current("Tutor");
        return (
          <div key={slot} className="tutor-row">
            <label>
              {label}
              <select
                value={assigned ?? ""}
                disabled={disabled}
                onChange={(e) =>
                  e.target.value && run(() => api.assignTutor(thesis.thesis_id, slot, Number(e.target.value)))
                }
              >
                <option value="">{disabled ? "Assign the tutor first" : "Not assigned"}</option>
                {professors.map((p) => (
                  <option key={p.professor_id} value={p.professor_id} disabled={reviewerIds.has(p.professor_id)}>
                    {p.full_name}
                    {reviewerIds.has(p.professor_id) ? " (reviewer)" : ""}
                  </option>
                ))}
              </select>
            </label>
            {assigned && (
              <button
                type="button"
                className="button button-small button-secondary"
                onClick={() => run(() => api.removeTutor(thesis.thesis_id, slot))}
              >
                Remove
              </button>
            )}
          </div>
        );
      })}
      {error && <p className="notice notice-error">{error}</p>}
    </div>
  );
}
