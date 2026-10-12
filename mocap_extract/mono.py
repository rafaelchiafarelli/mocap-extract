"""Single-camera 3D (test and preview path): MediaPipe Pose world landmarks from one video.

Output has the names and shapes of FreeMoCap's (`extract/freemocap/output_data/`), so `mocap-blender`
reads it the same way: body frames x 33 x 3 in mm, hands NaN (MediaPipe Pose has no fingers). Depth is
MediaPipe's estimate, not triangulated. Frames are resampled to 30 fps (nearest source frame) and
smoothed with FreeMoCap's own filter settings (Butterworth, order 4, 7 Hz, zero phase).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FPS = 30.0
BODY_POINTS, HAND_POINTS = 33, 21
FILTER_ORDER, FILTER_CUTOFF_HZ = 4, 7.0  # FreeMoCap 1.8.2 ButterworthFilterParametersModel defaults


class MonoError(ValueError):
    """The video can't be used."""


@dataclass(frozen=True)
class Mono:
    body: Path
    frames: int
    missing_frames: int
    """Frames where MediaPipe found no person (filled by interpolation)."""


def mono_take(video: Path | str, take_dir: Path | str, start_s: float | None = None,
              end_s: float | None = None) -> Mono:
    import cv2
    from mediapipe.python.solutions import pose as mp_pose

    video, take_dir = Path(video), Path(take_dir)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise MonoError(f"can't open {video}")
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not src_fps or count <= 0:
        raise MonoError(f"{video}: no frame rate or frame count")
    duration = count / src_fps
    start, end = start_s or 0.0, duration if end_s is None else end_s
    if not 0 <= start < end <= duration + 1e-6:
        raise MonoError(f"window {start}-{end} s is outside the video (0-{duration:.2f} s)")
    wanted = np.minimum(np.rint((start + np.arange(int((end - start) * FPS)) / FPS) * src_fps).astype(int), count - 1)

    body = np.full((len(wanted), BODY_POINTS, 3), np.nan)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(wanted[0]))
    index, frame = int(wanted[0]) - 1, None
    with mp_pose.Pose(model_complexity=1, smooth_landmarks=True) as pose:
        for n, target in enumerate(wanted):
            while index < target:
                ok, frame = cap.read()
                if not ok:
                    raise MonoError(f"{video} ended at frame {index + 1}, needed {target}")
                index += 1
            result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if result.pose_world_landmarks is not None:
                body[n] = [(p.x * 1000, p.y * 1000, p.z * 1000) for p in result.pose_world_landmarks.landmark]
    cap.release()

    missing = int(np.isnan(body[:, 0, 0]).sum())
    if missing == len(body):
        raise MonoError(f"no person found in {video} between {start} and {end} s")
    body = _smooth(_fill(body))
    out = take_dir / "extract" / "freemocap" / "output_data"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "mediapipe_body_3d_xyz.npy"
    np.save(path, body)
    for side in ("left", "right"):
        np.save(out / f"mediapipe_{side}_hand_3d_xyz.npy", np.full((len(body), HAND_POINTS, 3), np.nan))
    (take_dir / "extract" / "freemocap" / "mono.json").write_text(json.dumps({
        "source": str(video), "start_s": start, "end_s": end, "fps": FPS, "frames": len(body),
        "missing_frames": missing, "model": "mediapipe Pose (legacy), model_complexity=1, world landmarks",
    }, indent=2), encoding="utf-8")
    return Mono(body=path, frames=len(body), missing_frames=missing)


def _fill(points: np.ndarray) -> np.ndarray:
    t = np.arange(len(points))
    bad = np.isnan(points[:, 0, 0])
    if bad.any():
        for p in range(points.shape[1]):
            for axis in range(3):
                points[bad, p, axis] = np.interp(t[bad], t[~bad], points[~bad, p, axis])
    return points


def _smooth(points: np.ndarray) -> np.ndarray:
    from scipy.signal import butter, filtfilt

    b, a = butter(FILTER_ORDER, FILTER_CUTOFF_HZ, btype="low", fs=FPS)
    if len(points) <= 3 * max(len(a), len(b)):
        return points
    return filtfilt(b, a, points, axis=0)
