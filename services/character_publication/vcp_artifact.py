"""LAB-L3: build one verified portable ``.vchar`` from a LAB-L2 compilation.

Orchestration only. Every byte-level and package-level contract is owned by
Shared Core (VCP); this module calls, in order:

    materialize_package_v1 -> verify_package_v1 -> write_vchar_v1
        -> streaming artifact SHA/size check -> extract_vchar_v1

and requires the identities reported by each stage to agree. It compiles
nothing, reads no Authoring store, ApprovalEvidence, or lifecycle pointer, and
does not decide whether a release is publishable: the LAB-L2 compilation is the
immutable logical input.

Workspace model: the caller supplies an absolute path that must NOT exist. This
module creates it and owns only what it creates beneath it. On any failure the
workspace it created is removed; on success it is left intact so the exact
artifact can be persisted by a later slice without rebuilding. The workspace is
not a release store and not an export destination.

Like ``vcp_domains`` and ``vcp_release`` this module is deliberately not
re-exported from ``services.character_publication``.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, TypeVar

from services.character_authoring import ApprovalEvidence

from .model import SourceProvenance
from .vcp_release import AuthoringVcpReleaseCompilation

from voyage_character_platform.package_v1 import (
    PackageV1Error,
    VerifiedPackageV1,
    materialize_package_v1,
    verify_package_v1,
)
from voyage_character_platform.vchar import (
    WrittenVcharV1,
    extract_vchar_v1,
    write_vchar_v1,
)


PACKAGE_DIRNAME = "package"
ARTIFACT_FILENAME = "artifact.vchar"
ROUNDTRIP_DIRNAME = "roundtrip"

_READ_CHUNK = 1024 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

_T = TypeVar("_T")


class VcpArtifactStage(str, Enum):
    """The orchestration stage in which a build failed."""

    INPUT = "INPUT"
    WORKSPACE = "WORKSPACE"
    MATERIALIZE = "MATERIALIZE"
    DIRECTORY_VERIFY = "DIRECTORY_VERIFY"
    VCHAR_WRITE = "VCHAR_WRITE"
    ARTIFACT_INTEGRITY = "ARTIFACT_INTEGRITY"
    ROUNDTRIP = "ROUNDTRIP"


class AuthoringVcpArtifactBuildError(ValueError):
    """A stage of the verified-artifact build failed; no artifact is returned.

    ``stage`` names the failing stage. ``cleanup_complete`` is False only if
    the workspace this call created could not be fully removed. The original
    VCP or OS exception is preserved as ``__cause__`` where there is one.
    """

    def __init__(
        self,
        stage: VcpArtifactStage,
        message: str,
        *,
        cleanup_complete: bool = True,
    ) -> None:
        super().__init__(f"{stage.value}: {message}")
        self.stage = stage
        self.detail = message
        self.cleanup_complete = cleanup_complete


@dataclass(frozen=True, slots=True)
class BuiltVcpArtifact:
    """One verified ``.vchar`` and the identity it was verified against.

    Package identity is (``character_id``, ``release_id``, ``package_hash``).
    ``artifact_sha256`` and ``byte_length`` describe the transport bytes only.
    ``artifact_path`` is the exact file a later slice persists; it lives in the
    build workspace and is neither an export destination nor a release store.
    """

    workspace_root: Path
    package_root: Path
    roundtrip_root: Path
    artifact_path: Path
    character_id: str
    release_id: str
    package_hash: str
    artifact_sha256: str
    byte_length: int
    aggregate_candidate_id: str
    aggregate_hash: str
    acceptance_record_hash: str
    source: SourceProvenance
    approval: ApprovalEvidence
    verified_package: VerifiedPackageV1
    verified_roundtrip: VerifiedPackageV1
    written: WrittenVcharV1


def _fail(
    stage: VcpArtifactStage, message: str, *, cause: BaseException | None = None
) -> AuthoringVcpArtifactBuildError:
    error = AuthoringVcpArtifactBuildError(stage, message)
    error.__cause__ = cause
    return error


def _run_stage(stage: VcpArtifactStage, description: str, call: Callable[[], _T]) -> _T:
    try:
        return call()
    except AuthoringVcpArtifactBuildError:
        raise
    except (PackageV1Error, OSError, ValueError) as exc:
        raise _fail(stage, f"{description} failed: {exc}", cause=exc) from exc


def _is_link(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _validated_workspace(workspace_root: object) -> Path:
    if not isinstance(workspace_root, (str, os.PathLike)):
        raise _fail(VcpArtifactStage.WORKSPACE, "workspace_root must be a path")
    workspace = Path(workspace_root)
    if not workspace.is_absolute():
        raise _fail(VcpArtifactStage.WORKSPACE, "workspace_root must be absolute")
    if ".." in workspace.parts:
        raise _fail(
            VcpArtifactStage.WORKSPACE, "workspace_root must not contain '..' segments"
        )
    if workspace.name in ("", ".") or workspace.parent == workspace:
        raise _fail(VcpArtifactStage.WORKSPACE, "workspace_root must name a directory")
    if os.path.lexists(workspace):
        raise _fail(
            VcpArtifactStage.WORKSPACE,
            "workspace_root already exists; the build never reuses or merges",
        )
    if not workspace.parent.is_dir():
        raise _fail(
            VcpArtifactStage.WORKSPACE,
            "the parent of workspace_root must be an existing directory",
        )
    return workspace


def _hash_file(path: Path) -> tuple[str, int]:
    """Stream the file once and return (sha256 hex, byte length)."""

    status = path.lstat()
    if _is_link(status) or not stat.S_ISREG(status.st_mode):
        raise ValueError("artifact must be a regular file")
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_READ_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            length += len(chunk)
    return digest.hexdigest(), length


def _require_identity(
    stage: VcpArtifactStage,
    label: str,
    verified: VerifiedPackageV1,
    compilation: AuthoringVcpReleaseCompilation,
    expected_package_hash: str,
) -> None:
    metadata = verified.metadata
    problems = []
    if verified.package_hash != expected_package_hash:
        problems.append("packageHash")
    if metadata.character_id != compilation.metadata.character_id:
        problems.append("characterId")
    if metadata.character_id != compilation.source.source_character_id:
        problems.append("characterId (source)")
    if metadata.release_id != compilation.metadata.release_id:
        problems.append("releaseId")
    if metadata.accepted_aggregate_hash != compilation.aggregate_hash:
        problems.append("acceptedAggregateHash")
    if metadata.acceptance_record_hash != compilation.acceptance_record_hash:
        problems.append("acceptanceRecordHash")
    if problems:
        raise _fail(
            stage,
            f"{label} does not agree with the LAB-L2 compilation on: "
            + ", ".join(problems),
        )


def build_verified_vchar_artifact(
    compilation: AuthoringVcpReleaseCompilation,
    workspace_root: str | os.PathLike[str],
) -> BuiltVcpArtifact:
    """Turn a LAB-L2 compilation into one verified ``.vchar`` in a fresh workspace.

    ``workspace_root`` must be an absolute path that does not exist and whose
    parent does. It is created here; on any failure it is removed again, and on
    success it is kept with ``package/``, ``artifact.vchar`` and ``roundtrip/``.
    """

    if not isinstance(compilation, AuthoringVcpReleaseCompilation):
        raise _fail(
            VcpArtifactStage.INPUT,
            "compilation must be a LAB-L2 AuthoringVcpReleaseCompilation",
        )
    workspace = _validated_workspace(workspace_root)
    try:
        workspace.mkdir()
    except OSError as exc:
        # Not ours (or not creatable): nothing was created, so nothing is removed.
        raise _fail(
            VcpArtifactStage.WORKSPACE, f"workspace_root cannot be created: {exc}",
            cause=exc,
        ) from exc

    try:
        return _build_in_workspace(compilation, workspace)
    except BaseException as exc:
        shutil.rmtree(workspace, ignore_errors=True)
        if os.path.lexists(workspace) and isinstance(exc, AuthoringVcpArtifactBuildError):
            exc.cleanup_complete = False
        raise


def _build_in_workspace(
    compilation: AuthoringVcpReleaseCompilation, workspace: Path
) -> BuiltVcpArtifact:
    package_root = workspace / PACKAGE_DIRNAME
    artifact_path = workspace / ARTIFACT_FILENAME
    roundtrip_root = workspace / ROUNDTRIP_DIRNAME

    materialized = _run_stage(
        VcpArtifactStage.MATERIALIZE,
        "materialize_package_v1",
        lambda: materialize_package_v1(package_root, files=dict(compilation.files)),
    )
    package_hash = materialized.package_hash

    verified = _run_stage(
        VcpArtifactStage.DIRECTORY_VERIFY,
        "verify_package_v1",
        lambda: verify_package_v1(package_root, expected_package_hash=package_hash),
    )
    _require_identity(
        VcpArtifactStage.DIRECTORY_VERIFY,
        "verified directory package",
        verified,
        compilation,
        package_hash,
    )

    written = _run_stage(
        VcpArtifactStage.VCHAR_WRITE,
        "write_vchar_v1",
        lambda: write_vchar_v1(package_root, artifact_path),
    )
    if (
        Path(written.path) != artifact_path
        or written.character_id != verified.metadata.character_id
        or written.release_id != verified.metadata.release_id
        or written.package_hash != verified.package_hash
    ):
        raise _fail(
            VcpArtifactStage.VCHAR_WRITE,
            "write_vchar_v1 reported a path or identity that disagrees with the "
            "verified directory package",
        )

    actual_sha256, actual_length = _run_stage(
        VcpArtifactStage.ARTIFACT_INTEGRITY,
        "artifact read-back",
        lambda: _hash_file(artifact_path),
    )
    if actual_sha256 != written.artifact_sha256:
        raise _fail(
            VcpArtifactStage.ARTIFACT_INTEGRITY,
            "artifact SHA-256 on disk differs from the value reported by write_vchar_v1",
        )
    if actual_length != written.byte_length:
        raise _fail(
            VcpArtifactStage.ARTIFACT_INTEGRITY,
            "artifact size on disk differs from the value reported by write_vchar_v1",
        )

    roundtrip = _run_stage(
        VcpArtifactStage.ROUNDTRIP,
        "extract_vchar_v1",
        lambda: extract_vchar_v1(
            artifact_path, roundtrip_root, expected_package_hash=package_hash
        ),
    )
    _require_identity(
        VcpArtifactStage.ROUNDTRIP,
        "round-trip extracted package",
        roundtrip,
        compilation,
        package_hash,
    )
    if roundtrip.manifest != verified.manifest:
        raise _fail(
            VcpArtifactStage.ROUNDTRIP,
            "round-trip manifest differs from the verified directory package",
        )

    return BuiltVcpArtifact(
        workspace_root=workspace,
        package_root=package_root,
        roundtrip_root=roundtrip_root,
        artifact_path=artifact_path,
        character_id=verified.metadata.character_id,
        release_id=verified.metadata.release_id,
        package_hash=package_hash,
        artifact_sha256=actual_sha256,
        byte_length=actual_length,
        aggregate_candidate_id=compilation.aggregate_candidate_id,
        aggregate_hash=compilation.aggregate_hash,
        acceptance_record_hash=compilation.acceptance_record_hash,
        source=compilation.source,
        approval=compilation.approval,
        verified_package=verified,
        verified_roundtrip=roundtrip,
        written=written,
    )


__all__ = [
    "ARTIFACT_FILENAME",
    "AuthoringVcpArtifactBuildError",
    "BuiltVcpArtifact",
    "PACKAGE_DIRNAME",
    "ROUNDTRIP_DIRNAME",
    "VcpArtifactStage",
    "build_verified_vchar_artifact",
]
