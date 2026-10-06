import hashlib
from pathlib import Path

import pytest
from mocap_contracts import CameraFileReady, FileKind, SyncEvent, SyncKind, SyncSource, TakeClosed, layout, to_json

from mocap_extract.intake import FileRejected, check_file, take_state

TAKE = "take-001"


@pytest.fixture
def take_dir(tmp_path: Path) -> Path:
    take = layout.take_dir(tmp_path, "session-1", TAKE)
    take.mkdir(parents=True)
    return take


def put_file(take: Path, rel_path: str, data: bytes, role: str, kind: str, **override) -> Path:
    path = take / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    fields = dict(
        take_id=TAKE,
        role=role,
        kind=FileKind.Value(kind),
        path=rel_path,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        frames=3,
        first_ts_ns=1_000,
        last_ts_ns=3_000,
    )
    fields.update(override)
    layout.ready_sidecar(path).write_text(to_json(CameraFileReady(**fields)), encoding="utf-8")
    return path


def put_timestamps(take: Path, role: str, **override) -> Path:
    return put_file(take, f"raw/{role}.timestamps.csv", b"frame,host_ts_ns\n0,1000\n", role,
                    "FILE_KIND_TIMESTAMPS", **override)


def put_video(take: Path, role: str, **override) -> Path:
    return put_file(take, f"prep/{role}.mkv", b"\x1a\x45\xdf\xa3video-" + role.encode(), role,
                    "FILE_KIND_VIDEO", **override)


def put_closed(take: Path, roles: list[str], take_id: str = TAKE) -> None:
    closed = TakeClosed(
        take_id=take_id,
        roles=roles,
        start=SyncEvent(kind=SyncKind.Value("SYNC_KIND_START"), host_ts_ns=1_000,
                        source=SyncSource.Value("SYNC_SOURCE_MANUAL")),
        end=SyncEvent(kind=SyncKind.Value("SYNC_KIND_END"), host_ts_ns=3_000,
                      source=SyncSource.Value("SYNC_SOURCE_MANUAL")),
    )
    layout.closed_json(take).write_text(to_json(closed), encoding="utf-8")


# ---------------------------------------------------------------- check_file

def test_good_file_passes(take_dir):
    put_video(take_dir, "front")
    ready = check_file(take_dir, "prep/front.mkv")
    assert ready.role == "front"
    assert FileKind.Name(ready.kind) == "FILE_KIND_VIDEO"


def test_missing_sidecar_refused(take_dir):
    path = put_video(take_dir, "front")
    layout.ready_sidecar(path).unlink()
    with pytest.raises(FileRejected, match="no sidecar"):
        check_file(take_dir, "prep/front.mkv")


def test_wrong_size_refused(take_dir):
    path = put_video(take_dir, "front")
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(FileRejected, match="size"):
        check_file(take_dir, "prep/front.mkv")


def test_wrong_sha256_refused(take_dir):
    path = put_video(take_dir, "front")
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(FileRejected, match="sha256"):
        check_file(take_dir, "prep/front.mkv")


def test_file_not_arrived_refused(take_dir):
    put_video(take_dir, "front").unlink()
    with pytest.raises(FileRejected, match="file not found"):
        check_file(take_dir, "prep/front.mkv")


def test_sidecar_for_another_take_refused(take_dir):
    put_video(take_dir, "front", take_id="take-999")
    with pytest.raises(FileRejected, match="take-999"):
        check_file(take_dir, "prep/front.mkv")


def test_sidecar_announcing_another_path_refused(take_dir):
    put_video(take_dir, "front", path="prep/side.mkv")
    with pytest.raises(FileRejected, match="announces"):
        check_file(take_dir, "prep/front.mkv")


def test_invalid_sidecar_refused(take_dir):
    path = put_video(take_dir, "front")
    layout.ready_sidecar(path).write_text("{}", encoding="utf-8")
    with pytest.raises(FileRejected, match="invalid sidecar"):
        check_file(take_dir, "prep/front.mkv")


@pytest.mark.parametrize("rel_path", ["/etc/passwd", "../other/prep/front.mkv", ""])
def test_path_outside_take_refused(take_dir, rel_path):
    with pytest.raises(FileRejected, match="relative"):
        check_file(take_dir, rel_path)


# ---------------------------------------------------------------- take_state

def test_half_arrived_take_lists_exactly_whats_missing(take_dir):
    put_timestamps(take_dir, "front")
    put_timestamps(take_dir, "side")
    put_closed(take_dir, ["front", "side"])
    put_video(take_dir, "front")

    state = take_state(take_dir)

    assert state.expected_roles == ("front", "side")
    assert set(state.verified) == {"raw/front.timestamps.csv", "raw/side.timestamps.csv", "prep/front.mkv"}
    assert state.missing == (("side", "FILE_KIND_VIDEO"),)
    assert state.rejected == {}
    assert not state.complete


def test_complete_take(take_dir):
    for role in ("front", "side"):
        put_timestamps(take_dir, role)
        put_video(take_dir, role)
    put_closed(take_dir, ["front", "side"])

    state = take_state(take_dir)

    assert state.missing == ()
    assert state.complete
    assert state.files("side", "FILE_KIND_VIDEO") == ["prep/side.mkv"]


def test_before_closed_roles_are_unknown(take_dir):
    put_timestamps(take_dir, "front")

    state = take_state(take_dir)

    assert state.closed is None
    assert state.expected_roles == ()
    assert state.missing == ()
    assert list(state.verified) == ["raw/front.timestamps.csv"]
    assert not state.complete


def test_mismatching_file_is_rejected_and_still_missing(take_dir):
    put_timestamps(take_dir, "front")
    put_closed(take_dir, ["front"])
    put_video(take_dir, "front").write_bytes(b"truncated")

    state = take_state(take_dir)

    assert "prep/front.mkv" not in state.verified
    assert "size" in state.rejected["prep/front.mkv"]
    assert state.missing == (("front", "FILE_KIND_VIDEO"),)


def test_file_without_sidecar_has_not_arrived(take_dir):
    put_timestamps(take_dir, "front")
    put_closed(take_dir, ["front"])
    (take_dir / "prep").mkdir()
    (take_dir / "prep/front.mkv").write_bytes(b"still copying")

    state = take_state(take_dir)

    assert "prep/front.mkv" not in state.verified
    assert state.missing == (("front", "FILE_KIND_VIDEO"),)


def test_closed_json_for_another_take_is_rejected(take_dir):
    put_closed(take_dir, ["front"], take_id="take-999")

    state = take_state(take_dir)

    assert state.closed is None
    assert "closed.json" in state.rejected


def test_take_state_is_the_same_on_a_rescan(take_dir):
    put_timestamps(take_dir, "front")
    put_closed(take_dir, ["front"])

    assert take_state(take_dir) == take_state(take_dir)
