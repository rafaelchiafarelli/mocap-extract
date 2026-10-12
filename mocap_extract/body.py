"""Body and hands (P3.2): FreeMoCap 2D per camera, then 3D, for one synced PERFORMANCE take.

`extract/freemocap/` is laid out as a FreeMoCap recording folder, so FreeMoCap
(and its Blender add-on) can open it like any of its own recordings:

    extract/freemocap/
        synchronized_videos/<role>.mp4      hard links to extract/synced/<role>.mp4
        <take>_camera_calibration.toml      copy of <session>/calibration/calibration.toml
        output_data/                        FreeMoCap's 3D (and everything else it writes)
        output_data/raw_data/...            its stacked 2D, the input to its 3D
        roles_2d/<role>/                    our per-camera 2D runs

2D runs one camera at a time (`track_role`), so a camera can be processed as
soon as its video is in; `reconstruct` stacks the per-camera 2D in the
calibration's camera order and runs FreeMoCap's pipeline with its own 2D
tracking switched off. Both paths use FreeMoCap's default tracker and
parameters, which give the same 2D and 3D as its stock all-cameras run.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mocap_contracts import ContractError, Take, TakeType, from_json, layout

from mocap_extract.freemocap_import import import_freemocap

PERFORMANCE = TakeType.Value("TAKE_TYPE_PERFORMANCE")


class BodyError(ValueError):
    """The take can't be processed (wrong type, no calibration, missing videos, ...)."""


@dataclass(frozen=True)
class Body:
    recording_dir: Path
    """extract/freemocap/, a FreeMoCap recording folder."""
    data_3d: Path
    """FreeMoCap's 3D (frames x markers x xyz, mm, calibration frame)."""
    frames: int
    roles: tuple[str, ...]
    """Camera order of the 2D and the calibration."""


def recording_dir(take_dir: Path) -> Path:
    return layout.extract_dir(take_dir) / "freemocap"


def prepare(take_dir: Path | str) -> tuple[Take, Path]:
    """Lay out extract/freemocap/ (videos and calibration); return the take and the calibration copy."""
    take_dir = Path(take_dir)
    take = _read_take(take_dir)
    calibration = layout.calibration_toml(take_dir.parents[2], take.session_id)
    if not calibration.is_file():
        raise BodyError(f"no calibration for session {take.session_id}: run mocap-extract calibrate first "
                        f"({calibration} not found)")
    rec = recording_dir(take_dir)
    videos = rec / "synchronized_videos"
    videos.mkdir(parents=True, exist_ok=True)
    for role in _roles(take):
        synced = layout.synced_video(take_dir, role)
        if not synced.is_file():
            raise BodyError(f"run mocap-extract align first: {synced.relative_to(take_dir)} not found")
        link = videos / synced.name
        if not link.exists():
            try:
                os.link(synced, link)
            except OSError:
                shutil.copyfile(synced, link)
    toml = rec / f"{take.id}_camera_calibration.toml"
    shutil.copyfile(calibration, toml)
    names = _calibration_names(toml)
    if sorted(names) != sorted(_roles(take)):
        raise BodyError(f"calibration cameras {names} != take roles {_roles(take)}")
    return take, toml


def track_role(take_dir: Path | str, role: str) -> Path:
    """FreeMoCap 2D of one camera; returns its .npy (1 x frames x points x 3)."""
    take_dir = Path(take_dir)
    take, _ = prepare(take_dir)
    if role not in _roles(take):
        raise BodyError(f"take {take.id} has no role {role!r}")
    import_freemocap()
    from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
    from skellytracker.process_folder_of_videos import process_list_of_videos

    params = ProcessingParameterModel()
    out = recording_dir(take_dir) / "roles_2d" / role
    out.mkdir(parents=True, exist_ok=True)
    data = process_list_of_videos(
        model_info=params.tracking_model_info,
        tracking_params=params.tracking_parameters_model,
        video_paths=[recording_dir(take_dir) / "synchronized_videos" / f"{role}.mp4"],
        output_folder_path=out,
        annotated_video_path=None,
        num_processes=1,
    )
    path = out / f"{role}_2d.npy"
    np.save(path, data)
    return path


def reconstruct(take_dir: Path | str) -> Body:
    """Stack every role's 2D in the calibration's camera order and run FreeMoCap's 3D on it."""
    take_dir = Path(take_dir)
    take, toml = prepare(take_dir)
    order = _calibration_names(toml)
    missing = [r for r in order if not (recording_dir(take_dir) / "roles_2d" / r / f"{r}_2d.npy").is_file()]
    if missing:
        raise BodyError(f"no 2D yet for {missing}: run track_role first")
    data_2d = np.concatenate([np.load(recording_dir(take_dir) / "roles_2d" / r / f"{r}_2d.npy") for r in order])

    import_freemocap()
    from freemocap.core_processes.process_motion_capture_videos.process_recording_folder import (
        process_recording_folder,
    )
    from freemocap.data_layer.recording_models.post_processing_parameter_models import ProcessingParameterModel
    from freemocap.data_layer.recording_models.recording_info_model import RecordingInfoModel

    params = ProcessingParameterModel()
    params.recording_info_model = RecordingInfoModel(recording_folder_path=recording_dir(take_dir))
    params.recording_info_model.calibration_toml_path = toml
    params.tracking_parameters_model.run_image_tracking = False
    data_2d_path = Path(params.recording_info_model.data_2d_npy_file_path)
    data_2d_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(data_2d_path, data_2d)
    process_recording_folder(recording_processing_parameter_model=params, use_tqdm=False)

    data_3d = Path(params.recording_info_model.data_3d_npy_file_path)
    if not data_3d.is_file():
        raise BodyError(f"FreeMoCap wrote no 3D ({data_3d} not found)")
    return Body(recording_dir=recording_dir(take_dir), data_3d=data_3d, frames=int(np.load(data_3d).shape[0]),
                roles=tuple(order))


def extract_body(take_dir: Path | str) -> Body:
    """2D for every role, then 3D."""
    take, _ = prepare(take_dir)
    for role in _roles(take):
        track_role(take_dir, role)
    return reconstruct(take_dir)


def _roles(take: Take) -> list[str]:
    return [c.config.role for c in take.cameras]


def _calibration_names(toml: Path) -> list[str]:
    """Camera names in the order FreeMoCap triangulates them (its CameraGroup.load sorts the sections)."""
    import toml as toml_lib

    data = toml_lib.load(toml)
    return [data[k]["name"] for k in sorted(data) if k != "metadata"]


def _read_take(take_dir: Path) -> Take:
    path = layout.take_json(take_dir)
    if not path.is_file():
        raise BodyError("take.json not found")
    try:
        take = from_json(Take, path.read_text(encoding="utf-8"))
    except ContractError as e:
        raise BodyError(f"take.json: {e}") from None
    if take.type != PERFORMANCE:
        raise BodyError(f"take {take.id} is not a PERFORMANCE take")
    if layout.take_dir(take_dir.parents[2], take.session_id, take.id) != take_dir:
        raise BodyError(f"{take_dir} isn't <root>/{take.session_id}/takes/{take.id}")
    return take
