import { useState, type FormEvent } from "react";
import { api, tokenStore } from "../api";
import { useAuth } from "../auth";

const ROLE_LABEL = { admin: "Administrator", professor: "Professor", student: "Student" };

/** The user's own account: details and password change. */
export default function ProfilePage() {
  const { user } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    if (next !== repeat) {
      setError("The new passwords do not match");
      return;
    }
    try {
      const { access_token } = await api.changePassword(current, next);
      // The old token is revoked; keep this session with the new one.
      tokenStore.set(access_token);
      setCurrent("");
      setNext("");
      setRepeat("");
      setMessage("Password changed. Your other sessions have been closed.");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <section className="panel">
        <h1>My profile</h1>
        <dl className="facts">
          <dt>Name</dt>
          <dd>{user.display_name}</dd>
          <dt>E-mail</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd>{ROLE_LABEL[user.role]}</dd>
        </dl>
      </section>
      <section className="panel">
        <h2>Change password</h2>
        <form className="form-grid" onSubmit={submit}>
          <label>
            Current password
            <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" required />
          </label>
          <label>
            New password (min. 12 characters)
            <input
              type="password"
              minLength={12}
              maxLength={72}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <label>
            Repeat the new password
            <input
              type="password"
              minLength={12}
              maxLength={72}
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          {message && <p className="notice notice-ok full">{message}</p>}
          {error && <p className="notice notice-error full">{error}</p>}
          <div className="actions full">
            <button type="submit" className="button">
              Change password
            </button>
          </div>
        </form>
      </section>
    </>
  );
}
