---
version: alpha
name: StreamTurbo Web Panel
description: A dense, calm control surface for a live show, derived from Vercel's Geist language.
colors:
  primary: "#171717"
  on-primary: "#ffffff"
  surface: "#ffffff"
  surface-sunken: "#fafafa"
  neutral: "#f2f2f2"
  border: "#ebebeb"
  border-strong: "#c9c9c9"
  text: "#171717"
  text-secondary: "#4d4d4d"
  text-disabled: "#8f8f8f"
  focus: "#006bff"
  info: "#005ff2"
  info-surface: "#f0f7ff"
  success: "#107d32"
  warning: "#aa4d00"
  warning-surface: "#fff6de"
  error: "#d8001b"
  error-surface: "#ffeeef"
  dark-primary: "#ededed"
  dark-on-primary: "#0a0a0a"
  dark-surface: "#0a0a0a"
  dark-surface-sunken: "#000000"
  dark-neutral: "#1a1a1a"
  dark-border: "#2e2e2e"
  dark-border-strong: "#454545"
  dark-text: "#ededed"
  dark-text-secondary: "#a0a0a0"
  dark-focus: "#47a8ff"
  dark-info: "#47a8ff"
  dark-info-surface: "#0f1e33"
  dark-success: "#00ca50"
  dark-warning: "#ff9300"
  dark-warning-surface: "#2a1a06"
  dark-error: "#ff565f"
  dark-error-surface: "#2d0d10"
  slider-track: "#c9c9c9"
  slider-fill: "#171717"
  dark-slider-track: "#454545"
  dark-slider-fill: "#ededed"
typography:
  wordmark: { fontFamily: Geist, fontSize: 16px, fontWeight: 600, lineHeight: 24px, letterSpacing: -0.01em }
  section-label:
    { fontFamily: Geist, fontSize: 13px, fontWeight: 600, lineHeight: 18px, letterSpacing: 0.04em }
  label: { fontFamily: Geist, fontSize: 14px, fontWeight: 500, lineHeight: 20px }
  body: { fontFamily: Geist, fontSize: 14px, fontWeight: 400, lineHeight: 20px }
  help: { fontFamily: Geist, fontSize: 13px, fontWeight: 400, lineHeight: 18px }
  metric-label: { fontFamily: Geist, fontSize: 12px, fontWeight: 400, lineHeight: 16px }
  metric: { fontFamily: Geist, fontSize: 14px, fontWeight: 500, lineHeight: 20px, fontFeature: '"tnum"' }
  mono: { fontFamily: Geist Mono, fontSize: 13px, fontWeight: 400, lineHeight: 18px }
rounded:
  sm: 6px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  control-height: 36px
  slider-track-height: 4px
  slider-thumb-size: 16px
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    height: 36px
    padding: 0 12px
  button-hover:
    backgroundColor: "{colors.neutral}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    height: 36px
    padding: 0 12px
  button-danger:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.sm}"
    height: 36px
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    height: 36px
    padding: 0 10px
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: 16px
  segmented:
    backgroundColor: "{colors.neutral}"
    rounded: "{rounded.md}"
    padding: 2px
  segment-selected:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    height: 32px
  badge-live:
    backgroundColor: "{colors.info-surface}"
    textColor: "{colors.info}"
    typography: "{typography.metric-label}"
    rounded: "{rounded.sm}"
    height: 20px
  badge-reset:
    backgroundColor: "{colors.warning-surface}"
    textColor: "{colors.warning}"
    typography: "{typography.metric-label}"
    rounded: "{rounded.sm}"
    height: 20px
  badge-rebuild:
    backgroundColor: "{colors.error-surface}"
    textColor: "{colors.error}"
    typography: "{typography.metric-label}"
    rounded: "{rounded.sm}"
    height: 20px
  slider-thumb:
    backgroundColor: "{colors.slider-fill}"
    rounded: "{rounded.full}"
    size: 16px
  switch:
    backgroundColor: "{colors.slider-track}"
    checkedBackgroundColor: "{colors.slider-fill}"
    rounded: "{rounded.full}"
    width: 40px
    height: 24px
---

# StreamTurbo Web Panel

The tokens above are the source of truth; `web/src/styles.css` implements them as CSS custom properties.

## Overview

A control surface for a live performance, used beside TouchDesigner and often in a dark venue. It should feel calm
and exact: dense information, quiet chrome, nothing that competes with the show. The language is Vercel's Geist:
neutral grays, one accent reserved for focus and information, Geist Sans for everything, tabular numbers for every
live value.

Light-theme values are Geist's published tokens. Public sources define no dark palette, slider or motion tokens, so
those are this project's (ADR-0007). The panel follows the system theme and can be set to Light or Dark.

## Colors

- **Primary (#171717 / dark #ededed):** text, primary buttons and the slider fill. Gray-1000 in Geist terms.
- **Surface (#ffffff / dark #0a0a0a) on Surface Sunken (#fafafa / dark #000000):** panels sit on a slightly darker
  page. The dark surface is lifted off pure black so panel edges stay visible on stage monitors.
- **Neutral (#f2f2f2 / dark #1a1a1a):** hover fills, segmented-control tracks, empty preview frames.
- **Focus (#006bff / dark #47a8ff):** the 2px focus ring. Blue appears nowhere else except the Live badge.
- **Semantic pairs:** info (Live badge), warning (Reset badge, waiting state, disconnected banner), error (Rebuild
  badge, errors, lost state), success (connected and live dots). Each is a text colour on its own tinted surface.
- Status is never colour alone: every dot sits next to a word, every badge carries its class name.

## Typography

Geist Sans (variable, 100–900) for all text, Geist Mono only for identifiers. Both are vendored in `web/src/fonts`
under the SIL Open Font License, shipped as `fonts/OFL.txt` in the build, so the panel works offline.

- Section labels are 13px uppercase with 0.04em tracking, in secondary text colour.
- Control labels are 14px medium; help text 13px regular in secondary colour.
- Every number that changes while you watch (metrics, slider values) uses `font-variant-numeric: tabular-nums`, with a
  non-breaking space before its unit: `20.8 fps`, `188 ms`, `1024 px`.

## Layout

A 4px grid. A two-column layout from 900px: previews and Presets on the left (sticky), Settings groups on the right.
Below 900px, one column. Panels are 16px inset with 12px between controls. Control height is 36px; hit targets are at
least 24px on desktop.

## Elevation & Depth

Flat. Panels use a 1px border, no shadow. The only shadow is the selected segment's 1px ring with a 2px blur, so the
choice reads as raised.

## Shapes

Radii are concentric: 12px panels, 8px segmented tracks and preview frames, 6px controls and badges, full circles for
the slider thumb and status dots.

## Components

- **Setting:** label and class badge on one line, the control below, help text under it, and an inline error that is
  announced politely. Every Setting in the Runtime's schema gets one, generated from the schema.
- **Slider:** a 4px track filled to the value, a 16px thumb with a 2px surface ring, and an exact numeric entry beside
  it. Live Settings follow the thumb (throttled to 10 updates a second); Reset Settings apply on release so output
  pauses once. Arrow keys step, Home and End jump to the limits.
- **Segmented control:** native radio buttons for enumerations (Transport, Fit Mode).
- **Switch:** a native checkbox with the switch role for on/off Settings (Temporal Coherence): the slider track's
  colour when off, the slider fill's when on, with a surface-coloured knob. The knob moves without a transition.
- **Class badge:** Live (info), Reset (warning), Rebuild (error), with the class's meaning as its tooltip.
- **Preset row:** name, a Bundled tag for read-only Presets, Recall, Rename… and a two-step Delete that turns into
  Confirm Delete for four seconds.
- **Status bar:** labelled metrics in a wrapping row, with applying and error messages in a live region.

## Motion

Motion tokens: `duration-fast` 120ms for hover and selection, `duration-base` 200ms, easing
`cubic-bezier(0.2, 0, 0, 1)`. Only colours, borders and the slider thumb's scale transition, and never with
`transition: all`. With `prefers-reduced-motion: reduce`, both durations are 0ms.

## Do's and Don'ts

- Do keep every flow keyboard operable with a visible focus ring, and label every control.
- Do show the Live/Reset/Rebuild class next to every control.
- Do show the NDI attribution and link wherever NDI is selected.
- Don't signal state with colour alone, animate layout, or load anything from the network: the panel must work offline.
- Don't add a second accent colour; blue means focus and information.
