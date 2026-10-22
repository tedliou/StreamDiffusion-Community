import { useEffect, useId, useRef, useState } from "react";
import { changeAt, type Field, type Result } from "../runtime";
import { classText, optionText, settingText, text } from "../strings";
import { PromptBlend, type WeightedPrompt } from "./PromptBlend";

const LIVE_THROTTLE_MS = 100;

interface Props {
  field: Field;
  value: unknown;
  update: (changes: Record<string, unknown>) => Promise<Result>;
  suggestions?: string[];
  children?: React.ReactNode;
}

/** One Setting: its label, class badge, control and inline error. The control is chosen from the schema. */
export function SettingControl({ field, value, update, suggestions, children }: Props) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  const info = settingText[field.path] ?? { label: field.path };

  const commitChanges = async (changes: Record<string, unknown>) => {
    const result = await update(changes);
    setError(result.ok ? null : (result.error ?? "Rejected"));
    return result.ok;
  };
  const commit = (next: unknown) => commitChanges(changeAt(field.path, next));
  // One item of a list Setting, by index: `{prompts: {"1": {weight: 0.5}}}`.
  const commitItem = (index: number, changes: object) => commitChanges(changeAt(field.path, { [index]: changes }));

  return (
    <div className="setting" data-path={field.path}>
      <div className="setting-head">
        {field.type === "enum" ? (
          <span className="label" id={`${id}-label`}>
            {info.label}
          </span>
        ) : (
          <label htmlFor={id}>{info.label}</label>
        )}
        <ClassBadge kind={field.class} />
      </div>
      {field.type === "list" ? (
        <PromptBlend
          id={id}
          field={field}
          value={(value as WeightedPrompt[] | undefined) ?? []}
          commit={commit}
          commitItem={commitItem}
        />
      ) : (
        renderControl(id, field, value, commit, suggestions)
      )}
      {children}
      {info.help && (
        <p className="help" id={`${id}-help`}>
          {info.help}
        </p>
      )}
      <p className="field-error" role="status" aria-live="polite">
        {error}
      </p>
    </div>
  );
}

export function ClassBadge({ kind }: { kind: Field["class"] }) {
  return (
    <span className={`badge badge-${kind}`} title={classText[kind].help}>
      {classText[kind].label}
    </span>
  );
}

function renderControl(
  id: string,
  field: Field,
  value: unknown,
  commit: (next: unknown) => Promise<boolean>,
  suggestions?: string[],
) {
  if (field.type === "enum") return <Segmented id={id} field={field} value={String(value)} commit={commit} />;
  if (field.type === "string")
    return <TextInput id={id} value={String(value ?? "")} commit={commit} suggestions={suggestions} />;
  if (field.path === "seed") return <SeedInput id={id} field={field} value={Number(value)} commit={commit} />;
  return <SliderInput id={id} field={field} value={Number(value)} commit={commit} />;
}

function Segmented({
  id,
  field,
  value,
  commit,
}: {
  id: string;
  field: Field;
  value: string;
  commit: (next: unknown) => Promise<boolean>;
}) {
  return (
    <div className="segmented" role="radiogroup" id={id} aria-labelledby={`${id}-label`}>
      {field.options?.map((option) => (
        <label key={option} className="segment">
          <input
            type="radio"
            name={`${id}-${field.path}`}
            value={option}
            checked={value === option}
            onChange={() => void commit(option)}
          />
          <span>{optionText[option] ?? option}</span>
        </label>
      ))}
    </div>
  );
}

/** A value that follows the Runtime unless the user is editing it. */
export function useDraft<T>(value: T) {
  const [draft, setDraft] = useState(value);
  const editing = useRef(false);
  useEffect(() => {
    if (!editing.current) setDraft(value);
  }, [value]);
  return { draft, setDraft, editing };
}

function TextInput({
  id,
  value,
  commit,
  suggestions,
}: {
  id: string;
  value: string;
  commit: (next: unknown) => Promise<boolean>;
  suggestions?: string[];
}) {
  const { draft, setDraft, editing } = useDraft(value);
  const send = () => {
    editing.current = false;
    if (draft.trim() !== value) void commit(draft.trim());
  };
  return (
    <>
      <input
        id={id}
        type="text"
        value={draft}
        list={suggestions ? `${id}-list` : undefined}
        autoComplete="off"
        spellCheck={false}
        onFocus={() => {
          editing.current = true;
        }}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={send}
        onKeyDown={(event) => {
          if (event.key === "Enter") send();
        }}
      />
      {suggestions && (
        <datalist id={`${id}-list`}>
          {suggestions.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      )}
    </>
  );
}

function SeedInput({
  id,
  field,
  value,
  commit,
}: {
  id: string;
  field: Field;
  value: number;
  commit: (next: unknown) => Promise<boolean>;
}) {
  const { draft, setDraft, editing } = useDraft(String(value));
  const send = () => {
    editing.current = false;
    if (draft !== String(value)) void commit(Number(draft));
  };
  return (
    <div className="inline">
      <input
        id={id}
        type="number"
        inputMode="numeric"
        className="number"
        min={field.minimum}
        max={field.maximum === undefined ? undefined : field.maximum - 1}
        step={1}
        value={draft}
        onFocus={() => {
          editing.current = true;
        }}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={send}
        onKeyDown={(event) => {
          if (event.key === "Enter") send();
        }}
      />
      <button
        type="button"
        className="button"
        onClick={() => void commit(Math.floor(Math.random() * (field.maximum ?? 2 ** 31)))}
      >
        {text.randomSeed}
      </button>
    </div>
  );
}

/** A slider for quick changes with an exact numeric entry beside it. `label` names both when several share a field. */
export function SliderInput({
  id,
  field,
  value,
  commit,
  label,
}: {
  id: string;
  field: Field;
  value: number;
  commit: (next: unknown) => Promise<boolean>;
  label?: string;
}) {
  const step = field.step ?? (field.type === "integer" ? 1 : 0.01);
  const minimum = field.minimum ?? 0;
  const maximum = field.maximum ?? 100;
  const { draft, setDraft, editing } = useDraft(value);
  const [typed, setTyped] = useState<string | null>(null);
  const lastSent = useRef(0);
  const unit = settingText[field.path]?.unit;

  const slide = (next: number) => {
    editing.current = true;
    setDraft(next);
    // Live Settings follow the slider; Reset Settings wait for release, so output pauses once.
    if (field.class === "live" && performance.now() - lastSent.current > LIVE_THROTTLE_MS) {
      lastSent.current = performance.now();
      void commit(next);
    }
  };
  const release = () => {
    editing.current = false;
    if (draft !== value) void commit(draft);
  };
  const sendTyped = () => {
    if (typed === null) return;
    setTyped(null);
    const next = Number(typed);
    if (typed.trim() !== "" && Number.isFinite(next) && next !== value) void commit(next);
  };

  return (
    <div className="slider">
      <input
        type="range"
        aria-label={`${label ?? settingText[field.path]?.label ?? field.path} slider`}
        min={minimum}
        max={maximum}
        step={step}
        value={draft}
        style={{ "--fill": `${((draft - minimum) / (maximum - minimum)) * 100}%` } as React.CSSProperties}
        onChange={(event) => slide(Number(event.target.value))}
        onPointerUp={release}
        onKeyUp={release}
        onBlur={release}
      />
      <span className="number-with-unit">
        <input
          id={id}
          type="number"
          aria-label={label}
          inputMode={field.type === "integer" ? "numeric" : "decimal"}
          className="number"
          min={minimum}
          max={maximum}
          step={step}
          value={typed ?? String(draft)}
          onChange={(event) => setTyped(event.target.value)}
          onBlur={sendTyped}
          onKeyDown={(event) => {
            if (event.key === "Enter") sendTyped();
          }}
        />
        {unit && <span className="unit">{unit}</span>}
      </span>
    </div>
  );
}
