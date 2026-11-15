/** Sections of the thesis dashboard's center panel (student home, professor thesis
 * view), chosen from the sub-navigation bar. The choice lives in the URL
 * (`?section=…`), so switching does not reload the page and the browser's back button
 * and a refresh keep it. */
export const THESIS_SECTIONS = [
  { key: "next-steps", label: "Next Steps" },
  { key: "requirements", label: "Requirements" },
  { key: "observations", label: "Observations" },
  { key: "plagiarism", label: "Plagiarism" },
  { key: "history", label: "History" },
  { key: "defenses", label: "Defenses" },
] as const;

export type ThesisSection = (typeof THESIS_SECTIONS)[number]["key"];

export const DEFAULT_SECTION: ThesisSection = "next-steps";

export function sectionFrom(value: string | null): ThesisSection {
  return THESIS_SECTIONS.some((s) => s.key === value) ? (value as ThesisSection) : DEFAULT_SECTION;
}

/** Pages shown as a thesis dashboard: the student home and a professor's thesis. */
export function isThesisDashboard(role: string, pathname: string): boolean {
  return (role === "student" && pathname === "/") || (role === "professor" && /^\/theses\/\d+$/.test(pathname));
}
