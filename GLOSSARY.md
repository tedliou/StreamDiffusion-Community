# Real-time Generation

A Windows application that receives a live video stream, regenerates every frame with a one-step diffusion model, and sends the result back out, typically to TouchDesigner.

## Pipeline

**Runtime**:
The running application process: it pulls Input Frames from a Source, generates, and pushes Output Frames to a Sink.
_Avoid_: Engine (reserved for TensorRT), server, app

**Source**:
Where Input Frames come from, bound to one Transport and one stream name.
_Avoid_: Input device, receiver

**Sink**:
Where Output Frames go, bound to one Transport and one stream name.
_Avoid_: Output device, sender

**Transport**:
The video link a Source or Sink uses: NDI or Spout.
_Avoid_: Protocol, I/O backend

**Input Frame**:
One picture received from the Source, at whatever size and format the Source provides.

**Output Frame**:
One picture sent to the Sink, at the Output Resolution.

**Generation**:
Turning one Input Frame into one Output Frame with the diffusion model.
_Avoid_: Inference (too generic), render

**Generation Resolution**:
The pixel size the model actually works at, always a multiple of 64 on each side.
_Avoid_: Model resolution, internal resolution

**Output Resolution**:
The pixel size of Output Frames: reached from the Generation Resolution through the Upscaler when it is on and the Output Resolution is larger, otherwise by plain resizing.

**Upscaler**:
The learned model that enlarges a generated picture with new detail on its way to the Output Resolution. It always enlarges 4x; the picture is then resized to the Output Resolution.
_Avoid_: Super resolution, ESRGAN, SR

**Fit Mode**:
How an Input Frame whose aspect ratio differs from the Generation Resolution is mapped onto it: fill (crop), fit (letterbox) or stretch.

## Generation controls

**Prompt**:
The text that steers Generation.

**Prompt Blend**:
A weighted mix of several Prompts used together as one.

**Prompt Transition**:
The time a change to the Prompt Blend takes to blend in, instead of snapping.

**Strength**:
How far Generation may move away from the Input Frame, from 0 (keep the Input Frame) to 1 (ignore it).
_Avoid_: Denoise, t_index, noise level

**Strength Glide**:
The time Strength takes to move to a new value, whichever Control Surface set it.

**Seed**:
The number that fixes the noise used for Generation, so the same Input Frame and Settings give the same Output Frame.

**Temporal Smoothing**:
Blending each Generation with the previous one to reduce flicker between consecutive Output Frames.
_Avoid_: Frame blending, stabilisation

**Temporal Coherence**:
Letting each Generation attend to the previous Generation's features, so detail stays in place between Output Frames instead of being re-invented.
_Avoid_: Feature bank, StreamV2V (paper terms)

**Similar Frame Skip**:
Reusing the previous Output Frame instead of generating when the Input Frame has barely changed.
_Avoid_: SSF, stochastic similarity filter (paper term), idle mode

## Configuration

**Settings**:
The complete set of values that control the Runtime at a given moment.
_Avoid_: Config, parameters

**Live Setting**:
A Setting that takes effect on the next Output Frame without interrupting output.

**Reset Setting**:
A Setting whose change briefly pauses output while buffers are rebuilt.

**Rebuild Setting**:
A Setting whose change needs a new Engine to be built before it fully takes effect.

**Preset**:
A named, saved snapshot of the look Settings that can be recalled. It leaves out the Source and Sink, so a Preset works at any venue.
_Avoid_: Profile, scene

**Control Surface**:
Anything that changes Settings while the Runtime runs: the Web Panel or OSC.

**Web Panel**:
The browser-based Control Surface served by the Runtime.
_Avoid_: GUI, dashboard, frontend

## Models and acceleration

**Model Spec**:
The description of one supported diffusion model: which weights, which tiny VAE, which Generation Resolutions it accepts.

**Backend**:
What executes the model: PyTorch or TensorRT.

**Engine**:
A TensorRT build of one model component for one GPU and one TensorRT version.
_Avoid_: Plan, compiled model

**Low-VRAM Mode**:
How the Runtime runs on a GPU with less than 6 GB of VRAM, or when forced from the command line: Engines build with the GPU to themselves while output pauses. A property of the machine, never a Setting.
_Avoid_: Low memory mode, lite mode

## Measurement

**Generation Time**:
GPU time to turn one Input Frame into one Output Frame, excluding Transport.

**Round-trip Latency**:
Time from TouchDesigner sending a frame to TouchDesigner receiving the matching Output Frame.
_Avoid_: Latency (alone, ambiguous), lag

**Throughput**:
Output Frames actually generated per second, excluding frames reused by Similar Frame Skip.
_Avoid_: FPS (alone, ambiguous)
