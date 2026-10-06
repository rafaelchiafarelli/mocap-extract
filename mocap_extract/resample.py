"""Alignment (P3.1), step 2: resample every camera onto one constant-fps clock.

Output frame n sits at t0 + n / TARGET_FPS, for every n up to the END marker,
so every camera gets the same frame count. Each output frame is the camera's
real frame nearest in host time (`raw/<role>.timestamps.csv`; preprocessing
keeps one frame per input frame, so row i is video frame i). A gap repeats a
frame, extra frames are dropped, and nothing is blended.

Whenever the frame used is more than MAX_MISALIGNMENT_NS away from the output
frame's time (a drop, a late start, an early stop), a warning is logged and
the run of affected output frames is returned in `ResampledVideo.misaligned`.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from mocap_contracts import CameraAlignment, layout

from mocap_extract.alignment import Alignment, AlignmentError, read_timestamps
from mocap_extract.intake import FileRejected, check_file

log = logging.getLogger(__name__)

# Rafael, 2026-10-06: one target fps for the baseline.
TARGET_FPS = 30.0
# Rafael, 2026-10-06: warn past one frame time at 30 fps, whatever the target.
MAX_MISALIGNMENT_NS = 1e9 / 30.0
# Claude, for Rafael's review: near-transparent H.264 that OpenCV and FreeMoCap read without trouble.
FFMPEG_ENCODE = ("-c:v", "libx264", "-preset", "medium", "-crf", "10", "-pix_fmt", "yuv420p")


@dataclass(frozen=True)
class Misalignment:
    """A run of consecutive output frames whose source frame is too far off in time."""

    first_out: int
    last_out: int
    worst_ns: int
    """Signed host-time error with the largest magnitude in the run (source - output)."""


@dataclass(frozen=True)
class ResampledVideo:
    role: str
    path: str
    """Take-relative path of extract/synced/<role>.mp4."""
    fps: float
    frames_out: int
    source_frames: np.ndarray
    """Input frame index (timestamps row) used for each output frame."""
    misaligned: tuple[Misalignment, ...]


def output_frame_count(alignment: Alignment, fps: float = TARGET_FPS) -> int:
    """Frames n = 0, 1, ... with t0 + n / fps <= END."""
    return int((alignment.end_ns - alignment.t0_ns) * fps // 1e9) + 1


def nearest_frames(ts: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Index into ts of the timestamp nearest each target (ties go to the earlier frame)."""
    right = np.clip(np.searchsorted(ts, targets), 1, len(ts) - 1)
    left = right - 1
    return np.where(targets - ts[left] <= ts[right] - targets, left, right)


def find_misalignments(errors_ns: np.ndarray, limit_ns: float = MAX_MISALIGNMENT_NS) -> tuple[Misalignment, ...]:
    bad = np.flatnonzero(np.abs(errors_ns) > limit_ns)
    runs = []
    for run in np.split(bad, np.flatnonzero(np.diff(bad) != 1) + 1) if len(bad) else []:
        worst = run[np.argmax(np.abs(errors_ns[run]))]
        runs.append(Misalignment(int(run[0]), int(run[-1]), int(errors_ns[worst])))
    return tuple(runs)


def resample_role(take_dir: Path | str, alignment: Alignment, role: str, fps: float = TARGET_FPS) -> ResampledVideo:
    """Write extract/synced/<role>.mp4 from the verified prep/<role>.mkv."""
    take_dir = Path(take_dir)
    alignment.camera(role)  # KeyError for a role take.json doesn't declare
    ts_rel = layout.raw_timestamps(take_dir, role).relative_to(take_dir).as_posix()
    video_rel = layout.prep_video(take_dir, role).relative_to(take_dir).as_posix()
    try:
        check_file(take_dir, ts_rel)
        ready = check_file(take_dir, video_rel)
    except FileRejected as e:
        raise AlignmentError(f"{role}: {e}") from None
    _, ts = read_timestamps(take_dir / ts_rel)
    if len(ts) < 2:
        raise AlignmentError(f"{role}: {len(ts)} timestamp row(s), need at least 2")
    if ready.frames != len(ts):
        raise AlignmentError(f"{role}: video has {ready.frames} frames, timestamps have {len(ts)} rows")

    n_out = output_frame_count(alignment, fps)
    targets = alignment.t0_ns + np.rint(np.arange(n_out) * (1e9 / fps)).astype(np.int64)
    source = nearest_frames(ts, targets)
    misaligned = find_misalignments(ts[source] - targets)
    for m in misaligned:
        log.warning(
            "%s: output frames %d-%d are up to %.1f ms off their source frame (limit %.1f ms)",
            role, m.first_out, m.last_out, m.worst_ns / 1e6, MAX_MISALIGNMENT_NS / 1e6,
        )

    out = layout.synced_video(take_dir, role)
    _write_resampled(take_dir / video_rel, source, out, fps)
    return ResampledVideo(
        role=role,
        path=out.relative_to(take_dir).as_posix(),
        fps=fps,
        frames_out=n_out,
        source_frames=source,
        misaligned=misaligned,
    )


def camera_alignment(alignment: Alignment, video: ResampledVideo) -> CameraAlignment:
    """The `CameraAlignment` contract record for one resampled camera."""
    cam = alignment.camera(video.role)
    return CameraAlignment(
        role=cam.role,
        offset_ns=cam.offset_ns,
        drift_ppm=cam.drift_ppm,
        frames_in=cam.frames_in,
        frames_out=video.frames_out,
    )


def _write_resampled(src: Path, source: np.ndarray, out: Path, fps: float) -> None:
    """Decode src once, in order, and pipe frame source[n] as output frame n into FFmpeg."""
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise AlignmentError(f"can't open {src}")
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", f"{fps:g}", "-i", "-",
        *FFMPEG_ENCODE, "-r", f"{fps:g}", "-f", "mp4", str(tmp),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        index, frame = -1, None
        for wanted in source:
            while index < wanted:
                ok, frame = cap.read()
                if not ok:
                    raise AlignmentError(f"{src.name} ended at frame {index + 1}, needed frame {wanted}")
                index += 1
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise AlignmentError(f"ffmpeg failed: {proc.stderr.read().decode(errors='replace')}")
    except BaseException:
        proc.kill()
        proc.wait()
        tmp.unlink(missing_ok=True)
        raise
    finally:
        cap.release()
    os.replace(tmp, out)
