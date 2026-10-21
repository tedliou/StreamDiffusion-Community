"""The `streamturbo` command line."""

import argparse
from collections.abc import Sequence

from streamturbo import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="streamturbo", description="Real-time sd-turbo Generation over NDI and Spout."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("doctor", help="report GPU, driver, library and Transport status")

    args = parser.parse_args(argv)
    if args.command == "doctor":
        from streamturbo import doctor

        report = doctor.collect()
        print(doctor.render(report))
        return 0 if report.ok else 1
    parser.error(f"unknown command {args.command!r}")
