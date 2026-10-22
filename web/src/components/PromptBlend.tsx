import { type KeyboardEvent, useId } from "react";
import type { Field } from "../runtime";
import { text } from "../strings";
import { SliderInput, useDraft } from "./SettingControl";

export interface WeightedPrompt {
  text: string;
  weight: number;
}

type Commit = (next: unknown) => Promise<boolean>;

/** The Prompt Blend: one row per weighted Prompt. Rows change by index, so edits from OSC are never overwritten. */
export function PromptBlend({
  id,
  field,
  value,
  commit,
  commitItem,
}: {
  id: string;
  field: Field;
  value: WeightedPrompt[];
  commit: Commit;
  commitItem: (index: number, changes: Partial<WeightedPrompt>) => Promise<boolean>;
}) {
  const itemField = (path: string) => field.items?.find((item) => item.path === path);
  const textField = itemField("text");
  const weightField = itemField("weight");
  const atLeast = field.min_items ?? 1;
  const atMost = field.max_items ?? Number.POSITIVE_INFINITY;

  return (
    <div className="prompt-blend" id={id}>
      <ol className="prompt-rows">
        {value.map((prompt, index) => (
          <PromptRow
            // biome-ignore lint/suspicious/noArrayIndexKey: rows are addressed by index, like the Settings path
            key={index}
            index={index}
            prompt={prompt}
            maxLength={textField?.max_length}
            weightField={weightField}
            removable={value.length > atLeast}
            commitItem={commitItem}
            remove={() => commit(value.filter((_, other) => other !== index))}
          />
        ))}
      </ol>
      <button
        type="button"
        className="button"
        disabled={value.length >= atMost}
        onClick={() => void commit([...value, { text: "", weight: 0 }])}
      >
        {text.promptAdd}
      </button>
    </div>
  );
}

function PromptRow({
  index,
  prompt,
  maxLength,
  weightField,
  removable,
  commitItem,
  remove,
}: {
  index: number;
  prompt: WeightedPrompt;
  maxLength?: number;
  weightField?: Field;
  removable: boolean;
  commitItem: (index: number, changes: Partial<WeightedPrompt>) => Promise<boolean>;
  remove: () => Promise<boolean>;
}) {
  const id = useId();
  const { draft, setDraft, editing } = useDraft(prompt.text);
  const label = text.promptLabel(index + 1);
  const send = () => {
    editing.current = false;
    if (draft !== prompt.text) void commitItem(index, { text: draft });
  };

  return (
    <li className="prompt-row">
      <label className="visually-hidden" htmlFor={`${id}-text`}>
        {label}
      </label>
      <textarea
        id={`${id}-text`}
        value={draft}
        rows={3}
        maxLength={maxLength}
        placeholder={text.promptPlaceholder}
        onFocus={() => {
          editing.current = true;
        }}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={send}
        onKeyDown={(event: KeyboardEvent<HTMLTextAreaElement>) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            send();
          }
        }}
      />
      <div className="prompt-row-foot">
        <label className="prompt-weight-label" htmlFor={`${id}-weight`}>
          {text.promptWeight}
        </label>
        {weightField && (
          <SliderInput
            id={`${id}-weight`}
            field={weightField}
            label={text.promptWeightLabel(index + 1)}
            value={prompt.weight}
            commit={(weight) => commitItem(index, { weight: Number(weight) })}
          />
        )}
        <button
          type="button"
          className="button"
          disabled={!removable}
          aria-label={text.promptRemoveLabel(index + 1)}
          onClick={() => void remove()}
        >
          {text.promptRemove}
        </button>
      </div>
    </li>
  );
}
