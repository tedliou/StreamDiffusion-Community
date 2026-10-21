# Windows and NVIDIA GPUs only

The Runtime targets Windows 10/11 x64 with an NVIDIA GPU of the Turing generation (RTX 20) or newer and at least 8 GB of VRAM. Linux, WSL2, Docker, macOS, AMD and CPU-only paths are removed rather than kept half-working. The only intended user runs TouchDesigner on Windows, Spout exists only on Windows, and CUDA 13 / TensorRT 11 already dropped pre-Turing GPUs, so supporting more platforms would cost testing effort for no real user.

## Consequences

- Launch scripts and docs are Windows-first (`start.cmd`); code still uses `pathlib` rather than hard-coded separators.
- The transport layer may import Windows-only packages such as SpoutGL.
- The upstream rule "develop in Linux" no longer applies.
