import { useEffect, useId, useState } from "react";
import type { Preset, Result } from "../runtime";
import { text } from "../strings";

const CONFIRM_MS = 4000;

interface Props {
  presets: Preset[];
  request: (type: string, fields?: Record<string, unknown>) => Promise<Result>;
}

export function Presets({ presets, request }: Props) {
  const id = useId();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const run = async (type: string, fields: Record<string, unknown>) => {
    const result = await request(type, fields);
    setError(result.ok ? null : (result.error ?? "Rejected"));
    return result.ok;
  };

  return (
    <div className="presets">
      <p className="help">{text.presets.help}</p>
      <form
        className="inline"
        onSubmit={async (event) => {
          event.preventDefault();
          if (await run("preset.save", { name: name.trim() })) setName("");
        }}
      >
        <label htmlFor={id} className="visually-hidden">
          {text.presets.saveLabel}
        </label>
        <input
          id={id}
          type="text"
          value={name}
          placeholder={text.presets.savePlaceholder}
          autoComplete="off"
          onChange={(event) => setName(event.target.value)}
        />
        <button type="submit" className="button button-primary" disabled={!name.trim()}>
          {text.presets.save}
        </button>
      </form>
      <p className="field-error" role="status" aria-live="polite">
        {error}
      </p>
      {presets.length === 0 ? (
        <p className="help">{text.presets.empty}</p>
      ) : (
        <ul className="preset-list">
          {presets.map((preset) => (
            <PresetRow key={preset.name} preset={preset} run={run} />
          ))}
        </ul>
      )}
    </div>
  );
}

function PresetRow({
  preset,
  run,
}: {
  preset: Preset;
  run: (type: string, fields: Record<string, unknown>) => Promise<boolean>;
}) {
  const id = useId();
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState(preset.name);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return;
    const timer = window.setTimeout(() => setConfirming(false), CONFIRM_MS);
    return () => window.clearTimeout(timer);
  }, [confirming]);

  if (renaming) {
    return (
      <li className="preset-row">
        <form
          className="inline"
          onSubmit={async (event) => {
            event.preventDefault();
            if (await run("preset.rename", { name: preset.name, new_name: newName.trim() })) setRenaming(false);
          }}
        >
          <label htmlFor={id} className="visually-hidden">
            {text.presets.renameLabel(preset.name)}
          </label>
          <input
            id={id}
            type="text"
            value={newName}
            autoComplete="off"
            onChange={(event) => setNewName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setRenaming(false);
            }}
          />
          <button type="submit" className="button button-primary">
            {text.presets.renameConfirm}
          </button>
          <button type="button" className="button" onClick={() => setRenaming(false)}>
            {text.presets.cancel}
          </button>
        </form>
      </li>
    );
  }

  return (
    <li className="preset-row" data-preset={preset.name}>
      <span className="preset-name" translate="no">
        {preset.name}
      </span>
      {preset.bundled && <span className="badge">{text.presets.bundled}</span>}
      <span className="preset-actions">
        <button type="button" className="button" onClick={() => void run("preset.recall", { name: preset.name })}>
          {text.presets.recall}
        </button>
        {!preset.bundled && (
          <>
            <button
              type="button"
              className="button"
              onClick={() => {
                setNewName(preset.name);
                setRenaming(true);
              }}
            >
              {text.presets.rename}
            </button>
            <button
              type="button"
              className={`button ${confirming ? "button-danger" : ""}`}
              onClick={() => {
                if (confirming) void run("preset.delete", { name: preset.name });
                else setConfirming(true);
              }}
            >
              {confirming ? text.presets.confirmDelete : text.presets.delete}
            </button>
          </>
        )}
      </span>
    </li>
  );
}
