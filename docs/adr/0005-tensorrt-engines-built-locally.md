# TensorRT 11 Engines are built on the user's machine, with a PyTorch fallback

The fast path runs the UNet and tiny VAE as TensorRT 11 FP16 Engines with dynamic-shape profiles covering Generation Resolutions from 256 to 1024 per side. Engines are never committed or downloaded. They are built on first use and cached under a key made of model revision, component, resolution profile, GPU name, compute capability and TensorRT version. While an Engine builds, the PyTorch Backend (SDPA attention) keeps producing Output Frames, so a fresh clone shows output within seconds.

An Engine only runs on the GPU and TensorRT version it was built for, so shipping Engines would break on most machines; building locally costs a few minutes once.

## Considered Options

- TensorRT-RTX (JIT-compiled, portable across RTX GPUs): kept as an experiment, it is younger and its operator coverage less proven.
- torch.compile as the main path: rejected, on Windows it needs MSVC and triton-windows, which breaks the one-click setup.
- Polygraphy and ONNX Runtime as in upstream: dropped, TensorRT 11's own Python API covers building and running.
