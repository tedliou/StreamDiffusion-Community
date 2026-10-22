import { useEffect, useState } from "react";
import { Presets } from "./components/Presets";
import { Previews } from "./components/Previews";
import { SettingControl } from "./components/SettingControl";
import { StatusBar } from "./components/StatusBar";
import { type Field, type Runtime, type Settings, useRuntime, valueAt } from "./runtime";
import { groupText, text } from "./strings";

const GROUPS: { key: keyof typeof groupText; paths: string[] }[] = [
  {
    key: "look",
    paths: ["prompts", "prompt_transition", "strength", "strength_glide", "seed", "temporal_smoothing"],
  },
  { key: "source", paths: ["source.transport", "source.name"] },
  { key: "sink", paths: ["sink.transport", "sink.name", "sink.fps"] },
  { key: "resolution", paths: ["generation.width", "generation.height", "fit_mode"] },
  { key: "output", paths: ["output.width", "output.height"] },
  { key: "performance", paths: ["similar_frame_skip.threshold", "similar_frame_skip.max_skips", "backend"] },
];

type Theme = "system" | "light" | "dark";

export function App() {
  const runtime = useRuntime();
  const [theme, setTheme] = useTheme();
  const [previewOn, setPreviewOn] = useState(true);
  const { settings, schema, status, connection } = runtime;
  const update = (changes: Settings) => runtime.request("update", { changes });
  const applying = status !== null && status.settings_version < runtime.version;

  return (
    <>
      <a className="skip-link" href="#settings">
        {text.skipToSettings}
      </a>
      <header className="header">
        <h1 className="wordmark">{text.title}</h1>
        <span className={`connection connection-${connection}`} role="status" aria-live="polite">
          <span className="dot" aria-hidden="true" />
          {text.connection[connection]}
        </span>
        <ThemePicker theme={theme} onChange={setTheme} />
      </header>
      {connection !== "open" && <p className="banner">{text.disconnectedHelp}</p>}
      <StatusBar status={status} applying={applying} />
      <main className="layout">
        <section className="panel sidebar" aria-labelledby="previews-title">
          <h2 id="previews-title">{groupText.previews}</h2>
          <Previews
            input={runtime.previews.input}
            output={runtime.previews.output}
            enabled={previewOn}
            onToggle={() => {
              runtime.setPreview(!previewOn);
              setPreviewOn(!previewOn);
            }}
          />
          <h2 id="presets-title">{groupText.presets}</h2>
          <Presets presets={runtime.presets} request={runtime.request} />
        </section>
        <section id="settings" className="settings" tabIndex={-1} aria-label="Settings">
          {settings &&
            groupsFor(schema).map(({ key, fields }) => (
              <fieldset key={key} className="panel group" disabled={connection !== "open"}>
                <legend>
                  <h2>{groupText[key]}</h2>
                </legend>
                {fields.map((field) => (
                  <SettingControl key={field.path} field={field} value={valueAt(settings, field.path)} update={update}>
                    {field.path === "source.name" && (
                      <SourcePicker runtime={runtime} transport={String(valueAt(settings, "source.transport"))} />
                    )}
                  </SettingControl>
                ))}
                {(key === "source" || key === "sink") && valueAt(settings, `${key}.transport`) === "ndi" && (
                  <NdiNotice />
                )}
              </fieldset>
            ))}
        </section>
      </main>
    </>
  );
}

/** Every Setting in the schema gets a control: unknown paths land in the last group rather than disappearing. */
function groupsFor(schema: Field[]) {
  const known = new Set(GROUPS.flatMap((group) => group.paths));
  const byPath = new Map(schema.map((field) => [field.path, field]));
  const groups = GROUPS.map(({ key, paths }) => ({
    key,
    fields: paths.flatMap((path) => byPath.get(path) ?? []),
  }));
  const extra = schema.filter((field) => !known.has(field.path));
  groups.at(-1)?.fields.push(...extra);
  return groups.filter((group) => group.fields.length > 0);
}

function SourcePicker({ runtime, transport }: { runtime: Runtime; transport: string }) {
  const [names, setNames] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  if (transport === "none") return null;
  const refresh = async () => {
    setBusy(true);
    const result = await runtime.request("sources.list", { transport });
    setBusy(false);
    setNames(result.ok ? (result.names as string[]) : []);
  };
  const choose = (name: string) => void runtime.request("update", { changes: { source: { name } } });
  return (
    <div className="source-picker">
      <button type="button" className="button" onClick={refresh} disabled={busy} aria-busy={busy}>
        {busy ? text.refreshingSources : text.refreshSources}
      </button>
      {names !== null &&
        (names.length === 0 ? (
          <span className="help">{text.noSources}</span>
        ) : (
          <ul className="source-list">
            {names.map((name) => (
              <li key={name}>
                <button type="button" className="chip" translate="no" onClick={() => choose(name)}>
                  {name}
                </button>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}

function NdiNotice() {
  return (
    <p className="ndi-notice">
      {text.ndi.notice}{" "}
      <a href={text.ndi.href} target="_blank" rel="noreferrer">
        {text.ndi.link}
      </a>
    </p>
  );
}

function ThemePicker({ theme, onChange }: { theme: Theme; onChange: (theme: Theme) => void }) {
  return (
    <label className="theme-picker">
      <span>{text.theme}</span>
      <select value={theme} onChange={(event) => onChange(event.target.value as Theme)}>
        {(["system", "light", "dark"] as const).map((option) => (
          <option key={option} value={option}>
            {text.themes[option]}
          </option>
        ))}
      </select>
    </label>
  );
}

function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("theme") as Theme | null) ?? "system");
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  return [theme, setTheme];
}
