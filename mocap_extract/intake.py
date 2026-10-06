"""Take intake on the processing PC: a file is only usable once its sidecar vouches for it.

The recorder fills the take folder file by file. Next to each file it writes
`<file>.ready.json` (a `CameraFileReady`), and once every timestamps file is in
it writes `closed.json` (a `TakeClosed`, which lists the roles). Everything
here is read from those sidecars on disk, so a lost event or a restart loses
nothing: calling `take_state` again gives the same answer.

Each role is expected to deliver one TIMESTAMPS file and one VIDEO file. They
are tracked by (role, kind), not by path, because the path each one arrives
under is the recorder's to declare in the sidecar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from mocap_contracts import CameraFileReady, ContractError, FileKind, TakeClosed, from_json, layout

EXPECTED_KINDS = ("FILE_KIND_TIMESTAMPS", "FILE_KIND_VIDEO")

_READY_SUFFIX = ".ready.json"
_HASH_CHUNK = 1 << 20


class FileRejected(Exception):
    """A file that must not be processed: no sidecar, or it doesn't match its sidecar."""

    def __init__(self, rel_path: str, reason: str):
        super().__init__(f"{rel_path}: {reason}")
        self.rel_path = rel_path
        self.reason = reason


@dataclass(frozen=True)
class TakeState:
    take_id: str
    closed: TakeClosed | None
    """The take's `TakeClosed`, or None while closed.json hasn't arrived (or is invalid)."""
    expected_roles: tuple[str, ...]
    """From closed.json. Empty until it arrives."""
    verified: dict[str, CameraFileReady]
    """Take-relative path -> its sidecar, for every file that matches its sidecar."""
    rejected: dict[str, str]
    """Take-relative path -> why it can't be processed."""
    missing: tuple[tuple[str, str], ...]
    """(role, kind) pairs of expected roles with no verified file yet."""

    @property
    def complete(self) -> bool:
        return self.closed is not None and not self.missing

    def files(self, role: str, kind: str) -> list[str]:
        """Verified paths for one role and kind (FILE_KIND_* name)."""
        return sorted(
            path for path, ready in self.verified.items()
            if ready.role == role and FileKind.Name(ready.kind) == kind
        )


def check_file(take_dir: Path | str, rel_path: str) -> CameraFileReady:
    """Return the sidecar of `rel_path` once the file matches it, else raise FileRejected.

    Checks the sidecar is a valid `CameraFileReady` for this take and this path,
    then the file's size and sha256.
    """
    take_dir = Path(take_dir)
    _check_relative(rel_path)
    path = take_dir / rel_path
    sidecar = layout.ready_sidecar(path)
    if not sidecar.is_file():
        raise FileRejected(rel_path, "no sidecar")
    try:
        ready = from_json(CameraFileReady, sidecar.read_text(encoding="utf-8"))
    except ContractError as e:
        raise FileRejected(rel_path, f"invalid sidecar: {e}") from None
    if ready.take_id != take_dir.name:
        raise FileRejected(rel_path, f"sidecar is for take {ready.take_id!r}, not {take_dir.name!r}")
    if PurePosixPath(ready.path) != PurePosixPath(rel_path):
        raise FileRejected(rel_path, f"sidecar announces {ready.path!r}")
    if not path.is_file():
        raise FileRejected(rel_path, "file not found")
    size = path.stat().st_size
    if size != ready.size_bytes:
        raise FileRejected(rel_path, f"size {size} != sidecar {ready.size_bytes}")
    digest = _sha256(path)
    if digest != ready.sha256:
        raise FileRejected(rel_path, f"sha256 {digest} != sidecar {ready.sha256}")
    return ready


def take_state(take_dir: Path | str) -> TakeState:
    """What the take expects, what has arrived and been verified, and what's missing."""
    take_dir = Path(take_dir)
    rejected: dict[str, str] = {}

    closed = None
    closed_path = layout.closed_json(take_dir)
    if closed_path.is_file():
        try:
            closed = from_json(TakeClosed, closed_path.read_text(encoding="utf-8"))
        except ContractError as e:
            rejected[closed_path.name] = f"invalid: {e}"
        else:
            if closed.take_id != take_dir.name:
                rejected[closed_path.name] = f"is for take {closed.take_id!r}, not {take_dir.name!r}"
                closed = None

    verified: dict[str, CameraFileReady] = {}
    for sidecar in sorted(take_dir.rglob("*" + _READY_SUFFIX)):
        rel_path = sidecar.relative_to(take_dir).as_posix()[: -len(_READY_SUFFIX)]
        try:
            verified[rel_path] = check_file(take_dir, rel_path)
        except FileRejected as e:
            rejected[rel_path] = e.reason

    expected_roles = tuple(closed.roles) if closed else ()
    have = {(r.role, FileKind.Name(r.kind)) for r in verified.values()}
    missing = tuple(
        (role, kind) for role in expected_roles for kind in EXPECTED_KINDS if (role, kind) not in have
    )
    return TakeState(
        take_id=take_dir.name,
        closed=closed,
        expected_roles=expected_roles,
        verified=verified,
        rejected=rejected,
        missing=missing,
    )


def _check_relative(rel_path: str) -> None:
    parts = PurePosixPath(rel_path).parts
    if not rel_path or rel_path.startswith("/") or ".." in parts:
        raise FileRejected(rel_path, "path must be relative to the take folder")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_HASH_CHUNK):
            h.update(chunk)
    return h.hexdigest()
