import { text } from "../strings";

interface Props {
  input: string | null;
  output: string | null;
  enabled: boolean;
  onToggle: () => void;
}

export function Previews({ input, output, enabled, onToggle }: Props) {
  return (
    <div className="previews">
      <div className="preview-grid">
        <Preview label={text.previews.input} src={input} />
        <Preview label={text.previews.output} src={output} />
      </div>
      <button type="button" className="button" aria-pressed={!enabled} onClick={onToggle}>
        {enabled ? text.previews.pause : text.previews.resume}
      </button>
    </div>
  );
}

function Preview({ label, src }: { label: string; src: string | null }) {
  return (
    <figure className="preview">
      <div className="frame">
        {src ? <img src={src} alt={`${label} preview`} /> : <span className="empty">{text.previews.empty}</span>}
      </div>
      <figcaption>{label}</figcaption>
    </figure>
  );
}
