import { useState, type FormEvent } from "react";
import { api, type ThesisDetail } from "../api";

/** Title and abstract of a thesis. Students may edit them until the topic is approved. */
export default function EditTopicForm({
  thesis,
  isAdmin,
  onCancel,
  onSaved,
}: {
  thesis: ThesisDetail;
  isAdmin: boolean;
  onCancel: () => void;
  onSaved: (t: ThesisDetail) => void;
}) {
  const [title, setTitle] = useState(thesis.title);
  const [abstract, setAbstract] = useState(thesis.abstract ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      onSaved(await api.updateThesis(thesis.thesis_id, { title, abstract: abstract || null }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <label className="full">
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} minLength={5} maxLength={255} required />
      </label>
      <label className="full">
        Abstract
        <textarea value={abstract} onChange={(e) => setAbstract(e.target.value)} rows={6} maxLength={5000} />
      </label>
      {!isAdmin && <p className="muted full">You can edit the topic until it is approved.</p>}
      {error && <p className="notice notice-error full">{error}</p>}
      <div className="actions full">
        <button type="submit" className="button">
          Save
        </button>
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
