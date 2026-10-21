# The Web Panel is a React + TypeScript app whose built files are committed

The Web Panel is written in React and TypeScript with Vite, and talks to the Runtime over one WebSocket. Its production build is committed inside the Python package, so running the Runtime never needs Node.js; CI rebuilds it and fails when the committed build is stale. Fonts and all other assets are vendored, so the panel works offline.

Its visual language follows Vercel's Geist style, recorded in a root `DESIGN.md` in the google-labs-code/design.md format. Public sources only define light tokens, so the dark palette, slider and motion tokens are defined by this project.

The Runtime binds the panel to 127.0.0.1 by default. Exposing it on the LAN, for example to control it from a tablet, is an explicit setting that also requires an access token.

## Considered Options

- Native window (Dear PyGui, Qt): rejected, it cannot be used from a second device and would be another UI toolkit beside OSC.
- No-build HTML and JavaScript: rejected, a panel with many live controls, Presets and metrics benefits from typed state and components.
