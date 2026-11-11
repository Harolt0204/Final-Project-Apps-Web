import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, type ThesisSummary } from "../api";
import { useAuth } from "../auth";
import RequirementsPanel from "../components/RequirementsPanel";
import { StatusBadge, StatusStepper } from "../components/Status";

export default function HomePage() {
  const { user } = useAuth();
  const [theses, setTheses] = useState<ThesisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.theses().then(setTheses).catch((e: Error) => setError(e.message));
  }, []);

  if (!user) return null;

  return (
    <>
      <section className="panel hero">
        <div className="panel-header" />
        <div className="hero-body">
          <div>
            <h1>Thesis Management</h1>
            <p>Undergraduate thesis and graduation process — from topic registration to the final defense grade.</p>
          </div>
        </div>
        <div className="panel-footer">
          <strong>{user.display_name}</strong>
        </div>
      </section>

      {error && <p className="notice notice-error">{error}</p>}
      {!theses && !error && <p className="muted">Loading…</p>}

      {theses && user.role === "student" && <StudentHome thesis={theses[0]} />}
      {user.role === "student" && user.student_id && (
        <RequirementsPanel studentId={user.student_id} canEdit={false} title="My graduation requirements" />
      )}
      {theses && user.role === "professor" && <ProfessorHome theses={theses} />}
      {theses && user.role === "admin" && <AdminHome theses={theses} />}
    </>
  );
}

function StudentHome({ thesis }: { thesis?: ThesisSummary }) {
  if (!thesis) {
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
  return (
    <section className="panel">
      <h2>My thesis</h2>
      <p>
        <Link to={`/theses/${thesis.thesis_id}`}>{thesis.title}</Link>
      </p>
      <StatusStepper status={thesis.status} />
    </section>
  );
}

function ProfessorHome({ theses }: { theses: ThesisSummary[] }) {
  const count = (role: string) => theses.filter((t) => t.my_roles.includes(role)).length;
  return (
    <>
      <div className="stats">
        <Stat label="As tutor" value={count("Tutor")} />
        <Stat label="As co-tutor" value={count("Co-Tutor")} />
        <Stat label="As committee president" value={count("President")} />
        <Stat label="As committee member" value={count("Committee")} />
      </div>
      <ul className="quick-links">
        <li>
          <Link to="/theses">View my theses</Link>
        </li>
      </ul>
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
        <Stat label="Ready for defense" value={byStatus.READY_FOR_DEFENSE ?? 0} />
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
          <Link to="/students">Students</Link> · <Link to="/professors">Professors</Link> ·{" "}
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
                <Link to={`/theses/${t.thesis_id}`}>{t.title}</Link> <StatusBadge status={t.status} />
              </li>
            ))}
        </ul>
      </section>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}
