# TensorRT Engines are built on the user's machine, with a PyTorch fallback

The fast path runs the UNet and tiny VAE as TensorRT FP16 Engines with dynamic-shape profiles covering Generation Resolutions from 256 to 1024 per side. Engines are never committed or downloaded. They are built on first use and cached under a key made of model revision, component, resolution profile, precision, export version, GPU name, compute capability and TensorRT version. While an Engine builds, the PyTorch Backend (SDPA attention) keeps producing Output Frames, so a fresh clone shows output within seconds.

An INT8 UNet (ModelOpt post-training quantisation, exported as Q/DQ) exists only as a bench option. Its profile covers just the bench matrix's 4:3 Generation Resolutions, and it does not build on an 8 GB RTX 3070 yet.

The FP16 UNet Engine also carries Temporal Coherence (#16): a `switch` input and each coherent layer's previous keys and values in, this call's out, with token counts dynamic over the same profile. One Engine serves the setting on and off, since `switch` 0 masks the previous features out, so toggling never triggers a build. The INT8 UNet stays without it. The export version is per Engine, so this change rebuilt only the FP16 UNet.

An Engine only runs on the GPU and TensorRT version it was built for, so shipping Engines would break on most machines; building locally costs a few minutes once.

## Considered Options

- TensorRT-RTX (JIT-compiled, portable across RTX GPUs): kept as an experiment, it is younger and its operator coverage less proven.
- torch.compile as the main path: rejected, on Windows it needs MSVC and triton-windows, which breaks the one-click setup.
- Polygraphy and ONNX Runtime as in upstream: dropped, TensorRT's own Python API covers building and running.
- TensorRT 11 (11.4): rejected for now. With a dynamic-shape profile its sd-turbo UNet Engine outputs NaN at 64x64 latents (512 px) and above. A fixed-shape profile from the same ONNX is correct, and so is TensorRT 10.16 from the same ONNX with the same dynamic profile, so the cause is TensorRT 11. Exporter choice (legacy or dynamo with the ONNX Attention op), FP32 normalisation and attention fusion (fused in both cases) were ruled out. BF16 avoids the NaN but is slower and less accurate. The Runtime pins TensorRT 10.16; retry TensorRT 11 when a release fixes it, since the Engine cache key includes the TensorRT version.
