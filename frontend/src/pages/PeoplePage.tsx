import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import {
  api,
  personId,
  type PersonInput,
  type PersonKind,
  type PersonRecord,
  type School,
  type Student,
} from "../api";

const LABEL: Record<PersonKind, { plural: string; singular: string }> = {
  students: { plural: "Students", singular: "student" },
  professors: { plural: "Professors", singular: "professor" },
};

/** Administration of students or professors: search, create, edit, delete. */
export default function PeoplePage({ kind }: { kind: PersonKind }) {
  const [people, setPeople] = useState<PersonRecord[] | null>(null);
  const [schools, setSchools] = useState<School[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();

  const editId = params.get("edit");
  const creating = params.get("new") === "1";
  const editing = editId ? people?.find((p) => personId(p) === Number(editId)) : undefined;

  const load = useCallback(
    (q = "") =>
      api
        .people(kind, q)
        .then(setPeople)
        .catch((e: Error) => setError(e.message)),
    [kind],
  );

  useEffect(() => {
    setPeople(null);
    setQuery("");
    load();
    api.schools().then(setSchools).catch(() => setSchools([]));
  }, [load]);

  async function remove(p: PersonRecord) {
    if (!window.confirm(`Delete ${p.full_name}? This cannot be undone.`)) return;
    try {
      await api.deletePerson(kind, personId(p));
      load(query);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const closeForm = () => setParams({});

  return (
    <>
      {(creating || editing) && (
        <PersonForm
          key={editId ?? "new"}
          kind={kind}
          schools={schools}
          person={editing}
          onCancel={closeForm}
          onSaved={() => {
            closeForm();
            load(query);
          }}
        />
      )}

      <section className="panel">
        <div className="panel-title">
          <h1>{LABEL[kind].plural}</h1>
          {!creating && (
            <button type="button" className="button" onClick={() => setParams({ new: "1" })}>
              New {LABEL[kind].singular}
            </button>
          )}
        </div>
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            load(query);
          }}
        >
          <input
            type="search"
            placeholder="Search by name, e-mail or national id"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search"
          />
          <button type="submit" className="button button-secondary">
            Search
          </button>
        </form>

        {error && <p className="notice notice-error">{error}</p>}
        {!people && !error && <p className="muted">Loading…</p>}
        {people?.length === 0 && <p className="muted">No {LABEL[kind].plural.toLowerCase()} found.</p>}
        {people && people.length > 0 && (
          <div className="table-wrap">
            <table className="grid">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>National ID</th>
                  <th>E-mail</th>
                  <th>School</th>
                  <th>Account</th>
                  {kind === "students" && <th>Thesis</th>}
                  <th />
                </tr>
              </thead>
              <tbody>
                {people.map((p) => (
                  <tr key={personId(p)}>
                    <td>{p.full_name}</td>
                    <td>{p.national_id ?? "—"}</td>
                    <td>{p.email}</td>
                    <td>{p.school?.code ?? "—"}</td>
                    <td>{p.has_account ? "Yes" : "No"}</td>
                    {kind === "students" && <td>{(p as Student).has_thesis ? "Registered" : "—"}</td>}
                    <td className="row-actions">
                      {kind === "students" && (
                        <Link
                          to={`/students/${personId(p)}/requirements`}
                          className="button button-small button-secondary"
                        >
                          Requirements
                        </Link>
                      )}
                      <button
                        type="button"
                        className="button button-small button-secondary"
                        onClick={() => setParams({ edit: String(personId(p)) })}
                      >
                        Edit
                      </button>
                      <button type="button" className="button button-small button-danger" onClick={() => remove(p)}>
                        Delete
                      </button>
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

function PersonForm({
  kind,
  schools,
  person,
  onCancel,
  onSaved,
}: {
  kind: PersonKind;
  schools: School[];
  person?: PersonRecord;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    first_name: person?.first_name ?? "",
    last_name: person?.last_name ?? "",
    national_id: person?.national_id ?? "",
    email: person?.email ?? "",
    school_id: person?.school ? String(person.school.school_id) : "",
    institution: person?.institution ?? "Yachay Tech",
    phone: (person as Student | undefined)?.phone ?? "",
  });
  const [createAccount, setCreateAccount] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (field: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const data: PersonInput = {
      first_name: form.first_name,
      last_name: form.last_name,
      email: form.email,
      national_id: form.national_id || null,
      school_id: form.school_id ? Number(form.school_id) : null,
      institution: form.institution || null,
    };
    if (kind === "students") data.phone = form.phone || null;
    try {
      if (person) {
        await api.updatePerson(kind, personId(person), data);
      } else {
        if (createAccount) data.account_password = password;
        await api.createPerson(kind, data);
      }
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>{person ? `Edit ${person.full_name}` : `New ${LABEL[kind].singular}`}</h2>
      <form className="form-grid" onSubmit={submit}>
        <label>
          First name
          <input value={form.first_name} onChange={set("first_name")} required maxLength={100} />
        </label>
        <label>
          Last name
          <input value={form.last_name} onChange={set("last_name")} required maxLength={100} />
        </label>
        <label>
          National ID (cédula or passport)
          <input value={form.national_id} onChange={set("national_id")} pattern="[A-Za-z0-9\-]{5,20}" />
        </label>
        <label>
          Institutional e-mail
          <input type="email" value={form.email} onChange={set("email")} required maxLength={100} />
        </label>
        <label>
          School
          <select value={form.school_id} onChange={set("school_id")}>
            <option value="">—</option>
            {schools.map((s) => (
              <option key={s.school_id} value={s.school_id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Institution
          <input value={form.institution} onChange={set("institution")} maxLength={100} />
        </label>
        {kind === "students" && (
          <label>
            Phone
            <input value={form.phone} onChange={set("phone")} pattern="[0-9 +()\-]{6,20}" />
          </label>
        )}

        {!person && (
          <fieldset className="full fieldset">
            <label className="checkbox">
              <input type="checkbox" checked={createAccount} onChange={(e) => setCreateAccount(e.target.checked)} />
              Create a login account with this e-mail
            </label>
            {createAccount && (
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
            )}
          </fieldset>
        )}

        {error && <p className="notice notice-error full">{error}</p>}
        <div className="actions full">
          <button type="submit" className="button" disabled={busy}>
            {person ? "Save changes" : `Create ${LABEL[kind].singular}`}
          </button>
          <button type="button" className="button button-secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  );
}
