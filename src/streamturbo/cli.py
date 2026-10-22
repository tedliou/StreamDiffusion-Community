"""The `streamturbo` command line."""

import argparse
import time
from collections.abc import Sequence
from pathlib import Path

from streamturbo import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="streamturbo", description="Real-time sd-turbo Generation over NDI and Spout."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("doctor", help="report GPU, driver, library and Transport status")
    run = commands.add_parser("run", help="run the Runtime with the Web Panel and OSC (default: last-used Settings)")
    run.add_argument("--settings", type=Path, help="start from a Settings TOML file instead of the last-used Settings")
    run.add_argument("--preset", help="apply this Preset's look on start")
    run.add_argument("--list-sources", action="store_true", help="list visible NDI and Spout senders and exit")
    run.add_argument("--port", type=int, default=8765, help="Web Panel port (default 8765)")
    run.add_argument("--lan", action="store_true", help="also serve the Web Panel on the LAN, protected by a token")
    run.add_argument("--osc-port", type=int, default=7000, help="OSC port to listen on (default 7000)")
    run.add_argument(
        "--osc-reply", default="127.0.0.1:7001", metavar="HOST:PORT", help="where OSC status and Settings go"
    )
    run.add_argument("--no-browser", action="store_true", help="do not open the Web Panel in the browser")
    build = commands.add_parser("build-engines", help="build the TensorRT Engines now, e.g. before a show")
    build.add_argument("--precision", choices=("fp16", "int8"), default="fp16", help="UNet precision (default fp16)")
    bench = commands.add_parser("bench", help="measure the Glass workload and write a JSON report")
    bench.add_argument("--settings", type=Path, help="a Settings TOML file")
    bench.add_argument("--frames", type=int, default=120, help="frames to measure after warm-up")
    bench.add_argument("--backend", choices=("tensorrt", "pytorch"), default="tensorrt", help="default tensorrt")
    bench.add_argument("--precision", choices=("fp16", "int8"), default="fp16", help="TensorRT UNet precision")
    bench.add_argument("--input", type=Path, help="an image to use as the Input Frame instead of the test pattern")
    bench.add_argument(
        "--matrix", action="store_true", help="run the quality/speed matrix, saving one Output Frame per option"
    )

    args = parser.parse_args(argv)
    if args.command == "doctor":
        from streamturbo import doctor

        report = doctor.collect()
        print(doctor.render(report))
        return 0 if report.ok else 1
    if args.command == "run":
        return _list_sources() if args.list_sources else _run(args)
    if args.command == "build-engines":
        return _build_engines(args.precision)
    from streamturbo import bench as bench_module

    if args.matrix:
        folder = bench_module.matrix(_settings(args.settings), args.frames, image=args.input)
        print((folder / "results.md").read_text(encoding="utf-8"))
        print(f"Results and one image per option in {folder}")
        return 0
    report_path = bench_module.run(
        _settings(args.settings), args.frames, backend=args.backend, precision=args.precision, image=args.input
    )
    print(report_path.read_text(encoding="utf-8"))
    print(f"Report written to {report_path}")
    return 0


def _settings(path: Path | None):
    from streamturbo.settings import Settings

    return Settings.load(path) if path else Settings()


def _list_sources() -> int:
    from streamturbo.transports import list_senders

    for transport in ("ndi", "spout"):
        names = list_senders(transport)
        print(f"{transport.upper()}: {', '.join(names) if names else '(none visible)'}")
    return 0


def _run(args: argparse.Namespace) -> int:
    import webbrowser

    from streamturbo import weights
    from streamturbo.backends import BestBackend
    from streamturbo.backends.pytorch import PyTorchBackend
    from streamturbo.backends.tensorrt import builder
    from streamturbo.control import Control
    from streamturbo.control.osc import OscServer
    from streamturbo.control.web import WebServer
    from streamturbo.model_spec import SD_TURBO
    from streamturbo.paths import engines_dir, last_settings_path, presets_dir, project_home
    from streamturbo.presets import PresetStore, initial_settings
    from streamturbo.runtime import Runtime
    from streamturbo.transports import SystemTransports

    store, transports = PresetStore(presets_dir()), SystemTransports()
    settings = initial_settings(store, last_settings_path(), args.settings, args.preset)
    reply_host, _, reply_port = args.osc_reply.rpartition(":")
    print("Loading sd-turbo ...")
    pytorch = PyTorchBackend(*weights.fetch_all(SD_TURBO))
    backend = BestBackend(pytorch, builder(pytorch, SD_TURBO, engines_dir()))
    runtime = Runtime(settings, backend, transports)
    control = Control(runtime, store, transports, last_settings_path())
    token = _access_token(project_home() / "access-token") if args.lan else None
    web = WebServer(control, "0.0.0.0" if args.lan else "127.0.0.1", args.port, token)
    osc = OscServer(control, port=args.osc_port, reply_host=reply_host, reply_port=int(reply_port))
    src, dst = settings.source, settings.sink
    print(f"Source: {src.transport} {src.name or '(first visible)'}  ->  Sink: {dst.transport} {dst.name}")
    with runtime:
        web.start()
        osc.start()
        print(f"Web Panel: {web.url}")
        if args.lan:
            print(f"  on the LAN: http://<this computer's IP>:{web.port}/?token={token}")
        print(f"OSC: listening on {args.osc_port}, replying to {args.osc_reply}")
        print("Running. Press Ctrl+C to stop.")
        if not args.no_browser:
            webbrowser.open(web.url)
        try:
            while True:
                time.sleep(1)
                print(_status_line(runtime.status()).ljust(110), end="\r", flush=True)
        except KeyboardInterrupt:
            print("\nStopping ...")
        finally:
            osc.stop()
            web.stop()
    return 0


def _status_line(status) -> str:
    line = (
        f"source {status.source_state:<7} | throughput {status.throughput_fps:5.1f} fps | "
        f"generation {status.generation_ms_p50:5.0f} ms p50, {status.generation_ms_p95:5.0f} ms p95 | "
        f"dropped {status.dropped_frames} | {status.backend}"
    )
    if status.engines.state == "building":
        line += f" (building Engines {status.engines.progress:.0%})"
    elif status.engines.state == "failed":
        line += f" | Engines failed: {status.engines.detail}"
    return f"{line} | {status.error}" if status.error else line


def _build_engines(precision: str) -> int:
    from streamturbo import weights
    from streamturbo.backends.pytorch import PyTorchBackend
    from streamturbo.backends.tensorrt import build_engines, missing_engines
    from streamturbo.model_spec import SD_TURBO
    from streamturbo.paths import engines_dir

    todo = missing_engines(engines_dir(), SD_TURBO, precision)  # pyright: ignore[reportArgumentType]
    if not todo:
        print(f"All {precision} Engines are already built in {engines_dir()}")
        return 0
    print(f"Building {', '.join(todo)} ({precision}); this takes a few minutes once ...")
    pytorch = PyTorchBackend(*weights.fetch_all(SD_TURBO))

    def progress(component: str, fraction: float) -> None:
        print(f"  {component or 'done':<12} {fraction:4.0%}".ljust(40), end="\r", flush=True)

    paths = build_engines(pytorch, SD_TURBO, engines_dir(), precision, progress)  # pyright: ignore[reportArgumentType]
    print()
    for component, path in paths.items():
        print(f"{component:<12} {path}")
    return 0


def _access_token(path: Path) -> str:
    """The LAN access token, kept across restarts so a tablet's bookmark keeps working."""
    import secrets

    if path.is_file() and (token := path.read_text(encoding="utf-8").strip()):
        return token
    token = secrets.token_urlsafe(16)
    path.write_text(token, encoding="utf-8")
    return token
