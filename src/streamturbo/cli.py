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
        return _list_sources() if args.list_sources else _run(args)
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


def _run(args: argparse.Namespace) -> int:
    import webbrowser

    from streamturbo import weights
    from streamturbo.backends.pytorch import PyTorchBackend
    from streamturbo.control import Control
    from streamturbo.control.osc import OscServer
    from streamturbo.control.web import WebServer
    from streamturbo.model_spec import SD_TURBO
    from streamturbo.paths import last_settings_path, presets_dir, project_home
    from streamturbo.presets import PresetStore, initial_settings
    from streamturbo.runtime import Runtime
    from streamturbo.transports import SystemTransports

    store, transports = PresetStore(presets_dir()), SystemTransports()
    settings = initial_settings(store, last_settings_path(), args.settings, args.preset)
    reply_host, _, reply_port = args.osc_reply.rpartition(":")
    print("Loading sd-turbo ...")
    backend = PyTorchBackend(*weights.fetch_all(SD_TURBO))
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
        f"dropped {status.dropped_frames}"
    )
    return f"{line} | {status.error}" if status.error else line


def _access_token(path: Path) -> str:
    """The LAN access token, kept across restarts so a tablet's bookmark keeps working."""
    import secrets

    if path.is_file() and (token := path.read_text(encoding="utf-8").strip()):
        return token
    token = secrets.token_urlsafe(16)
    path.write_text(token, encoding="utf-8")
    return token
