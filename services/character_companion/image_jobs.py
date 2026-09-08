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
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple

STATE_QUEUED = "QUEUED"
STATE_GENERATING = "GENERATING"
STATE_READY = "READY"
STATE_FAILED = "FAILED"
STATE_CANCELLED = "CANCELLED"
TERMINAL_STATES = frozenset({STATE_READY, STATE_FAILED, STATE_CANCELLED})

KIND_CUSTOM = "custom"       # "Создать изображение..." -- user description
KIND_CONTEXT = "context"     # "Кадр по контексту" -- derived from scene + excerpt

_JOBS_FILENAME = "companion_image_jobs.json"


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
    prompt: Optional[str] = None
    context: Optional[dict] = None
    result_ref: Optional[str] = None
    error: Optional[str] = None

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
            prompt=row.get("prompt"),
            context=row.get("context"),
            result_ref=row.get("result_ref"),
            error=row.get("error"),
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
            "prompt": self.prompt,
            "context": self.context,
            "result_ref": self.result_ref,
            "error": self.error,
        }


class CompanionImageGenerator(Protocol):
    """The seam a real visual pipeline implements later.

    ``advance`` moves ONE non-terminal job forward by at most one step and
    returns the updated job. It must be non-blocking / fast and must never
    perform an external network call in this slice's implementations.
    """

    def advance(self, job: ImageJob, *, images_dir: Path) -> ImageJob:  # pragma: no cover - protocol
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

    # ------------------------------------------------------------ create
    def create_job(
        self,
        *,
        session_id: str,
        character_id: str,
        kind: str,
        prompt: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> ImageJob:
        if kind not in (KIND_CUSTOM, KIND_CONTEXT):
            raise CompanionImageError("invalid_request", f"unknown image kind {kind!r}")
        if kind == KIND_CUSTOM and not (isinstance(prompt, str) and prompt.strip()):
            raise CompanionImageError("invalid_request", "a description is required for a custom image")
        now = _now_iso()
        job = ImageJob(
            job_id="img-" + uuid.uuid4().hex,
            session_id=session_id,
            character_id=character_id,
            kind=kind,
            state=STATE_QUEUED,
            created_at=now,
            updated_at=now,
            prompt=prompt.strip() if isinstance(prompt, str) else None,
            context=context,
        )
        rows = self._load()
        rows.append(job.to_row())
        self._save(rows)
        return job

    # ------------------------------------------------------------ advance
    def tick(self) -> int:
        """Advance every non-terminal job by one step. Returns how many moved.
        Called by the poll/list transport methods -- never by send_message."""
        rows = self._load()
        moved = 0
        for i, row in enumerate(rows):
            job = ImageJob.from_row(row)
            if job.state in TERMINAL_STATES:
                continue
            updated = self._generator.advance(job, images_dir=self._images_dir())
            if updated.state != job.state or updated.result_ref != job.result_ref:
                rows[i] = updated.to_row()
                moved += 1
        if moved:
            self._save(rows)
        return moved

    def run_to_completion(self, job_id: str, *, max_steps: int = 8) -> ImageJob:
        """Test/dev helper: tick until the job is terminal."""
        for _ in range(max_steps):
            if self.get_job(job_id).state in TERMINAL_STATES:
                break
            self.tick()
        return self.get_job(job_id)

    # ------------------------------------------------------------ read
    def get_job(self, job_id: str) -> ImageJob:
        for row in self._load():
            if row.get("job_id") == job_id:
                return ImageJob.from_row(row)
        raise CompanionImageError("unknown_job", f"unknown image job {job_id!r}")

    def list_jobs(self, *, session_id: Optional[str] = None) -> Tuple[ImageJob, ...]:
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
