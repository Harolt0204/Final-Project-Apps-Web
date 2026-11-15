import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router";
import { api, type ThesisSummary } from "../api";
import { useAuth } from "../auth";
import { Stat } from "../components/Stats";
import { StatusBadge } from "../components/Status";
import ThesisDashboard from "../components/ThesisDashboard";

export default function HomePage() {
  const { user } = useAuth();
  const [theses, setTheses] = useState<ThesisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .theses()
      .then(setTheses)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (!user) return null;
  // Professors have no home page: their work starts at My Theses.
  if (user.role === "professor") return <Navigate to="/theses" replace />;

  return (
    <>
      {error && <p className="notice notice-error">{error}</p>}
      {!theses && !error && <p className="muted">Loading…</p>}

      {theses && user.role === "student" && <ThesisDashboard summary={theses[0]} />}
      {theses && user.role === "admin" && <AdminHome theses={theses} />}
    </>
  );
}

function AdminHome({ theses }: { theses: ThesisSummary[] }) {
  const byStatus = theses.reduce<Record<string, number>>((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <>
      <div className="stats">
        <Stat label="Theses" value={theses.length} />
        <Stat label="In committee review" value={byStatus.IN_REVIEW ?? 0} />
        <Stat
          label="Ready for defense"
          value={byStatus.READY_FOR_DEFENSE ?? 0}
        />
        <Stat label="Defended" value={byStatus.DEFENDED ?? 0} />
      </div>
      <ul className="quick-links">
        <li>
          <Link to="/theses">All theses</Link>
        </li>
        <li>
          <Link to="/theses/new">Register a thesis</Link>
        </li>
        <li>
          <Link to="/students">Students</Link> ·{" "}
          <Link to="/professors">Professors</Link> ·{" "}
          <Link to="/periods">Academic periods</Link>
        </li>
        <li>
          <Link to="/users">User accounts</Link>
        </li>
      </ul>
      <section className="panel">
        <h2>Recently updated</h2>
        <ul className="plain-list">
          {[...theses]
            .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
            .slice(0, 5)
            .map((t) => (
              <li key={t.thesis_id}>
                <Link to={`/theses/${t.thesis_id}`}>{t.title}</Link>{" "}
                <StatusBadge status={t.status} />
              </li>
            ))}
        </ul>
      </section>
    </>
  );
}
