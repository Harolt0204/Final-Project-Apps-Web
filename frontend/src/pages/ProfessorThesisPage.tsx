import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, type ThesisSummary } from "../api";
import ThesisDashboard from "../components/ThesisDashboard";

/** A professor's view of one of their theses, laid out like the student home. */
export default function ProfessorThesisPage() {
  const { id } = useParams();
  const [theses, setTheses] = useState<ThesisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .theses()
      .then(setTheses)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="notice notice-error">{error}</p>;
  if (!theses) return <p className="muted">Loading…</p>;

  const summary = theses.find((t) => t.thesis_id === Number(id));
  if (!summary) {
    return (
      <section className="panel">
        <p className="notice notice-error">Thesis not found, or you do not take part in it.</p>
        <Link to="/theses">Back to my theses</Link>
      </section>
    );
  }
  return <ThesisDashboard summary={summary} theses={theses} />;
}
