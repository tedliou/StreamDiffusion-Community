# sd-turbo single-step Generation replaces the StreamDiffusion multi-step design

The Runtime is built around one model, `stabilityai/sd-turbo`, run as one UNet step per Output Frame with no classifier-free guidance. Upstream StreamDiffusion's Stream Batch, Residual CFG and LCM-LoRA paths only pay off with several denoising steps and guidance, so they are dropped instead of ported; the original code stays readable in git history. The safety checker is dropped too: the project is non-commercial and artistic, and the checker costs VRAM and a CLIP pass per frame.

Other one-step models (sdxl-turbo, Hyper-SD) may be added later through a Model Spec, not by reviving the multi-step pipeline.

## Considered Options

- Keep the upstream pipeline and add sd-turbo special cases: rejected. The upstream class is shaped around multi-step batching, and its sd-turbo path is a side branch chosen by finding "turbo" in the model id.
