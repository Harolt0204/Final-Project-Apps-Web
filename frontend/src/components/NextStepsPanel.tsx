import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, STATUS_FLOW, STATUS_LABEL, type ThesisDetail, type WorkflowOption } from "../api";
import type { ThesisSection } from "./thesisSections";

const ACTOR_LABEL: Record<string, string> = { admin: "coordination", tutor: "your tutor" };

/** Section of the student home where each kind of blocker can be followed up. */
function sectionFor(blocker: string): ThesisSection | null {
  const text = blocker.toLowerCase();
  if (text.includes("observation")) return "observations";
  if (text.includes("similarity")) return "plagiarism";
  if (text.includes("requirement")) return "requirements";
  return null;
}

/** The student's view of the workflow: only the step forward (not "return for
 * changes" or "reject"), who takes it and what is still missing for it. */
export default function NextStepsPanel({ thesis }: { thesis: ThesisDetail }) {
  const [next, setNext] = useState<WorkflowOption | null | undefined>(undefined);

  useEffect(() => {
    const forward = STATUS_FLOW[STATUS_FLOW.indexOf(thesis.status) + 1];
    api
      .workflow(thesis.thesis_id)
      .then((w) => setNext(w.options.find((o) => o.to_status === forward) ?? null))
      .catch(() => setNext(null));
  }, [thesis]);

  return (
    <section className="panel">
      <h2>Next steps</h2>
      <p className="muted">
        Current stage: <strong>{STATUS_LABEL[thesis.status]}</strong>
      </p>
      <NextStep thesis={thesis} next={next} />
    </section>
  );
}

function NextStep({ thesis, next }: { thesis: ThesisDetail; next: WorkflowOption | null | undefined }) {
  if (thesis.status === "DEFENDED") {
    return (
      <div className="next-step next-step-done">
        <strong>Process completed</strong>
        <p>Your thesis has been defended.</p>
      </div>
    );
  }
  if (thesis.status === "REJECTED") {
    return <p className="notice notice-error">This thesis topic was rejected. Contact coordination.</p>;
  }
  if (next === undefined) return <p className="muted">Loading…</p>;
  if (next === null) return <p className="muted">There is no step you can follow up right now.</p>;

  const by = next.actors.map((a) => ACTOR_LABEL[a] ?? a).join(" or ");
  return (
    <div className={`next-step ${next.blockers.length ? "" : "next-step-ready"}`}>
      <span className="next-step-kicker">Next step</span>
      <strong>{STATUS_LABEL[next.to_status]}</strong>
      <span className="muted small"> · by {by}</span>
      {next.blockers.length === 0 ? (
        <p className="ok-line">All prerequisites are met. Waiting for {by}.</p>
      ) : (
        <>
          <p className="next-step-missing">Still missing:</p>
          <ul className="blockers">
            {next.blockers.map((b) => {
              const section = sectionFor(b);
              return <li key={b}>{section ? <Link to={`/?section=${section}`}>{b}</Link> : b}</li>;
            })}
          </ul>
        </>
      )}
    </div>
  );
}
