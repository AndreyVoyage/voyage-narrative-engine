"""TEST-ONLY native control character for LAB-L5 publication tests.

Everything is created through the public Character Lab / Authoring APIs in
pytest temp storage. ``native-control-e2e`` is test data only and never a
production canonical character.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.character_authoring import CharacterAuthoringStore
from services.character_lab_application import (
    CharacterLabApplicationConfig,
    CharacterLabApplicationService,
)
from services.character_publication.release_store import CharacterReleaseStore

CHARACTER_ID = "native-control-e2e"
RELEASE_A = "native-control-r1"
RELEASE_B = "native-control-r2"
DISPLAY_NAME = "Native Control E2E"
DECIDED_BY = "test-owner"
APPROVED_AT = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
PUBLISHED_BASE = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def native_semantic(biography: str = "Synthetic control biography.") -> dict:
    """Ratified V1 semantic minimum plus the core/visual data Slice B needs."""

    return {
        "identity": {"display_name": DISPLAY_NAME},
        "biography": biography,
        "psychology": {
            "personality": ["steady"],
            "behavioral_traits": ["methodical"],
            "emotional_tendencies": ["calm"],
            "goals_motivations": ["prove the pipeline"],
        },
        "speech": {"speech_style": "plain", "register": None},
        "character_relations": {
            "relational_tendencies": ["cooperative"],
            "attachment_traits": ["secure"],
        },
        "appearance": {"descriptors": ["plain test figure"]},
        "boundaries": {"principles": ["respects refusal"]},
        "visual_identity": {},
    }


def native_semantic_with_sexology(
    biography: str = "Synthetic control biography.",
) -> dict:
    """Native semantic plus populated descriptions and sexology (Slice 1)."""

    semantic = native_semantic(biography)
    semantic["identity"]["short_description"] = "Synthetic card description."
    semantic["identity"]["detailed_description"] = "Synthetic detailed description."
    semantic["sexology"] = {
        "intimacy_attitudes": ["tender"],
        "preferences": ["slow"],
        "emotional_dynamics": ["trust"],
        "communication": ["verbal"],
        "vulnerabilities": ["rejection"],
        "intimacy_boundaries": ["no coercion"],
    }
    return semantic


class TickingClock:
    """Deterministic UTC clock: each call advances one minute."""

    def __init__(self, start: datetime = PUBLISHED_BASE) -> None:
        self._next = start

    def __call__(self) -> datetime:
        moment, self._next = self._next, self._next + timedelta(minutes=1)
        return moment


@dataclass(frozen=True)
class Approved:
    version_id: str
    revision_id: str
    snapshot_hash: str


@dataclass
class NativeLab:
    tmp: Path
    service: CharacterLabApplicationService
    authoring: CharacterAuthoringStore
    releases: CharacterReleaseStore
    builds: Path

    def create_draft(
        self, version_id: str = "native-v1", revision_id: str = "native-v1-r1",
        *, biography: str = "Synthetic control biography.", first: bool = True,
    ):
        create = self.service.create_character if first else self.service.create_new_version
        return create(
            character_id=CHARACTER_ID,
            version_id=version_id,
            revision_id=revision_id,
            version_label=f"Native {version_id}",
            semantic=native_semantic(biography),
        )

    def approve(self, version_id: str, revision_id: str, snapshot_hash: str) -> Approved:
        self.service.submit_for_approval(
            character_id=CHARACTER_ID, version_id=version_id,
            revision_id=revision_id, snapshot_hash=snapshot_hash,
        )
        approved = self.service.approve_as_canon(
            character_id=CHARACTER_ID, version_id=version_id,
            revision_id=revision_id, snapshot_hash=snapshot_hash,
            decided_by=DECIDED_BY,
        )
        assert approved.lifecycle_state == "APPROVED_AS_CANON"
        return Approved(version_id, revision_id, snapshot_hash)

    def approved_v1(self) -> Approved:
        created = self.create_draft()
        return self.approve("native-v1", "native-v1-r1", created.snapshot_hash)

    def approved_v2(self) -> Approved:
        """A genuinely different approved candidate for the same character."""

        created = self.create_draft(
            "native-v2", "native-v2-r1",
            biography="Synthetic control biography, second edition.", first=False,
        )
        return self.approve("native-v2", "native-v2-r1", created.snapshot_hash)

    def publish_kwargs(self, approved: Approved, release_id: str = RELEASE_A, **extra):
        kwargs = dict(
            authoring_store=self.authoring,
            release_store=self.releases,
            character_id=CHARACTER_ID,
            version_id=approved.version_id,
            revision_id=approved.revision_id,
            snapshot_hash=approved.snapshot_hash,
            release_id=release_id,
            display_name=DISPLAY_NAME,
            build_workspace_root=self.builds,
        )
        kwargs.update(extra)
        return kwargs


def make_native_lab(tmp_path: Path) -> NativeLab:
    authoring_root = tmp_path / "authoring"
    service = CharacterLabApplicationService(
        CharacterLabApplicationConfig(character_authoring_root=authoring_root),
        approval_clock=lambda: APPROVED_AT,
    )
    builds = tmp_path / "builds"
    builds.mkdir()
    return NativeLab(
        tmp=tmp_path,
        service=service,
        authoring=CharacterAuthoringStore(authoring_root),
        releases=CharacterReleaseStore(tmp_path / "releases", clock=TickingClock()),
        builds=builds,
    )


def tree(root: Path) -> dict[str, bytes | None]:
    if not root.exists():
        return {}
    return {
        p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


def durable_state(store: CharacterReleaseStore) -> dict[str, bytes | None]:
    """Everything durable in the release store (scratch/locks excluded)."""

    state = {}
    for namespace in ("artifacts", "releases", "current", "history"):
        state.update(
            {f"{namespace}/{k}": v for k, v in tree(store.root / namespace).items()}
        )
    return state
