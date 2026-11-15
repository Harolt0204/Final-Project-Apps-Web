import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { api, STATUS_FLOW, STATUS_LABEL, type ThesisStatus, type ThesisSummary } from "../api";
import { useAuth } from "../auth";
import { StatusBadge } from "../components/Status";

export default function ThesesPage() {
  const { user } = useAuth();
  const [theses, setTheses] = useState<ThesisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ThesisStatus | "">("");

  useEffect(() => {
    api.theses().then(setTheses).catch((e: Error) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (theses ?? []).filter(
      (t) =>
        (!status || t.status === status) &&
        (!q || t.title.toLowerCase().includes(q) || t.student.full_name.toLowerCase().includes(q)),
    );
  }, [theses, query, status]);

  return (
    <section className="panel">
      <div className="panel-title">
        <h1>{user?.role === "admin" ? "All theses" : "My theses"}</h1>
        {user?.role === "admin" && (
          <Link to="/theses/new" className="button">
            Register thesis
          </Link>
        )}
      </div>
      {user?.role === "professor" && (
        <p className="muted">Only theses where you are tutor, co-tutor or committee member are listed.</p>
      )}

      <div className="filters">
        <input
          type="search"
          placeholder="Search by title or student"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value as ThesisStatus | "")} aria-label="Status">
          <option value="">All statuses</option>
          {[...STATUS_FLOW, "REJECTED" as const].map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="notice notice-error">{error}</p>}
      {!theses && !error && <p className="muted">Loading…</p>}
      {theses && filtered.length === 0 && <p className="muted">No theses to show.</p>}

      {filtered.length > 0 && (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Title</th>
                <th>Student</th>
                <th>Tutor</th>
                <th>Committee</th>
                <th>Status</th>
                {user?.role === "professor" && <th>My role</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.thesis_id}>
                  <td>
                    <Link to={`/theses/${t.thesis_id}`}>{t.title}</Link>
                  </td>
                  <td>{t.student.full_name}</td>
                  <td>{t.tutors.find((x) => x.role === "Tutor")?.professor.full_name ?? "—"}</td>
                  <td>{t.reviewers.length}/3</td>
                  <td>
                    <StatusBadge status={t.status} />
                  </td>
                  {user?.role === "professor" && <td>{t.my_roles.join(", ")}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
