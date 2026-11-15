import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AuthProvider, useAuth } from "./auth";
import type { UserRole } from "./api";
import Layout from "./components/Layout";
import DefensesPage from "./pages/DefensesPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import PeoplePage from "./pages/PeoplePage";
import PeriodsPage from "./pages/PeriodsPage";
import ProfessorThesisPage from "./pages/ProfessorThesisPage";
import ProfilePage from "./pages/ProfilePage";
import ReportsPage from "./pages/ReportsPage";
import RegisterThesisPage from "./pages/RegisterThesisPage";
import RoomsPage from "./pages/RoomsPage";
import SettingsPage from "./pages/SettingsPage";
import StudentRequirementsPage from "./pages/StudentRequirementsPage";
import ThesesPage from "./pages/ThesesPage";
import ThesisDetailPage from "./pages/ThesisDetailPage";
import UsersPage from "./pages/UsersPage";
import "./styles.css";

/** Client-side guard for navigation only; the API enforces every permission itself. */
/** Professors see a thesis as a dashboard (like the student home); admins get the
 * full management page. */
function ThesisRoute() {
  const { user } = useAuth();
  return user?.role === "professor" ? <ProfessorThesisPage /> : <ThesisDetailPage />;
}

function RequireAuth({ children, roles }: { children: ReactNode; roles?: UserRole[] }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted center">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<HomePage />} />
            {/* Students follow their thesis from the home dashboard, not these pages. */}
            <Route
              path="theses"
              element={
                <RequireAuth roles={["admin", "professor"]}>
                  <ThesesPage />
                </RequireAuth>
              }
            />
            <Route path="theses/new" element={<RegisterThesisPage />} />
            <Route
              path="theses/:id"
              element={
                <RequireAuth roles={["admin", "professor"]}>
                  <ThesisRoute />
                </RequireAuth>
              }
            />
            <Route
              path="students"
              element={
                <RequireAuth roles={["admin"]}>
                  <PeoplePage kind="students" />
                </RequireAuth>
              }
            />
            <Route
              path="professors"
              element={
                <RequireAuth roles={["admin"]}>
                  <PeoplePage kind="professors" />
                </RequireAuth>
              }
            />
            <Route
              path="students/:id/requirements"
              element={
                <RequireAuth roles={["admin"]}>
                  <StudentRequirementsPage />
                </RequireAuth>
              }
            />
            <Route
              path="defenses"
              element={
                <RequireAuth roles={["admin", "professor"]}>
                  <DefensesPage />
                </RequireAuth>
              }
            />
            <Route
              path="profile"
              element={
                <RequireAuth roles={["admin"]}>
                  <ProfilePage />
                </RequireAuth>
              }
            />
            {(["overview", "workload", "grades", "rooms"] as const).map((view) => (
              <Route
                key={view}
                path={view === "overview" ? "reports" : `reports/${view}`}
                element={
                  <RequireAuth roles={["admin"]}>
                    <ReportsPage view={view} />
                  </RequireAuth>
                }
              />
            ))}
            <Route
              path="rooms"
              element={
                <RequireAuth roles={["admin"]}>
                  <RoomsPage />
                </RequireAuth>
              }
            />
            <Route
              path="settings"
              element={
                <RequireAuth roles={["admin"]}>
                  <SettingsPage />
                </RequireAuth>
              }
            />
            <Route
              path="periods"
              element={
                <RequireAuth roles={["admin"]}>
                  <PeriodsPage />
                </RequireAuth>
              }
            />
            <Route
              path="users"
              element={
                <RequireAuth roles={["admin"]}>
                  <UsersPage />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
