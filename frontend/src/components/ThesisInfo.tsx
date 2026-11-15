import { STATUS_LABEL, type ThesisDetail } from "../api";

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

/** Student, school, periods and abstract of a thesis. */
export function GeneralInfoPanel({ thesis }: { thesis: ThesisDetail }) {
  return (
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
  );
}

/** Read-only tutor and co-tutor of a thesis. */
export function TutorFacts({ thesis }: { thesis: ThesisDetail }) {
  return (
    <dl className="facts">
      <dt>Tutor</dt>
      <dd>{thesis.tutors.find((t) => t.role === "Tutor")?.professor.full_name ?? "Not assigned"}</dd>
      <dt>Co-tutor</dt>
      <dd>{thesis.tutors.find((t) => t.role === "Co-Tutor")?.professor.full_name ?? "—"}</dd>
    </dl>
  );
}

/** Every status change of the thesis, newest first. */
export function StatusHistoryPanel({ thesis }: { thesis: ThesisDetail }) {
  return (
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
  );
}
