"""`mocap-extract` command line."""

import argparse

from mocap_extract import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mocap-extract", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mocap-extract {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
