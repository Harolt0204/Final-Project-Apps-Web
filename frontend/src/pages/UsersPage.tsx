import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { api, personId, type PersonRecord, type User, type UserRole } from "../api";
import { useAuth } from "../auth";

export default function UsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const showForm = params.get("new") === "1";

  const load = () => api.users().then(setUsers).catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function toggleActive(u: User) {
    try {
      const updated = await api.updateUser(u.user_id, { is_active: !u.is_active });
      setUsers((list) => list?.map((x) => (x.user_id === updated.user_id ? updated : x)) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      {showForm && (
        <NewUserForm
          onCancel={() => setParams({})}
          onCreated={() => {
            setParams({});
            load();
          }}
        />
      )}
      <section className="panel">
        <h1>User accounts</h1>
        {error && <p className="notice notice-error">{error}</p>}
        {!users && !error && <p className="muted">Loading…</p>}
        {users && (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>E-mail</th>
                  <th>Role</th>
                  <th>Last login</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className={u.is_active ? "" : "inactive"}>
                    <td>{u.display_name}</td>
                    <td>{u.email}</td>
                    <td className="capitalize">{u.role}</td>
                    <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString("en-GB") : "Never"}</td>
                    <td>{u.is_active ? "Active" : "Disabled"}</td>
                    <td>
                      {u.user_id !== me?.user_id && (
                        <button type="button" className="button button-small" onClick={() => toggleActive(u)}>
                          {u.is_active ? "Disable" : "Enable"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function NewUserForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("professor");
  const [linkedId, setLinkedId] = useState("");
  const [candidates, setCandidates] = useState<PersonRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Only people without an account can receive one; the e-mail defaults to theirs.
  useEffect(() => {
    setLinkedId("");
    setCandidates([]);
    if (role === "admin") return;
    api
      .people(role === "student" ? "students" : "professors")
      .then((all) => setCandidates(all.filter((p) => !p.has_account)))
      .catch((e: Error) => setError(e.message));
  }, [role]);

  function choosePerson(value: string) {
    setLinkedId(value);
    const person = candidates.find((p) => personId(p) === Number(value));
    if (person) setEmail(person.email);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const id = linkedId ? Number(linkedId) : undefined;
    try {
      await api.createUser({
        email,
        password,
        role,
        student_id: role === "student" ? id : undefined,
        professor_id: role === "professor" ? id : undefined,
      });
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>New account</h2>
      <form className="form-grid" onSubmit={submit}>
        <label>
          E-mail
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Initial password (min. 12 characters)
          <input
            type="password"
            minLength={12}
            maxLength={72}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            <option value="professor">Professor</option>
            <option value="student">Student</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        {role !== "admin" && (
          <label>
            {role === "student" ? "Student" : "Professor"} without an account
            <select value={linkedId} onChange={(e) => choosePerson(e.target.value)} required>
              <option value="">{candidates.length ? "Select…" : "Everyone already has an account"}</option>
              {candidates.map((p) => (
                <option key={personId(p)} value={personId(p)}>
                  {p.full_name}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && <p className="notice notice-error full">{error}</p>}
        <div className="actions full">
          <button type="submit" className="button">
            Create account
          </button>
          <button type="button" className="button button-secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
