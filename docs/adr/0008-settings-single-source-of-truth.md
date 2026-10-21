# Settings are the single source of truth, changed only through Control Surfaces

All behaviour of the Runtime is described by one validated Settings object. The Web Panel, OSC and the command line never call into the pipeline directly. They submit changes to Settings, and the generation thread applies one consistent snapshot between two Output Frames. Every Setting is classified as Live, Reset or Rebuild, and the Web Panel shows that class next to its control.

This stops several Control Surfaces from fighting over half-applied state, and makes a Preset nothing more than saved Settings.
