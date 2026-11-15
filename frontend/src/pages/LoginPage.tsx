import { useState, type FormEvent } from "react";
import { Navigate } from "react-router";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { user, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-banner">
          <img src="/logo.png" alt="Yachay Tech" className="login-logo" />
          <div className="login-brand">
            <span className="brand-title">Thesis Management</span>
            <span className="brand-sub">Yachay Tech</span>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <h1>Log In</h1>
          <label>
            User Name
            <input
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="name.lastname"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && (
            <p className="notice notice-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button" disabled={busy}>
            {busy ? "Signing in…" : "Log In"}
          </button>
        </form>
      </div>
    </div>
  );
}
