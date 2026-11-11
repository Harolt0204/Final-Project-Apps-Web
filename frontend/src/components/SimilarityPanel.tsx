import { useEffect, useState, type FormEvent } from "react";
import { api, localDate, type SimilarityCheck, type ThesisDetail, type User } from "../api";

const RECORDABLE = ["THESIS_II", "IN_REVIEW"];

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

/** Similarity (plagiarism) check history (FR-07). Admins record new checks; the verdict
 * is computed by the API from the threshold in force. */
export default function SimilarityPanel({
  thesis,
  user,
  onChanged,
}: {
  thesis: ThesisDetail;
  user: User;
  onChanged: () => void;
}) {
  const [data, setData] = useState<{ threshold: string; checks: SimilarityCheck[] } | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .similarity(thesis.thesis_id)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [thesis]);

  const canRecord = user.role === "admin" && RECORDABLE.includes(thesis.status);
  const latest = data?.checks.at(-1);

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>Similarity check</h2>
        {canRecord && !showForm && (
          <button type="button" className="button button-small" onClick={() => setShowForm(true)}>
            Record check
          </button>
        )}
      </div>
      {data && (
        <p className="muted small">Maximum similarity accepted: {Number(data.threshold)}%</p>
      )}
      {error && <p className="notice notice-error">{error}</p>}

      {showForm && (
        <SimilarityForm
          thesisId={thesis.thesis_id}
          onCancel={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            onChanged();
          }}
        />
      )}

      {data && data.checks.length === 0 && <p className="muted">No similarity check recorded yet.</p>}
      {latest && (
        <div className={`similarity-latest ${latest.verdict === "ACCEPTED" ? "ok" : "bad"}`}>
          <span className="similarity-value">{Number(latest.similarity_percentage)}%</span>
          <span>
            <strong>{latest.verdict === "ACCEPTED" ? "Accepted" : "Above the threshold"}</strong>
            <br />
            <span className="muted small">
              {latest.tool} · {formatDate(latest.checked_at)}
            </span>
          </span>
        </div>
      )}
      {data && data.checks.length > 0 && (
        <div className="table-wrap">
          <table className="grid compact">
            <thead>
              <tr>
                <th>Date</th>
                <th>Similarity</th>
                <th>Threshold</th>
                <th>Verdict</th>
                <th>Tool</th>
                <th>Report</th>
              </tr>
            </thead>
            <tbody>
              {[...data.checks].reverse().map((c) => (
                <tr key={c.check_id} title={c.notes ?? ""}>
                  <td>{formatDate(c.checked_at)}</td>
                  <td>{Number(c.similarity_percentage)}%</td>
                  <td>{Number(c.threshold_applied)}%</td>
                  <td>
                    <span className={`badge ${c.verdict === "ACCEPTED" ? "badge-defended" : "badge-rejected"}`}>
                      {c.verdict === "ACCEPTED" ? "Accepted" : "Rejected"}
                    </span>
                  </td>
                  <td>{c.tool}</td>
                  <td>
                    {c.report_url ? (
                      <a href={c.report_url} target="_blank" rel="noreferrer noopener">
                        Open
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SimilarityForm({
  thesisId,
  onCancel,
  onSaved,
}: {
  thesisId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const today = localDate();
  const [percentage, setPercentage] = useState("");
  const [tool, setTool] = useState("Turnitin");
  const [date, setDate] = useState(today);
  const [reportUrl, setReportUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.addSimilarity(thesisId, {
        similarity_percentage: percentage,
        tool,
        // Today means "now"; another day is recorded at noon of that day.
        checked_at: date === today ? undefined : `${date}T12:00:00`,
        report_url: reportUrl || undefined,
        notes: notes || undefined,
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <form className="form-grid inline-form" onSubmit={submit}>
      <label>
        Similarity (%)
        <input type="number" min={0} max={100} step="0.01" value={percentage} onChange={(e) => setPercentage(e.target.value)} required />
      </label>
      <label>
        Tool
        <input value={tool} onChange={(e) => setTool(e.target.value)} maxLength={100} required />
      </label>
      <label>
        Report date
        <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} required />
      </label>
      <label>
        Report URL (optional)
        <input type="url" value={reportUrl} onChange={(e) => setReportUrl(e.target.value)} maxLength={500} />
      </label>
      <label className="full">
        Notes (optional)
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={2000} />
      </label>
      {error && <p className="notice notice-error full">{error}</p>}
      <div className="actions full">
        <button type="submit" className="button button-small">
          Save check
        </button>
        <button type="button" className="button button-small button-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
