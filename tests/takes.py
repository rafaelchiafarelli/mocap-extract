"""Builders for synthetic take folders, laid out and sidecar'd the way the recorder hands them off."""

import hashlib
from pathlib import Path

from mocap_contracts import (
    CameraConfig, CameraFileReady, CameraSource, FileKind, SyncEvent, SyncKind, SyncSource, Take,
    TakeCamera, TakeClosed, TakeType, layout, to_json,
)

TAKE = "take-001"
SESSION = "session-1"


def sync(kind: str, ts: int) -> SyncEvent:
    return SyncEvent(kind=SyncKind.Value(kind), host_ts_ns=ts, source=SyncSource.Value("SYNC_SOURCE_MANUAL"))


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


def put_timestamps(take: Path, role: str, rows=((0, 1000),), **override) -> Path:
    text = ",".join(layout.TIMESTAMPS_COLUMNS) + "\n" + "".join(f"{f},{t}\n" for f, t in rows)
    rel = layout.raw_timestamps(take, role).relative_to(take).as_posix()
    return put_file(take, rel, text.encode(), role, "FILE_KIND_TIMESTAMPS", **override)


def put_video(take: Path, role: str, **override) -> Path:
    rel = layout.prep_video(take, role).relative_to(take).as_posix()
    return put_file(take, rel, b"\x1a\x45\xdf\xa3video-" + role.encode(), role, "FILE_KIND_VIDEO", **override)


def put_closed(take: Path, roles: list[str], take_id: str = TAKE) -> None:
    closed = TakeClosed(
        take_id=take_id,
        roles=roles,
        start=sync("SYNC_KIND_START", 1_000),
        end=sync("SYNC_KIND_END", 3_000),
    )
    layout.closed_json(take).write_text(to_json(closed), encoding="utf-8")


def put_take_json(take: Path, fps_by_role: dict[str, float], start_ns: int, end_ns: int | None,
                  take_id: str = TAKE) -> None:
    cameras = [
        TakeCamera(config=CameraConfig(
            role=role, source=CameraSource.Value("CAMERA_SOURCE_UVC"), width=1920, height=1080,
            fps=fps, notes="", device_hint=f"/dev/v4l/by-id/{role}",
        ))
        for role, fps in fps_by_role.items()
    ]
    msg = Take(id=take_id, session_id=SESSION, type=TakeType.Value("TAKE_TYPE_PERFORMANCE"),
               start=sync("SYNC_KIND_START", start_ns), cameras=cameras)
    if end_ns is not None:
        msg.end.CopyFrom(sync("SYNC_KIND_END", end_ns))
    layout.take_json(take).write_text(to_json(msg), encoding="utf-8")
