#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion image-generation JOB boundary (async foundation).

This slice does NOT create a real visual pipeline. It defines:

- :class:`CompanionImageGenerator` -- a narrow protocol a future real pipeline
  (the parallel Narrative visual work) can implement later;
- :class:`FakeImageGenerator` -- deterministic, offline, step-driven; writes a
  tiny placeholder SVG so the UI path is provable;
- :class:`UnavailableImageGenerator` -- the safe default until a real adapter is
  configured (every job fails closed with ``generator_unavailable``);
- :class:`ImageJobService` -- durable job metadata in a small additive JSON file
  under the Companion data root (NOT a new database).

Hard invariant: creating / advancing an image job NEVER touches conversation
history and NEVER blocks ``CompanionService.send_message``. Jobs advance only on
explicit ``tick`` (called by the poll/list transport methods), exactly like a
client polling a real async service. No generated image is ever auto-deleted.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

STATE_QUEUED = "QUEUED"
STATE_GENERATING = "GENERATING"
STATE_READY = "READY"
STATE_FAILED = "FAILED"
STATE_CANCELLED = "CANCELLED"
TERMINAL_STATES = frozenset({STATE_READY, STATE_FAILED, STATE_CANCELLED})

KIND_CUSTOM = "custom"       # "Создать изображение..." -- user description
KIND_CONTEXT = "context"     # "Кадр по контексту" -- derived from scene + excerpt

_JOBS_FILENAME = "companion_image_jobs.json"
_MAX_REQUEST_ID_LENGTH = 128
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")

_EXECUTION_CLAIMED = "CLAIMED"
_EXECUTION_INTERRUPTED = "generation_interrupted_ambiguous"

# Services that point at the same registry share one in-process persistence
# lock. Provider work is deliberately performed outside this lock.
_REGISTRY_LOCKS_GUARD = threading.Lock()
_REGISTRY_LOCKS: Dict[str, Any] = {}


def _registry_lock(path: Path):
    key = os.path.normcase(str(path.resolve()))
    with _REGISTRY_LOCKS_GUARD:
        return _REGISTRY_LOCKS.setdefault(key, threading.RLock())

PINNED_GENERATION_SPEC_SCHEMA_VERSION = "companion_pinned_generation_spec/0.1"
_MIN_PINNED_REFERENCES = 2
_MAX_PINNED_REFERENCES = 4
_PINNED_FILE_TYPES = frozenset({"PNG", "JPEG", "WEBP"})


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _required_sha256(value: Any, field: str) -> str:
    text = _required_text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError(f"{field} must be a sha256 hex digest")
    return text


@dataclass(frozen=True)
class PinnedReferenceSpec:
    """Exact non-secret identity-reference metadata captured for one job."""

    asset_id: str
    roles: Tuple[str, ...]
    relative_path: str
    sha256: str
    file_type: str
    byte_length: int
    source_semantic_key: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", _required_text(self.asset_id, "assetId"))
        roles = tuple(_required_text(role, "reference role") for role in self.roles)
        if not roles:
            raise ValueError("a pinned reference must have at least one role")
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "relative_path", _required_text(self.relative_path, "relativePath"))
        object.__setattr__(self, "sha256", _required_sha256(self.sha256, "reference sha256"))
        file_type = _required_text(self.file_type, "fileType")
        if file_type not in _PINNED_FILE_TYPES:
            raise ValueError(f"unsupported pinned reference fileType {file_type!r}")
        object.__setattr__(self, "file_type", file_type)
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length <= 0:
            raise ValueError("byteLength must be a positive integer")
        object.__setattr__(self, "source_semantic_key", _optional_text(self.source_semantic_key))

    @classmethod
    def from_reference_entry(cls, entry) -> "PinnedReferenceSpec":
        return cls(
            asset_id=entry.asset_id,
            roles=tuple(entry.roles),
            relative_path=entry.relative_path,
            sha256=entry.sha256,
            file_type=entry.image_format,
            byte_length=entry.byte_length,
            source_semantic_key=entry.source_semantic_key,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "PinnedReferenceSpec":
        if not isinstance(data, dict):
            raise ValueError("pinned reference must be an object")
        roles = data.get("roles")
        if not isinstance(roles, (list, tuple)):
            raise ValueError("pinned reference roles must be an array")
        return cls(
            asset_id=data.get("assetId"),
            roles=tuple(roles),
            relative_path=data.get("relativePath"),
            sha256=data.get("sha256"),
            file_type=data.get("fileType"),
            byte_length=data.get("byteLength"),
            source_semantic_key=data.get("sourceSemanticKey"),
        )

    def to_dict(self) -> dict:
        out = {
            "assetId": self.asset_id,
            "roles": list(self.roles),
            "relativePath": self.relative_path,
            "sha256": self.sha256,
            "fileType": self.file_type,
            "byteLength": self.byte_length,
        }
        if self.source_semantic_key is not None:
            out["sourceSemanticKey"] = self.source_semantic_key
        return out


@dataclass(frozen=True)
class PinnedGenerationSpec:
    """Immutable identity/provider inputs selected before a job becomes QUEUED."""

    schema_version: str
    character_id: str
    snapshot_version: str
    snapshot_hash: str
    source_canon_status: str
    source_canon_content_hash: str
    source_canon_source_hash: Optional[str]
    source_canon_character_id: Optional[str]
    references: Tuple[PinnedReferenceSpec, ...]
    provider_id: str
    model_id: str
    base_url: str
    size: str
    quality: str

    def __post_init__(self) -> None:
        if self.schema_version != PINNED_GENERATION_SPEC_SCHEMA_VERSION:
            raise ValueError(f"unexpected generation spec schema {self.schema_version!r}")
        object.__setattr__(self, "character_id", _required_text(self.character_id, "characterId"))
        object.__setattr__(self, "snapshot_version", _required_text(self.snapshot_version, "snapshotVersion"))
        object.__setattr__(self, "snapshot_hash", _required_sha256(self.snapshot_hash, "snapshotHash"))
        source_status = _required_text(self.source_canon_status, "sourceCanon.status")
        if source_status != "APPROVED_AS_CANON":
            raise ValueError("generation spec source Canon is not approved for production")
        object.__setattr__(self, "source_canon_status", source_status)
        object.__setattr__(
            self, "source_canon_content_hash",
            _required_sha256(self.source_canon_content_hash, "sourceCanon.contentHash"),
        )
        object.__setattr__(self, "source_canon_source_hash", _optional_text(self.source_canon_source_hash))
        object.__setattr__(self, "source_canon_character_id", _optional_text(self.source_canon_character_id))
        refs = tuple(self.references)
        if not (_MIN_PINNED_REFERENCES <= len(refs) <= _MAX_PINNED_REFERENCES):
            raise ValueError(
                f"generation spec must pin {_MIN_PINNED_REFERENCES}..{_MAX_PINNED_REFERENCES} references"
            )
        if len({ref.asset_id for ref in refs}) != len(refs):
            raise ValueError("generation spec contains duplicate reference assetId")
        object.__setattr__(self, "references", refs)
        object.__setattr__(self, "provider_id", _required_text(self.provider_id, "providerId"))
        object.__setattr__(self, "model_id", _required_text(self.model_id, "modelId"))
        object.__setattr__(self, "base_url", _required_text(self.base_url, "baseUrl"))
        object.__setattr__(self, "size", _required_text(self.size, "size"))
        object.__setattr__(self, "quality", _required_text(self.quality, "quality"))

    @classmethod
    def from_inputs(
        cls, *, snapshot, reference_bundle, provider_id: str, model_id: str,
        base_url: str, size: str, quality: str,
    ) -> "PinnedGenerationSpec":
        source = snapshot.source_canon
        return cls(
            schema_version=PINNED_GENERATION_SPEC_SCHEMA_VERSION,
            character_id=snapshot.character_id,
            snapshot_version=snapshot.snapshot_version,
            snapshot_hash=snapshot.snapshot_hash or snapshot.compute_hash(),
            source_canon_status=source.get("status"),
            source_canon_content_hash=source.get("contentHash"),
            source_canon_source_hash=source.get("sourceHash"),
            source_canon_character_id=source.get("sourceCharacterId"),
            references=tuple(
                PinnedReferenceSpec.from_reference_entry(ref)
                for ref in reference_bundle.references
            ),
            provider_id=provider_id,
            model_id=model_id,
            base_url=base_url,
            size=size,
            quality=quality,
        )

    @classmethod
    def from_dict(cls, data: Any) -> "PinnedGenerationSpec":
        if not isinstance(data, dict):
            raise ValueError("generation spec must be an object")
        identity = data.get("identity")
        provider = data.get("provider")
        parameters = data.get("parameters")
        if not all(isinstance(part, dict) for part in (identity, provider, parameters)):
            raise ValueError("generation spec identity/provider/parameters must be objects")
        source = identity.get("sourceCanon")
        if not isinstance(source, dict):
            raise ValueError("generation spec sourceCanon must be an object")
        references = data.get("references")
        if not isinstance(references, (list, tuple)):
            raise ValueError("generation spec references must be an array")
        return cls(
            schema_version=data.get("schemaVersion"),
            character_id=identity.get("characterId"),
            snapshot_version=identity.get("snapshotVersion"),
            snapshot_hash=identity.get("snapshotHash"),
            source_canon_status=source.get("status"),
            source_canon_content_hash=source.get("contentHash"),
            source_canon_source_hash=source.get("sourceHash"),
            source_canon_character_id=source.get("sourceCharacterId"),
            references=tuple(PinnedReferenceSpec.from_dict(ref) for ref in references),
            provider_id=provider.get("providerId"),
            model_id=provider.get("modelId"),
            base_url=provider.get("baseUrl"),
            size=parameters.get("size"),
            quality=parameters.get("quality"),
        )

    def to_dict(self) -> dict:
        source = {
            "status": self.source_canon_status,
            "contentHash": self.source_canon_content_hash,
        }
        if self.source_canon_source_hash is not None:
            source["sourceHash"] = self.source_canon_source_hash
        if self.source_canon_character_id is not None:
            source["sourceCharacterId"] = self.source_canon_character_id
        return {
            "schemaVersion": self.schema_version,
            "identity": {
                "characterId": self.character_id,
                "snapshotVersion": self.snapshot_version,
                "snapshotHash": self.snapshot_hash,
                "sourceCanon": source,
            },
            "references": [ref.to_dict() for ref in self.references],
            "provider": {
                "providerId": self.provider_id,
                "modelId": self.model_id,
                "baseUrl": self.base_url,
            },
            "parameters": {"size": self.size, "quality": self.quality},
        }


class CompanionImageError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ImageJob:
    job_id: str
    session_id: str
    character_id: str
    kind: str
    state: str
    created_at: str
    updated_at: str
    request_id: Optional[str] = None
    prompt: Optional[str] = None
    context: Optional[dict] = None
    result_ref: Optional[str] = None
    error: Optional[str] = None
    # Internal V1B execution-claim bookkeeping. Deliberately a SIBLING of
    # `context`, never nested inside it: `context` is the exact pinned-at-
    # creation input the generator reads (V1A), and must stay byte-identical
    # across every advance() call. The claim marker is service-internal
    # metadata the generator never sees or touches.
    execution: Optional[dict] = None

    @classmethod
    def from_row(cls, row: dict) -> "ImageJob":
        return cls(
            job_id=row["job_id"],
            session_id=row["session_id"],
            character_id=row.get("character_id", ""),
            kind=row.get("kind", KIND_CUSTOM),
            state=row.get("state", STATE_QUEUED),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", row.get("created_at", "")),
            request_id=row.get("request_id"),
            prompt=row.get("prompt"),
            context=row.get("context"),
            result_ref=row.get("result_ref"),
            error=row.get("error"),
            execution=row.get("execution"),
        )

    def to_row(self) -> dict:
        return {
            "job_id": self.job_id,
            "session_id": self.session_id,
            "character_id": self.character_id,
            "kind": self.kind,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request_id": self.request_id,
            "prompt": self.prompt,
            "context": self.context,
            "result_ref": self.result_ref,
            "error": self.error,
            "execution": self.execution,
        }


class CompanionImageGenerator(Protocol):
    """The seam a real visual pipeline implements later.

    ``advance`` moves ONE non-terminal job forward by at most one step and
    returns the updated job. It must be non-blocking / fast and must never
    perform an external network call in this slice's implementations.
    """

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:  # pragma: no cover - protocol
        ...

    def prepare_generation_spec(self, *, character_id: str) -> PinnedGenerationSpec:  # pragma: no cover
        ...


class UnavailableImageGenerator:
    """Safe default: no real pipeline is bound, so every job fails closed."""

    name = "unavailable"

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        return _with(job, state=STATE_FAILED, error="generator_unavailable")


_PLACEHOLDER_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='512' height='288'>"
    "<rect width='100%' height='100%' fill='#1b1d22'/>"
    "<text x='50%' y='50%' fill='#8a8f98' font-family='sans-serif' font-size='18' "
    "text-anchor='middle' dominant-baseline='middle'>{label}</text></svg>"
)


class FakeImageGenerator:
    """Deterministic dev/test generator. QUEUED -> GENERATING -> READY, writing a
    tiny placeholder SVG. No Pillow, no network."""

    name = "fake"

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:
        if job.state == STATE_QUEUED:
            return _with(job, state=STATE_GENERATING)
        if job.state == STATE_GENERATING:
            images_dir.mkdir(parents=True, exist_ok=True)
            path = images_dir / f"{job.job_id}.svg"
            label = "context frame" if job.kind == KIND_CONTEXT else "generated image"
            path.write_text(_PLACEHOLDER_SVG.format(label=label), encoding="utf-8")
            return _with(job, state=STATE_READY, result_ref=f"images/{job.job_id}.svg")
        return job


def _with(job: ImageJob, **changes) -> ImageJob:
    row = job.to_row()
    row.update(changes)
    row["updated_at"] = _now_iso()
    return ImageJob.from_row(row)


class ImageJobService:
    """Durable job metadata + step-driven advancement. All persistence is one
    small additive JSON file; no SQLite, no second history store."""

    def __init__(self, data_root: Path, generator: Optional[CompanionImageGenerator] = None) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._generator = generator or UnavailableImageGenerator()
        self._persistence_lock = _registry_lock(self._path())
        self._owned_claims: set[str] = set()
        self._owned_claims_lock = threading.Lock()

    @property
    def generator_name(self) -> str:
        return getattr(self._generator, "name", "custom")

    def _path(self) -> Path:
        return self._data_root / _JOBS_FILENAME

    def _images_dir(self) -> Path:
        return self._data_root / "images"

    def _load(self) -> List[dict]:
        path = self._path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

    def _save(self, rows: List[dict]) -> None:
        path = self._path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def prepare_generation_spec(self, *, character_id: str) -> PinnedGenerationSpec:
        prepare = getattr(self._generator, "prepare_generation_spec", None)
        if not callable(prepare):
            raise CompanionImageError(
                "generation_spec_unavailable",
                "the configured image generator cannot pin generation inputs",
            )
        try:
            spec = prepare(character_id=character_id)
            return spec if isinstance(spec, PinnedGenerationSpec) else PinnedGenerationSpec.from_dict(spec)
        except CompanionImageError:
            raise
        except Exception as exc:  # bounded product error; no paths/secrets cross this boundary
            raise CompanionImageError(
                str(getattr(exc, "code", "generation_spec_invalid")),
                "image generation inputs could not be pinned",
            ) from exc

    # ------------------------------------------------------------ create
    def create_job(
        self,
        *,
        session_id: str,
        character_id: str,
        kind: str,
        request_id: Optional[str] = None,
        prompt: Optional[str] = None,
        context: Optional[dict] = None,
        generation_spec: Optional[PinnedGenerationSpec | dict] = None,
        generation_spec_factory: Optional[Callable[[], PinnedGenerationSpec | dict]] = None,
    ) -> ImageJob:
        if kind not in (KIND_CUSTOM, KIND_CONTEXT):
            raise CompanionImageError("invalid_request", f"unknown image kind {kind!r}")
        if kind == KIND_CUSTOM and not (isinstance(prompt, str) and prompt.strip()):
            raise CompanionImageError("invalid_request", "a description is required for a custom image")
        normalized_prompt = prompt.strip() if isinstance(prompt, str) else None
        normalized_request_id = self._validate_request_id(request_id)

        # Request replay, active-job exclusion, input pinning, and the append are
        # one critical section. This makes concurrent POSTs deterministic.
        with self._persistence_lock:
            rows = self._load()
            if normalized_request_id is not None:
                for row in rows:
                    if row.get("request_id") != normalized_request_id:
                        continue
                    existing = ImageJob.from_row(row)
                    if (
                        existing.session_id != session_id
                        or existing.character_id != character_id
                        or existing.kind != kind
                        or (kind == KIND_CUSTOM and existing.prompt != normalized_prompt)
                    ):
                        raise CompanionImageError(
                            "image_job_idempotency_conflict",
                            "requestId was already used for different image-job inputs",
                        )
                    return existing

            for row in rows:
                existing = ImageJob.from_row(row)
                if (
                    existing.session_id == session_id
                    and existing.character_id == character_id
                    and existing.state not in TERMINAL_STATES
                ):
                    raise CompanionImageError(
                        "image_job_active_conflict",
                        "an image job is already active for this session and character",
                    )

            if generation_spec is not None and generation_spec_factory is not None:
                raise CompanionImageError(
                    "generation_spec_invalid", "generation specification has multiple sources"
                )
            raw_spec = generation_spec
            if raw_spec is None and generation_spec_factory is not None:
                raw_spec = generation_spec_factory()
            if raw_spec is None:
                raise CompanionImageError(
                    "generation_spec_missing", "a pinned generation specification is required"
                )
            try:
                spec = (
                    raw_spec
                    if isinstance(raw_spec, PinnedGenerationSpec)
                    else PinnedGenerationSpec.from_dict(raw_spec)
                )
            except (TypeError, ValueError) as exc:
                raise CompanionImageError(
                    "generation_spec_invalid", "invalid generation specification"
                ) from exc
            if spec.character_id != character_id:
                raise CompanionImageError(
                    "generation_spec_invalid", "generation specification character mismatch"
                )
            job_context = dict(context or {})
            if "generationSpec" in job_context:
                raise CompanionImageError(
                    "generation_spec_invalid", "reserved job metadata was supplied"
                )
            job_context["generationSpec"] = spec.to_dict()
            now = _now_iso()
            job = ImageJob(
                job_id="img-" + uuid.uuid4().hex,
                session_id=session_id,
                character_id=character_id,
                kind=kind,
                state=STATE_QUEUED,
                created_at=now,
                updated_at=now,
                request_id=normalized_request_id,
                prompt=normalized_prompt,
                context=job_context,
            )
            rows.append(job.to_row())
            self._save(rows)
            return job

    @staticmethod
    def _validate_request_id(request_id: Optional[str]) -> Optional[str]:
        if request_id is None:
            return None
        if not isinstance(request_id, str):
            raise CompanionImageError("invalid_request", "requestId must be a string")
        value = request_id.strip()
        if (
            not value
            or len(value) > _MAX_REQUEST_ID_LENGTH
            or _REQUEST_ID_PATTERN.fullmatch(value) is None
        ):
            raise CompanionImageError("invalid_request", "requestId has an invalid format")
        return value

    # ------------------------------------------------------------ advance
    def tick(self) -> int:
        """Advance every non-terminal job by one step. Returns how many moved.
        Called by the poll/list transport methods -- never by send_message."""
        with self._persistence_lock:
            job_ids = [
                row.get("job_id") for row in self._load()
                if row.get("state") not in TERMINAL_STATES and isinstance(row.get("job_id"), str)
            ]
        return sum(self._advance_one(job_id) for job_id in job_ids)

    def _advance_one(self, job_id: str) -> int:
        claimed_job: Optional[ImageJob] = None
        with self._persistence_lock:
            rows = self._load()
            index = next((i for i, row in enumerate(rows) if row.get("job_id") == job_id), None)
            if index is None:
                return 0
            job = ImageJob.from_row(rows[index])
            if job.state in TERMINAL_STATES:
                return 0

            raw_spec = (job.context or {}).get("generationSpec")
            if raw_spec is None:
                rows[index] = _with(
                    job, state=STATE_FAILED, error="generation_spec_missing"
                ).to_row()
                self._save(rows)
                return 1
            try:
                spec = PinnedGenerationSpec.from_dict(raw_spec)
                if spec.character_id != job.character_id:
                    raise ValueError("generation specification character mismatch")
            except (TypeError, ValueError):
                rows[index] = _with(
                    job, state=STATE_FAILED, error="generation_spec_invalid"
                ).to_row()
                self._save(rows)
                return 1

            if job.state == STATE_QUEUED:
                rows[index] = _with(job, state=STATE_GENERATING).to_row()
                self._save(rows)
                return 1

            execution = job.execution
            if isinstance(execution, dict) and execution.get("state") == _EXECUTION_CLAIMED:
                with self._owned_claims_lock:
                    locally_owned = job_id in self._owned_claims
                if locally_owned:
                    return 0
                rows[index] = _with(
                    job,
                    state=STATE_FAILED,
                    error=_EXECUTION_INTERRUPTED,
                ).to_row()
                self._save(rows)
                return 1

            # Claim bookkeeping lives OUTSIDE `context` -- the generator must
            # see exactly the pinned-at-creation context on every call (V1A).
            claimed_job = _with(
                job,
                execution={"state": _EXECUTION_CLAIMED, "claimedAt": _now_iso()},
            )
            rows[index] = claimed_job.to_row()
            with self._owned_claims_lock:
                self._owned_claims.add(job_id)
            self._save(rows)

        # This is the only provider-capable call. The durable claim is already
        # on disk, and no registry lock is held while it runs.
        try:
            try:
                updated = self._generator.advance(claimed_job, images_dir=self._images_dir())
            except Exception:
                updated = _with(claimed_job, state=STATE_FAILED, error="generation_failed")
            if updated.state not in TERMINAL_STATES:
                updated = _with(
                    claimed_job,
                    state=STATE_FAILED,
                    error=_EXECUTION_INTERRUPTED,
                )

            with self._persistence_lock:
                rows = self._load()
                index = next((i for i, row in enumerate(rows) if row.get("job_id") == job_id), None)
                if index is None:
                    return 1
                current = ImageJob.from_row(rows[index])
                if current.state in TERMINAL_STATES:
                    return 1
                rows[index] = updated.to_row()
                self._save(rows)
            return 1
        finally:
            with self._owned_claims_lock:
                self._owned_claims.discard(job_id)

    def run_to_completion(self, job_id: str, *, max_steps: int = 8) -> ImageJob:
        """Test/dev helper: tick until the job is terminal."""
        for _ in range(max_steps):
            if self.get_job(job_id).state in TERMINAL_STATES:
                break
            self.tick()
        return self.get_job(job_id)

    # ------------------------------------------------------------ read
    def get_job(self, job_id: str) -> ImageJob:
        with self._persistence_lock:
            rows = self._load()
        for row in rows:
            if row.get("job_id") == job_id:
                return ImageJob.from_row(row)
        raise CompanionImageError("unknown_job", f"unknown image job {job_id!r}")

    def list_jobs(self, *, session_id: Optional[str] = None) -> Tuple[ImageJob, ...]:
        with self._persistence_lock:
            jobs = [ImageJob.from_row(r) for r in self._load()]
        if session_id is not None:
            jobs = [j for j in jobs if j.session_id == session_id]
        jobs.sort(key=lambda j: (j.created_at, j.job_id))
        return tuple(jobs)

    def ready_results(self, session_id: str) -> Tuple[str, ...]:
        return tuple(j.result_ref for j in self.list_jobs(session_id=session_id)
                     if j.state == STATE_READY and j.result_ref)

    # ------------------------------------------------------------ delete
    def delete_job(self, job_id: str) -> None:
        """Explicit user action only. Removes the job row; if it produced an
        image file, remove only that file. Never touches other jobs, portrait,
        history, or scene metadata."""
        with self._persistence_lock:
            rows = self._load()
            kept, removed = [], None
            for row in rows:
                if row.get("job_id") == job_id:
                    removed = ImageJob.from_row(row)
                else:
                    kept.append(row)
            if removed is None:
                raise CompanionImageError("unknown_job", f"unknown image job {job_id!r}")
            self._save(kept)
        if removed.result_ref:
            try:
                (self._data_root / removed.result_ref).unlink(missing_ok=True)
            except OSError:
                pass
