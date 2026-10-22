import type { Status } from "../runtime";
import { sourceStateText, text } from "../strings";

const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const whole = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 0 });

/** Health at a glance: every value is text, so no state is signalled by colour alone. */
export function StatusBar({ status, applying }: { status: Status | null; applying: boolean }) {
  const vram =
    status?.vram_used_gib != null && status.vram_total_gib != null
      ? `${number.format(status.vram_used_gib)} / ${number.format(status.vram_total_gib)} GiB`
      : "—";
  return (
    <section className="status" aria-label="Status">
      <dl className="metrics">
        <Metric label={text.metrics.source}>
          {status ? (
            <span className={`state state-${status.source_state}`}>
              <span className="dot" aria-hidden="true" />
              {sourceStateText[status.source_state]}
            </span>
          ) : (
            "—"
          )}
        </Metric>
        <Metric label={text.metrics.throughput}>{status ? `${number.format(status.throughput_fps)} fps` : "—"}</Metric>
        <Metric label={text.metrics.generation}>
          {status
            ? `${whole.format(status.generation_ms_p50)} ms p50 · ${whole.format(status.generation_ms_p95)} ms p95`
            : "—"}
        </Metric>
        <Metric label={text.metrics.dropped}>{status ? whole.format(status.dropped_frames) : "—"}</Metric>
        <Metric label={text.metrics.skipped}>{status ? whole.format(status.frames_skipped) : "—"}</Metric>
        <Metric label={text.metrics.vram}>{vram}</Metric>
        <Metric label={text.metrics.power}>
          {status?.power_w != null ? `${whole.format(status.power_w)} W` : "—"}
        </Metric>
        <Metric label={text.metrics.backend}>
          {status?.backend ?? "—"}
          {status?.engines.state === "building" && (
            <span className="engines">{text.metrics.building(percent.format(status.engines.progress))}</span>
          )}
        </Metric>
      </dl>
      <p className="status-line" role="status" aria-live="polite">
        {applying && <span className="applying">{text.metrics.applying}</span>}
        {status?.error && <span className="status-error">{status.error}</span>}
        {status?.engines.state === "failed" && (
          <span className="status-error">
            {text.metrics.engineFailed}: {status.engines.detail}
          </span>
        )}
      </p>
    </section>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="metric">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
