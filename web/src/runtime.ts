// The Web Panel's side of the control API (see src/streamturbo/control/web.py for the protocol).
import { useCallback, useEffect, useRef, useState } from "react";

export type SettingClass = "live" | "reset" | "rebuild";

export interface Field {
  path: string;
  class: SettingClass;
  type: "integer" | "number" | "string" | "enum";
  default: unknown;
  options?: string[];
  minimum?: number;
  maximum?: number;
  step?: number;
  max_length?: number;
}

export type Settings = { [key: string]: unknown };

export interface Preset {
  name: string;
  bundled: boolean;
}

export interface Status {
  source_state: "none" | "waiting" | "live" | "lost";
  error: string | null;
  settings_version: number;
  frames_received: number;
  frames_sent: number;
  dropped_frames: number;
  throughput_fps: number;
  generation_ms_p50: number;
  generation_ms_p95: number;
  backend: string;
  vram_used_gib: number | null;
  vram_total_gib: number | null;
  power_w: number | null;
}

export type Connection = "connecting" | "open" | "closed";

export interface Result {
  ok: boolean;
  error?: string;
  [key: string]: unknown;
}

export interface Runtime {
  connection: Connection;
  schema: Field[];
  settings: Settings | null;
  version: number;
  presets: Preset[];
  status: Status | null;
  previews: { input: string | null; output: string | null };
  request: (type: string, fields?: Record<string, unknown>) => Promise<Result>;
  setPreview: (enabled: boolean) => void;
}

const RETRY_MIN_MS = 500;
const RETRY_MAX_MS = 5000;

function socketUrl(): string {
  const url = new URL("ws", window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = new URLSearchParams(window.location.search).get("token");
  if (token) url.searchParams.set("token", token);
  return url.toString();
}

/** Reads a dotted path such as `generation.width`. */
export function valueAt(settings: Settings, path: string): unknown {
  return path.split(".").reduce<unknown>((node, key) => (node as Settings | undefined)?.[key], settings);
}

/** A nested partial update for one dotted path. */
export function changeAt(path: string, value: unknown): Settings {
  return path
    .split(".")
    .reverse()
    .reduce<unknown>((inner, key) => ({ [key]: inner }), value) as Settings;
}

export function useRuntime(): Runtime {
  const [connection, setConnection] = useState<Connection>("connecting");
  const [schema, setSchema] = useState<Field[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [version, setVersion] = useState(0);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [previews, setPreviews] = useState<{ input: string | null; output: string | null }>({
    input: null,
    output: null,
  });
  const socket = useRef<WebSocket | null>(null);
  const pending = useRef(new Map<number, (result: Result) => void>());
  const nextId = useRef(1);
  const wantPreview = useRef(true);

  useEffect(() => {
    let retryMs = RETRY_MIN_MS;
    let retryTimer: number | undefined;
    let stopped = false;
    const urls: { [channel: number]: string } = {};

    const connect = () => {
      setConnection("connecting");
      const ws = new WebSocket(socketUrl());
      ws.binaryType = "arraybuffer";
      socket.current = ws;
      ws.onopen = () => {
        retryMs = RETRY_MIN_MS;
        setConnection("open");
        ws.send(JSON.stringify({ type: "preview", enabled: wantPreview.current }));
      };
      ws.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
        if (typeof event.data !== "string") {
          const bytes = new Uint8Array(event.data);
          const channel = bytes[0] ?? 0;
          const url = URL.createObjectURL(new Blob([bytes.subarray(1)], { type: "image/jpeg" }));
          if (urls[channel]) URL.revokeObjectURL(urls[channel]);
          urls[channel] = url;
          setPreviews((current) => (channel === 0 ? { ...current, input: url } : { ...current, output: url }));
          return;
        }
        const message = JSON.parse(event.data);
        switch (message.type) {
          case "hello":
            setSchema(message.schema);
            setSettings(message.settings);
            setVersion(message.version);
            setPresets(message.presets);
            break;
          case "settings":
            setSettings(message.settings);
            setVersion(message.version);
            break;
          case "presets":
            setPresets(message.presets);
            break;
          case "status":
            setStatus(message as Status);
            break;
          case "result": {
            const resolve = pending.current.get(message.id);
            pending.current.delete(message.id);
            resolve?.(message as Result);
            break;
          }
        }
      };
      ws.onclose = () => {
        for (const resolve of pending.current.values())
          resolve({ ok: false, error: "Lost connection to the Runtime" });
        pending.current.clear();
        setConnection("closed");
        setStatus(null); // stale numbers would look live
        if (stopped) return;
        retryTimer = window.setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, RETRY_MAX_MS);
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      socket.current?.close();
      for (const url of Object.values(urls)) URL.revokeObjectURL(url);
    };
  }, []);

  const request = useCallback((type: string, fields: Record<string, unknown> = {}): Promise<Result> => {
    const ws = socket.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return Promise.resolve({ ok: false, error: "Not connected to the Runtime" });
    }
    const id = nextId.current++;
    return new Promise((resolve) => {
      pending.current.set(id, resolve);
      ws.send(JSON.stringify({ type, id, ...fields }));
    });
  }, []);

  const setPreview = useCallback(
    (enabled: boolean) => {
      wantPreview.current = enabled;
      void request("preview", { enabled });
    },
    [request],
  );

  return { connection, schema, settings, version, presets, status, previews, request, setPreview };
}
