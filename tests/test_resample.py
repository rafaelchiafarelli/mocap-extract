import logging
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from mocap_contracts import layout, to_json
from takes import SESSION, TAKE, put_file, put_take_json, put_timestamps

from mocap_extract.alignment import AlignmentError, compute_alignment
from mocap_extract.resample import (
    MAX_MISALIGNMENT_NS, Misalignment, camera_alignment, find_misalignments, nearest_frames, output_frame_count,
    resample_role,
)

T0 = 1_759_700_000_000_000_000
DURATION = 2_000_000_000  # 2 s: 61 output frames at 30 fps
BITS, BAR, H = 10, 8, 16  # frame index drawn as 10 black/white bars


def index_frame(i: int) -> np.ndarray:
    img = np.zeros((H, BITS * BAR, 3), np.uint8)
    for b in range(BITS):
        if i >> b & 1:
            img[:, b * BAR:(b + 1) * BAR] = 255
    return img


def read_indices(path: Path) -> list[int]:
    cap = cv2.VideoCapture(str(path))
    out = []
    while True:
        ok, img = cap.read()
        if not ok:
            return out
        row = img[H // 2, BAR // 2::BAR, 0][:BITS]
        out.append(sum(1 << b for b, v in enumerate(row) if v > 127))


def put_prep_video(take: Path, role: str, n: int) -> None:
    path = layout.prep_video(take, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{BITS * BAR}x{H}", "-r", "30", "-i", "-", "-c:v", "ffv1", str(path)]
    subprocess.run(cmd, input=b"".join(index_frame(i).tobytes() for i in range(n)), check=True)
    put_file(take, path.relative_to(take).as_posix(), path.read_bytes(), role, "FILE_KIND_VIDEO", frames=n)


@pytest.fixture
def take_dir(tmp_path: Path) -> Path:
    take = layout.take_dir(tmp_path, SESSION, TAKE)
    take.mkdir(parents=True)
    return take


def make_take(take: Path, ts: list[int], role="tablet"):
    put_take_json(take, {role: 30.0}, T0, T0 + DURATION)
    put_timestamps(take, role, list(enumerate(ts)))
    put_prep_video(take, role, len(ts))
    return compute_alignment(take)


def vfr_timestamps(seed=0) -> list[int]:
    """A tablet wandering between ~24 and ~36 fps, from 0.2 s before START to 0.2 s after END."""
    rng = np.random.default_rng(seed)
    t, out = T0 - 200_000_000, []
    while t <= T0 + DURATION + 200_000_000:
        out.append(int(t))
        t += int(rng.uniform(1e9 / 36, 1e9 / 24))
    return out


def test_vfr_to_cfr_has_the_right_count_and_nearest_frames(take_dir):
    ts = vfr_timestamps()
    alignment = make_take(take_dir, ts)

    video = resample_role(take_dir, alignment, "tablet")

    n = output_frame_count(alignment)
    assert n == 61
    assert video.frames_out == n
    targets = T0 + np.rint(np.arange(n) * (1e9 / 30)).astype(np.int64)
    expected = [int(np.argmin(np.abs(np.array(ts) - t))) for t in targets]
    assert video.source_frames.tolist() == expected
    out = take_dir / video.path
    assert video.path == "extract/synced/tablet.mp4"
    assert read_indices(out) == expected
    assert cv2.VideoCapture(str(out)).get(cv2.CAP_PROP_FPS) == pytest.approx(30.0)
    assert video.misaligned == ()


def test_every_camera_gets_the_same_frame_count(take_dir):
    put_take_json(take_dir, {"a": 30.0, "b": 60.0}, T0, T0 + DURATION)
    for role, fps, seed in (("a", 30.0, 1), ("b", 60.0, 2)):
        ts = [T0 - 50_000_000 + int(k * 1e9 / fps) for k in range(int(2.2 * fps))]
        put_timestamps(take_dir, role, list(enumerate(ts)))
        put_prep_video(take_dir, role, len(ts))
    alignment = compute_alignment(take_dir)

    counts = {r: resample_role(take_dir, alignment, r).frames_out for r in ("a", "b")}
    assert counts == {"a": 61, "b": 61}
    assert {len(read_indices(take_dir / f"extract/synced/{r}.mp4")) for r in ("a", "b")} == {61}


def test_gap_longer_than_one_frame_time_warns(take_dir, caplog):
    ts = [T0 + int(k * 1e9 / 30) for k in range(-3, 64)]
    ts = [t for t in ts if not (T0 + 500_000_000 < t < T0 + 700_000_000)]  # 200 ms dropped
    alignment = make_take(take_dir, ts)

    with caplog.at_level(logging.WARNING, logger="mocap_extract.resample"):
        video = resample_role(take_dir, alignment, "tablet")

    assert len(video.misaligned) == 1
    m = video.misaligned[0]
    assert 15 <= m.first_out <= m.last_out <= 21  # output frames inside the hole
    assert abs(m.worst_ns) > MAX_MISALIGNMENT_NS
    assert "tablet: output frames" in caplog.text


def test_camera_starting_late_warns_at_the_start(take_dir):
    ts = [T0 + 100_000_000 + int(k * 1e9 / 30) for k in range(70)]  # first frame 100 ms after START
    alignment = make_take(take_dir, ts)

    video = resample_role(take_dir, alignment, "tablet")

    assert video.misaligned[0].first_out == 0
    assert video.misaligned[0].worst_ns == 100_000_000


def test_camera_alignment_record(take_dir):
    alignment = make_take(take_dir, vfr_timestamps())
    video = resample_role(take_dir, alignment, "tablet")

    rec = camera_alignment(alignment, video)

    assert rec.role == "tablet" and rec.frames_out == 61
    assert rec.frames_in == alignment.camera("tablet").frames_in
    to_json(rec)  # valid contract message


def test_frame_count_mismatch_is_refused(take_dir):
    ts = vfr_timestamps()
    alignment = make_take(take_dir, ts)
    put_timestamps(take_dir, "tablet", list(enumerate(ts[:-1])))
    with pytest.raises(AlignmentError, match="frames"):
        resample_role(take_dir, alignment, "tablet")


def test_unverified_video_is_refused(take_dir):
    alignment = make_take(take_dir, vfr_timestamps())
    layout.ready_sidecar(layout.prep_video(take_dir, "tablet")).unlink()
    with pytest.raises(AlignmentError, match="no sidecar"):
        resample_role(take_dir, alignment, "tablet")


def test_nearest_frames_and_runs():
    ts = np.array([0, 10, 20, 50])
    assert nearest_frames(ts, np.array([-5, 4, 5, 6, 34, 36, 99])).tolist() == [0, 0, 0, 1, 2, 3, 3]
    errors = np.array([0, 40, -50, 0, 0, 35, 0])
    assert find_misalignments(errors, limit_ns=33) == (Misalignment(1, 2, -50), Misalignment(5, 5, 35))
