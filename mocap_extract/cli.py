"""`mocap-extract` command line."""

import argparse
import sys
from pathlib import Path

from mocap_extract import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mocap-extract", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mocap-extract {__version__}")
    sub = parser.add_subparsers(dest="command")

    align = sub.add_parser("align", help="resample every camera of one take to extract/synced/<role>.mp4")
    align.add_argument("take_dir", type=Path, help="the take folder, as the recorder handed it off")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "align":
        return _align(args.take_dir)
    parser.print_help()
    return 0


def _align(take_dir: Path) -> int:
    from mocap_extract.alignment import AlignmentError, compute_alignment
    from mocap_extract.resample import resample_role

    try:
        alignment = compute_alignment(take_dir)
        for cam in alignment.cameras:
            video = resample_role(take_dir, alignment, cam.role)
            print(
                f"{cam.role}: offset {cam.offset_ns / 1e6:.1f} ms, drift {cam.drift_ppm:+.0f} ppm, "
                f"{cam.frames_in} frames in, {video.frames_out} out -> {video.path}"
            )
            for m in video.misaligned:
                print(f"  warning: output frames {m.first_out}-{m.last_out} up to {m.worst_ns / 1e6:.1f} ms off")
    except AlignmentError as e:
        print(f"mocap-extract align: {e}", file=sys.stderr)
        return 1
    return 0
