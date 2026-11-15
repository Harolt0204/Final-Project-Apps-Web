import { STATUS_FLOW, STATUS_LABEL, type ThesisStatus } from "../api";

export function StatusBadge({ status }: { status: ThesisStatus }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{STATUS_LABEL[status]}</span>;
}

/** Where the thesis stands in the graduation workflow (proposal, Fig. 1). */
export function StatusStepper({ status, vertical = false }: { status: ThesisStatus; vertical?: boolean }) {
  if (status === "REJECTED") {
    return <p className="notice notice-error">This thesis topic was rejected.</p>;
  }
  const current = STATUS_FLOW.indexOf(status);
  return (
    <ol className={vertical ? "stepper stepper-vertical" : "stepper"}>
      {STATUS_FLOW.map((step, i) => (
        <li
          key={step}
          className={i < current ? "done" : i === current ? "current" : ""}
          aria-current={i === current ? "step" : undefined}
        >
          <span className="dot">{i < current ? "✓" : i + 1}</span>
          <span className="step-label">{STATUS_LABEL[step]}</span>
        </li>
      ))}
    </ol>
  );
}
