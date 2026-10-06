"""Alignment (P3.1), step 1: per-camera offset and drift from the host-clock timestamps.

Every camera's frames are stamped on the recorder's host clock
(`raw/<role>.timestamps.csv`), so cameras need no common trigger: the START
marker in `take.json` is t0 and every camera is placed against it.

- **Window:** the frames with START <= host_ts_ns <= END.
- **Offset:** host time of the first frame in the window minus t0 (>= 0).
- **Drift:** the camera's measured frame period against the nominal one
  declared in `take.json` (`CameraConfig.fps`), in ppm. Positive means the
  camera runs slower than declared (longer period).

The measured period is a least-squares fit of host time against frame slot.
Slots, not row numbers, because a dropped frame leaves a gap: each step
between consecutive frames counts as round(step / median step) slots.

Inputs are read only once intake has verified them against their sidecars.
`report.json` isn't read: everything it summarises is in the timestamps, and
alignment starts before it arrives.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mocap_contracts import ContractError, Take, from_json, layout

from mocap_extract.intake import FileRejected, check_file


class AlignmentError(ValueError):
    """The take can't be aligned (missing END, unusable timestamps, ...)."""


@dataclass(frozen=True)
class CameraTiming:
    role: str
    nominal_fps: float
    measured_period_ns: float
    drift_ppm: float
    offset_ns: int
    """Host time of the first frame in the window minus t0."""
    frames_in: int
    """Frames inside [START, END]."""
    first_frame: int
    last_frame: int
    """`frame` values of the first and last frame inside the window."""


@dataclass(frozen=True)
class Alignment:
    take_id: str
    t0_ns: int
    """START marker on the host clock: frame 0 of the take."""
    end_ns: int
    """END marker on the host clock."""
    cameras: tuple[CameraTiming, ...]

    def camera(self, role: str) -> CameraTiming:
        for cam in self.cameras:
            if cam.role == role:
                return cam
        raise KeyError(role)


def compute_alignment(take_dir: Path | str) -> Alignment:
    take_dir = Path(take_dir)
    take = _read_take(take_dir)
    t0, end = take.start.host_ts_ns, take.end.host_ts_ns
    cameras = []
    for tc in take.cameras:
        role, fps = tc.config.role, tc.config.fps
        rel_path = layout.raw_timestamps(take_dir, role).relative_to(take_dir).as_posix()
        try:
            check_file(take_dir, rel_path)
        except FileRejected as e:
            raise AlignmentError(f"{role}: {e}") from None
        frames, ts = read_timestamps(take_dir / rel_path)
        cameras.append(_camera_timing(role, fps, frames, ts, t0, end))
    return Alignment(take_id=take.id, t0_ns=t0, end_ns=end, cameras=tuple(cameras))


def read_timestamps(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """(frame, host_ts_ns) columns of a timestamps CSV, as int64 arrays."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = tuple(next(reader, ()))
        if header != layout.TIMESTAMPS_COLUMNS:
            raise AlignmentError(f"{path.name}: header {header} != {layout.TIMESTAMPS_COLUMNS}")
        try:
            rows = [(int(frame), int(ts)) for frame, ts in reader]
        except ValueError as e:
            raise AlignmentError(f"{path.name}: {e}") from None
    data = np.array(rows, dtype=np.int64).reshape(-1, 2)
    frames, ts = data[:, 0], data[:, 1]
    if np.any(np.diff(frames) <= 0) or np.any(np.diff(ts) <= 0):
        raise AlignmentError(f"{path.name}: frame and host_ts_ns must both strictly increase")
    return frames, ts


def _read_take(take_dir: Path) -> Take:
    path = layout.take_json(take_dir)
    if not path.is_file():
        raise AlignmentError("take.json not found")
    try:
        take = from_json(Take, path.read_text(encoding="utf-8"))
    except ContractError as e:
        raise AlignmentError(f"take.json: {e}") from None
    if take.id != take_dir.name:
        raise AlignmentError(f"take.json is for take {take.id!r}, not {take_dir.name!r}")
    if not take.HasField("end"):
        raise AlignmentError("take.json has no END marker: the take is still recording")
    if not take.cameras:
        raise AlignmentError("take.json lists no cameras")
    return take


def _camera_timing(role: str, fps: float, frames: np.ndarray, ts: np.ndarray, t0: int, end: int) -> CameraTiming:
    inside = (ts >= t0) & (ts <= end)
    frames, ts = frames[inside], ts[inside]
    if len(ts) < 2:
        raise AlignmentError(f"{role}: {len(ts)} frame(s) between START and END, need at least 2")
    nominal_period = 1e9 / fps
    measured_period = _measured_period(ts)
    return CameraTiming(
        role=role,
        nominal_fps=fps,
        measured_period_ns=measured_period,
        drift_ppm=(measured_period / nominal_period - 1.0) * 1e6,
        offset_ns=int(ts[0] - t0),
        frames_in=len(ts),
        first_frame=int(frames[0]),
        last_frame=int(frames[-1]),
    )


def _measured_period(ts: np.ndarray) -> float:
    steps = np.diff(ts).astype(np.float64)
    step = float(np.median(steps))
    slots = np.concatenate(([0], np.cumsum(np.maximum(1, np.rint(steps / step)))))
    slope, _ = np.polyfit(slots, (ts - ts[0]).astype(np.float64), 1)
    return float(slope)
