// Every piece of UI text, so a translation is one file (spec #2: UI text is English, kept in one string table).

export const settingText: Record<string, { label: string; help?: string; unit?: string }> = {
  prompts: {
    label: "Prompt Blend",
    help: "Weighted Prompts used together as one; each weight counts relative to the total. A new Prompt starts at weight 0. Press Ctrl+Enter or leave a Prompt to apply it.",
  },
  prompt_transition: {
    label: "Prompt Transition",
    unit: "s",
    help: "How long a Prompt Blend change takes to blend in. 0 switches at once.",
  },
  strength: { label: "Strength", help: "0 keeps the Input Frame, 1 ignores it." },
  strength_glide: {
    label: "Strength Glide",
    unit: "s",
    help: "How long Strength takes to reach a new value, from any Control Surface. 0 jumps.",
  },
  temporal_smoothing: {
    label: "Temporal Smoothing",
    help: "How much of the previous Generation each new one keeps, to reduce flicker. 0 turns it off; high values trail behind fast motion.",
  },
  temporal_coherence: {
    label: "Temporal Coherence",
    help: "Each Generation also looks at the previous one, so detail stays in place instead of shimmering. Costs a few percent of Generation Time and keeps the picture sharp; combines with Temporal Smoothing.",
  },
  seed: { label: "Seed", help: "Fixes the noise. Changing Strength never re-rolls it." },
  "source.transport": { label: "Transport" },
  "source.name": { label: "Name", help: "Leave empty to use the first visible sender." },
  "sink.transport": { label: "Transport" },
  "sink.name": { label: "Name" },
  "sink.fps": { label: "Declared Rate", unit: "fps", help: "The frame rate announced to NDI receivers." },
  "generation.width": { label: "Width", unit: "px" },
  "generation.height": { label: "Height", unit: "px" },
  "output.width": { label: "Width", unit: "px" },
  "output.height": { label: "Height", unit: "px" },
  fit_mode: { label: "Fit Mode", help: "How an Input Frame with another aspect ratio is mapped." },
  "similar_frame_skip.threshold": {
    label: "Skip Threshold",
    help: "Repeat the last Output Frame while the Input Frame changes less than this. 0 turns Similar Frame Skip off.",
  },
  "similar_frame_skip.max_skips": {
    label: "Maximum Skips",
    help: "Generate after this many repeats, so slow changes still appear.",
  },
  backend: {
    label: "Backend",
    help: "Auto switches to TensorRT once its Engines are built. PyTorch rules TensorRT out when diagnosing.",
  },
};

export const optionText: Record<string, string> = {
  ndi: "NDI",
  spout: "Spout",
  none: "None",
  fill: "Fill",
  fit: "Fit",
  stretch: "Stretch",
  auto: "Auto",
  pytorch: "PyTorch",
};

export const classText = {
  live: { label: "Live", help: "Applies on the next Output Frame without interrupting output." },
  reset: { label: "Reset", help: "Output pauses briefly while buffers or Transports are rebuilt." },
  rebuild: { label: "Rebuild", help: "Needs a new Engine to be built before it fully takes effect." },
} as const;

export const groupText = {
  look: "Look",
  source: "Source",
  sink: "Sink",
  resolution: "Generation Resolution",
  output: "Output Resolution",
  performance: "Performance",
  presets: "Presets",
  previews: "Previews",
};

export const sourceStateText = {
  none: "No Source",
  waiting: "Waiting",
  live: "Live",
  lost: "Lost",
} as const;

export const text = {
  title: "StreamTurbo",
  skipToSettings: "Skip to Settings",
  connection: {
    connecting: "Connecting…",
    open: "Connected",
    closed: "Reconnecting…",
  },
  disconnectedHelp: "The Runtime is not reachable. The panel reconnects by itself when it is running again.",
  theme: "Theme",
  themes: { system: "System", light: "Light", dark: "Dark" },
  metrics: {
    source: "Source",
    throughput: "Throughput",
    generation: "Generation Time",
    dropped: "Dropped",
    vram: "VRAM",
    power: "GPU Power",
    backend: "Backend",
    skipped: "Skipped",
    building: (percent: string) => `Building Engines ${percent}`,
    engineFailed: "Engines failed, using PyTorch",
    applying: "Applying…",
  },
  previews: {
    input: "Input",
    output: "Output",
    pause: "Pause Previews",
    resume: "Resume Previews",
    empty: "No frame yet",
  },
  refreshSources: "Refresh",
  refreshingSources: "Refreshing…",
  noSources: "No senders visible",
  randomSeed: "Random",
  promptAdd: "Add Prompt",
  promptRemove: "Remove",
  promptWeight: "Weight",
  promptPlaceholder: "Describe the look",
  promptLabel: (n: number) => `Prompt ${n}`,
  promptWeightLabel: (n: number) => `Prompt ${n} Weight`,
  promptRemoveLabel: (n: number) => `Remove Prompt ${n}`,
  presets: {
    saveLabel: "New Preset Name",
    savePlaceholder: "Evening Show…",
    save: "Save Preset",
    recall: "Recall",
    rename: "Rename…",
    renameLabel: (name: string) => `New name for ${name}`,
    renameConfirm: "Rename",
    cancel: "Cancel",
    delete: "Delete",
    confirmDelete: "Confirm Delete",
    bundled: "Bundled",
    empty: "No Presets yet. Save the current look to create one.",
    help: "Presets keep the look: every Setting except Source and Sink.",
  },
  ndi: {
    notice: "NDI® is a registered trademark of Vizrt NDI AB.",
    link: "ndi.video",
    href: "https://ndi.video",
  },
};
