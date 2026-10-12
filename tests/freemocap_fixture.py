"""FreeMoCap's own test recording (3 cameras), trimmed and laid out as one of our PERFORMANCE takes.

Source: skellysamples `test_data_v06_09_25` (AGPL-3.0), fetched by `make fixtures` into
$MOCAP_FIXTURES (default /mnt/g/mocap-studio-downloads/fixtures), never committed.
"""

import os
import subprocess
import zipfile
from pathlib import Path

import pytest
import toml
from mocap_contracts import (
    CameraConfig, CameraSource, SyncEvent, SyncKind, SyncSource, Take, TakeCamera, TakeType, layout, to_json,
)

FIXTURES = Path(os.environ.get("MOCAP_FIXTURES", "/mnt/g/mocap-studio-downloads/fixtures"))
ZIP = FIXTURES / "freemocap-test-data-v06_09_25" / "freemocap_test_data.zip"
ROLES = {"body_1": "Cam1", "body_2": "Cam2", "body_3": "Cam3"}
PREFIX = "freemocap_test_data/"


def unpack(cache: Path) -> Path:
    if not ZIP.is_file():
        pytest.fail(f"{ZIP} not found: run `make fixtures`")
    out = cache / "freemocap_test_data"
    if not out.is_dir():
        zipfile.ZipFile(ZIP).extractall(cache)
    return out


def make_performance_take(take_dir: Path, source: Path, frames: int) -> None:
    for role, cam in ROLES.items():
        [video] = (source / "synchronized_videos").glob(f"*_{cam}.mp4")
        out = layout.synced_video(take_dir, role)
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                        "-frames:v", str(frames), "-an", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
                        str(out)], check=True)
    calibration = toml.load(source / "freemocap_test_data_camera_calibration.toml")
    by_cam = {v: k for k, v in ROLES.items()}
    for key, cam in calibration.items():
        if key != "metadata":
            cam["name"] = by_cam[cam["name"].rsplit("_", 1)[1]]
    session = take_dir.parents[1]
    path = layout.calibration_toml(session.parent, session.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(toml.dumps(calibration), encoding="utf-8")

    def sync(kind: str, ts: int) -> SyncEvent:
        return SyncEvent(kind=SyncKind.Value(kind), host_ts_ns=ts, source=SyncSource.Value("SYNC_SOURCE_MANUAL"))

    take = Take(id=take_dir.name, session_id=session.name, type=TakeType.Value("TAKE_TYPE_PERFORMANCE"),
                start=sync("SYNC_KIND_START", 1_000), end=sync("SYNC_KIND_END", 2_000_000_000))
    take.cameras.extend(TakeCamera(config=CameraConfig(
        role=role, source=CameraSource.Value("CAMERA_SOURCE_STREAM"), width=720, height=1280, fps=30,
        notes="FreeMoCap test data", stream_host="192.168.1.20", video_port=8080, sync_port=8081,
        control_port=8082, stats_port=8083)) for role in ROLES)
    layout.take_json(take_dir).write_text(to_json(take), encoding="utf-8")
