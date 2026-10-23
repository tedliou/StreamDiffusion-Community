# Windows and NVIDIA GPUs only

The Runtime targets Windows 10/11 x64 with an NVIDIA GPU of the Turing generation (RTX 20) or newer and at least 4 GB of VRAM. 8 GB is the full target; below 6 GB the Runtime runs in Low-VRAM Mode (#24), so a 4 GB laptop GPU such as the RTX 3050 Laptop still gets TensorRT Engines. Linux, WSL2, Docker, macOS, AMD and CPU-only paths are removed rather than kept half-working. The only intended user runs TouchDesigner on Windows, Spout exists only on Windows, and CUDA 13 and the TensorRT builds for it already dropped pre-Turing GPUs, so supporting more platforms would cost testing effort for no real user.

## Consequences

- Launch scripts and docs are Windows-first (`start.cmd`); code still uses `pathlib` rather than hard-coded separators.
- The transport layer may import Windows-only packages such as SpoutGL.
- The upstream rule "develop in Linux" no longer applies.
