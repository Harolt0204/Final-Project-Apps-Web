import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, type ThesisDetail, type ThesisSummary, type User } from "../api";
import { useAuth } from "../auth";
import CommitteePanel from "./CommitteePanel";
import DefensePanel from "./DefensePanel";
import EditTopicForm from "./EditTopicForm";
import ObservationsPanel from "./ObservationsPanel";
import RequirementsPanel from "./RequirementsPanel";
import SimilarityPanel from "./SimilarityPanel";
import { StatusStepper } from "./Status";
import { sectionFrom, type ThesisSection } from "./thesisSections";
import { GeneralInfoPanel, StatusHistoryPanel, TutorFacts } from "./ThesisInfo";
import WorkflowPanel from "./WorkflowPanel";

/** One thesis on one page: its progress (left), the section picked in the
 * sub-navigation bar (center) and its facts (right). Used as the student home and as
 * a professor's view of a thesis they take part in.
 *
 * `summary` is the thesis to show (a student without a thesis has none); `theses`
 * lets a professor switch to another of their theses. */
export default function ThesisDashboard({
  summary,
  theses = [],
}: {
  summary?: ThesisSummary;
  theses?: ThesisSummary[];
}) {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const section = sectionFrom(params.get("section"));
  const [thesis, setThesis] = useState<ThesisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingTopic, setEditingTopic] = useState(false);
  const thesisId = summary?.thesis_id;

  // Picking another section in the bar closes the topic editor.
  useEffect(() => setEditingTopic(false), [section]);

  const load = useCallback(() => {
    if (!thesisId) return;
    api
      .thesis(thesisId)
      .then(setThesis)
      .catch((e: Error) => setError(e.message));
  }, [thesisId]);

  useEffect(() => {
    setThesis(null);
    setError(null);
    load();
  }, [load]);

  if (!user) return null;
  const isStudent = user.role === "student";

  return (
    <div className="thesis-dashboard">
      <aside className="thesis-dashboard-thesis">
        <ThesisProgressPanel
          user={user}
          summary={summary}
          thesis={thesis}
          theses={theses}
          section={section}
          editing={editingTopic}
          onEdit={() => setEditingTopic(true)}
        />
      </aside>

      <div className="thesis-dashboard-main">
        {error && <p className="notice notice-error">{error}</p>}
        {editingTopic && thesis ? (
          <section className="panel">
            <h2>Edit thesis topic</h2>
            <EditTopicForm
              thesis={thesis}
              isAdmin={false}
              onCancel={() => setEditingTopic(false)}
              onSaved={(t) => {
                setThesis(t);
                setEditingTopic(false);
              }}
            />
          </section>
        ) : section === "requirements" && isStudent ? (
          // A student's requirements exist before the thesis does.
          user.student_id && (
            <RequirementsPanel studentId={user.student_id} canEdit={false} title="My graduation requirements" />
          )
        ) : !summary ? (
          <section className="panel">
            <p className="muted">Register your thesis topic first; this section will then show its progress.</p>
          </section>
        ) : !thesis ? (
          !error && <p className="muted">Loading…</p>
        ) : (
          <SectionContent section={section} thesis={thesis} user={user} onChange={setThesis} onChanged={load} />
        )}
      </div>

      <aside className="thesis-dashboard-facts">
        {thesis && (
          <>
            <GeneralInfoPanel thesis={thesis} />
            <section className="panel">
              <h2>Tutors and committee</h2>
              <TutorFacts thesis={thesis} />
              <CommitteePanel thesis={thesis} user={user} onChange={setThesis} />
            </section>
          </>
        )}
      </aside>
    </div>
  );
}

function SectionContent({
  section,
  thesis,
  user,
  onChange,
  onChanged,
}: {
  section: ThesisSection;
  thesis: ThesisDetail;
  user: User;
  onChange: (t: ThesisDetail) => void;
  onChanged: () => void;
}) {
  switch (section) {
    case "next-steps":
      return (
        <section className="panel">
          <WorkflowPanel
            thesis={thesis}
            onChange={onChange}
            emptyText={
              thesis.status === "DEFENDED"
                ? "The thesis process is complete."
                : "Nothing is pending at this stage."
            }
          />
        </section>
      );
    case "requirements":
      return (
        <RequirementsPanel thesisId={thesis.thesis_id} canEdit={false} title="Graduation requirements" />
      );
    case "observations":
      return <ObservationsPanel thesis={thesis} user={user} onChanged={onChanged} alwaysShow />;
    case "plagiarism":
      return <SimilarityPanel thesis={thesis} user={user} onChanged={onChanged} />;
    case "history":
      return <StatusHistoryPanel thesis={thesis} />;
    case "defenses":
      return thesis.defense || thesis.status === "READY_FOR_DEFENSE" ? (
        <DefensePanel thesis={thesis} user={user} onChange={onChange} />
      ) : (
        <section className="panel">
          <h2>Oral defense</h2>
          <p className="muted">
            The defense will be scheduled by coordination once the thesis is ready for defense.
          </p>
        </section>
      );
  }
}

/** Left column: title and the vertical status stepper. Students get "Edit topic"
 * while the topic is proposed; professors get a switcher between their theses. */
function ThesisProgressPanel({
  user,
  summary,
  thesis,
  theses,
  section,
  editing,
  onEdit,
}: {
  user: User;
  summary?: ThesisSummary;
  thesis: ThesisDetail | null;
  theses: ThesisSummary[];
  section: ThesisSection;
  editing: boolean;
  onEdit: () => void;
}) {
  const navigate = useNavigate();
  const isStudent = user.role === "student";

  if (!summary) {
    return (
      <section className="panel">
        <h2>My thesis</h2>
        <p>You have not registered a thesis topic yet.</p>
        <Link to="/theses/new" className="button">
          Register my thesis topic
        </Link>
      </section>
    );
  }

  const status = thesis?.status ?? summary.status;
  // The student may change title and abstract until the topic is approved.
  const canEditTopic = isStudent && thesis !== null && status === "PROPOSED";

  return (
    <section className="panel">
      <h2>{isStudent ? "My thesis" : "Thesis"}</h2>
      {!isStudent && theses.length > 1 && (
        <label className="thesis-dashboard-switch">
          <span className="visually-hidden">Switch thesis</span>
          <select
            value={summary.thesis_id}
            onChange={(e) => navigate(`/theses/${e.target.value}?section=${section}`)}
          >
            {theses.map((t) => (
              <option key={t.thesis_id} value={t.thesis_id}>
                {t.student.full_name} — {t.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <p className="thesis-dashboard-title">{thesis?.title ?? summary.title}</p>
      {!isStudent && (
        <p className="muted small thesis-dashboard-meta">
          {summary.student.full_name}
          {summary.my_roles.length > 0 && <> · Your role: {summary.my_roles.join(", ")}</>}
        </p>
      )}
      <StatusStepper status={status} vertical />
      {canEditTopic && (
        <div className="thesis-dashboard-actions">
          <button type="button" className="button" onClick={onEdit} disabled={editing}>
            Edit topic
          </button>
        </div>
      )}
      {!isStudent && (
        <div className="thesis-dashboard-actions">
          <Link to="/theses" className="button button-secondary">
            Back to my theses
          </Link>
        </div>
      )}
    </section>
  );
}
