"""LAB-L4: durable immutable Character Lab releases and explicit canonical current.

Takes the exact verified LAB-L3 ``BuiltVcpArtifact`` and makes it a durable,
immutable release without rebuilding anything: it never compiles, never
materializes a package, and never writes an archive. Publication persists the
exact ``.vchar`` bytes and one write-once release record; that record is the
publication commit point.

PUBLISH != DESIGNATE CURRENT (OWNER ratified). ``publish_release`` never touches
canonical current; only an explicit ``set_canonical_current`` does, and rollback
is simply ``set_canonical_current`` to an older release.

Store layout under the caller-supplied absolute root (four distinct namespaces
plus scratch space):

    artifacts/<package_hash>.vchar              immutable, exact archive bytes
    releases/<character_id>/<release_id>.json   immutable, write-once record
    current/<character_id>.json                 mutable canonical-current pointer
    history/<character_id>/<generation>.json    append-only, write-once entries
    locks/<character_id>.lock                   coordination only, never deleted
    tmp/                                        scratch (temp copies, verification)

Designation (OD-LAB-L4-DESIGNATION-TX-01): every current mutation for one
character runs under one exclusive OS-backed advisory lock
(``locks/<character_id>.lock``; ``msvcrt`` on Windows, ``fcntl`` elsewhere,
standard library only, released by the OS if the holder dies, independent per
character). Under it a designation *claims* the next history generation by
exclusive create, then atomically replaces the current pointer. The claim is the
durable intent; the pointer is its commit. A crash between the two leaves
exactly one *pending* claim: reads (which take no lock) keep returning the
previous, still-valid current, and the next designation rolls the pending claim
forward, once, before evaluating its own request.

Durability (OD-LAB-L4-DURABILITY-01): once a release record exists, its artifact
is durable published state. If it is missing or corrupt the store is corrupt and
publication fails closed; it is never restored from a newly supplied artifact.
An artifact with no record is a pre-commit orphan and may be reused by a retry.

Like ``vcp_domains``, ``vcp_release`` and ``vcp_artifact`` this module is
deliberately not re-exported from ``services.character_publication``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from services.character_authoring import (
    APPROVAL_DECISION_HUMAN_APPROVED,
    ApprovalClock,
    CharacterAuthoringError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStore,
    LifecycleState,
    format_decided_at,
    system_utc_clock,
    validate_decided_at,
    validate_decided_by,
    validate_identifier,
)

from .model import SourceProvenance
from .errors import PublicationValidationError
from .vcp_artifact import BuiltVcpArtifact

from voyage_character_platform.package_v1 import PackageV1Error
from voyage_character_platform.paths import PackagePathError, normalize_package_path
from voyage_character_platform.vchar import extract_vchar_v1

try:  # Windows OS-backed byte-range lock
    import msvcrt
except ImportError:  # pragma: no cover - platform dependent
    msvcrt = None  # type: ignore[assignment]
try:  # POSIX OS-backed advisory lock
    import fcntl
except ImportError:  # pragma: no cover - platform dependent
    fcntl = None  # type: ignore[assignment]


RELEASE_RECORD_SCHEMA_VERSION = "character_release_record/1.0"
CURRENT_SCHEMA_VERSION = "character_current_release/1.0"
HISTORY_SCHEMA_VERSION = "character_current_history/1.0"

ARTIFACTS_DIRNAME = "artifacts"
RELEASES_DIRNAME = "releases"
CURRENT_DIRNAME = "current"
HISTORY_DIRNAME = "history"
SCRATCH_DIRNAME = "tmp"
LOCKS_DIRNAME = "locks"

# msvcrt has no blocking lock (LK_LOCK gives up after ~10 s at 1 s granularity),
# so Windows polls a non-blocking exclusive lock until this deadline. POSIX
# flock blocks natively and needs no timeout.
_LOCK_TIMEOUT_SECONDS = 60.0
_LOCK_POLL_SECONDS = 0.005
_READ_CHUNK = 1024 * 1024
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_RELEASE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
_HEX64_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)
_CANDIDATE_ID_RE = re.compile(r"[a-z][a-z0-9._-]{0,127}", re.ASCII)
_HISTORY_NAME_RE = re.compile(r"([0-9]{8})\.json", re.ASCII)


# -- errors (small, code-carrying) ---------------------------------------------


class CharacterReleaseStoreError(Exception):
    """Base for Lab release-store failures; ``code`` is the stable category."""

    code = "RELEASE_STORE_ERROR"


class ReleaseInputError(CharacterReleaseStoreError):
    code = "INVALID_INPUT"


class ReleasePublishabilityError(CharacterReleaseStoreError):
    code = "RELEASE_NOT_PUBLISHABLE"


class ReleaseSourceArtifactError(CharacterReleaseStoreError):
    code = "SOURCE_ARTIFACT_INVALID"


class ReleaseIdHashCollisionError(CharacterReleaseStoreError):
    """Same (character_id, release_id) with a different packageHash."""

    code = "RELEASE_ID_HASH_COLLISION"


class ReleaseRecordConflictError(CharacterReleaseStoreError):
    """A same-hash record disagrees on other immutable fields, or ids collide."""

    code = "RELEASE_RECORD_CONFLICT"


class ReleaseRecordCorruptError(CharacterReleaseStoreError):
    code = "RELEASE_RECORD_CORRUPT"


class DurableArtifactCorruptError(CharacterReleaseStoreError):
    code = "DURABLE_ARTIFACT_CORRUPT"


class ReleaseNotFoundError(CharacterReleaseStoreError):
    code = "RELEASE_NOT_FOUND"


class CurrentDesignationError(CharacterReleaseStoreError):
    code = "CURRENT_DESIGNATION_FAILED"


class ReleaseExportError(CharacterReleaseStoreError):
    code = "RELEASE_EXPORT_FAILED"


class ReleaseStorageError(CharacterReleaseStoreError):
    code = "RELEASE_STORAGE_FAILED"


# -- validation helpers -----------------------------------------------------------


def validate_release_id(value: object) -> str:
    """VCP-compatible release id that is also a safe Windows file name."""

    if not isinstance(value, str) or _RELEASE_ID_RE.fullmatch(value) is None:
        raise ReleaseInputError(
            "release_id must be 1-128 ASCII letters, digits, '.', '_' or '-' "
            "and start with a letter or digit"
        )
    try:
        if normalize_package_path(value) != value:
            raise ReleaseInputError("release_id is not a canonical package path segment")
    except PackagePathError as exc:
        raise ReleaseInputError(f"release_id is not path-safe: {exc}") from exc
    return value


def _character_id(value: object) -> str:
    try:
        return validate_identifier(value, field="character_id")
    except CharacterAuthoringError as exc:
        raise ReleaseInputError(str(exc)) from exc


def _hex64(value: object, field: str, error: type[CharacterReleaseStoreError]) -> str:
    if not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None:
        raise error(f"{field}: expected lowercase 64-character SHA-256")
    return value


def _positive_int(value: object, field: str, error: type[CharacterReleaseStoreError]) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise error(f"{field}: expected a positive integer")
    return value


def _is_link(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or bool(
        getattr(status, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT
    )


# -- records ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReleaseApproval:
    """Approval facts retained from the LAB-L1 evidence at publication time."""

    decision: str
    decided_by: str
    decided_at: str

    def __post_init__(self) -> None:
        try:
            if self.decision != APPROVAL_DECISION_HUMAN_APPROVED:
                raise ValueError("decision must be HUMAN_APPROVED")
            validate_decided_by(self.decided_by)
            validate_decided_at(self.decided_at)
        except (CharacterAuthoringError, ValueError) as exc:
            raise ReleaseRecordCorruptError(f"approval is invalid: {exc}") from exc

    def to_dict(self) -> dict[str, str]:
        return {
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True, slots=True)
class ReleaseRecord:
    """The immutable release record; its durable write is the commit point."""

    character_id: str
    release_id: str
    package_hash: str
    artifact_sha256: str
    byte_length: int
    source: SourceProvenance
    aggregate_candidate_id: str
    aggregate_hash: str
    acceptance_record_hash: str
    approval: ReleaseApproval
    published_at: str

    def __post_init__(self) -> None:
        bad = ReleaseRecordCorruptError
        try:
            validate_identifier(self.character_id, field="character_id")
            validate_release_id(self.release_id)
            validate_decided_at(self.published_at)
        except (CharacterAuthoringError, CharacterReleaseStoreError) as exc:
            raise bad(f"release record is invalid: {exc}") from exc
        _hex64(self.package_hash, "package_hash", bad)
        _hex64(self.artifact_sha256, "artifact_sha256", bad)
        _hex64(self.aggregate_hash, "aggregate_hash", bad)
        _hex64(self.acceptance_record_hash, "acceptance_record_hash", bad)
        _positive_int(self.byte_length, "byte_length", bad)
        if (
            not isinstance(self.aggregate_candidate_id, str)
            or _CANDIDATE_ID_RE.fullmatch(self.aggregate_candidate_id) is None
        ):
            raise bad("aggregate_candidate_id: invalid")
        if not isinstance(self.source, SourceProvenance):
            raise bad("source: expected SourceProvenance")
        if self.source.source_character_id != self.character_id:
            raise bad("source character does not match the release character")
        if not isinstance(self.approval, ReleaseApproval):
            raise bad("approval: expected ReleaseApproval")

    @property
    def artifact_ref(self) -> str:
        return f"{ARTIFACTS_DIRNAME}/{self.package_hash}.vchar"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RELEASE_RECORD_SCHEMA_VERSION,
            "character_id": self.character_id,
            "release_id": self.release_id,
            "package_hash": self.package_hash,
            "artifact_sha256": self.artifact_sha256,
            "byte_length": self.byte_length,
            "artifact_ref": self.artifact_ref,
            "source": {
                "character_id": self.source.source_character_id,
                "version_id": self.source.source_version_id,
                "revision_id": self.source.source_revision_id,
                "snapshot_hash": self.source.source_snapshot_hash,
            },
            "aggregate_candidate_id": self.aggregate_candidate_id,
            "aggregate_hash": self.aggregate_hash,
            "acceptance_record_hash": self.acceptance_record_hash,
            "approval": self.approval.to_dict(),
            "published_at": self.published_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ReleaseRecord":
        expected = {
            "schema_version", "character_id", "release_id", "package_hash",
            "artifact_sha256", "byte_length", "artifact_ref", "source",
            "aggregate_candidate_id", "aggregate_hash", "acceptance_record_hash",
            "approval", "published_at",
        }
        data = _require_keys(data, expected, "release record")
        if data["schema_version"] != RELEASE_RECORD_SCHEMA_VERSION:
            raise ReleaseRecordCorruptError("unsupported release record schema")
        source = _require_keys(
            data["source"], {"character_id", "version_id", "revision_id", "snapshot_hash"},
            "release record source",
        )
        approval = _require_keys(
            data["approval"], {"decision", "decided_by", "decided_at"}, "release approval"
        )
        try:
            provenance = SourceProvenance(
                source_character_id=source["character_id"],
                source_version_id=source["version_id"],
                source_revision_id=source["revision_id"],
                source_snapshot_hash=source["snapshot_hash"],
            )
        except PublicationValidationError as exc:
            raise ReleaseRecordCorruptError(f"release record source invalid: {exc}") from exc
        record = cls(
            character_id=data["character_id"],
            release_id=data["release_id"],
            package_hash=data["package_hash"],
            artifact_sha256=data["artifact_sha256"],
            byte_length=data["byte_length"],
            source=provenance,
            aggregate_candidate_id=data["aggregate_candidate_id"],
            aggregate_hash=data["aggregate_hash"],
            acceptance_record_hash=data["acceptance_record_hash"],
            approval=ReleaseApproval(**approval),
            published_at=data["published_at"],
        )
        if data["artifact_ref"] != record.artifact_ref:
            raise ReleaseRecordCorruptError("artifact_ref does not match package_hash")
        return record


@dataclass(frozen=True, slots=True)
class CanonicalCurrent:
    """The explicit current designation for one character."""

    character_id: str
    release_id: str
    package_hash: str
    generation: int

    def __post_init__(self) -> None:
        bad = CurrentDesignationError
        try:
            validate_identifier(self.character_id, field="character_id")
            validate_release_id(self.release_id)
        except (CharacterAuthoringError, CharacterReleaseStoreError) as exc:
            raise bad(f"current designation is invalid: {exc}") from exc
        _hex64(self.package_hash, "package_hash", bad)
        _positive_int(self.generation, "generation", bad)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "character_id": self.character_id,
            "release_id": self.release_id,
            "package_hash": self.package_hash,
            "generation": self.generation,
        }

    @classmethod
    def from_dict(cls, data: object) -> "CanonicalCurrent":
        data = _require_keys(
            data,
            {"schema_version", "character_id", "release_id", "package_hash", "generation"},
            "current designation",
            error=CurrentDesignationError,
        )
        if data["schema_version"] != CURRENT_SCHEMA_VERSION:
            raise CurrentDesignationError("unsupported current designation schema")
        return cls(
            character_id=data["character_id"], release_id=data["release_id"],
            package_hash=data["package_hash"], generation=data["generation"],
        )


@dataclass(frozen=True, slots=True)
class DesignationEntry:
    """One append-only history entry: an actual current change."""

    generation: int
    character_id: str
    from_release_id: Optional[str]
    from_package_hash: Optional[str]
    to_release_id: str
    to_package_hash: str
    designated_at: str

    def __post_init__(self) -> None:
        bad = CurrentDesignationError
        try:
            validate_identifier(self.character_id, field="character_id")
            validate_release_id(self.to_release_id)
            if (self.from_release_id is None) != (self.from_package_hash is None):
                raise ValueError("from_release_id and from_package_hash go together")
            if self.from_release_id is not None:
                validate_release_id(self.from_release_id)
            validate_decided_at(self.designated_at)
        except (CharacterAuthoringError, CharacterReleaseStoreError, ValueError) as exc:
            raise bad(f"designation entry is invalid: {exc}") from exc
        _positive_int(self.generation, "generation", bad)
        _hex64(self.to_package_hash, "to_package_hash", bad)
        if self.from_package_hash is not None:
            _hex64(self.from_package_hash, "from_package_hash", bad)
        if (self.generation == 1) != (self.from_release_id is None):
            raise bad("only the first designation may have no previous release")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "generation": self.generation,
            "character_id": self.character_id,
            "from_release_id": self.from_release_id,
            "from_package_hash": self.from_package_hash,
            "to_release_id": self.to_release_id,
            "to_package_hash": self.to_package_hash,
            "designated_at": self.designated_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "DesignationEntry":
        data = _require_keys(
            data,
            {"schema_version", "generation", "character_id", "from_release_id",
             "from_package_hash", "to_release_id", "to_package_hash", "designated_at"},
            "designation entry",
            error=CurrentDesignationError,
        )
        if data["schema_version"] != HISTORY_SCHEMA_VERSION:
            raise CurrentDesignationError("unsupported designation history schema")
        return cls(**{k: v for k, v in data.items() if k != "schema_version"})


def _require_keys(
    value: object,
    expected: set[str],
    label: str,
    *,
    error: type[CharacterReleaseStoreError] = ReleaseRecordCorruptError,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise error(f"{label}: expected exactly the keys {sorted(expected)}")
    return value


@dataclass(frozen=True, slots=True)
class PublishedRelease:
    """Result of ``publish_release``; ``newly_published`` is False when idempotent."""

    record: ReleaseRecord
    artifact_path: Path
    newly_published: bool


@dataclass(frozen=True, slots=True)
class VerifiedRelease:
    """A release whose stored artifact was re-verified through authoritative VCP."""

    record: ReleaseRecord
    artifact_path: Path


@dataclass(frozen=True, slots=True)
class ExportedRelease:
    """Where the exact stored bytes were copied; export creates no new identity."""

    path: Path
    character_id: str
    release_id: str
    package_hash: str
    artifact_sha256: str
    byte_length: int


# -- durable file primitives ---------------------------------------------------------


def _serialize(data: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _parse_canonical(raw: bytes, label: str, error: type[CharacterReleaseStoreError]) -> dict:
    try:
        text = raw.decode("utf-8")
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeError, ValueError) as exc:
        raise error(f"{label} is unreadable or invalid JSON") from exc
    if not isinstance(data, dict):
        raise error(f"{label} must be a JSON object")
    try:
        if _serialize(data) != raw:
            raise error(f"{label} is not in canonical form")
    except (TypeError, ValueError) as exc:
        raise error(f"{label} cannot be canonicalized") from exc
    return data


def _write_temp(directory: Path, data: Mapping[str, Any]) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    payload = _serialize(data)
    fd, temp_path = tempfile.mkstemp(dir=str(directory), prefix=".tmp_release_", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return temp_path


def _write_once_json(target: Path, data: Mapping[str, Any]) -> bool:
    """Exclusively create ``target``; return False if it already exists."""

    temp_path = _write_temp(target.parent, data)
    try:
        try:
            os.link(temp_path, target)
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _atomic_replace_json(target: Path, data: Mapping[str, Any]) -> None:
    temp_path = _write_temp(target.parent, data)
    try:
        os.replace(temp_path, target)
    except OSError:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _stream_copy(source: Path, temp_path: Path) -> tuple[str, int]:
    """Copy ``source`` to ``temp_path`` in chunks; return (sha256, length)."""

    digest = hashlib.sha256()
    length = 0
    with source.open("rb") as reader, temp_path.open("wb") as writer:
        while True:
            chunk = reader.read(_READ_CHUNK)
            if not chunk:
                break
            writer.write(chunk)
            digest.update(chunk)
            length += len(chunk)
        writer.flush()
        os.fsync(writer.fileno())
    return digest.hexdigest(), length


def _hash_file(path: Path) -> tuple[str, int]:
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


class _DesignationLock:
    """Exclusive cross-process OS lock on one persistent lock file.

    Standard library only: ``msvcrt.locking`` on Windows, ``fcntl.flock`` on
    POSIX. The OS releases it automatically if the holder dies. The lock file is
    coordination state only and is never deleted. Locks conflict between handles
    of the same process too, so threads are serialized as well.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: Optional[int] = None

    @staticmethod
    def _require_regular(status: os.stat_result) -> None:
        if _is_link(status) or not stat.S_ISREG(status.st_mode):
            raise CurrentDesignationError("designation lock path is not a regular file")

    def __enter__(self) -> "_DesignationLock":
        if msvcrt is None and fcntl is None:
            raise CurrentDesignationError("no OS file-locking primitive is available")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._require_regular(self._path.lstat())
        except FileNotFoundError:
            pass
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        fd = os.open(self._path, flags, 0o666)
        try:
            self._require_regular(os.fstat(fd))
            self._acquire(fd)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def _acquire(self, fd: int) -> None:
        if msvcrt is not None:
            deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
            while True:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    if time.monotonic() >= deadline:
                        raise CurrentDesignationError(
                            "timed out waiting for the character designation lock"
                        ) from None
                    time.sleep(_LOCK_POLL_SECONDS)
        fcntl.flock(fd, fcntl.LOCK_EX)  # blocks until the holder releases or dies

    def __exit__(self, *_exc: object) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            if msvcrt is not None:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass  # closing the descriptor releases the lock regardless
        finally:
            os.close(fd)


# -- the store ----------------------------------------------------------------------


class CharacterReleaseStore:
    """Durable, append-only Character Lab release store (V1: keep everything)."""

    def __init__(self, root: Path | str, *, clock: Optional[ApprovalClock] = None) -> None:
        candidate = Path(root)
        if not candidate.is_absolute() or ".." in candidate.parts:
            raise ReleaseInputError("release store root must be an absolute path")
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReleaseStorageError("release store root cannot be created") from exc
        if not candidate.is_dir():
            raise ReleaseInputError("release store root is not a directory")
        self._root = candidate.resolve()
        self._clock: ApprovalClock = clock or system_utc_clock

    @property
    def root(self) -> Path:
        return self._root

    # -- paths ------------------------------------------------------------------

    def _safe(self, *parts: str) -> Path:
        """Join validated components under the root, lexically.

        Every component is already a validated identifier, hex digest, digit
        run, or fixed namespace name; this is a defensive check that none can
        carry a separator, drive, or dot segment. The filesystem is deliberately
        not re-resolved: ``resolve()`` can return differing forms under load.
        """

        for part in parts:
            if (
                not isinstance(part, str)
                or part in ("", ".", "..")
                or any(char in part for char in "/\\:")
            ):
                raise ReleaseStorageError("unsafe release store path component")
        return self._root.joinpath(*parts)

    def _artifact_path(self, package_hash: str) -> Path:
        return self._safe(ARTIFACTS_DIRNAME, f"{package_hash}.vchar")

    def _record_path(self, character_id: str, release_id: str) -> Path:
        return self._safe(RELEASES_DIRNAME, character_id, f"{release_id}.json")

    def _current_path(self, character_id: str) -> Path:
        return self._safe(CURRENT_DIRNAME, f"{character_id}.json")

    def _history_dir(self, character_id: str) -> Path:
        return self._safe(HISTORY_DIRNAME, character_id)

    def _now(self) -> str:
        try:
            return format_decided_at(self._clock())
        except CharacterAuthoringError as exc:
            raise ReleaseInputError(f"release store clock is invalid: {exc}") from exc

    @contextmanager
    def _scratch(self) -> Iterator[Path]:
        base = self._safe(SCRATCH_DIRNAME)
        base.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="work-", dir=base))
        try:
            yield directory
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    # -- artifact verification (shared by source and durable checks) ----------------

    def _verify_archive(
        self,
        path: Path,
        *,
        expected_sha256: str,
        expected_length: int,
        package_hash: str,
        character_id: str,
        release_id: str,
        aggregate_hash: str,
        acceptance_record_hash: str,
        error: type[CharacterReleaseStoreError],
        label: str,
    ) -> None:
        try:
            status = path.lstat()
        except FileNotFoundError as exc:
            raise error(f"{label} does not exist") from exc
        except OSError as exc:
            raise error(f"{label} cannot be inspected: {exc}") from exc
        if _is_link(status) or not stat.S_ISREG(status.st_mode):
            raise error(f"{label} must be a regular non-link file")
        try:
            actual_sha256, actual_length = _hash_file(path)
        except OSError as exc:
            raise error(f"{label} cannot be read: {exc}") from exc
        if actual_length != expected_length:
            raise error(f"{label} size differs from the recorded byte_length")
        if actual_sha256 != expected_sha256:
            raise error(f"{label} SHA-256 differs from the recorded artifact_sha256")
        with self._scratch() as scratch:
            try:
                verified = extract_vchar_v1(
                    path, scratch / "extract", expected_package_hash=package_hash
                )
            except (PackageV1Error, ValueError, OSError) as exc:
                raise error(f"{label} does not verify through VCP: {exc}") from exc
            metadata = verified.metadata
            problems = []
            if verified.package_hash != package_hash:
                problems.append("packageHash")
            if metadata.character_id != character_id:
                problems.append("characterId")
            if metadata.release_id != release_id:
                problems.append("releaseId")
            if metadata.accepted_aggregate_hash != aggregate_hash:
                problems.append("acceptedAggregateHash")
            if metadata.acceptance_record_hash != acceptance_record_hash:
                problems.append("acceptanceRecordHash")
            if problems:
                raise error(f"{label} disagrees with its release on: " + ", ".join(problems))

    # -- publication --------------------------------------------------------------------

    def publish_release(
        self, built: BuiltVcpArtifact, *, authoring_store: CharacterAuthoringStore
    ) -> PublishedRelease:
        """Persist the exact verified artifact and commit one immutable release.

        Never rebuilds anything and never modifies canonical current.
        """

        if not isinstance(built, BuiltVcpArtifact):
            raise ReleaseInputError("built must be a LAB-L3 BuiltVcpArtifact")
        if not isinstance(authoring_store, CharacterAuthoringStore):
            raise ReleaseInputError("authoring_store must be a CharacterAuthoringStore")
        try:
            _character_id(built.character_id)
            validate_release_id(built.release_id)
            self._require_publishable(built, authoring_store)  # 2
            self._verify_source_artifact(built)  # 3
            existing = self._existing_for_publication(built)  # 4
            if existing is not None:
                # OD-LAB-L4-DURABILITY-01: once a record exists its artifact is
                # durable published state. Verify it; never restore or recopy it.
                return PublishedRelease(
                    existing, self._verify_committed_artifact(existing), False
                )
            artifact_path = self._persist_artifact(built)  # 5 + 6
            record = self._record_from_built(built, self._now())
            stored, created = self._commit_record(record)  # 7: the commit point
            return PublishedRelease(stored, artifact_path, created)
        except CharacterReleaseStoreError:
            raise
        except OSError as exc:
            raise ReleaseStorageError(f"release storage failed: {exc}") from exc

    @staticmethod
    def _record_from_built(built: BuiltVcpArtifact, published_at: str) -> ReleaseRecord:
        approval = built.approval
        return ReleaseRecord(
            character_id=built.character_id,
            release_id=built.release_id,
            package_hash=built.package_hash,
            artifact_sha256=built.artifact_sha256,
            byte_length=built.byte_length,
            source=built.source,
            aggregate_candidate_id=built.aggregate_candidate_id,
            aggregate_hash=built.aggregate_hash,
            acceptance_record_hash=built.acceptance_record_hash,
            approval=ReleaseApproval(
                decision=approval.decision,
                decided_by=approval.decided_by,
                decided_at=approval.decided_at,
            ),
            published_at=published_at,
        )

    def _require_publishable(
        self, built: BuiltVcpArtifact, authoring_store: CharacterAuthoringStore
    ) -> None:
        source = built.source
        coordinate = (
            source.source_character_id, source.source_version_id, source.source_revision_id
        )
        if source.source_character_id != built.character_id:
            raise ReleasePublishabilityError("artifact source is not the release character")
        try:
            pointer = authoring_store.read_version_pointer(coordinate[0], coordinate[1])
            record = authoring_store.load_revision(*coordinate)
            evidence = authoring_store.load_approval_evidence(*coordinate)
        except CharacterAuthoringNotFoundError as exc:
            raise ReleasePublishabilityError(
                f"source is not publishable: {exc}; historical approvals without "
                "LAB-L1 evidence cannot be published"
            ) from exc
        except CharacterAuthoringError as exc:
            raise ReleasePublishabilityError(f"source failed integrity checks: {exc}") from exc
        if pointer.lifecycle_state is not LifecycleState.APPROVED_AS_CANON:
            raise ReleasePublishabilityError(
                f"version is {pointer.lifecycle_state.value}, not APPROVED_AS_CANON"
            )
        if pointer.selected_revision_id != source.source_revision_id:
            raise ReleasePublishabilityError("artifact revision is not the selected revision")
        if record.snapshot_hash != source.source_snapshot_hash:
            raise ReleasePublishabilityError("artifact snapshot_hash differs from the revision")
        if evidence.snapshot_hash != source.source_snapshot_hash or evidence != built.approval:
            raise ReleasePublishabilityError(
                "approval evidence does not match the artifact's approval lineage"
            )
        if built.approval.decision != APPROVAL_DECISION_HUMAN_APPROVED:
            raise ReleasePublishabilityError("approval decision is not HUMAN_APPROVED")

    def _verify_source_artifact(self, built: BuiltVcpArtifact) -> None:
        self._verify_archive(
            Path(built.artifact_path),
            expected_sha256=built.artifact_sha256,
            expected_length=built.byte_length,
            package_hash=built.package_hash,
            character_id=built.character_id,
            release_id=built.release_id,
            aggregate_hash=built.aggregate_hash,
            acceptance_record_hash=built.acceptance_record_hash,
            error=ReleaseSourceArtifactError,
            label="source artifact",
        )

    def _casefold_conflict(self, character_id: str, release_id: str) -> None:
        directory = self._safe(RELEASES_DIRNAME, character_id)
        if not directory.is_dir():
            return
        for entry in directory.iterdir():
            if entry.suffix == ".json":
                other = entry.stem
                if other != release_id and other.casefold() == release_id.casefold():
                    raise ReleaseRecordConflictError(
                        f"release_id {release_id!r} differs from existing {other!r} "
                        "only by letter case"
                    )

    def _existing_for_publication(self, built: BuiltVcpArtifact) -> Optional[ReleaseRecord]:
        self._casefold_conflict(built.character_id, built.release_id)
        path = self._record_path(built.character_id, built.release_id)
        if not os.path.lexists(path):
            return None
        return self._reconcile(path, built)

    def _reconcile(self, path: Path, built: BuiltVcpArtifact) -> ReleaseRecord:
        try:
            existing = self._read_record(path)
        except ReleaseNotFoundError as exc:
            raise ReleaseRecordCorruptError("release record vanished during publication") from exc
        if existing.character_id != built.character_id or existing.release_id != built.release_id:
            raise ReleaseRecordConflictError(
                "existing record path identity differs from the requested release"
            )
        if existing.package_hash != built.package_hash:
            raise ReleaseIdHashCollisionError(
                f"release {built.release_id!r} of {built.character_id!r} already "
                "exists with a different packageHash"
            )
        probe = self._record_from_built(built, existing.published_at)
        if probe != existing:
            raise ReleaseRecordConflictError(
                "existing release has the same packageHash but conflicting immutable fields"
            )
        return existing

    def _verify_committed_artifact(self, record: ReleaseRecord) -> Path:
        """Verify the durable artifact bound by an existing record; never repair it."""

        path = self._artifact_path(record.package_hash)
        self._verify_archive(
            path,
            expected_sha256=record.artifact_sha256,
            expected_length=record.byte_length,
            package_hash=record.package_hash,
            character_id=record.character_id,
            release_id=record.release_id,
            aggregate_hash=record.aggregate_hash,
            acceptance_record_hash=record.acceptance_record_hash,
            error=DurableArtifactCorruptError,
            label="durable artifact of a committed release",
        )
        return path

    def _persist_artifact(self, built: BuiltVcpArtifact) -> Path:
        """Persist or reuse the artifact of a release that has NO record yet.

        An existing exact artifact here is a pre-commit orphan and may be reused.
        """

        target = self._artifact_path(built.package_hash)
        if not os.path.lexists(target):
            scratch = self._safe(SCRATCH_DIRNAME)
            target.parent.mkdir(parents=True, exist_ok=True)
            scratch.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(dir=str(scratch), prefix=".artifact-", suffix=".tmp")
            os.close(fd)
            temp = Path(temp_name)
            try:
                sha256, length = _stream_copy(Path(built.artifact_path), temp)
                if sha256 != built.artifact_sha256 or length != built.byte_length:
                    raise ReleaseSourceArtifactError(
                        "source artifact changed while being copied into the store"
                    )
                try:
                    os.link(temp, target)  # exclusive, no-clobber publish
                except FileExistsError:
                    pass  # a concurrent exact publisher won; verified below
            finally:
                try:
                    temp.unlink()
                except OSError:
                    pass
        self._verify_archive(  # existing, reused, or freshly stored: always re-verified
            target,
            expected_sha256=built.artifact_sha256,
            expected_length=built.byte_length,
            package_hash=built.package_hash,
            character_id=built.character_id,
            release_id=built.release_id,
            aggregate_hash=built.aggregate_hash,
            acceptance_record_hash=built.acceptance_record_hash,
            error=DurableArtifactCorruptError,
            label="durable artifact",
        )
        return target

    def _commit_record(self, record: ReleaseRecord) -> tuple[ReleaseRecord, bool]:
        path = self._record_path(record.character_id, record.release_id)
        if _write_once_json(path, record.to_dict()):
            return record, True
        existing = self._read_record(path)
        if existing.character_id != record.character_id or existing.release_id != record.release_id:
            raise ReleaseRecordConflictError("existing record path identity differs")
        if existing.package_hash != record.package_hash:
            raise ReleaseIdHashCollisionError(
                f"release {record.release_id!r} of {record.character_id!r} was "
                "published concurrently with a different packageHash"
            )
        if replace(record, published_at=existing.published_at) != existing:
            raise ReleaseRecordConflictError(
                "existing release has the same packageHash but conflicting immutable fields"
            )
        return existing, False

    # -- reading -----------------------------------------------------------------------

    def _read_record(self, path: Path) -> ReleaseRecord:
        try:
            status = path.lstat()
        except FileNotFoundError as exc:
            raise ReleaseNotFoundError("release record does not exist") from exc
        if _is_link(status) or not stat.S_ISREG(status.st_mode):
            raise ReleaseRecordCorruptError("release record must be a regular non-link file")
        raw = path.read_bytes()
        data = _parse_canonical(raw, "release record", ReleaseRecordCorruptError)
        return ReleaseRecord.from_dict(data)

    def load_release_record(self, character_id: str, release_id: str) -> ReleaseRecord:
        """Cheap read: schema, canonical form and path identity. Not artifact-verified."""

        character_id = _character_id(character_id)
        release_id = validate_release_id(release_id)
        try:
            record = self._read_record(self._record_path(character_id, release_id))
        except OSError as exc:
            raise ReleaseStorageError(f"release record cannot be read: {exc}") from exc
        if record.character_id != character_id or record.release_id != release_id:
            raise ReleaseRecordCorruptError("release record identity does not match its path")
        return record

    def verify_release(self, character_id: str, release_id: str) -> VerifiedRelease:
        """Full read: the record plus its stored artifact re-verified through VCP."""

        record = self.load_release_record(character_id, release_id)
        path = self._artifact_path(record.package_hash)
        try:
            self._verify_archive(
                path,
                expected_sha256=record.artifact_sha256,
                expected_length=record.byte_length,
                package_hash=record.package_hash,
                character_id=record.character_id,
                release_id=record.release_id,
                aggregate_hash=record.aggregate_hash,
                acceptance_record_hash=record.acceptance_record_hash,
                error=DurableArtifactCorruptError,
                label="stored artifact",
            )
        except OSError as exc:
            raise ReleaseStorageError(f"stored artifact cannot be verified: {exc}") from exc
        return VerifiedRelease(record, path)

    def load_release(self, character_id: str, release_id: str) -> ReleaseRecord:
        """The verified record: equivalent to ``verify_release(...).record``."""

        return self.verify_release(character_id, release_id).record

    def list_release_ids(self, character_id: str) -> tuple[str, ...]:
        character_id = _character_id(character_id)
        directory = self._safe(RELEASES_DIRNAME, character_id)
        if not directory.is_dir():
            return ()
        return tuple(sorted(e.stem for e in directory.iterdir() if e.suffix == ".json"))

    # -- canonical current ---------------------------------------------------------------

    def _read_designation_state(
        self, character_id: str
    ) -> tuple[Optional[CanonicalCurrent], tuple[DesignationEntry, ...], Optional[DesignationEntry]]:
        """Return (committed current, committed history, pending claim) or fail closed."""

        history_dir = self._history_dir(character_id)
        entries: list[DesignationEntry] = []
        if history_dir.is_dir():
            for item in sorted(history_dir.iterdir()):
                if item.suffix == ".tmp":
                    continue
                match = _HISTORY_NAME_RE.fullmatch(item.name)
                if match is None:
                    raise CurrentDesignationError(f"unexpected history file {item.name!r}")
                data = _parse_canonical(item.read_bytes(), "designation entry", CurrentDesignationError)
                entry = DesignationEntry.from_dict(data)
                if entry.generation != int(match.group(1)) or entry.character_id != character_id:
                    raise CurrentDesignationError("designation entry identity does not match its path")
                entries.append(entry)
        for index, entry in enumerate(entries, start=1):
            if entry.generation != index:
                raise CurrentDesignationError("designation history has a gap")
            if index > 1:
                previous = entries[index - 2]
                if (entry.from_release_id, entry.from_package_hash) != (
                    previous.to_release_id, previous.to_package_hash
                ):
                    raise CurrentDesignationError("designation history chain is broken")

        pointer_path = self._current_path(character_id)
        current: Optional[CanonicalCurrent] = None
        if os.path.lexists(pointer_path):
            data = _parse_canonical(pointer_path.read_bytes(), "current designation", CurrentDesignationError)
            current = CanonicalCurrent.from_dict(data)
            if current.character_id != character_id:
                raise CurrentDesignationError("current designation identity does not match its path")
            if current.generation > len(entries):
                raise CurrentDesignationError("current designation is ahead of its history")
            claimed = entries[current.generation - 1]
            if (claimed.to_release_id, claimed.to_package_hash) != (
                current.release_id, current.package_hash
            ):
                raise CurrentDesignationError("current designation disagrees with its history entry")
        committed = current.generation if current else 0
        if len(entries) - committed > 1:
            raise CurrentDesignationError("more than one pending designation claim")
        pending = entries[committed] if len(entries) == committed + 1 else None
        return current, tuple(entries[:committed]), pending

    def get_canonical_current(self, character_id: str) -> Optional[CanonicalCurrent]:
        """The committed current, cross-checked against history and its release record."""

        character_id = _character_id(character_id)
        try:
            current, _history, _pending = self._read_designation_state(character_id)
            if current is not None:
                record = self.load_release_record(character_id, current.release_id)
                if record.package_hash != current.package_hash:
                    raise CurrentDesignationError(
                        "current designation package_hash differs from its release record"
                    )
        except ReleaseNotFoundError as exc:
            raise CurrentDesignationError(
                "current designation points to a release that does not exist"
            ) from exc
        except OSError as exc:
            raise ReleaseStorageError(f"current designation cannot be read: {exc}") from exc
        return current

    def read_designation_history(self, character_id: str) -> tuple[DesignationEntry, ...]:
        """Committed history only (entries up to the current generation)."""

        character_id = _character_id(character_id)
        try:
            return self._read_designation_state(character_id)[1]
        except OSError as exc:
            raise ReleaseStorageError(f"designation history cannot be read: {exc}") from exc

    def pending_designation(self, character_id: str) -> Optional[DesignationEntry]:
        """A claimed but uncommitted designation left by an interrupted change."""

        character_id = _character_id(character_id)
        try:
            return self._read_designation_state(character_id)[2]
        except OSError as exc:
            raise ReleaseStorageError(f"designation state cannot be read: {exc}") from exc

    def _write_pointer(self, character_id: str, entry: DesignationEntry) -> CanonicalCurrent:
        current = CanonicalCurrent(
            character_id=character_id,
            release_id=entry.to_release_id,
            package_hash=entry.to_package_hash,
            generation=entry.generation,
        )
        _atomic_replace_json(self._current_path(character_id), current.to_dict())
        return current

    def _complete_pending(
        self, character_id: str, current: Optional[CanonicalCurrent], pending: DesignationEntry
    ) -> CanonicalCurrent:
        verified = self.verify_release(character_id, pending.to_release_id)
        if verified.record.package_hash != pending.to_package_hash:
            raise CurrentDesignationError(
                "pending designation no longer matches its release; it cannot complete"
            )
        # Runs under the per-character designation lock: the state read by the
        # caller cannot have changed, so the pointer is written exactly once,
        # in generation order.
        if (current.generation if current else 0) != pending.generation - 1:
            raise CurrentDesignationError("pending designation is out of order")
        return self._write_pointer(character_id, pending)

    def _designation_lock(self, character_id: str) -> _DesignationLock:
        """The per-character cross-process writer lock (different characters are independent)."""

        return _DesignationLock(self._safe(LOCKS_DIRNAME, f"{character_id}.lock"))

    def _require_committed(
        self, character_id: str, expected: CanonicalCurrent
    ) -> CanonicalCurrent:
        """Final consistency check: pointer, history and no pending claim all agree."""

        current, _history, pending = self._read_designation_state(character_id)
        if (
            current != expected
            or pending is not None
            or current is None
        ):
            raise CurrentDesignationError(
                "designation did not reach a consistent committed state"
            )
        return current

    def set_canonical_current(self, character_id: str, release_id: str) -> CanonicalCurrent:
        """Explicitly designate ``release_id`` as current (also the rollback path).

        Every mutation for one character is serialized by an exclusive OS-backed
        cross-process lock held across state read, pending roll-forward, target
        verification, no-op determination, claim, pointer replace, and the final
        consistency check, so no older writer can write the pointer after a newer
        writer has returned. The target is fully re-verified. An exact no-op is
        idempotent and writes no history. Releases are never modified.
        """

        character_id = _character_id(character_id)
        release_id = validate_release_id(release_id)
        try:
            with self._designation_lock(character_id):
                verified = self.verify_release(character_id, release_id)
                current, _history, pending = self._read_designation_state(character_id)
                if pending is not None:
                    current = self._complete_pending(character_id, current, pending)
                if (
                    current is not None
                    and current.release_id == release_id
                    and current.package_hash == verified.record.package_hash
                ):
                    return self._require_committed(character_id, current)
                entry = DesignationEntry(
                    generation=(current.generation if current else 0) + 1,
                    character_id=character_id,
                    from_release_id=current.release_id if current else None,
                    from_package_hash=current.package_hash if current else None,
                    to_release_id=release_id,
                    to_package_hash=verified.record.package_hash,
                    designated_at=self._now(),
                )
                history = self._history_dir(character_id)
                claimed = _write_once_json(
                    history / f"{entry.generation:08d}.json", entry.to_dict()
                )
                if not claimed:
                    raise CurrentDesignationError(
                        "history generation already exists despite the designation lock"
                    )
                return self._require_committed(
                    character_id, self._write_pointer(character_id, entry)
                )
        except CharacterReleaseStoreError:
            raise
        except OSError as exc:
            raise CurrentDesignationError(f"current designation failed: {exc}") from exc

    # -- export --------------------------------------------------------------------------

    def export_release(
        self, character_id: str, release_id: str, destination: Path | str
    ) -> ExportedRelease:
        """Copy the exact stored ``.vchar`` to a new destination path.

        Reads only the store, never Authoring, and never rebuilds. Failure leaves
        publication, current, records and the stored artifact untouched.
        """

        target = Path(destination)
        if not target.is_absolute() or ".." in target.parts or target.name in ("", "."):
            raise ReleaseExportError("destination must be an absolute file path without '..'")
        if not target.parent.is_dir():
            raise ReleaseExportError("destination parent must be an existing directory")
        if os.path.lexists(target):
            raise ReleaseExportError("destination already exists; export never overwrites")
        lexical_target = os.path.normcase(os.path.abspath(target))
        lexical_root = os.path.normcase(str(self._root))
        inside = lexical_target == lexical_root or lexical_target.startswith(
            lexical_root.rstrip("\\/") + os.sep
        )
        if not inside:
            try:
                target.resolve(strict=False).relative_to(self._root)
                inside = True
            except (ValueError, OSError):
                pass
        if inside:
            raise ReleaseExportError("destination must be outside the release store")

        verified = self.verify_release(character_id, release_id)
        record = verified.record
        try:
            fd, temp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".export-", suffix=".tmp")
        except OSError as exc:
            raise ReleaseExportError(f"export temp file cannot be created: {exc}") from exc
        os.close(fd)
        temp = Path(temp_name)
        try:
            try:
                sha256, length = _stream_copy(verified.artifact_path, temp)
                if sha256 != record.artifact_sha256 or length != record.byte_length:
                    raise ReleaseExportError("copied bytes differ from the stored artifact")
                try:
                    os.link(temp, target)
                except FileExistsError as exc:
                    raise ReleaseExportError("destination already exists; export never overwrites") from exc
            except OSError as exc:
                raise ReleaseExportError(f"export failed: {exc}") from exc
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
        return ExportedRelease(
            path=target,
            character_id=record.character_id,
            release_id=record.release_id,
            package_hash=record.package_hash,
            artifact_sha256=record.artifact_sha256,
            byte_length=record.byte_length,
        )


__all__ = [
    "CanonicalCurrent",
    "CharacterReleaseStore",
    "CharacterReleaseStoreError",
    "CurrentDesignationError",
    "DesignationEntry",
    "DurableArtifactCorruptError",
    "ExportedRelease",
    "PublishedRelease",
    "ReleaseApproval",
    "ReleaseExportError",
    "ReleaseIdHashCollisionError",
    "ReleaseInputError",
    "ReleaseNotFoundError",
    "ReleasePublishabilityError",
    "ReleaseRecord",
    "ReleaseRecordConflictError",
    "ReleaseRecordCorruptError",
    "ReleaseSourceArtifactError",
    "ReleaseStorageError",
    "VerifiedRelease",
    "validate_release_id",
]
