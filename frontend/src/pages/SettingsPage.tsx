import { useEffect, useState, type FormEvent } from "react";
import { api, type RequirementType } from "../api";

const SIMILARITY_KEY = "similarity_max_percentage";

/** Administration of configurable rules: similarity threshold and requirement catalog. */
export default function SettingsPage() {
  return (
    <>
      <ThresholdSetting />
      <RequirementCatalog />
    </>
  );
}

function ThresholdSetting() {
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .settings()
      .then((all) => {
        const setting = all.find((s) => s.setting_key === SIMILARITY_KEY);
        if (setting) {
          setValue(String(Number(setting.value)));
          setSaved(setting.value);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const setting = await api.updateSetting(SIMILARITY_KEY, value);
      setSaved(setting.value);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h1>Settings</h1>
      <h2>Similarity check</h2>
      <form className="form-grid" onSubmit={submit}>
        <label>
          Maximum similarity accepted (%)
          <input type="number" min={0} max={100} step="0.01" value={value} onChange={(e) => setValue(e.target.value)} required />
        </label>
        <div className="actions align-end">
          <button type="submit" className="button">
            Save
          </button>
        </div>
        <p className="muted small full">
          Applies to new checks only; each recorded check keeps the threshold that was in force.
          {saved ? ` Current value: ${Number(saved)}%.` : ""}
        </p>
        {error && <p className="notice notice-error full">{error}</p>}
      </form>
    </section>
  );
}

function RequirementCatalog() {
  const [types, setTypes] = useState<RequirementType[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const load = () =>
    api
      .requirementTypes(true)
      .then(setTypes)
      .catch((e: Error) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  async function toggle(t: RequirementType) {
    setError(null);
    try {
      await api.updateRequirementType(t.requirement_type_id, { is_active: !t.is_active });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const next = Math.max(0, ...(types ?? []).map((t) => t.sort_order)) + 10;
      await api.createRequirementType({ code, name, description: description || undefined, sort_order: next });
      setCode("");
      setName("");
      setDescription("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <h2>Administrative requirements catalog</h2>
      <p className="muted small">
        Active requirements must all be certified before a thesis can be approved for defense.
      </p>
      {types && (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Code</th>
                <th>Requirement</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {types.map((t) => (
                <tr key={t.requirement_type_id} className={t.is_active ? "" : "inactive"}>
                  <td>
                    <code>{t.code}</code>
                  </td>
                  <td>
                    {t.name}
                    {t.description && <div className="muted small">{t.description}</div>}
                  </td>
                  <td>{t.is_active ? "Active" : "Inactive"}</td>
                  <td className="row-actions">
                    <button type="button" className="button button-small button-secondary" onClick={() => toggle(t)}>
                      {t.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="spaced">Add requirement</h3>
      <form className="form-grid" onSubmit={add}>
        <label>
          Code
          <input value={code} onChange={(e) => setCode(e.target.value)} pattern="[A-Za-z0-9_\-]{1,30}" required />
        </label>
        <label>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={150} required />
        </label>
        <label className="full">
          Description
          <input value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} />
        </label>
        <div className="actions full">
          <button type="submit" className="button">
            Add requirement
          </button>
        </div>
      </form>
      {error && <p className="notice notice-error">{error}</p>}
    </section>
  );
}
