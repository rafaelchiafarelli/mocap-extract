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

    calibrate = sub.add_parser("calibrate", help="FreeMoCap calibration of an aligned CALIBRATION take")
    calibrate.add_argument("take_dir", type=Path, help="the CALIBRATION take folder, after align")
    calibrate.add_argument("--max-error-px", type=float,
                           help="exit 2 when the mean reprojection error is above this")

    body = sub.add_parser("body", help="FreeMoCap body and hands 3D of an aligned PERFORMANCE take")
    body.add_argument("take_dir", type=Path, help="the PERFORMANCE take folder, after align (and calibrate)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "align":
        return _align(args.take_dir)
    if args.command == "calibrate":
        return _calibrate(args.take_dir, args.max_error_px)
    if args.command == "body":
        return _body(args.take_dir)
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


def _calibrate(take_dir: Path, max_error_px: float | None) -> int:
    from mocap_extract.calibration import CalibrationError, calibrate

    try:
        result = calibrate(take_dir)
    except CalibrationError as e:
        print(f"mocap-extract calibrate: {e}", file=sys.stderr)
        return 1
    print(f"wrote {result.toml_path}")
    print(f"reprojection error {result.reprojection_error_px:.2f} px")
    for role, error in result.camera_error_px.items():
        print(f"  {role}: {error:.2f} px")
    print("ground plane: board" if result.groundplane else f"ground plane: not set ({result.groundplane_error})")
    if max_error_px is not None and result.reprojection_error_px > max_error_px:
        print(f"mocap-extract calibrate: error above {max_error_px:g} px", file=sys.stderr)
        return 2
    return 0


def _body(take_dir: Path) -> int:
    from mocap_extract.body import BodyError, extract_body

    try:
        body = extract_body(take_dir)
    except BodyError as e:
        print(f"mocap-extract body: {e}", file=sys.stderr)
        return 1
    print(f"3D: {body.data_3d} ({body.frames} frames, cameras {', '.join(body.roles)})")
    print(f"FreeMoCap recording folder (open it in the FreeMoCap Blender add-on): {body.recording_dir}")
    return 0
