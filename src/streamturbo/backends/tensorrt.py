"""TensorRT Backend: the UNet and the tiny VAE as TensorRT 10 Engines built on this machine (ADR-0005).

The text encoder and the noise schedule stay on the PyTorch Backend it wraps: a Prompt change is rare and cheap.
The networks are built strongly typed, so precision comes from the ONNX graph: FP16 weights give an FP16 Engine,
Q/DQ nodes an INT8 one.
"""

import contextlib
import functools
import hashlib
import json
import shutil
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import torch
import torch.nn.functional as F

from streamturbo.backends import ProgressReport
from streamturbo.backends.pytorch import CoherentLayer, PyTorchBackend
from streamturbo.model_spec import ModelSpec

Component = Literal["unet", "vae_encoder", "vae_decoder"]
COMPONENTS: tuple[Component, ...] = ("unet", "vae_encoder", "vae_decoder")
Precision = Literal["fp16", "int8"]
Progress = Callable[[str, float], None]  # (component, fraction of all Engines done)

TEXT_TOKENS, TEXT_DIM = 77, 1024  # sd-turbo's OpenCLIP text encoder
EXPORT_VERSION = 1  # bumped whenever the exported graph changes, so older cached Engines are rebuilt
COHERENT_EXPORT_VERSION = 2  # the FP16 UNet's: 2 takes and returns Temporal Coherence features
# Tactic scratch while building. FP16 is built while the Runtime runs, and 2 GiB keeps that under 8 GB of VRAM;
# the INT8 UNet is a bench option built on its own.
WORKSPACE_BYTES: dict[Precision, int] = {"fp16": 2 << 30, "int8": 3 << 30}
# The INT8 UNet's profile, as (min, max) Generation Resolutions in pixels: the bench matrix's 4:3 options. Its
# attention is not fused, and over the full 256-1024 range the build needs more than 3 GiB of workspace.
INT8_RESOLUTIONS = ((768, 576), (1024, 768))


def component_precision(component: Component, precision: Precision) -> Precision:
    """The precision one component is built in: only the UNet has an INT8 option, the tiny VAE is always FP16."""
    return precision if component == "unet" else "fp16"


def _tensorrt() -> Any:
    """TensorRT, imported on first use; its compiled bindings ship without type stubs."""
    import tensorrt

    return tensorrt


@dataclass(frozen=True)
class EngineKey:
    """Everything an Engine depends on: a change to any of it means another Engine (ADR-0005)."""

    model_revision: str
    tiny_vae_revision: str
    component: Component
    min_side: int
    max_side: int
    precision: Precision
    export_version: int
    gpu: str
    compute_capability: tuple[int, int]
    tensorrt: str

    @classmethod
    def for_this_machine(cls, spec: ModelSpec, component: Component, precision: Precision = "fp16") -> "EngineKey":
        trt = _tensorrt()

        major, minor = torch.cuda.get_device_capability()
        precision = component_precision(component, precision)
        int8 = precision == "int8"
        return cls(
            model_revision=spec.model.revision,
            tiny_vae_revision=spec.tiny_vae.revision,
            component=component,
            min_side=min(INT8_RESOLUTIONS[0]) if int8 else spec.min_side,
            max_side=max(INT8_RESOLUTIONS[1]) if int8 else spec.max_side,
            precision=precision,
            export_version=COHERENT_EXPORT_VERSION if coherent(component, precision) else EXPORT_VERSION,
            gpu=torch.cuda.get_device_name(),
            compute_capability=(major, minor),
            tensorrt=trt.__version__,
        )

    @property
    def filename(self) -> str:
        """Readable where it matters, hashed so the name stays short and safe for any GPU name."""
        digest = hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()[:12]
        cc = "".join(map(str, self.compute_capability))
        sides = f"{self.min_side}-{self.max_side}"
        return f"{self.component}-{self.precision}-{sides}-sm{cc}-trt{self.tensorrt}-{digest}.plan"


def coherent(component: Component, precision: Precision) -> bool:
    """Only the FP16 UNet has Temporal Coherence; the INT8 bench UNet stays without it."""
    return component == "unet" and precision == "fp16"


def _coherent_layers(backend: PyTorchBackend, component: Component, precision: Precision) -> list[CoherentLayer]:
    return backend.coherent_layers if coherent(component, precision) else []


def engine_paths(engines_dir: Path, spec: ModelSpec, precision: Precision = "fp16") -> dict[Component, Path]:
    return {c: engines_dir / EngineKey.for_this_machine(spec, c, precision).filename for c in COMPONENTS}


def missing_engines(engines_dir: Path, spec: ModelSpec, precision: Precision = "fp16") -> list[Component]:
    return [c for c, path in engine_paths(engines_dir, spec, precision).items() if not path.is_file()]


class _Unet(torch.nn.Module):
    """The UNet with ONNX-friendly inputs: a float32 timestep instead of an int64 one."""

    def __init__(self, unet: torch.nn.Module) -> None:
        super().__init__()
        self.unet = unet

    def forward(self, sample: torch.Tensor, timestep: torch.Tensor, encoder_hidden_states: torch.Tensor):
        return self.unet(sample, timestep, encoder_hidden_states=encoder_hidden_states, return_dict=False)[0]


class _TinyVae(torch.nn.Module):
    """One half of the tiny VAE, with its weights registered so the export sees them as parameters."""

    def __init__(self, vae: torch.nn.Module, half: Literal["encode", "decode"]) -> None:
        super().__init__()
        self.vae, self.part = vae, half

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return getattr(self.vae, self.part)(x, return_dict=False)[0]


Shape = tuple[int, ...]
SWITCH = "switch"  # the FP16 UNet's Temporal Coherence input: 1 attends to the previous features, 0 masks them out


def feature_names(index: int) -> tuple[str, str, str, str]:
    """A coherent layer's Engine tensors: its previous keys and values in, this call's keys and values out."""
    return f"previous_keys_{index}", f"previous_values_{index}", f"keys_{index}", f"values_{index}"


@dataclass(frozen=True)
class _Io:
    """One component's ONNX inputs: (name, example shape, min shape, max shape) with sides in pixels or cells."""

    inputs: tuple[tuple[str, Shape, Shape, Shape], ...]
    outputs: tuple[str, ...]
    dynamic: dict[str, dict[int, str]]


def _io(
    component: Component,
    spec: ModelSpec,
    latent_scale: int,
    precision: Precision = "fp16",
    layers: Sequence[CoherentLayer] = (),
) -> _Io:
    """`layers` are the self-attention layers the FP16 UNet takes and returns Temporal Coherence features for."""
    lo, hi, step = spec.min_side, spec.max_side, spec.side_step
    mid = (lo + hi) // 2 // step * step
    if component == "unet":
        cells = (lo // latent_scale, mid // latent_scale, hi // latent_scale)
        sample = ((1, 4, cells[1], cells[1]), (1, 4, cells[0], cells[0]), (1, 4, cells[2], cells[2]))
        if precision == "int8":
            (lw, lh), (hw, hh) = INT8_RESOLUTIONS
            low, high = (1, 4, lh // latent_scale, lw // latent_scale), (1, 4, hh // latent_scale, hw // latent_scale)
            sample = (high, low, high)
        text = (1, TEXT_TOKENS, TEXT_DIM)
        inputs = [("sample", *sample), ("timestep", (1,), (1,), (1,)), ("encoder_hidden_states", text, text, text)]
        outputs, dynamic = ["noise"], {"sample": {2: "h", 3: "w"}, "noise": {2: "h", 3: "w"}}
        if layers:
            inputs.append((SWITCH, (1,), (1,), (1,)))
        for index, layer in enumerate(layers):
            low, opt, high = ((1, layer.tokens(c, c), layer.channels) for c in cells)
            names = feature_names(index)
            inputs += [(names[0], opt, low, high), (names[1], opt, low, high)]
            outputs += names[2:]
            dynamic |= {name: {1: f"tokens_{layer.downsample}"} for name in names}
        return _Io(tuple(inputs), tuple(outputs), dynamic)
    if component == "vae_encoder":
        return _Io(
            inputs=(("image", (1, 3, mid, mid), (1, 3, lo, lo), (1, 3, hi, hi)),),
            outputs=("latents",),
            dynamic={"image": {2: "H", 3: "W"}, "latents": {2: "h", 3: "w"}},
        )
    cells = (lo // latent_scale, mid // latent_scale, hi // latent_scale)
    return _Io(
        inputs=(("latents", (1, 4, cells[1], cells[1]), (1, 4, cells[0], cells[0]), (1, 4, cells[2], cells[2])),),
        outputs=("image",),
        dynamic={"latents": {2: "h", 3: "w"}, "image": {2: "H", 3: "W"}},
    )


@contextlib.contextmanager
def _fp32_normalization(module: torch.nn.Module) -> Iterator[None]:
    """Export GroupNorm and LayerNorm as float32 compute between casts.

    A strongly typed FP16 Engine computes normalisation statistics in FP16, where the squares overflow and the
    whole UNet output turns to NaN; PyTorch computes them in float32 internally.

    The patch sits on the PyTorch Backend's own modules, which keep generating during a background build: the
    patched forward computes the same result as the original, so a Generation running meanwhile is unaffected.
    """
    patched: list[torch.nn.Module] = []
    for norm in module.modules():
        if isinstance(norm, torch.nn.GroupNorm):
            norm.forward = functools.partial(_group_norm, norm)  # pyright: ignore[reportAttributeAccessIssue]
        elif isinstance(norm, torch.nn.LayerNorm):
            norm.forward = functools.partial(_layer_norm, norm)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            continue
        patched.append(norm)
    try:
        yield
    finally:
        for norm in patched:
            del norm.forward


def _group_norm(norm: torch.nn.GroupNorm, x: torch.Tensor) -> torch.Tensor:
    weight = norm.weight.float() if norm.weight is not None else None
    bias = norm.bias.float() if norm.bias is not None else None
    return F.group_norm(x.float(), norm.num_groups, weight, bias, norm.eps).to(x.dtype)


def _layer_norm(norm: torch.nn.LayerNorm, x: torch.Tensor) -> torch.Tensor:
    weight = norm.weight.float() if norm.weight is not None else None
    bias = norm.bias.float() if norm.bias is not None else None
    return F.layer_norm(x.float(), norm.normalized_shape, weight, bias, norm.eps).to(x.dtype)


def export_onnx(
    backend: PyTorchBackend, component: Component, spec: ModelSpec, path: Path, precision: Precision = "fp16"
) -> None:
    """Export one component of the loaded PyTorch Backend to ONNX (weights in a file beside it)."""
    module: torch.nn.Module
    if coherent(component, precision):
        module = backend.coherent_graph()
    elif component == "unet":
        module = _Unet(backend.unet_module())
    else:
        module = _TinyVae(backend._vae, "encode" if component == "vae_encoder" else "decode")
    io = _io(component, spec, backend.latent_scale, precision, _coherent_layers(backend, component, precision))
    dtypes = {"timestep": torch.float32}
    on_cpu = backend.device.type == "cpu"  # tracing on the CPU is slow: trace the smallest shape there
    args = tuple(
        torch.zeros(lo if on_cpu else opt, dtype=dtypes.get(name, backend.dtype), device=backend.device)
        for name, opt, lo, _ in io.inputs
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with torch.inference_mode(), _fp32_normalization(module):
        torch.onnx.export(
            module.eval(),
            args,
            str(path),
            dynamo=False,
            input_names=[name for name, *_ in io.inputs],
            output_names=list(io.outputs),
            dynamic_axes=io.dynamic,
            opset_version=17,
            external_data=True,
        )


def build_engine(
    onnx_path: Path,
    engine_path: Path,
    component: Component,
    spec: ModelSpec,
    latent_scale: int,
    progress=None,
    precision: Precision = "fp16",
    layers: Sequence[CoherentLayer] = (),
) -> None:
    """Build and save one Engine with a dynamic-shape profile covering every Generation Resolution."""
    trt = _tensorrt()

    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    # Strongly typed: the ONNX's own dtypes (FP16, or INT8 Q/DQ) decide every layer's precision.
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.STRONGLY_TYPED))
    parser = trt.OnnxParser(network, logger)
    if not parser.parse_from_file(str(onnx_path)):
        errors = "; ".join(str(parser.get_error(i)) for i in range(parser.num_errors))
        raise RuntimeError(f"could not parse {onnx_path.name}: {errors}")
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, WORKSPACE_BYTES[precision])
    if progress is not None:
        config.progress_monitor = progress
    profile = builder.create_optimization_profile()
    for name, opt, lo, hi in _io(component, spec, latent_scale, precision, layers).inputs:
        profile.set_shape(name, lo, opt, hi)
    config.add_optimization_profile(profile)
    serialized = builder.build_serialized_network(network, config)
    del parser, network  # the parser keeps the ONNX weight files open, which would stop the caller removing them
    if serialized is None:
        raise RuntimeError(f"TensorRT could not build the {component} Engine")
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    partial = engine_path.with_suffix(".partial")
    partial.write_bytes(memoryview(serialized))
    partial.replace(engine_path)  # a crash mid-write never leaves a broken Engine in the cache


def _progress_monitor(component: Component, done: int, total: int, report: Progress, cancel: threading.Event):
    """A TensorRT progress monitor reporting the build as a fraction of all Engines.

    A phase's fraction counts its finished steps plus the fraction of its running sub-phase, so the slow tactic
    search inside one top-level step still moves the bar.
    """
    trt = _tensorrt()

    class Monitor(trt.IProgressMonitor):
        def __init__(self) -> None:
            trt.IProgressMonitor.__init__(self)
            self._phases: dict[str, tuple[int, int, str | None]] = {}  # name: (finished, steps, parent)
            self._reported = 0.0

        def phase_start(self, phase_name, parent_phase, num_steps):
            self._phases[phase_name] = (0, max(1, num_steps), parent_phase)

        def step_complete(self, phase_name, step):
            _, steps, parent = self._phases.get(phase_name, (0, 1, None))
            self._phases[phase_name] = (min(step + 1, steps), steps, parent)
            top = [name for name, (*_, parent) in self._phases.items() if parent is None]
            # A finished sub-phase can briefly lower the estimate: report only forward steps of 0.1% or more.
            fraction = (done + self._fraction(top[0])) / total if top else 0.0
            if fraction >= self._reported + 0.001:
                self._reported = fraction
                report(component, fraction)
            return not cancel.is_set()

        def phase_finish(self, phase_name):
            self._phases.pop(phase_name, None)

        def _fraction(self, phase: str) -> float:
            finished, steps, _ = self._phases[phase]
            running = [name for name, (*_, parent) in self._phases.items() if parent == phase]
            inner = self._fraction(running[-1]) if running and finished < steps else 0.0
            return min(1.0, (finished + inner) / steps)

    return Monitor()


def build_engines(
    backend: PyTorchBackend,
    spec: ModelSpec,
    engines_dir: Path,
    precision: Precision = "fp16",
    progress: Progress | None = None,
    cancel: threading.Event | None = None,
) -> dict[Component, Path]:
    """Export and build every missing Engine; returns the Engine paths. Existing Engines are reused."""
    cancel = cancel or threading.Event()
    paths = engine_paths(engines_dir, spec, precision)
    todo: list[Component] = [c for c, path in paths.items() if not path.is_file()]
    report = progress or (lambda _component, _fraction: None)
    for done, component in enumerate(todo):
        report(component, done / len(todo))
        work = engines_dir / "onnx" / paths[component].stem
        try:
            if component == "unet" and precision == "int8":
                from streamturbo.backends import int8

                int8.export_quantized_unet(backend, spec, work / "model.onnx")
            else:
                export_onnx(backend, component, spec, work / "model.onnx")
            torch.cuda.empty_cache()
            monitor = _progress_monitor(component, done, len(todo), report, cancel)
            build_engine(
                work / "model.onnx",
                paths[component],
                component,
                spec,
                backend.latent_scale,
                monitor,
                component_precision(component, precision),
                _coherent_layers(backend, component, precision),
            )
        finally:
            shutil.rmtree(work, ignore_errors=True)
        if cancel.is_set():
            raise RuntimeError("Engine build cancelled")
    report("", 1.0)
    return paths


class _Scratch:
    """Activation memory the Engines share: they run one after another on one stream, so one buffer, sized for
    the largest shape actually used rather than for the 1024x1024 maximum, serves all three."""

    def __init__(self, device: torch.device) -> None:
        self.tensor = torch.empty(0, dtype=torch.uint8, device=device)
        self.version = 0  # bumped when the buffer moves, which invalidates captured CUDA graphs

    def ensure(self, nbytes: int) -> None:
        if nbytes > self.tensor.numel():
            self.tensor = torch.empty(nbytes, dtype=torch.uint8, device=self.tensor.device)
            self.version += 1


class Engine:
    """One deserialised Engine with an execution context, run on the caller's current CUDA stream.

    Each input shape gets its own CUDA graph after a first eager run, so a Generation replays one launch per
    Engine instead of hundreds of kernel launches.
    """

    def __init__(self, path: Path, runtime, scratch: _Scratch, cuda_graphs: bool = True) -> None:
        trt = _tensorrt()

        self._engine = runtime.deserialize_cuda_engine(path.read_bytes())
        if self._engine is None:
            raise RuntimeError(f"could not load the Engine {path.name}")
        self._context = self._engine.create_execution_context(trt.ExecutionContextAllocationStrategy.USER_MANAGED)
        self._scratch, self._scratch_version = scratch, scratch.version
        self._names = [self._engine.get_tensor_name(i) for i in range(self._engine.num_io_tensors)]
        self._inputs = [n for n in self._names if self._engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT]
        self._outputs = [n for n in self._names if self._engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT]
        # TensorRT's own auxiliary streams are blocking ones: while a capture forks onto them, any other thread's
        # work on the legacy stream fails with CUDA_ERROR_STREAM_CAPTURE_IMPLICIT. Torch's streams are non-blocking.
        self._aux_streams = [torch.cuda.Stream(scratch.tensor.device) for _ in range(self._engine.num_aux_streams)]
        if self._aux_streams:
            self._context.set_aux_streams([s.cuda_stream for s in self._aux_streams])
        self._cuda_graphs = cuda_graphs
        self._graphs: dict[tuple, tuple[torch.cuda.CUDAGraph | None, dict[str, torch.Tensor]]] = {}
        self._dtype = {n: _torch_dtype(self._engine.get_tensor_dtype(n)) for n in self._names}

    @property
    def inputs(self) -> list[str]:
        return self._inputs

    def __call__(self, **inputs: torch.Tensor) -> torch.Tensor:
        """The first output; `run` returns them all."""
        return self.run(**inputs)[self._outputs[0]]

    def run(self, **inputs: torch.Tensor) -> dict[str, torch.Tensor]:
        """Every output by name, copied out of the buffers the next call reuses."""
        key = tuple(tuple(inputs[n].shape) for n in self._inputs)
        stream = torch.cuda.current_stream()
        if self._scratch_version != self._scratch.version:  # another Engine grew the shared buffer
            self._graphs.clear()
            self._scratch_version = self._scratch.version
        if key not in self._graphs:
            self._graphs[key] = self._prepare(inputs, stream)
        graph, buffers = self._graphs[key]
        for name in self._inputs:
            buffers[name].copy_(inputs[name])
        if graph is None:
            self._context.execute_async_v3(stream.cuda_stream)
        else:
            graph.replay()
        return {name: buffers[name].clone() for name in self._outputs}

    def _prepare(self, inputs: dict[str, torch.Tensor], stream: torch.cuda.Stream):
        buffers = {n: torch.empty_like(inputs[n], dtype=self._dtype[n]).contiguous() for n in self._inputs}
        for name, tensor in buffers.items():
            self._context.set_input_shape(name, tuple(tensor.shape))
        self._scratch.ensure(self._context.update_device_memory_size_for_shapes())
        if self._scratch_version != self._scratch.version:  # the buffer moved: earlier graphs point at the old one
            self._graphs.clear()
            self._scratch_version = self._scratch.version
        self._context.set_device_memory(self._scratch.tensor.data_ptr(), self._scratch.tensor.numel())
        for name in self._outputs:
            shape = tuple(self._context.get_tensor_shape(name))
            buffers[name] = torch.empty(shape, dtype=self._dtype[name], device=inputs[self._inputs[0]].device)
        for name, tensor in buffers.items():
            self._context.set_tensor_address(name, tensor.data_ptr())
        for name in self._inputs:
            buffers[name].copy_(inputs[name])
        self._context.execute_async_v3(stream.cuda_stream)  # the eager run TensorRT needs before a capture
        if not self._cuda_graphs:
            return None, buffers
        graph = torch.cuda.CUDAGraph()
        # Captured on torch's side stream; thread-local so the send thread may keep waiting on its events.
        with torch.cuda.graph(graph, capture_error_mode="thread_local"):
            self._context.execute_async_v3(torch.cuda.current_stream().cuda_stream)
        return graph, buffers


def _torch_dtype(dtype) -> torch.dtype:
    trt = _tensorrt()

    return {
        trt.DataType.FLOAT: torch.float32,
        trt.DataType.HALF: torch.float16,
        trt.DataType.INT32: torch.int32,
        trt.DataType.INT64: torch.int64,
        trt.DataType.BOOL: torch.bool,
    }[dtype]


def builder(pytorch: PyTorchBackend, spec: ModelSpec, engines_dir: Path, precision: Precision = "fp16"):
    """The background build for BestBackend: reuse or build the Engines, then load them."""

    def build(report: ProgressReport) -> "TensorRTBackend":
        paths = build_engines(pytorch, spec, engines_dir, precision, lambda part, fraction: report(fraction, part))
        return TensorRTBackend(pytorch, paths)

    return build


class TensorRTBackend:
    name = "tensorrt"
    latent_channels = 4
    latent_scale = 8

    def __init__(self, pytorch: PyTorchBackend, paths: dict[Component, Path], cuda_graphs: bool = True) -> None:
        trt = _tensorrt()

        self._pytorch = pytorch
        self.device, self.dtype = pytorch.device, pytorch.dtype
        self.alphas_cumprod = pytorch.alphas_cumprod
        self._runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
        scratch = _Scratch(self.device)
        self._unet = Engine(paths["unet"], self._runtime, scratch, cuda_graphs)
        self._encoder = Engine(paths["vae_encoder"], self._runtime, scratch, cuda_graphs)
        self._decoder = Engine(paths["vae_decoder"], self._runtime, scratch, cuda_graphs)
        # The INT8 bench UNet has no Temporal Coherence inputs; it then generates plainly.
        self._layers = pytorch.coherent_layers if SWITCH in self._unet.inputs else []
        self._switch = {on: torch.full((1,), float(on), dtype=self.dtype, device=self.device) for on in (0, 1)}
        self._zeros: tuple[Shape, dict[str, torch.Tensor]] = ((), {})  # masked-out features for one latent size

    def encode_prompt(self, prompt: str) -> torch.Tensor:
        return self._pytorch.encode_prompt(prompt)

    def encode(self, image: torch.Tensor) -> torch.Tensor:
        return self._encoder(image=image)

    def decode(self, latents: torch.Tensor) -> torch.Tensor:
        return self._decoder(latents=latents)

    def upscale(self, image: torch.Tensor) -> torch.Tensor:
        return self._pytorch.upscale(image)  # the PyTorch Upscaler until it has an Engine (#21)

    def unet(self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor) -> torch.Tensor:
        return self.coherent_unet(latents, timestep, prompt_embeds, None)[0]

    def coherent_unet(
        self, latents: torch.Tensor, timestep: torch.Tensor, prompt_embeds: torch.Tensor, previous: object | None
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor] | None]:
        plain = {"sample": latents, "timestep": timestep, "encoder_hidden_states": prompt_embeds}
        if not self._layers:
            return self._unet(**plain), None
        zeros = self._features_for(latents.shape)
        features: dict[str, torch.Tensor] = previous if isinstance(previous, dict) else zeros
        on = features is not zeros and all(features[n].shape == t.shape for n, t in zeros.items())
        outputs = self._unet.run(**plain, **(features if on else zeros), switch=self._switch[int(on)])
        returned: dict[str, torch.Tensor] = {}
        for index in range(len(self._layers)):
            keys, values, new_keys, new_values = feature_names(index)
            returned |= {keys: outputs[new_keys], values: outputs[new_values]}
        return outputs["noise"], returned

    def _features_for(self, latent_shape: Shape) -> dict[str, torch.Tensor]:
        """Zero features for a latent size: what the Engine gets, masked out, when there are no previous ones."""
        if self._zeros[0] != latent_shape:
            cells_h, cells_w = latent_shape[-2:]
            zeros = {}
            for index, layer in enumerate(self._layers):
                shape = (1, layer.tokens(cells_h, cells_w), layer.channels)
                keys, values, *_ = feature_names(index)
                zeros |= {name: torch.zeros(shape, dtype=self.dtype, device=self.device) for name in (keys, values)}
            self._zeros = (tuple(latent_shape), zeros)
        return self._zeros[1]
