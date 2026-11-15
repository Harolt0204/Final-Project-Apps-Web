import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, ApiError, type Professor, type ThesisDetail } from "../api";
import { useAuth } from "../auth";
import CommitteePanel from "../components/CommitteePanel";
import DefensePanel from "../components/DefensePanel";
import ObservationsPanel from "../components/ObservationsPanel";
import RequirementsPanel from "../components/RequirementsPanel";
import SimilarityPanel from "../components/SimilarityPanel";
import { StatusBadge, StatusStepper } from "../components/Status";
import { GeneralInfoPanel, StatusHistoryPanel, TutorFacts } from "../components/ThesisInfo";
import WorkflowPanel from "../components/WorkflowPanel";
import EditTopicForm from "../components/EditTopicForm";

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
  // Students edit their topic from the home dashboard; here only admins can.
  const canEdit = isAdmin;

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
        <GeneralInfoPanel thesis={thesis} />

        <section className="panel">
          <h2>Tutors and committee</h2>
          {isAdmin && !CLOSED.includes(thesis.status) ? (
            <TutorManager thesis={thesis} onChange={setThesis} />
          ) : (
            <TutorFacts thesis={thesis} />
          )}
          <CommitteePanel thesis={thesis} user={user} onChange={setThesis} />
        </section>
      </div>

      <ObservationsPanel thesis={thesis} user={user} onChanged={load} />

      <SimilarityPanel thesis={thesis} user={user} onChanged={load} />
      <RequirementsPanel thesisId={thesis.thesis_id} canEdit={isAdmin} onChanged={load} />

      <StatusHistoryPanel thesis={thesis} />
    </>
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
