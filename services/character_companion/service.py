#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CompanionService -- the minimal end-user chat surface for accepted characters.

Companion is a SEPARATE client from Character Lab. It never imports the Lab
adapter or Lab UI; it composes the same lower layers the Lab already uses:

    CompanionService
        v
    RuntimeService.turn(...)           (unchanged)  -- accepted package + policy
    RuntimeMemoryBackend               (unchanged)  -- the ONE durable event log
        v
    Character Runtime / Core

Persistence:
- conversation turns are the EXISTING Runtime Memory event log (USER_MESSAGE /
  CHARACTER_MESSAGE). No second chat database.
- a small durable JSON session registry (``companion_sessions.json``) records
  which COMPANION sessions exist, per character, plus ADDITIVE optional metadata
  (title, scene, scene cover). Old registry rows lacking the new fields still
  load, with defaults.
- image-generation job metadata lives in its own small additive JSON file
  (``companion_image_jobs.json``); see :mod:`image_jobs`.
- each character's Companion conversations share one memory / state root under
  ``<data_root>/characters/<character_id>/`` -- fully isolated from Character
  Lab's CLEAN_TEST workspaces (a different data root entirely).

Scene: a session may carry editable scene fields (place / time / situation /
mood + free-form). On each turn a plain :class:`Scene` is built from those
fields and passed through the EXISTING ``RuntimeService`` scene parameter. It is
never converted into memory / WORLD_FACT / Runtime State / EvolutionCandidate.

No provider or network calls of its own.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from services.character_lab import GroundedV2Policy, RuntimeService
from services.character_lab.runtime_policy import ContextBudgetExceededError
from services.character_lab.scene import new_scene, render_scene_block
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import AcceptedCharacter, RuntimeMemoryBackend

from .catalog import CompanionCatalog, CompanionCharacterEntry, build_default_catalog
from .session_character import (
    ExactCharacterSelectionV1,
    SessionCharacterError,
    SessionCharacterPinStatus,
    SessionCharacterPinV1,
)
from .image_readiness import ImageGenerationReadiness, evaluate_image_generation_readiness
from .public_profile import CharacterPublicProfile, CharacterPublicProfileStore
from .image_jobs import (
    KIND_CONTEXT,
    KIND_CUSTOM,
    CompanionImageError,
    ImageJob,
    ImageJobService,
    UnavailableImageGenerator,
)
from .cloud_provider import CloudProviderError
from .credentials import CredentialError, CredentialVault
from .local_provider import LocalLLMProviderError
from .provider_registry import (
    ALL_ROLES,
    ROLE_DIALOGUE,
    ROLE_DISPLAY_ORDER,
    RUNTIME_WIRED_ROLES,
    ProviderRegistryError,
    all_providers,
    get_provider,
    providers_supporting_role,
)
from .provider_resolution import (
    CompanionConfigError,
    resolve_dialogue_provider_factory,
    resolve_role_config,
    test_provider_connection,
)
from .settings import (
    DIALOGUE_CONTEXT_BUDGET_DEFAULT,
    DIALOGUE_CONTEXT_BUDGET_MAX,
    DIALOGUE_CONTEXT_BUDGET_MIN,
    NUM_CTX_KIRA_SAFE_HINT,
    NUM_CTX_MAX,
    NUM_CTX_MIN,
    CompanionSettings,
    SettingsError,
    SettingsStore,
)

PURPOSE_COMPANION = "COMPANION"

_ROLE_BY_EVENT_TYPE = {"USER_MESSAGE": "user", "CHARACTER_MESSAGE": "character"}
_HISTORY_ROLE = {"user": "user", "character": "assistant"}

# Co-author "user-originated memory" bound: newest USER_STATED statements from
# OTHER sessions of the same profile, whole-block or omit. Provenance label is
# the Character-Lab constant value (kept in sync; not imported to avoid a new
# cross-package dependency in this slice).
_COAUTHOR_USER_STATED_PROVENANCE = "USER_STATED"
_COAUTHOR_USER_MEMORY_MAX_EVENTS = 20
_COAUTHOR_USER_MEMORY_MAX_CHARS = 6000

_REGISTRY_FILENAME = "companion_sessions.json"
_SCENE_FIELDS = ("place", "time", "situation", "mood", "freeform")
# Session identity fields that are immutable once a session row is written.
_IMMUTABLE_SESSION_IDENTITY = ("character_id", "character_pin_v1")
_CONTEXT_EXCERPT_MAX = 8      # "Кадр по контексту" bounded recent context
_PREVIEW_MAX_CHARS = 120

# V1C -- the visual context-frame feeds ONLY the externally-observable, structured
# scene fields. ``freeform`` is deliberately excluded: free-form scene text may
# carry private / hidden / intended / hypothetical content, and there is no
# deterministic (no prompt-synthesis model) way to classify it as "visible" vs
# "not visible". Fail conservative: use less context rather than guessing.
_VISUAL_SCENE_FIELDS = ("place", "time", "situation", "mood")


class CompanionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CompanionProviderError(CompanionError):
    """The character response failed at the provider layer. Nothing was
    persisted; prior conversation history is unchanged."""


@dataclass(frozen=True)
class CompanionScene:
    place: str = ""
    time: str = ""
    situation: str = ""
    mood: str = ""
    freeform: str = ""

    @classmethod
    def from_row(cls, data: Optional[dict]) -> Optional["CompanionScene"]:
        if not isinstance(data, dict):
            return None
        picked = {k: str(data.get(k) or "").strip() for k in _SCENE_FIELDS}
        if not any(picked.values()):
            return None
        return cls(**picked)

    def to_row(self) -> dict:
        return {k: getattr(self, k) for k in _SCENE_FIELDS}

    def is_empty(self) -> bool:
        return not any(getattr(self, k) for k in _SCENE_FIELDS)


@dataclass(frozen=True)
class CompanionSession:
    session_id: str
    character_id: str
    purpose: str
    created_at: str
    updated_at: str
    label: str
    title: str = ""
    scene: Optional[CompanionScene] = None
    scene_cover_ref: Optional[str] = None
    last_message_preview: str = ""
    last_activity: str = ""
    # ---- durable PRESENTATION metadata (never touches Character Memory) ----
    title_override: Optional[str] = None
    hidden: bool = False
    hidden_message_ids: Tuple[int, ...] = ()
    # ---- S8B immutable character pin (additive; legacy rows stay unpinned) ----
    character_pin_status: str = "LEGACY_UNPINNED"
    character_pin: Optional[SessionCharacterPinV1] = None


@dataclass(frozen=True)
class CompanionMessage:
    seq: Optional[int]
    role: str
    text: str
    created_at: str


@dataclass(frozen=True)
class CompanionTurn:
    session_id: str
    response: str
    messages: Tuple[CompanionMessage, ...]
    scene_present: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_label(created_at: str) -> str:
    stamp = created_at.replace("T", " ")
    if "+" in stamp:
        stamp = stamp.split("+", 1)[0]
    return f"Диалог от {stamp}"


def _compose_situation(scene: CompanionScene) -> str:
    parts: List[str] = []
    if scene.freeform:
        parts.append(scene.freeform)
    if scene.time:
        parts.append(f"Время: {scene.time}.")
    if scene.situation:
        parts.append(f"Ситуация: {scene.situation}.")
    if scene.mood:
        parts.append(f"Настроение: {scene.mood}.")
    return " ".join(parts).strip()


def _hidden_message_ids(row: dict) -> Tuple[int, ...]:
    """Durable presentation-hidden message seqs for a session row.

    Empty when no visibility metadata exists (older rows) -- we never invent
    hidden-message metadata. Values are the stable Runtime Memory event ``seq``.
    """
    pres = row.get("presentation") if isinstance(row.get("presentation"), dict) else {}
    return tuple(
        int(x) for x in (pres.get("hiddenMessageIds") or [])
        if isinstance(x, int) and not isinstance(x, bool)
    )


class CompanionService:
    def __init__(
        self,
        *,
        acceptance_root,
        data_root,
        provider_factory,
        provider_info: dict,
        source_loader=None,
        catalog: Optional[CompanionCatalog] = None,
        image_generator=None,
        settings_store: Optional[SettingsStore] = None,
        credential_vault: Optional[CredentialVault] = None,
        http_post_local=None,
        http_post_cloud=None,
        mode: str = "dev",
    ) -> None:
        self._acceptance_root = Path(acceptance_root)
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._source_loader = source_loader or build_repo_source_loader(
            acceptance_root=self._acceptance_root
        )
        if provider_factory is None:
            raise CompanionError("provider_unavailable", "a provider factory is required")
        self._provider_factory = provider_factory
        self._provider_info = dict(provider_info or {})
        self._runtime = RuntimeService(
            acceptance_root=self._acceptance_root, source_loader=self._source_loader
        )
        self._catalog = catalog or build_default_catalog(
            self._acceptance_root, self._source_loader, data_root=self._data_root
        )
        self._images = ImageJobService(
            self._data_root, image_generator or UnavailableImageGenerator()
        )
        # Editable public presentation layer -- independent of the accepted
        # package / runtime / local visual snapshot / memory. A future Admin
        # Studio persists an edited profile through this same store.
        self._profiles = CharacterPublicProfileStore(self._data_root)
        # Secure provider configuration (optional). When BOTH a settings store
        # and a credential vault are present, send_message resolves the DIALOGUE
        # provider factory from settings each turn. Otherwise the injected
        # ``provider_factory`` is used unchanged (existing tests / fake server).
        self._settings_store = settings_store
        self._vault = credential_vault
        self._http_post_local = http_post_local
        self._http_post_cloud = http_post_cloud
        from .release import normalize_mode
        self._mode = normalize_mode(mode)

    @property
    def _secure_config_enabled(self) -> bool:
        return self._settings_store is not None and self._vault is not None

    # ------------------------------------------------------------- catalog
    def list_characters(self) -> Tuple[CompanionCharacterEntry, ...]:
        return self._catalog.available()

    def _require_character(self, character_id: str) -> CompanionCharacterEntry:
        entry = self._catalog.get(character_id)
        if entry is None or not entry.available:
            raise CompanionError("unknown_character", f"unknown character {character_id!r}")
        return entry

    # ---- public profile (editable editorial layer; never runtime truth) ----
    def get_public_profile(self, character_id: str) -> CharacterPublicProfile:
        entry = self._require_character(character_id)
        return self._profiles.load(entry.character_id, display_name=entry.display_name)

    def save_public_profile(self, profile: CharacterPublicProfile) -> CharacterPublicProfile:
        """Persist an author/admin-edited profile (future Admin Studio seam).
        Reads/writes ONLY the public-profile store -- no accepted package,
        runtime, snapshot, or memory write."""
        self._require_character(profile.character_id)
        return self._profiles.save(profile)

    # --------------------------------------------------------- registry io
    def _registry_path(self) -> Path:
        return self._data_root / _REGISTRY_FILENAME

    def _load_registry(self) -> List[dict]:
        path = self._registry_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CompanionError(
                "registry_corrupt", f"companion session registry is not valid JSON: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise CompanionError(
                "registry_corrupt", "companion session registry root must be a JSON array"
            )
        rows: List[dict] = []
        for item in data:
            if not isinstance(item, dict):
                raise CompanionError(
                    "registry_corrupt",
                    "companion session registry entries must all be JSON objects",
                )
            rows.append(item)
        return rows

    def _save_registry(self, rows: Sequence[dict]) -> None:
        path = self._registry_path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _char_root(self, character_id: str) -> Path:
        root = self._data_root / "characters" / character_id
        (root / "memory").mkdir(parents=True, exist_ok=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        return root

    def _pinned_storage_root(self, pin: SessionCharacterPinV1) -> Path:
        """Release-scoped storage root for a PINNED session.

        The root is ``<data_root>/character_namespaces/pinned-v1/<digest>/``
        where ``<digest>`` is ``pin.storage_namespace_id()`` (a full 64-char
        SHA-256 hex). Raw identity values never appear as path components, so
        filesystem safety does not depend on raw-ID path safety.
        """
        root = (
            self._data_root
            / "character_namespaces"
            / "pinned-v1"
            / pin.storage_namespace_id()
        )
        (root / "memory").mkdir(parents=True, exist_ok=True)
        (root / "state").mkdir(parents=True, exist_ok=True)
        return root

    def _storage_root_for_session(self, row: dict) -> Path:
        """Route a session row to its storage root, fail-closed.

        LEGACY_UNPINNED keeps the historical ``characters/<character_id>/``
        layout. A valid PINNED_V1 session uses the release-scoped hashed
        namespace. Invalid/partial/malformed/mismatched pinned metadata fails
        closed via the existing S8B pin parser -- never a character_id-only
        fallback.
        """
        pin_status, pin = self._pin_for_row(row)
        if pin_status is SessionCharacterPinStatus.LEGACY_UNPINNED:
            return self._char_root(row["character_id"])
        return self._pinned_storage_root(pin)

    # ------------------------------------------------------------- sessions
    def _next_activity_seq(self, registry: List[dict]) -> int:
        return max((int(r.get("activity_seq") or 0) for r in registry), default=0) + 1

    def list_sessions(self, character_id: str) -> Tuple[CompanionSession, ...]:
        self._require_character(character_id)
        registry = self._load_registry()
        rows = [r for r in registry if r.get("character_id") == character_id]
        # newest activity first -- a monotonic activity_seq is authoritative so
        # ordering is deterministic regardless of wall-clock granularity.
        rows.sort(
            key=lambda r: (int(r.get("activity_seq") or 0), r.get("updated_at") or "", r.get("session_id") or ""),
            reverse=True,
        )
        return tuple(self._enrich(r) for r in rows)

    def create_session(
        self,
        character_id: str,
        *,
        title: Optional[str] = None,
        scene: Optional[dict] = None,
    ) -> CompanionSession:
        self._require_character(character_id)
        now = _now_iso()
        row: dict = {
            "session_id": "cmp-" + uuid.uuid4().hex,
            "character_id": character_id,
            "purpose": PURPOSE_COMPANION,
            "created_at": now,
            "updated_at": now,
            "label": _default_label(now),
        }
        if isinstance(title, str) and title.strip():
            row["title"] = title.strip()
        parsed = CompanionScene.from_row(scene)
        if parsed is not None:
            row["scene"] = parsed.to_row()
        registry = self._load_registry()
        row["activity_seq"] = self._next_activity_seq(registry)
        registry.append(row)
        self._save_registry(registry)
        return self._enrich(row)

    def create_pinned_session(
        self,
        selection: ExactCharacterSelectionV1,
        *,
        title: Optional[str] = None,
        scene: Optional[dict] = None,
    ) -> CompanionSession:
        """Create a NEW session pinned to an exact immutable Package V1 identity.

        The four-field selection is verified against the installed package and
        the S8A runtime definition BEFORE any session row is written. There is
        no catalog / latest / active / fallback resolution, and no memory,
        history, state, or runtime wiring is opened.
        """
        if not isinstance(selection, ExactCharacterSelectionV1):
            raise CompanionError(
                "invalid_pin", "selection must be an ExactCharacterSelectionV1"
            )
        self._resolve_exact_definition(selection)
        now = _now_iso()
        row: dict = {
            "session_id": "cmp-" + uuid.uuid4().hex,
            "character_id": selection.character_id,
            "purpose": PURPOSE_COMPANION,
            "created_at": now,
            "updated_at": now,
            "label": _default_label(now),
            "character_pin_v1": selection.to_pin().to_json(),
        }
        if isinstance(title, str) and title.strip():
            row["title"] = title.strip()
        parsed = CompanionScene.from_row(scene)
        if parsed is not None:
            row["scene"] = parsed.to_row()
        registry = self._load_registry()
        row["activity_seq"] = self._next_activity_seq(registry)
        registry.append(row)
        self._save_registry(registry)
        return self._enrich(row)

    def resolve_pinned_definition(self, session_id: str):
        """Read-only exact definition resolution for a pinned session.

        Uses the STORED pin only (never a new/current selection), fails closed
        if the package is missing or either hash differs, and NEVER hands the
        definition to RuntimeService.turn in S8B.
        """
        row = self._session_row(session_id)
        pin_status, pin = self._pin_for_row(row)
        if pin_status is not SessionCharacterPinStatus.PINNED_V1 or pin is None:
            raise CompanionError(
                "pin_invalid", "session has no immutable character pin"
            )
        selection = ExactCharacterSelectionV1(
            character_id=pin.character_id,
            release_id=pin.release_id,
            package_hash=pin.package_hash,
            runtime_definition_hash=pin.runtime_definition_hash,
        )
        return self._resolve_exact_definition(selection)

    def _resolve_exact_definition(self, selection: ExactCharacterSelectionV1):
        """Exact-lookup the requested package and return its S8A definition.

        Fails closed on missing package, package_hash mismatch, or
        runtime_definition_hash mismatch. The returned definition is never
        passed into RuntimeService.turn by any S8B path.
        """
        from .character_import.package_importer import CharacterPackageImportService
        from .character_import.package_management import (
            CharacterPackageManagementError,
            CharacterPackageManagementService,
            InstalledPackageNotFoundError,
        )
        from .package_runtime import (
            ExactPackageRuntimeBinding,
            PackageRuntimeError,
            load_runtime_character_definition,
        )

        management = CharacterPackageManagementService(self._data_root)
        try:
            release = management.get_release(selection.character_id, selection.release_id)
        except InstalledPackageNotFoundError as exc:
            raise CompanionError(
                "package_missing",
                f"package {selection.character_id!r}/{selection.release_id!r} is not installed",
            ) from exc
        except CharacterPackageManagementError as exc:
            raise CompanionError(
                "package_missing",
                f"package {selection.character_id!r}/{selection.release_id!r} cannot be resolved: {exc}",
            ) from exc
        if release.package_hash != selection.package_hash:
            raise CompanionError(
                "package_identity_mismatch",
                "package_hash does not match the installed package",
            )

        importer = CharacterPackageImportService(self._data_root)
        package_root = importer.installed_path(selection.character_id, selection.release_id)
        binding = ExactPackageRuntimeBinding(
            package_root=package_root,
            expected_character_id=selection.character_id,
            expected_release_id=selection.release_id,
            expected_package_hash=selection.package_hash,
        )
        try:
            definition = load_runtime_character_definition(binding)
        except PackageRuntimeError as exc:
            raise CompanionError(
                "package_resolution_failed",
                f"package could not produce a runtime definition: {exc}",
            ) from exc

        if definition.runtime_definition_hash != selection.runtime_definition_hash:
            raise CompanionError(
                "runtime_definition_mismatch",
                "runtime_definition_hash does not match the resolved definition",
            )
        return definition

    def get_session(self, session_id: str) -> CompanionSession:
        return self._enrich(self._session_row(session_id))

    def _session_row(self, session_id: str) -> dict:
        for row in self._load_registry():
            if row.get("session_id") == session_id:
                return row
        raise CompanionError("unknown_session", f"unknown session {session_id!r}")

    def _pin_for_row(
        self, row: dict
    ) -> Tuple[SessionCharacterPinStatus, Optional[SessionCharacterPinV1]]:
        """Classify a session row's immutable character pin, fail-closed on
        malformed/partial/contradictory pin data. Absent key => LEGACY_UNPINNED.
        """
        if "character_pin_v1" not in row:
            return SessionCharacterPinStatus.LEGACY_UNPINNED, None
        data = row["character_pin_v1"]
        if data is None:
            raise CompanionError(
                "pin_invalid", "character_pin_v1 must be a JSON object, not null"
            )
        try:
            pin = SessionCharacterPinV1.from_json(data)
        except SessionCharacterError as exc:
            raise CompanionError("pin_invalid", f"invalid character_pin_v1: {exc}") from exc
        if pin.character_id != row.get("character_id"):
            raise CompanionError(
                "pin_invalid",
                "character_pin_v1.character_id does not match the session character_id",
            )
        return SessionCharacterPinStatus.PINNED_V1, pin

    def _require_executable_session(self, row: dict) -> None:
        """Centralized fail-closed guard for the PINNED_V1 operations that
        remain blocked after S8C2 (image execution, hidden visibility mutation).
        Must run BEFORE any memory/state/runtime/provider/image work.
        """
        pin_status, _pin = self._pin_for_row(row)
        if pin_status is SessionCharacterPinStatus.PINNED_V1:
            raise CompanionError(
                "pinned_execution_blocked",
                "PINNED_V1 image execution and hidden visibility mutation are "
                "blocked until a later slice",
            )

    def _enrich(self, row: dict) -> CompanionSession:
        pin_status, pin = self._pin_for_row(row)
        created = row.get("created_at", "")
        updated = row.get("updated_at", created)
        preview = ""
        if pin_status is SessionCharacterPinStatus.LEGACY_UNPINNED:
            try:
                history = self._history(row["character_id"], row["session_id"])
                if history:
                    preview = history[-1].text.strip().replace("\n", " ")
                    if len(preview) > _PREVIEW_MAX_CHARS:
                        preview = preview[: _PREVIEW_MAX_CHARS - 1].rstrip() + "…"
            except CompanionError:
                pass
        pres = row.get("presentation") if isinstance(row.get("presentation"), dict) else {}
        override = pres.get("titleOverride")
        override = override.strip() if isinstance(override, str) and override.strip() else None
        hidden_ids = _hidden_message_ids(row)
        return CompanionSession(
            session_id=row["session_id"],
            character_id=row["character_id"],
            purpose=row.get("purpose", PURPOSE_COMPANION),
            created_at=created,
            updated_at=updated,
            label=row.get("label") or _default_label(created),
            title=str(row.get("title") or "").strip(),
            scene=CompanionScene.from_row(row.get("scene")),
            scene_cover_ref=row.get("scene_cover_ref"),
            last_message_preview=preview,
            last_activity=updated,
            title_override=override,
            hidden=bool(pres.get("hidden")),
            hidden_message_ids=hidden_ids,
            character_pin_status=pin_status.value,
            character_pin=pin,
        )

    # ---- durable presentation metadata (UI-only; Character Memory untouched) --
    def _merge_presentation(self, session_id: str, patch: Dict) -> CompanionSession:
        row = self._session_row(session_id)
        pres = dict(row.get("presentation") or {})
        pres.update(patch)
        return self._enrich(self._mutate_row(session_id, {"presentation": pres}))

    def rename_session(self, session_id: str, title) -> CompanionSession:
        """Set a presentation title override. Empty -> clear it (fall back to the
        automatic label). Does NOT touch Memory or Scene facts; no AI."""
        clean = str(title or "").strip()[:_PREVIEW_MAX_CHARS] if title is not None else ""
        return self._merge_presentation(session_id, {"titleOverride": clean or None})

    def set_session_visibility(self, session_id: str, hidden: bool) -> CompanionSession:
        """Hide/restore a conversation in the UI list. The session, its history,
        generated media, cover and all Runtime effects remain exactly as before.
        This is presentation privacy, not erasure."""
        return self._merge_presentation(session_id, {"hidden": bool(hidden)})

    def set_message_visibility(self, session_id: str, message_id: int, hidden: bool) -> CompanionSession:
        """Hide/restore one message in the UI transcript. The underlying Memory
        event is NOT deleted, updated or filtered from Runtime retrieval -- only
        its presentation visibility changes."""
        if isinstance(message_id, bool) or not isinstance(message_id, int):
            raise CompanionError("invalid_request", "messageId must be an integer event seq")
        row = self._session_row(session_id)
        if hidden:
            self._require_executable_session(row)
            known = {m.seq for m in self._history(row["character_id"], session_id) if m.seq is not None}
            if message_id not in known:
                raise CompanionError("unknown_message", f"no message with seq {message_id} in this session")
        pres = dict(row.get("presentation") or {})
        current = [int(x) for x in (pres.get("hiddenMessageIds") or []) if isinstance(x, int) and not isinstance(x, bool)]
        if hidden and message_id not in current:
            current.append(message_id)
        if not hidden:
            current = [x for x in current if x != message_id]
        pres["hiddenMessageIds"] = sorted(set(current))
        return self._enrich(self._mutate_row(session_id, {"presentation": pres}))

    def writing_assistant_suggest(
        self,
        draft: str,
        *,
        session_id: Optional[str] = None,
        locale_hint: Optional[str] = None,
    ) -> dict:
        """Contextual co-author. COMPOSE when the trimmed draft is empty, else
        EXPAND. Runs on the EFFECTIVE DIALOGUE provider/model (never a separate
        WRITING_ASSISTANT assignment), with one provider call, no retry, no
        fallback. Builds a READ-ONLY user-safe context snapshot when a
        ``session_id`` is given; never routes through ``RuntimeService.turn`` /
        ``policy.persist`` and never writes memory or state."""
        store, _vault = self._require_secure_config()
        from .writing_assistant import WritingAssistantError, coauthor_suggest, derive_mode

        settings = store.load()
        assignment = settings.dialogue()
        factory = self._dialogue_factory()  # DIALOGUE inheritance + release fake-guard
        ctx = self._coauthor_context(session_id) if session_id else {}
        try:
            return coauthor_suggest(
                draft,
                mode=derive_mode(draft),
                provider_factory=factory,
                provider_id=assignment.provider_id,
                model_id=assignment.model_id,
                budget_est_tokens=settings.dialogue_context_budget_est_tokens,
                visible_history=ctx.get("visible_history", ()),
                scene_text=ctx.get("scene_text"),
                user_memory_block=ctx.get("user_memory_block"),
                locale_hint=locale_hint,
            )
        except WritingAssistantError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def writing_assistant_rewrite(
        self,
        draft: str,
        *,
        session_id: Optional[str] = None,
        locale_hint: Optional[str] = None,
    ) -> dict:
        """Legacy composer helper. A non-empty draft is delegated to the shared
        co-author core in EXPAND mode; an empty draft stays invalid."""
        if not isinstance(draft, str) or not draft.strip():
            raise CompanionError("invalid_draft", "draft must be a non-empty string")
        return self.writing_assistant_suggest(
            draft, session_id=session_id, locale_hint=locale_hint
        )

    def _coauthor_context(self, session_id: str) -> dict:
        """Assemble the READ-ONLY user-safe co-author context for one session:
        visible dialogue history (presentation-hidden messages removed), the
        shared Scene, and the user's own prior statements. Nothing character-
        private (RELATIONSHIP / PSYCHOLOGY / epistemic / FACT / Accepted
        package) and no KIRA core instruction. Opens no writable path."""
        row = self._session_row(session_id)
        pres = row.get("presentation") if isinstance(row.get("presentation"), dict) else {}
        hidden = {
            int(x) for x in (pres.get("hiddenMessageIds") or [])
            if isinstance(x, int) and not isinstance(x, bool)
        }

        pin_status, pin = self._pin_for_row(row)
        if pin_status is SessionCharacterPinStatus.PINNED_V1:
            # S8C2: exact Package V1 definition validates BEFORE any pinned
            # storage resolution/read. display_name + scene come only from the
            # resolved definition (no catalog/legacy fallback). Dimension
            # semantics are intentionally NOT part of this context.
            definition = self._resolve_exact_definition(self._selection_from_pin(pin))
            storage_root = self._pinned_storage_root(pin)
            subject_id = pin.character_id
            visible_history = [
                {"role": _HISTORY_ROLE[m.role], "content": m.text}
                for m in self._history_for_row(row)
                if m.seq not in hidden
            ]
            scene = self._scene_for_display_name(row, definition.display_name)
            scene_text = render_scene_block(scene) if scene is not None else None
            user_memory_block = self._coauthor_user_memory_block_for_root(
                storage_root / "memory", subject_id, session_id
            )
            return {
                "visible_history": visible_history,
                "scene_text": scene_text,
                "user_memory_block": user_memory_block,
            }

        entry = self._require_character(row["character_id"])
        visible_history = [
            {"role": _HISTORY_ROLE[m.role], "content": m.text}
            for m in self._history(row["character_id"], session_id)
            if m.seq not in hidden
        ]
        scene = self._scene_for_turn(row, entry)
        scene_text = render_scene_block(scene) if scene is not None else None
        user_memory_block = self._coauthor_user_memory_block(entry, session_id)
        return {
            "visible_history": visible_history,
            "scene_text": scene_text,
            "user_memory_block": user_memory_block,
        }

    def _coauthor_user_memory_block(
        self, entry: CompanionCharacterEntry, current_session_id: str
    ) -> Optional[str]:
        return self._coauthor_user_memory_block_for_root(
            self._char_root(entry.character_id) / "memory",
            entry.subject_id,
            current_session_id,
        )

    def _coauthor_user_memory_block_for_root(
        self, memory_root: Path, subject_id: str, current_session_id: str
    ) -> Optional[str]:
        """Newest USER_STATED statements from OTHER sessions of this profile,
        as bounded '- [со слов пользователя] ...' lines (whole block or omit).
        Read-only: a SELECT over the shared causal event log."""
        backend = RuntimeMemoryBackend(memory_root, subject_id)
        try:
            events = backend.load_events_causal(subject_id)
        finally:
            backend.close()
        lines: List[str] = []
        total = 0
        for e in reversed(events):
            if e.session_id == current_session_id:
                continue
            if e.event_type != "USER_MESSAGE":
                continue
            if (e.provenance or "") != _COAUTHOR_USER_STATED_PROVENANCE:
                continue
            text = " ".join((e.meaning or "").split())
            if not text:
                continue
            if (
                len(lines) >= _COAUTHOR_USER_MEMORY_MAX_EVENTS
                or total + len(text) > _COAUTHOR_USER_MEMORY_MAX_CHARS
            ):
                break
            lines.append(f"- [со слов пользователя] {text}")
            total += len(text)
        lines.reverse()
        return "\n".join(lines) if lines else None

    def _mutate_row(self, session_id: str, changes: Dict) -> dict:
        registry = self._load_registry()
        target = None
        for r in registry:
            if r.get("session_id") == session_id:
                target = r
        if target is None:
            raise CompanionError("unknown_session", f"unknown session {session_id!r}")
        for field in _IMMUTABLE_SESSION_IDENTITY:
            if field in changes and changes[field] != target.get(field):
                raise CompanionError(
                    "session_identity_immutable",
                    f"session identity field {field!r} cannot be changed after creation",
                )
        target.update(changes)
        self._save_registry(registry)
        return target

    def set_scene_cover(self, session_id: str, result_ref: str) -> CompanionSession:
        """Explicit user action. Does not auto-overwrite -- caller decides. The
        referenced image must be a READY job result for this session."""
        row = self._session_row(session_id)
        ready = self._images.ready_results(session_id)
        if result_ref not in ready:
            raise CompanionError("invalid_request", "cover must reference a READY generated image of this session")
        return self._enrich(self._mutate_row(session_id, {"scene_cover_ref": result_ref}))

    # ------------------------------------------------------------- messages
    def get_messages(self, session_id: str) -> Tuple[CompanionMessage, ...]:
        row = self._session_row(session_id)
        return self._history_for_row(row)

    def _history(self, character_id: str, session_id: str) -> Tuple[CompanionMessage, ...]:
        entry = self._require_character(character_id)
        return self._read_history(
            self._char_root(character_id) / "memory", entry.subject_id, session_id
        )

    def _history_for_row(self, row: dict) -> Tuple[CompanionMessage, ...]:
        """Read a session's conversation history from the correct namespace.

        PINNED_V1 sessions read from the S8B2 release-scoped namespace;
        LEGACY_UNPINNED sessions keep the historical character_id-only root.
        No package lookup, no provider, no RuntimeDefinition load.
        """
        pin_status, pin = self._pin_for_row(row)
        if pin_status is SessionCharacterPinStatus.PINNED_V1:
            return self._read_history(
                self._pinned_storage_root(pin) / "memory",
                pin.character_id,
                row["session_id"],
            )
        entry = self._require_character(row["character_id"])
        return self._read_history(
            self._char_root(row["character_id"]) / "memory",
            entry.subject_id,
            row["session_id"],
        )

    def _read_history(
        self, memory_root: Path, subject_id: str, session_id: str
    ) -> Tuple[CompanionMessage, ...]:
        backend = RuntimeMemoryBackend(memory_root, subject_id)
        try:
            events = backend.load_events_causal(subject_id)
        finally:
            backend.close()
        out: List[CompanionMessage] = []
        for e in events:
            if e.session_id != session_id:
                continue
            role = _ROLE_BY_EVENT_TYPE.get(e.event_type)
            if role is None:
                continue
            out.append(
                CompanionMessage(seq=e.seq, role=role, text=e.meaning, created_at=e.created_at)
            )
        return tuple(out)

    def _scene_for_turn(self, row: dict, entry: CompanionCharacterEntry):
        return self._scene_for_display_name(row, entry.display_name)

    def _scene_for_display_name(self, row: dict, display_name: str):
        parsed = CompanionScene.from_row(row.get("scene"))
        if parsed is None or parsed.is_empty():
            return None
        return new_scene(
            title=str(row.get("title") or "").strip(),
            location=parsed.place,
            participants=[display_name],
            prior_events=[],
            current_situation=_compose_situation(parsed),
            scene_id=f"companion-{row['session_id']}",
            created_at=row.get("created_at") or _now_iso(),
        )

    def _selection_from_pin(self, pin: SessionCharacterPinV1) -> ExactCharacterSelectionV1:
        return ExactCharacterSelectionV1(
            character_id=pin.character_id,
            release_id=pin.release_id,
            package_hash=pin.package_hash,
            runtime_definition_hash=pin.runtime_definition_hash,
        )

    def _accepted_character_from_definition(self, definition) -> AcceptedCharacter:
        return AcceptedCharacter(
            subject_id=definition.character_id,
            package=definition.candidate,
            source_candidate_hash=definition.source_acceptance.package_hash,
            acceptance_id=definition.source_acceptance.acceptance_id,
        )

    def _run_turn(self, turn_call):
        try:
            return turn_call()
        except CompanionError:
            raise
        except ContextBudgetExceededError as exc:
            # Mandatory context alone exceeds the configured budget -- raised by
            # assemble_context BEFORE any provider call or persistence.
            raise CompanionError(
                "context_budget_exceeded",
                "the mandatory request context exceeds the configured dialogue "
                "context budget",
            ) from exc
        except Exception as exc:  # noqa: BLE001 -- fail-closed, do not leak internals
            if _has_unavailable_cause(exc):
                local = _find_local_provider_error(exc)
                msg = "Локальная модель недоступна." if local is not None else "Выбранный провайдер недоступен."
                raise CompanionProviderError("provider_unavailable", msg) from exc
            raise CompanionProviderError(
                "provider_failed", "the character response could not be generated"
            ) from exc

    def send_message(self, session_id: str, text: str) -> CompanionTurn:
        if not isinstance(text, str) or not text.strip():
            raise CompanionError("empty_message", "message text must be a non-empty string")
        row = self._session_row(session_id)
        pin_status, pin = self._pin_for_row(row)

        # ONE deterministically-chosen factory. No retry, no second provider.
        try:
            factory = self._dialogue_factory()
        except (CompanionConfigError, SettingsError, ProviderRegistryError) as exc:
            raise CompanionError(getattr(exc, "code", "provider_config"), exc.message) from exc

        # Companion supplies its normalized DIALOGUE operational context budget
        # explicitly (V1C). Bare GroundedV2Policy() -- e.g. Character Lab -- stays
        # unbounded. The budget bounds ONLY the assembled provider request; the
        # persisted event log is never touched.
        context_budget = (
            self._settings_store.load().dialogue_context_budget_est_tokens
            if self._settings_store is not None
            else DIALOGUE_CONTEXT_BUDGET_DEFAULT
        )
        policy = GroundedV2Policy(context_budget_est_tokens=context_budget)
        provider_info = self._dialogue_provider_info()

        if pin_status is SessionCharacterPinStatus.PINNED_V1:
            # FAIL-CLOSED ORDER: exact definition validation runs BEFORE any
            # pinned storage/history read. No memory/state mkdir or SQLite
            # creation happens until package + both hashes verify.
            definition = self._resolve_exact_definition(self._selection_from_pin(pin))
            accepted = self._accepted_character_from_definition(definition)
            storage_root = self._pinned_storage_root(pin)
            scene = self._scene_for_display_name(row, definition.display_name)
            history = [
                {"role": _HISTORY_ROLE[m.role], "content": m.text}
                for m in self._history_for_row(row)
            ]
            result = self._run_turn(
                lambda: self._runtime.turn_with_resolved_character(
                    accepted,
                    pin.character_id,
                    policy=policy,
                    history=history,
                    user_message=text.strip(),
                    provider=factory(None),
                    provider_factory=factory,
                    memory_root=storage_root / "memory",
                    state_root=storage_root / "state",
                    session_id=session_id,
                    provider_info=provider_info,
                    scene=scene,
                    dimension_set=definition.dimension_semantics.dimension_set,
                )
            )
        else:
            entry = self._require_character(row["character_id"])
            char_root = self._char_root(entry.character_id)
            scene = self._scene_for_turn(row, entry)
            history = [
                {"role": _HISTORY_ROLE[m.role], "content": m.text}
                for m in self._history(entry.character_id, session_id)
            ]
            result = self._run_turn(
                lambda: self._runtime.turn(
                    entry.subject_id,
                    policy=policy,
                    history=history,
                    user_message=text.strip(),
                    provider=factory(None),
                    provider_factory=factory,
                    memory_root=char_root / "memory",
                    state_root=char_root / "state",
                    session_id=session_id,
                    provider_info=provider_info,
                    scene=scene,
                )
            )

        registry = self._load_registry()
        for r in registry:
            if r.get("session_id") == session_id:
                r["updated_at"] = _now_iso()
                r["activity_seq"] = self._next_activity_seq(registry)
        self._save_registry(registry)
        return CompanionTurn(
            session_id=session_id,
            response=result.response,
            messages=self._history_for_row(row),
            scene_present=scene is not None,
        )

    # ------------------------------------------------------- image jobs
    def create_image_job(
        self,
        session_id: str,
        *,
        kind: str,
        prompt: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ImageJob:
        row = self._session_row(session_id)
        self._require_executable_session(row)
        character_id = row["character_id"]
        if kind not in (KIND_CUSTOM, KIND_CONTEXT):
            raise CompanionError("invalid_request", f"unknown image kind {kind!r}")
        if kind == KIND_CUSTOM and not (isinstance(prompt, str) and prompt.strip()):
            raise CompanionError(
                "invalid_request", "a description is required for a custom image"
            )
        context: Optional[dict] = None
        if kind == KIND_CONTEXT:
            context = self._context_frame_request(row)
        try:
            return self._images.create_job(
                session_id=session_id, character_id=character_id, kind=kind,
                request_id=request_id, prompt=prompt, context=context,
                generation_spec_factory=lambda: self._images.prepare_generation_spec(
                    character_id=character_id
                ),
            )
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def image_generation_readiness(self, character_id: Optional[str] = None) -> ImageGenerationReadiness:
        """Provider-call-free readiness verdict for the image-generation product
        actions. Optionally binds the per-character ACTIVE local visual snapshot
        check."""
        cid: Optional[str] = None
        if character_id:
            cid = self._require_character(character_id).character_id
        from .character_import import SnapshotStore

        settings = self._settings_store.load() if self._settings_store is not None else None
        return evaluate_image_generation_readiness(
            settings,
            self._vault,
            snapshot_store=SnapshotStore(self._data_root),
            character_id=cid,
        )

    def _context_frame_request(self, row: dict) -> dict:
        """Structured intent for the visual pipeline (V1C): a SAFER, VISIBLE-only
        deterministic visual context.

        BOUNDED + VISIBLE-ONLY: only the current scene's externally-observable
        fields plus the last few NON-HIDDEN messages -- never the whole
        conversation, never presentation-hidden messages, never free-form scene
        text that may carry private / intended / hypothetical content.
        """
        history = self._history(row["character_id"], row["session_id"])
        hidden = set(_hidden_message_ids(row))
        excerpt = [
            {"role": m.role, "text": m.text}
            for m in history
            if m.seq not in hidden
        ][-_CONTEXT_EXCERPT_MAX:]
        scene = CompanionScene.from_row(row.get("scene"))
        return {
            "characterId": row["character_id"],
            "sessionId": row["session_id"],
            "scene": {k: getattr(scene, k) for k in _VISUAL_SCENE_FIELDS} if scene else None,
            "recentMessages": excerpt,
            "excerptLimit": _CONTEXT_EXCERPT_MAX,
        }

    def poll_image_jobs(self, session_id: str) -> Tuple[ImageJob, ...]:
        self._session_row(session_id)
        self._images.tick()
        return self._images.list_jobs(session_id=session_id)

    def get_image_job(self, job_id: str) -> ImageJob:
        # a point read -- never advances state; poll_image_jobs is the poller
        try:
            return self._images.get_job(job_id)
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def delete_image_job(self, job_id: str) -> None:
        try:
            self._images.delete_job(job_id)
        except CompanionImageError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def image_path(self, result_ref: str) -> Path:
        return self._data_root / result_ref

    # ------------------------------------------------- provider settings
    @property
    def mode(self) -> str:
        return self._mode

    def _dialogue_provider_id(self) -> str:
        if not self._secure_config_enabled:
            return str(self._provider_info.get("provider_id") or "fake")
        return self._settings_store.load().dialogue().provider_id

    def _dialogue_factory(self):
        # Release mode never silently answers as FakeKIRA: a real DIALOGUE
        # provider must be configured (Local Ollama or a cloud key in the vault).
        if self._mode == "release" and self._dialogue_provider_id() == "fake":
            raise CompanionError(
                "provider_not_configured",
                "Провайдер диалога не настроен. Откройте Настройки и выберите "
                "локальную модель или облачного провайдера.",
            )
        if not self._secure_config_enabled:
            return self._provider_factory
        return resolve_dialogue_provider_factory(
            self._settings_store.load(), self._vault,
            fake_factory=self._provider_factory,
            http_post_local=self._http_post_local,
            http_post_cloud=self._http_post_cloud,
        )

    def release_info(self, *, frontend_build_id=None) -> dict:
        from .release import build_release_manifest
        manifest = build_release_manifest(
            acceptance_root=self._acceptance_root, frontend_build_id=frontend_build_id
        )
        manifest["mode"] = self._mode
        manifest["dialogueProvider"] = self._dialogue_provider_id()
        return manifest

    def _dialogue_provider_info(self) -> dict:
        if not self._secure_config_enabled:
            return dict(self._provider_info)
        a = self._settings_store.load().dialogue()
        return {"provider_id": a.provider_id, "model": a.model_id}

    def _require_secure_config(self):
        if not self._secure_config_enabled:
            raise CompanionError("settings_unavailable", "provider settings are not enabled for this service")
        return self._settings_store, self._vault

    def settings_view(self) -> dict:
        store, vault = self._require_secure_config()
        settings = store.load()
        meta = {pid: m for pid, m in vault.list_metadata().items()}
        providers = []
        for e in all_providers(include_fake=True):
            m = meta.get(e.provider_id)
            assigned_model = None
            for role, a in settings.roles.items():
                if a.provider_id == e.provider_id:
                    assigned_model = a.model_id
            providers.append(e.to_json(
                connected=(m.connected if m else (not e.credential_required)),
                configured_model=assigned_model,
                masked_tail=(m.masked_tail if m else None),
                last_test_status=(m.last_test_status if m else None),
            ))
        role_catalog = []
        for role in ROLE_DISPLAY_ORDER:
            resolution = resolve_role_config(role, settings, vault)
            resolution["providerIds"] = list(providers_supporting_role(role))
            role_catalog.append(resolution)

        return {
            "providers": providers,
            "roles": {r: {"providerId": a.provider_id, "modelId": a.model_id}
                      for r, a in settings.roles.items()},
            "roleCatalog": role_catalog,
            "allRoles": list(ALL_ROLES),
            "roleDisplayOrder": list(ROLE_DISPLAY_ORDER),
            "runtimeWiredRoles": list(RUNTIME_WIRED_ROLES),
            "local": {
                "numCtx": settings.local_num_ctx,
                "baseUrl": settings.base_urls.get("local") or get_provider("local").default_base_url,
                "model": settings.roles.get(ROLE_DIALOGUE).model_id
                if settings.roles.get(ROLE_DIALOGUE) and settings.roles[ROLE_DIALOGUE].provider_id == "local"
                else get_provider("local").default_model,
                "numCtxMin": NUM_CTX_MIN,
                "numCtxMax": NUM_CTX_MAX,
                "kiraSafeHint": NUM_CTX_KIRA_SAFE_HINT,
                "numCtxWarning": bool(settings.local_num_ctx is not None
                                     and settings.local_num_ctx < NUM_CTX_KIRA_SAFE_HINT),
            },
            # Provider-independent DIALOGUE operational context budget (V1C
            # backend). ESTIMATED tokens -- not an exact provider token count and
            # not the Ollama local ``num_ctx``.
            "dialogueContextBudget": {
                "estTokens": settings.dialogue_context_budget_est_tokens,
                "min": DIALOGUE_CONTEXT_BUDGET_MIN,
                "default": DIALOGUE_CONTEXT_BUDGET_DEFAULT,
                "max": DIALOGUE_CONTEXT_BUDGET_MAX,
            },
            "allowCloudFallback": settings.allow_cloud_fallback,
            "dataRoutingNote": "Сообщения для этой роли отправляются выбранному провайдеру. "
                               "Дублирования между провайдерами нет.",
        }

    def set_role(self, role: str, provider_id: str, model_id: str) -> dict:
        store, _ = self._require_secure_config()
        try:
            store.set_role(role, provider_id, model_id)
        except SettingsError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        return self.settings_view()

    def resolve_media_role(self, role: str) -> dict:
        """Provider-call-free resolution metadata for one model role (foundation
        for future media adapters). Never returns a raw credential."""
        store, vault = self._require_secure_config()
        try:
            return resolve_role_config(role, store.load(), vault)
        except CompanionConfigError as exc:
            raise CompanionError(exc.code, exc.message) from exc

    def set_local_num_ctx(self, num_ctx) -> dict:
        store, _ = self._require_secure_config()
        try:
            store.set_local_num_ctx(num_ctx)
        except SettingsError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        return self.settings_view()

    def set_dialogue_context_budget(self, value) -> dict:
        """Persist the DIALOGUE operational context budget (estimated tokens).
        Delegates to the committed V1C store setter; no silent clamp/round."""
        store, _ = self._require_secure_config()
        try:
            store.set_dialogue_context_budget_est_tokens(value)
        except SettingsError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        return self.settings_view()

    def set_provider_base_url(self, provider_id: str, base_url) -> dict:
        store, _ = self._require_secure_config()
        try:
            store.set_base_url(provider_id, base_url)
        except SettingsError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        return self.settings_view()

    def store_credential(self, provider_id: str, secret: str) -> dict:
        _, vault = self._require_secure_config()
        try:
            entry = get_provider(provider_id)
        except ProviderRegistryError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        if not entry.credential_required:
            raise CompanionError("no_credential_needed", f"{entry.display_name} не требует ключа API")
        try:
            vault.store(entry.provider_id, secret)
        except CredentialError as exc:
            raise CompanionError(exc.code, exc.message) from exc  # message is secret-free by construction
        return self.settings_view()

    def delete_credential(self, provider_id: str) -> dict:
        _, vault = self._require_secure_config()
        try:
            get_provider(provider_id)
            vault.delete(provider_id)
        except (ProviderRegistryError, CredentialError) as exc:
            raise CompanionError(exc.code, exc.message) from exc
        return self.settings_view()

    def test_connection(self, provider_id: str, model_id: str = "") -> dict:
        store, vault = self._require_secure_config()
        try:
            entry = get_provider(provider_id)
        except ProviderRegistryError as exc:
            raise CompanionError(exc.code, exc.message) from exc
        result = test_provider_connection(
            entry.provider_id, model_id or entry.default_model, store.load(), vault,
            fake_factory=self._provider_factory,
            http_post_local=self._http_post_local, http_post_cloud=self._http_post_cloud,
        )
        # record status without ever touching the stored secret
        if hasattr(vault, "set_test_status"):
            vault.set_test_status(entry.provider_id, "ok" if result.get("ok") else "failed")
        return {"providerId": entry.provider_id, **result}


def _has_unavailable_cause(exc: BaseException) -> bool:
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        code = getattr(cur, "code", None)
        if code == "provider_unavailable":
            return True
        if isinstance(cur, (LocalLLMProviderError, CloudProviderError)) and getattr(cur, "code", "") == "provider_unavailable":
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _find_local_provider_error(exc: BaseException) -> Optional[LocalLLMProviderError]:
    seen = set()
    cur: Optional[BaseException] = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, LocalLLMProviderError):
            return cur
        cur = cur.__cause__ or cur.__context__
    return None
