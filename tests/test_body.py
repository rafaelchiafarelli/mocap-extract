from pathlib import Path

import numpy as np
import pytest
from freemocap_fixture import ROLES, make_performance_take, unpack
from mocap_contracts import layout
from takes import SESSION, TAKE

from mocap_extract.body import BodyError, extract_body, recording_dir, track_role
from mocap_extract.cli import main
from mocap_extract.freemocap_import import import_freemocap

FRAMES = 60
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12  # MediaPipe pose landmarks, first in FreeMoCap's marker list


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    return unpack(tmp_path_factory.mktemp("freemocap"))


@pytest.fixture
def take_dir(tmp_path: Path, source: Path) -> Path:
    take = layout.take_dir(tmp_path, SESSION, TAKE)
    take.mkdir(parents=True)
    make_performance_take(take, source, FRAMES)
    return take


def test_one_role_2d_matches_the_all_cameras_run(take_dir):
    one = np.load(track_role(take_dir, "body_2"))

    import_freemocap()
    from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
    from skellytracker.process_folder_of_videos import process_folder_of_videos
    params = ProcessingParameterModel()
    stock = process_folder_of_videos(
        model_info=params.tracking_model_info, tracking_params=params.tracking_parameters_model,
        synchronized_video_path=recording_dir(take_dir) / "synchronized_videos",
        output_folder_path=take_dir.parent / "stock", annotated_video_path=None, num_processes=1)

    assert one.shape == (1, *stock.shape[1:])
    np.testing.assert_array_equal(one[0], stock[sorted(ROLES).index("body_2")])


def test_extract_body_gives_3d_in_mm(take_dir):
    body = extract_body(take_dir)

    assert body.roles == tuple(sorted(ROLES))
    data = np.load(body.data_3d)
    assert data.shape[0] == FRAMES and data.shape[2] == 3
    shoulders = np.linalg.norm(data[:, LEFT_SHOULDER] - data[:, RIGHT_SHOULDER], axis=1)
    assert np.mean(~np.isnan(shoulders)) > 0.9
    assert 250 < np.nanmedian(shoulders) < 500  # an adult's shoulder width, in mm


def test_cli_body(take_dir, capsys):
    assert main(["body", str(take_dir)]) == 0
    assert "3D:" in capsys.readouterr().out


def test_needs_the_session_calibration(take_dir):
    layout.calibration_toml(take_dir.parents[2], SESSION).unlink()
    with pytest.raises(BodyError, match="run mocap-extract calibrate first"):
        extract_body(take_dir)
