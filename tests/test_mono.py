from pathlib import Path

import numpy as np
import pytest
from freemocap_fixture import unpack

from mocap_extract.cli import main
from mocap_extract.mono import MonoError, mono_take


@pytest.fixture(scope="module")
def video(tmp_path_factory) -> Path:
    [cam] = (unpack(tmp_path_factory.mktemp("freemocap")) / "synchronized_videos").glob("*_Cam2.mp4")
    return cam


def test_one_camera_body_in_mm(video, tmp_path):
    mono = mono_take(video, tmp_path / "t", start_s=1.0, end_s=3.0)

    body = np.load(mono.body)
    assert body.shape == (60, 33, 3) and mono.frames == 60
    assert not np.isnan(body).any()
    shoulders = np.linalg.norm(body[:, 11] - body[:, 12], axis=1)
    assert 250 < np.median(shoulders) < 500
    hands = np.load(mono.body.parent / "mediapipe_left_hand_3d_xyz.npy")
    assert hands.shape == (60, 21, 3) and np.isnan(hands).all()


def test_window_outside_the_video(video, tmp_path):
    with pytest.raises(MonoError, match="outside the video"):
        mono_take(video, tmp_path / "t", start_s=5.0, end_s=500.0)


def test_cli_mono(video, tmp_path, capsys):
    assert main(["mono", str(video), str(tmp_path / "t"), "--end", "1"]) == 0
    assert "30 frames at 30 fps" in capsys.readouterr().out
