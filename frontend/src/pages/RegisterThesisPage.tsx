import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api, type Period, type Student } from "../api";
import { useAuth } from "../auth";

/** Topic registration (FR-03). Students register their own thesis; admins choose the student. */
export default function RegisterThesisPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [title, setTitle] = useState("");
  const [abstract, setAbstract] = useState("");
  const [studentId, setStudentId] = useState("");
  const [periodIds, setPeriodIds] = useState<number[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [periods, setPeriods] = useState<Period[]>([]);
  const [existing, setExisting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isAdmin) {
      api.people<Student>("students").then((all) => setStudents(all.filter((s) => !s.has_thesis)));
      api.periods().then(setPeriods);
    } else {
      // A student who already registered goes back to the home dashboard.
      api.theses().then((t) => setExisting(t[0]?.thesis_id ?? null));
    }
  }, [isAdmin]);

  if (user?.role === "professor") return <Navigate to="/theses" replace />;
  // A student's thesis lives on the home dashboard; admins go to the thesis page.
  if (existing) return <Navigate to="/" replace />;
  const back = isAdmin ? "/theses" : "/";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const thesis = await api.registerThesis({
        title,
        abstract: abstract || null,
        ...(isAdmin ? { student_id: Number(studentId), period_ids: periodIds } : {}),
      });
      navigate(isAdmin ? `/theses/${thesis.thesis_id}` : "/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const togglePeriod = (id: number) =>
    setPeriodIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  return (
    <section className="panel">
      <p className="breadcrumb">
        <Link to={back}>{isAdmin ? "Theses" : "Home"}</Link> › Register
      </p>
      <h1>Register thesis topic</h1>
      <p className="muted">
        The topic starts as <em>proposed</em>. {isAdmin ? "The student" : "You"} can edit it until it is approved.
      </p>
      <form className="form-grid" onSubmit={submit}>
        {isAdmin && (
          <label className="full">
            Student (only students without a thesis are listed)
            <select value={studentId} onChange={(e) => setStudentId(e.target.value)} required>
              <option value="">Select a student…</option>
              {students.map((s) => (
                <option key={s.student_id} value={s.student_id}>
                  {s.full_name} — {s.email}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="full">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} minLength={5} maxLength={255} required />
        </label>
        <label className="full">
          Abstract
          <textarea value={abstract} onChange={(e) => setAbstract(e.target.value)} rows={6} maxLength={5000} />
        </label>
        {isAdmin && periods.length > 0 && (
          <fieldset className="full fieldset">
            <legend>Academic periods (leave empty to use the period in course)</legend>
            {periods.map((p) => (
              <label key={p.period_id} className="checkbox">
                <input type="checkbox" checked={periodIds.includes(p.period_id)} onChange={() => togglePeriod(p.period_id)} />
                {p.name}
              </label>
            ))}
          </fieldset>
        )}
        {error && <p className="notice notice-error full">{error}</p>}
        <div className="actions full">
          <button type="submit" className="button" disabled={busy}>
            Register topic
          </button>
          <Link to={back} className="button button-secondary">
            Cancel
          </Link>
        </div>
      </form>
    </section>
  );
}
