import cv2
from mocap_contracts import layout
from takes import put_take_json, put_timestamps
from test_resample import DURATION, T0, put_prep_video, take_dir, vfr_timestamps  # noqa: F401

from mocap_extract.cli import main
from mocap_extract.resample import TARGET_FPS


def frame_count(path) -> int:
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def test_align_writes_every_role_with_the_same_frame_count(take_dir, capsys):
    roles = {"body_1": vfr_timestamps(seed=1), "body_2": vfr_timestamps(seed=2)}
    put_take_json(take_dir, {role: 30.0 for role in roles}, T0, T0 + DURATION)
    for role, ts in roles.items():
        put_timestamps(take_dir, role, list(enumerate(ts)))
        put_prep_video(take_dir, role, len(ts))

    assert main(["align", str(take_dir)]) == 0

    expected = int(DURATION * TARGET_FPS // 1e9) + 1
    for role in roles:
        assert frame_count(layout.synced_video(take_dir, role)) == expected
    out = capsys.readouterr().out
    assert "body_1:" in out and "body_2:" in out


def test_align_fails_on_a_take_without_end(take_dir, capsys):
    put_take_json(take_dir, {"body_1": 30.0}, T0, None)

    assert main(["align", str(take_dir)]) == 1
    assert "no END marker" in capsys.readouterr().err
