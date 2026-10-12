from pathlib import Path

import cv2
import numpy as np
import pytest
import toml
from mocap_contracts import CalibrationBoard, layout
from synthetic_calibration import make_calibration_take
from takes import SESSION, TAKE, put_take_json

from mocap_extract.calibration import CalibrationError, calibrate
from mocap_extract.cli import main

BOARD = dict(squares_x=5, squares_y=3, square_length_mm=150, marker_length_mm=120,
             aruco_dictionary="DICT_4X4_250", measured_square_length_mm=150)
ROLES = ["body_1", "body_2", "body_3"]


@pytest.fixture
def take_dir(tmp_path: Path) -> Path:
    take = layout.take_dir(tmp_path, SESSION, TAKE)
    take.mkdir(parents=True)
    return take


def camera_centres(toml_path: Path) -> dict[str, np.ndarray]:
    centres = {}
    for key, cam in toml.load(toml_path).items():
        if key == "metadata":
            continue
        r, _ = cv2.Rodrigues(np.array(cam["rotation"], dtype=np.float64))
        centres[cam["name"]] = -r.T @ np.array(cam["translation"], dtype=np.float64)
    return centres


def test_calibration_recovers_the_cameras_in_mm(take_dir):
    truth = make_calibration_take(take_dir, CalibrationBoard(**BOARD), ROLES, [-35, 0, 35], still_frames=15).centres

    result = calibrate(take_dir)

    assert result.toml_path == layout.calibration_toml(take_dir.parents[2], SESSION)
    assert result.toml_path.is_file()
    assert result.reprojection_error_px < 1.0
    assert set(result.camera_error_px) == set(ROLES)
    assert result.groundplane, result.groundplane_error
    found = camera_centres(result.toml_path)
    for a, b in [("body_1", "body_2"), ("body_2", "body_3"), ("body_1", "body_3")]:
        true_mm = np.linalg.norm(truth[a] - truth[b])
        assert np.linalg.norm(found[a] - found[b]) == pytest.approx(true_mm, rel=0.02)


def kabsch(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """R, t with dst ~ R @ src + t (rows are points)."""
    cs, cd = src.mean(0), dst.mean(0)
    u, _, vt = np.linalg.svd((src - cs).T @ (dst - cd))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1, 1, d]) @ u.T
    return r, cd - r @ cs


def test_ground_plane_is_the_still_board(take_dir):
    truth = make_calibration_take(take_dir, CalibrationBoard(**BOARD), ROLES, [-35, 0, 35], still_frames=15)

    result = calibrate(take_dir)

    assert result.groundplane, result.groundplane_error
    found = camera_centres(result.toml_path)
    r, t = kabsch(np.array([truth.centres[k] for k in ROLES]), np.array([found[k] for k in ROLES]))
    normal = r @ truth.first_board_rotation[:, 2]
    assert abs(normal[2]) > 0.995  # Z perpendicular to the board
    board_centre = r @ truth.first_board_centre + t
    assert abs(board_centre[2]) < 10  # the board lies in z = 0 (mm)


def test_cli_calibrate(take_dir, capsys):
    make_calibration_take(take_dir, CalibrationBoard(**BOARD), ROLES, [-35, 0, 35], frames=60)

    assert main(["calibrate", str(take_dir), "--max-error-px", "1.0"]) == 0
    out = capsys.readouterr().out
    assert "reprojection error" in out and "body_3" in out
    assert "ground plane: not set" in out  # the board never holds still
    assert main(["calibrate", str(take_dir), "--max-error-px", "0.0001"]) == 2


def test_only_calibration_takes(take_dir):
    put_take_json(take_dir, {"body_1": 30.0}, 1_000, 2_000)
    with pytest.raises(CalibrationError, match="not a CALIBRATION take"):
        calibrate(take_dir)


@pytest.mark.parametrize("change, message", [
    (dict(squares_x=8, squares_y=11), "8x11 squares"),
    (dict(aruco_dictionary="DICT_6X6_250"), "dictionary DICT_6X6_250"),
    (dict(marker_length_mm=100), "marker 100 mm on a 150 mm square"),
])
def test_boards_freemocap_cant_detect_are_refused(take_dir, change, message):
    board = CalibrationBoard(**{**BOARD, **change})
    make_calibration_take(take_dir, board, ROLES[:2], [-20, 20], frames=2)
    with pytest.raises(CalibrationError, match=message):
        calibrate(take_dir)


def test_needs_the_synced_videos(take_dir):
    make_calibration_take(take_dir, CalibrationBoard(**BOARD), ROLES[:2], [-20, 20], frames=2)
    layout.synced_video(take_dir, "body_2").unlink()
    with pytest.raises(CalibrationError, match="run mocap-extract align first"):
        calibrate(take_dir)
