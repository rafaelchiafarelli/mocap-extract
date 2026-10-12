"""Calibration (P3): FreeMoCap ChArUco calibration of one synced CALIBRATION take.

The board comes only from `take.json` (`Take.board`, copied there by the
recorder from its declaration), and the square length used is the one
measured on the print (`measured_square_length_mm`), so 3D comes out in mm.
FreeMoCap 1.8.2 detects only its own boards (5x3 and 7x5 squares,
DICT_4X4_250, marker 0.8 of the square); any other board is refused before
anything runs.

FreeMoCap calibrates `extract/synced/` (alignment's output) with camera 0
pinned to the origin and then, if it finds a still frame of the board, the
board as the ground plane (lay it flat on the floor at the start of the take).
It writes the .toml next to the synced folder and into ~/freemocap_data; the
copy that counts is `<session>/calibration/calibration.toml`.

FreeMoCap discards its calibration error, so the reprojection error is
measured here: the board corners are detected again (FreeMoCap's own
detector, skellytracker), triangulated with the new calibration and projected
back, in pixels, overall and per camera.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mocap_contracts import ContractError, Take, TakeType, from_json, layout

from mocap_extract.freemocap_import import import_freemocap

CALIBRATION = TakeType.Value("TAKE_TYPE_CALIBRATION")
# What FreeMoCap 1.8.2 can detect (charuco_board_definition.py, anipose_camera_calibrator.py).
FREEMOCAP_BOARD_SQUARES = ((5, 3), (7, 5))
FREEMOCAP_DICTIONARY = "DICT_4X4_250"
FREEMOCAP_MARKER_RATIO = 0.8


class CalibrationError(ValueError):
    """The take can't be calibrated (wrong type, no board, unsupported board, missing videos, ...)."""


@dataclass(frozen=True)
class Calibration:
    toml_path: Path
    """`<session>/calibration/calibration.toml`."""
    reprojection_error_px: float
    """Mean over every board corner seen by at least two cameras."""
    camera_error_px: dict[str, float]
    """Mean per camera (role), over the corners it saw."""
    groundplane: bool
    groundplane_error: str | None


def calibrate(take_dir: Path | str) -> Calibration:
    take_dir = Path(take_dir)
    take = _read_take(take_dir)
    roles = [c.config.role for c in take.cameras]
    synced = [layout.synced_video(take_dir, role) for role in roles]
    missing = [v.relative_to(take_dir).as_posix() for v in synced if not v.is_file()]
    if missing:
        raise CalibrationError(f"run mocap-extract align first: {missing} not found")
    extra = sorted({p.name for p in synced[0].parent.glob("*.mp4")} - {v.name for v in synced})
    if extra:
        raise CalibrationError(f"{synced[0].parent} holds videos take.json doesn't list: {extra}")

    import_freemocap()
    definition = _board_definition(take)
    square_mm = take.board.measured_square_length_mm

    from freemocap.core_processes.capture_volume_calibration.run_anipose_capture_volume_calibration import (
        run_anipose_capture_volume_calibration,
    )

    toml, groundplane = run_anipose_capture_volume_calibration(
        charuco_board_definition=definition,
        charuco_square_size=square_mm,
        calibration_videos_folder_path=synced[0].parent,
        pin_camera_0_to_origin=True,
        use_charuco_as_groundplane=True,
    )
    out = layout.calibration_toml(take_dir.parents[2], take.session_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(toml, out)

    overall, per_camera = reprojection_errors(out, synced[0].parent, definition)
    return Calibration(
        toml_path=out,
        reprojection_error_px=overall,
        camera_error_px=per_camera,
        groundplane=bool(groundplane and groundplane.success),
        groundplane_error=None if groundplane is None or groundplane.success else groundplane.error,
    )


def reprojection_errors(toml: Path, videos_dir: Path, definition) -> tuple[float, dict[str, float]]:
    """(mean, per camera) reprojection error in px of the board corners in `videos_dir` under `toml`."""
    import_freemocap()
    import cv2
    from freemocap.core_processes.capture_volume_calibration.anipose_camera_calibration.freemocap_anipose import (
        CameraGroup,
    )
    from freemocap.utilities.get_video_paths import get_video_paths
    from skellytracker.process_folder_of_videos import process_list_of_videos
    from skellytracker.trackers.charuco_tracker.charuco_model_info import CharucoModelInfo, CharucoTrackingParams

    group = CameraGroup.load(str(toml))
    videos = get_video_paths(videos_dir)
    names = [v.stem for v in videos]
    if names != group.get_names():
        raise CalibrationError(f"{toml.name} cameras {group.get_names()} != videos {names}")
    data = process_list_of_videos(
        model_info=CharucoModelInfo(),
        tracking_params=CharucoTrackingParams(
            charuco_squares_x_in=definition.number_of_squares_width,
            charuco_squares_y_in=definition.number_of_squares_height,
            charuco_dict_id=getattr(cv2.aruco, FREEMOCAP_DICTIONARY),
        ),
        video_paths=videos,
        num_processes=1,
    )
    p2d = data[..., :2].reshape(len(videos), -1, 2).astype(np.float64)
    seen = np.sum(~np.isnan(p2d[..., 0]), axis=0) >= 2
    if not seen.any():
        raise CalibrationError("no board corner is seen by two cameras at once")
    p2d = p2d[:, seen]
    p3d = group.triangulate(p2d)
    err = np.linalg.norm(group.reprojection_error(p3d, p2d), axis=2)  # cameras x points
    err[np.isnan(p2d[..., 0])] = np.nan
    per_camera = {name: float(np.nanmean(e)) for name, e in zip(names, err)}
    return float(np.nanmean(err)), per_camera


def _read_take(take_dir: Path) -> Take:
    path = layout.take_json(take_dir)
    if not path.is_file():
        raise CalibrationError("take.json not found")
    try:
        take = from_json(Take, path.read_text(encoding="utf-8"))
    except ContractError as e:
        raise CalibrationError(f"take.json: {e}") from None
    if take.type != CALIBRATION:
        raise CalibrationError(f"take {take.id} is not a CALIBRATION take")
    if not take.HasField("board"):
        raise CalibrationError(f"take {take.id} has no board in take.json")
    if layout.take_dir(take_dir.parents[2], take.session_id, take.id) != take_dir:
        raise CalibrationError(f"{take_dir} isn't <root>/{take.session_id}/takes/{take.id}")
    return take


def _board_definition(take: Take):
    from freemocap.core_processes.capture_volume_calibration.charuco_stuff.charuco_board_definition import (
        CharucoBoardDefinition,
    )

    b = take.board
    squares = (b.squares_x, b.squares_y)
    problems = []
    if squares not in FREEMOCAP_BOARD_SQUARES:
        problems.append(f"{squares[0]}x{squares[1]} squares (FreeMoCap: {FREEMOCAP_BOARD_SQUARES})")
    if b.aruco_dictionary != FREEMOCAP_DICTIONARY:
        problems.append(f"dictionary {b.aruco_dictionary} (FreeMoCap: {FREEMOCAP_DICTIONARY})")
    if abs(b.marker_length_mm / b.square_length_mm - FREEMOCAP_MARKER_RATIO) > 0.01:
        problems.append(f"marker {b.marker_length_mm:g} mm on a {b.square_length_mm:g} mm square "
                        f"(FreeMoCap: {FREEMOCAP_MARKER_RATIO:g} of the square)")
    if problems:
        raise CalibrationError("FreeMoCap 1.8.2 can't detect this board: " + "; ".join(problems))
    return CharucoBoardDefinition(
        name=f"{squares[0]}x{squares[1]} Charuco",
        number_of_squares_width=squares[0],
        number_of_squares_height=squares[1],
        black_square_side_length=1,
        aruco_marker_length_proportional=FREEMOCAP_MARKER_RATIO,
    )
