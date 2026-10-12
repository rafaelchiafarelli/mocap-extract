"""A synthetic CALIBRATION take: pinhole cameras with known poses filming a ChArUco board that moves.

World: metres in, millimetres out (FreeMoCap works in the board's unit). y is up, every camera sits on a
circle around the origin at the same height and looks at the origin; the board wanders and tilts around it.
"""

import subprocess
from pathlib import Path

import cv2
import numpy as np
from mocap_contracts import (
    CalibrationBoard, CameraConfig, CameraSource, SyncEvent, SyncKind, SyncSource, Take, TakeCamera, TakeType,
    layout, to_json,
)

WIDTH, HEIGHT, FOCAL = 1280, 720, 900.0
K = np.array([[FOCAL, 0, WIDTH / 2], [0, FOCAL, HEIGHT / 2], [0, 0, 1]])
PX_PER_MM = 2.0
QUIET_ZONE_MM = 40


def rotation(yaw: float, pitch: float, roll: float) -> np.ndarray:
    cy, sy, cp, sp, cr, sr = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch), np.cos(roll), np.sin(roll)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return ry @ rx @ rz


def camera_poses(radius_mm: float, azimuths_deg: list[float]) -> list[tuple[np.ndarray, np.ndarray]]:
    """(R world->camera, centre) per camera: on the circle, looking at the origin, image y pointing down."""
    poses = []
    for az in np.radians(azimuths_deg):
        centre = np.array([radius_mm * np.sin(az), 0.0, radius_mm * np.cos(az)])
        forward = -centre / np.linalg.norm(centre)
        right = np.cross(forward, [0, 1, 0])
        right /= np.linalg.norm(right)
        down = np.cross(forward, right)
        poses.append((np.stack([right, down, forward]), centre))
    return poses


def board_image(board: CalibrationBoard) -> tuple[np.ndarray, float, float]:
    """The board with a white quiet zone, and its size in mm (with the quiet zone)."""
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, board.aruco_dictionary))
    charuco = cv2.aruco.CharucoBoard((board.squares_x, board.squares_y), board.square_length_mm,
                                     board.marker_length_mm, dictionary)
    w_mm, h_mm = board.squares_x * board.square_length_mm, board.squares_y * board.square_length_mm
    img = charuco.generateImage((int(w_mm * PX_PER_MM), int(h_mm * PX_PER_MM)), marginSize=0)
    q = int(QUIET_ZONE_MM * PX_PER_MM)
    img = cv2.copyMakeBorder(img, q, q, q, q, cv2.BORDER_CONSTANT, value=255)
    return img, w_mm + 2 * QUIET_ZONE_MM, h_mm + 2 * QUIET_ZONE_MM


def render(img: np.ndarray, w_mm: float, h_mm: float, r_board: np.ndarray, t_board: np.ndarray,
           r_cam: np.ndarray, centre: np.ndarray) -> np.ndarray:
    pixel_to_board = np.array([[1 / PX_PER_MM, 0, -w_mm / 2], [0, -1 / PX_PER_MM, h_mm / 2], [0, 0, 1]])
    board_to_image = K @ np.column_stack([r_cam @ r_board[:, 0], r_cam @ r_board[:, 1], r_cam @ (t_board - centre)])
    frame = cv2.warpPerspective(img, board_to_image @ pixel_to_board, (WIDTH, HEIGHT),
                                flags=cv2.INTER_AREA, borderValue=128)
    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)


def write_video(path: Path, frames: list[np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{WIDTH}x{HEIGHT}", "-r", "30", "-i", "-", "-c:v", "libx264", "-crf", "18",
           "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, input=b"".join(f.tobytes() for f in frames), check=True)


def make_calibration_take(take_dir: Path, board: CalibrationBoard, roles: list[str], azimuths_deg: list[float],
                          radius_mm: float = 2500, frames: int = 90, seed: int = 0,
                          still_frames: int = 0) -> list[np.ndarray]:
    """Write take.json and extract/synced/<role>.mp4; return the true camera centres (mm), in role order.

    The board holds its first pose for `still_frames` more frames, as when it's laid still for the ground plane.
    """
    rng = np.random.default_rng(seed)
    img, w_mm, h_mm = board_image(board)
    cams = camera_poses(radius_mm, azimuths_deg)
    poses = [(rotation(*np.radians(rng.uniform([-25, -25, -30], [25, 25, 30]))),
              rng.uniform([-300, -300, -300], [300, 300, 300])) for _ in range(frames)]
    poses = poses[:1] * still_frames + poses
    for role, (r_cam, centre) in zip(roles, cams):
        write_video(layout.synced_video(take_dir, role),
                    [render(img, w_mm, h_mm, rb, tb, r_cam, centre) for rb, tb in poses])

    def sync(kind: str, ts: int) -> SyncEvent:
        return SyncEvent(kind=SyncKind.Value(kind), host_ts_ns=ts, source=SyncSource.Value("SYNC_SOURCE_MANUAL"))

    take = Take(id=take_dir.name, session_id=take_dir.parents[1].name,
                type=TakeType.Value("TAKE_TYPE_CALIBRATION"),
                start=sync("SYNC_KIND_START", 1_000), end=sync("SYNC_KIND_END", 3_000_000_000), board=board)
    take.cameras.extend(TakeCamera(config=CameraConfig(
        role=role, source=CameraSource.Value("CAMERA_SOURCE_STREAM"), width=WIDTH, height=HEIGHT, fps=30,
        notes="synthetic", stream_host="192.168.1.20", video_port=8080, sync_port=8081, control_port=8082,
        stats_port=8083)) for role in roles)
    layout.take_json(take_dir).write_text(to_json(take), encoding="utf-8")
    return [centre for _, centre in cams]
