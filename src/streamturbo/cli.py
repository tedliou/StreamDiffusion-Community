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
    run = commands.add_parser("run", help="run the Runtime (defaults: the Glass Preset, NDI in and out)")
    run.add_argument("--settings", type=Path, help="a Settings TOML file")
    run.add_argument("--list-sources", action="store_true", help="list visible NDI and Spout senders and exit")
    bench = commands.add_parser("bench", help="measure the Glass workload and write a JSON report")
    bench.add_argument("--settings", type=Path, help="a Settings TOML file")
    bench.add_argument("--frames", type=int, default=120, help="frames to measure after warm-up")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        from streamturbo import doctor

        report = doctor.collect()
        print(doctor.render(report))
        return 0 if report.ok else 1
    if args.command == "run":
        return _list_sources() if args.list_sources else _run(_settings(args.settings))
    from streamturbo import bench as bench_module

    report_path = bench_module.run(_settings(args.settings), args.frames)
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


def _run(settings) -> int:
    from streamturbo import weights
    from streamturbo.backends.pytorch import PyTorchBackend
    from streamturbo.model_spec import SD_TURBO
    from streamturbo.runtime import Runtime
    from streamturbo.transports import create_sink, create_source

    print("Loading sd-turbo ...")
    backend = PyTorchBackend(SD_TURBO, *weights.fetch_all(SD_TURBO))
    source, sink = create_source(settings.source), create_sink(settings.sink)
    src, dst = settings.source, settings.sink
    print(f"Source: {src.transport} {src.name or '(first visible)'}  ->  Sink: {dst.transport} {dst.name}")
    print("Running. Press Ctrl+C to stop.")
    with Runtime(settings, backend, source, sink) as runtime:
        try:
            while True:
                time.sleep(1)
                status = runtime.status()
                line = (
                    f"source {status.source_state:<7} | {status.throughput_fps:5.1f} fps | "
                    f"generation {status.generation_ms_p50:5.0f} ms p50, {status.generation_ms_p95:5.0f} ms p95 | "
                    f"dropped {status.dropped_frames}"
                )
                if status.error:
                    line += f" | {status.error}"
                print(line.ljust(110), end="\r", flush=True)
        except KeyboardInterrupt:
            print("\nStopping ...")
    return 0
