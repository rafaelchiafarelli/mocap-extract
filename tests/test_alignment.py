from pathlib import Path

import numpy as np
import pytest
from mocap_contracts import layout
from takes import SESSION, TAKE, put_file, put_take_json, put_timestamps

from mocap_extract.alignment import AlignmentError, compute_alignment

T0 = 1_759_700_000_000_000_000
DURATION = 60_000_000_000  # 60 s between START and END


@pytest.fixture
def take_dir(tmp_path: Path) -> Path:
    take = layout.take_dir(tmp_path, SESSION, TAKE)
    take.mkdir(parents=True)
    return take


def camera_rows(fps, offset_ns, drift_ppm, jitter_ns=0, drop=(), seed=0, lead_s=2.0, tail_s=2.0):
    """Frames from lead_s before START to tail_s after END; frame k (k = 0 first inside) at
    t0 + offset + k * period * (1 + drift). Dropped slots are skipped, the frame counter isn't."""
    rng = np.random.default_rng(seed)
    period = 1e9 / fps * (1 + drift_ppm * 1e-6)
    lead = int(lead_s * 1e9 / period)
    n = int((DURATION + tail_s * 1e9) / period)
    rows, frame = [], 100  # a camera's counter doesn't start at 0
    for k in range(-lead, n):
        if k in drop:
            continue
        t = T0 + offset_ns + k * period + (rng.normal(0, jitter_ns) if jitter_ns else 0)
        rows.append((frame, int(round(t))))
        frame += 1
    return rows


def make_take(take_dir, cams):
    put_take_json(take_dir, {role: c["fps"] for role, c in cams.items()}, T0, T0 + DURATION)
    for role, c in cams.items():
        put_timestamps(take_dir, role, camera_rows(**c))


def test_known_offset_and_drift_exact(take_dir):
    make_take(take_dir, {"front": dict(fps=30.0, offset_ns=12_000_000, drift_ppm=150.0)})

    cam = compute_alignment(take_dir).camera("front")

    assert cam.offset_ns == pytest.approx(12_000_000, abs=1)
    assert cam.drift_ppm == pytest.approx(150.0, abs=0.1)


def test_known_offset_and_drift_with_jitter_and_dropped_frames(take_dir):
    make_take(take_dir, {
        "front": dict(fps=30.0, offset_ns=5_000_000, drift_ppm=-80.0, jitter_ns=1_000_000,
                      drop={10, 11, 500, 1200}, seed=1),
        "side": dict(fps=60.0, offset_ns=9_000_000, drift_ppm=400.0, jitter_ns=500_000,
                     drop={3, 900}, seed=2),
    })

    alignment = compute_alignment(take_dir)

    assert alignment.t0_ns == T0 and alignment.end_ns == T0 + DURATION
    front, side = alignment.camera("front"), alignment.camera("side")
    assert front.drift_ppm == pytest.approx(-80.0, abs=10)
    assert side.drift_ppm == pytest.approx(400.0, abs=10)
    assert front.offset_ns == pytest.approx(5_000_000, abs=5 * 1_000_000)  # first frame carries its jitter
    assert side.offset_ns == pytest.approx(9_000_000, abs=5 * 500_000)


def test_window_counts_only_frames_between_start_and_end(take_dir):
    make_take(take_dir, {"front": dict(fps=30.0, offset_ns=0, drift_ppm=0.0, drop={7})})

    cam = compute_alignment(take_dir).camera("front")

    # slots 0..1800 inclusive (t0 .. t0 + 60 s at 30 fps), minus the dropped one
    assert cam.frames_in == 1800
    assert cam.last_frame - cam.first_frame + 1 == cam.frames_in
    assert cam.offset_ns == 0


def test_camera_slower_than_declared_shows_large_positive_drift(take_dir):
    # declared 30 fps, delivers 29.97
    put_take_json(take_dir, {"tablet": 30.0}, T0, T0 + DURATION)
    put_timestamps(take_dir, "tablet", camera_rows(fps=29.97, offset_ns=0, drift_ppm=0.0))

    cam = compute_alignment(take_dir).camera("tablet")

    assert cam.drift_ppm == pytest.approx((30.0 / 29.97 - 1) * 1e6, abs=1)


def test_take_still_recording_is_refused(take_dir):
    put_take_json(take_dir, {"front": 30.0}, T0, None)
    with pytest.raises(AlignmentError, match="END"):
        compute_alignment(take_dir)


def test_unverified_timestamps_are_refused(take_dir):
    make_take(take_dir, {"front": dict(fps=30.0, offset_ns=0, drift_ppm=0.0)})
    layout.ready_sidecar(layout.raw_timestamps(take_dir, "front")).unlink()
    with pytest.raises(AlignmentError, match="no sidecar"):
        compute_alignment(take_dir)


def test_bad_header_is_refused(take_dir):
    put_take_json(take_dir, {"front": 30.0}, T0, T0 + DURATION)
    rel = layout.raw_timestamps(take_dir, "front").relative_to(take_dir).as_posix()
    put_file(take_dir, rel, b"idx,ts\n0,1\n", "front", "FILE_KIND_TIMESTAMPS")
    with pytest.raises(AlignmentError, match="header"):
        compute_alignment(take_dir)


def test_camera_with_no_frames_in_window_is_refused(take_dir):
    put_take_json(take_dir, {"front": 30.0}, T0, T0 + DURATION)
    put_timestamps(take_dir, "front", [(0, T0 - 2_000), (1, T0 - 1_000)])
    with pytest.raises(AlignmentError, match="0 frame"):
        compute_alignment(take_dir)
