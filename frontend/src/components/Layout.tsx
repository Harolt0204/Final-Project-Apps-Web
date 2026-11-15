import { Link, NavLink, Outlet, useLocation } from "react-router";
import type { UserRole } from "../api";
import { useAuth } from "../auth";
import { ProfessorStats } from "./Stats";
import { isThesisDashboard, sectionFrom, THESIS_SECTIONS } from "./thesisSections";

interface Tab {
  to: string;
  label: string;
  roles: UserRole[];
  sub?: { to: string; label: string }[];
}

// Top tabs and sub-navigation, in the style of the MiYT academic portal.
const TABS: Tab[] = [
  { to: "/", label: "Home", roles: ["admin", "student"] },
  {
    to: "/theses",
    label: "Theses",
    roles: ["admin"],
    sub: [
      { to: "/theses", label: "Thesis list" },
      { to: "/theses/new", label: "Register thesis" },
    ],
  },
  { to: "/theses", label: "My Theses", roles: ["professor"] },
  {
    to: "/defenses",
    label: "Defenses",
    roles: ["admin"],
    sub: [
      { to: "/defenses", label: "Calendar" },
      { to: "/rooms", label: "Rooms" },
    ],
  },
  { to: "/defenses", label: "Defenses", roles: ["professor"] },
  {
    to: "/students",
    label: "Students",
    roles: ["admin"],
    sub: [
      { to: "/students", label: "Student list" },
      { to: "/students?new=1", label: "New student" },
    ],
  },
  {
    to: "/professors",
    label: "Professors",
    roles: ["admin"],
    sub: [
      { to: "/professors", label: "Professor list" },
      { to: "/professors?new=1", label: "New professor" },
    ],
  },
  { to: "/periods", label: "Periods", roles: ["admin"] },
  {
    to: "/reports",
    label: "Reports",
    roles: ["admin"],
    sub: [
      { to: "/reports", label: "Overview" },
      { to: "/reports/workload", label: "Tutor workload" },
      { to: "/reports/grades", label: "Grades by school" },
      { to: "/reports/rooms", label: "Room availability" },
    ],
  },
  { to: "/settings", label: "Settings", roles: ["admin"] },
  {
    to: "/users",
    label: "Users",
    roles: ["admin"],
    sub: [
      { to: "/users", label: "Accounts" },
      { to: "/users?new=1", label: "New account" },
    ],
  },
];

const ROLE_LABEL: Record<UserRole, string> = {
  admin: "Administrator",
  professor: "Professor",
  student: "Student",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  if (!user) return null;

  const tabs = TABS.filter((t) => t.roles.includes(user.role));
  // A tab is active on its own page and on the pages of its sub-menu (e.g. Rooms).
  const active = tabs.find((t) =>
    t.to === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(t.to) ||
        t.sub?.some((s) => location.pathname === s.to.split("?")[0]),
  );

  // Thesis dashboards (student home, professor thesis view): the sub-navigation picks
  // the section shown in the center panel, and the page uses the full window width.
  const dashboard = isThesisDashboard(user.role, location.pathname);
  const currentSection = sectionFrom(new URLSearchParams(location.search).get("section"));

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead-top">
          <span className="welcome">
            <strong>Welcome</strong> ({user.username}) · {ROLE_LABEL[user.role]}
          </span>
          <nav className="utility-links" aria-label="Account">
            <span>Sistema de Gestión de Tesis</span>
            {/* Only coordination manages its account here and uses the API reference. */}
            {user.role === "admin" && (
              <>
                <Link to="/profile">My Profile</Link>
                <a href="/docs" target="_blank" rel="noreferrer">
                  API Docs
                </a>
              </>
            )}
            <button type="button" className="link-button" onClick={logout}>
              Log Out
            </button>
          </nav>
        </div>
        <div className="brand">
          <span className="brand-title">Thesis Management</span>
          <span className="brand-sub">Yachay Tech University</span>
        </div>
        {user.role === "professor" && <ProfessorStats />}
        <nav className="tabs" aria-label="Main">
          {tabs.map((t) => (
            <NavLink
              key={t.label}
              to={t.to}
              end={t.to === "/"}
              className={({ isActive }) => (isActive || t === active ? "tab active" : "tab")}
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <nav className={dashboard ? "subnav subnav-sections" : "subnav"} aria-label="Section">
        {dashboard &&
          THESIS_SECTIONS.map((s) => (
            <Link
              key={s.key}
              to={`${location.pathname}?section=${s.key}`}
              className={s.key === currentSection ? "active" : undefined}
              aria-current={s.key === currentSection ? "page" : undefined}
            >
              {s.label}
            </Link>
          ))}
        {active?.sub?.map((s) => (
          // Compared with the query string too, so "/students?new=1" and "/students"
          // are not both highlighted.
          <Link
            key={s.to}
            to={s.to}
            className={location.pathname + location.search === s.to ? "active" : undefined}
          >
            {s.label}
          </Link>
        ))}
      </nav>
      <div className={dashboard ? "page page-wide" : "page"}>
        <aside className="sidebar" aria-hidden="true" />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
