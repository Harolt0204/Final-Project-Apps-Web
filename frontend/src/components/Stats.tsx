import { useEffect, useState } from "react";
import { api, type ThesisSummary } from "../api";

export function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

/** How many theses the professor takes part in, per role. Shown in the masthead. */
export function ProfessorStats() {
  const [theses, setTheses] = useState<ThesisSummary[] | null>(null);

  useEffect(() => {
    api
      .theses()
      .then(setTheses)
      .catch(() => setTheses(null));
  }, []);

  const count = (role: string) => (theses ? theses.filter((t) => t.my_roles.includes(role)).length : "–");

  return (
    <div className="stats masthead-stats" aria-label="My participation">
      <Stat label="As tutor" value={count("Tutor")} />
      <Stat label="As co-tutor" value={count("Co-Tutor")} />
      <Stat label="As committee president" value={count("President")} />
      <Stat label="As committee member" value={count("Committee")} />
    </div>
  );
}
