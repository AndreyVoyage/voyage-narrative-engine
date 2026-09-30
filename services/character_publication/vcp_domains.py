"""Deterministic pre-publication compilation of Authoring revisions to VCP.

This bounded module deliberately is not re-exported from
``services.character_publication``.  Importing the existing Character Lab
application therefore does not make the VCP distribution an unconditional
runtime dependency before operational dependency wiring is authorized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from services.character_authoring import (
    CharacterAuthoringStore,
    RevisionRecord,
    compute_snapshot_hash,
)
from services.character_media import (
    CharacterMediaError,
    CharacterMediaStore,
    CharacterMediaValidationError,
    MediaPublishability,
    PortraitBinding,
    format_extension,
    inspect_image,
    media_root_next_to,
)

from .errors import PublicationValidationError
from .model import SourceProvenance, validate_slice1_visual_identity

from voyage_character_platform.contracts import ContentState, DomainEnvelope
import voyage_character_platform.package_v1 as vcp_package_v1
from voyage_character_platform.validation import validate_required_domains


_DOMAIN_ORDER = (
    "core_identity",
    "psychology",
    "speech",
    "relationships",
    "visual_identity",
    "interaction_boundaries",
)


class AuthoringVcpDomainCompilationError(ValueError):
    """The exact Authoring revision cannot be compiled without guessing."""


class AuthoringVcpSourcePinMismatchError(AuthoringVcpDomainCompilationError):
    """The loaded immutable revision does not match the requested source pin."""


class AuthoringVcpVisualMappingError(AuthoringVcpDomainCompilationError):
    """Authoring visual references are not proven package-ready for Slice B."""


@dataclass(frozen=True, slots=True)
class PortraitPackageFile:
    """One PUBLISHABLE Primary Portrait resolved into an exact RAW package file.

    ``relative_path`` is the Package-V1-relative path; ``content`` is the exact
    managed bytes (never an external source path). ``semantic_role`` is the
    manifest-level role token.
    """

    relative_path: str
    content: bytes
    sha256: str
    byte_length: int
    media_type: str
    semantic_role: str


@dataclass(frozen=True, slots=True)
class AuthoringVcpDomainCompilation:
    """Exact Authoring source coordinate and its VCP domain envelopes.

    Always contains the six required domains; additionally contains the optional
    ``intimacy`` domain when the authoring ``sexology`` carries content. When
    the revision carries a PUBLISHABLE Primary Portrait,
    ``primary_portrait_file`` holds the resolved RAW package file.
    """

    source: SourceProvenance
    domains: tuple[DomainEnvelope, ...]
    primary_portrait_file: Optional[PortraitPackageFile] = None


def _has_semantic_content(value: object) -> bool:
    """Recognize genuinely empty normalized Authoring values without inference."""

    if value is None or value == "":
        return False
    if isinstance(value, Mapping):
        return any(_has_semantic_content(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return any(_has_semantic_content(item) for item in value)
    return True


def _domain(
    domain_id: str,
    structured: Mapping[str, Any],
    *,
    populated: bool,
) -> DomainEnvelope:
    return DomainEnvelope(
        domain_id=domain_id,
        domain_schema_version=(
            vcp_package_v1.get_domain_schema_version_v1(domain_id)
        ),
        content_state=(
            ContentState.POPULATED
            if populated
            else ContentState.EXPLICITLY_EMPTY
        ),
        provenance_refs=(),
        structured=structured,
    )


def _load_exact_revision(
    store: CharacterAuthoringStore, source: SourceProvenance
) -> RevisionRecord:
    record = store.load_revision(
        source.source_character_id,
        source.source_version_id,
        source.source_revision_id,
    )
    if not isinstance(record, RevisionRecord):
        raise AuthoringVcpDomainCompilationError(
            "authoring store returned an object that is not a RevisionRecord"
        )
    if (
        record.character_id != source.source_character_id
        or record.version_id != source.source_version_id
        or record.revision_id != source.source_revision_id
        or record.snapshot_hash != source.source_snapshot_hash
        or compute_snapshot_hash(record.semantic) != source.source_snapshot_hash
    ):
        raise AuthoringVcpSourcePinMismatchError(
            "loaded Character Authoring revision does not match the requested "
            "character_id/version_id/revision_id/snapshot_hash"
        )
    return record


_PRIMARY_PORTRAIT_SEMANTIC_ROLE = "PRIMARY_PORTRAIT"


def _resolve_primary_portrait(
    character_id: str,
    visual_identity: Mapping[str, Any],
    store: CharacterAuthoringStore,
    media_root: Optional[Path],
) -> tuple[list[dict[str, Any]], Optional[PortraitPackageFile], bool]:
    """Resolve a PUBLISHABLE Primary Portrait into assetRefs + a RAW package file.

    AUTHORING_ONLY portraits are Lab-local only and produce an empty assetRef
    list. A PUBLISHABLE portrait is resolved from the managed media store and
    yields one ``assets/portrait/<sha256>.<ext>`` RAW package entry. Fails
    closed when the binding is malformed or the managed bytes are unavailable.

    The store root is accessed only when a PUBLISHABLE portrait actually needs
    resolution, so media-free and AUTHORING_ONLY compilations read only the
    exact revision (preserving the compiler's bounded read contract).
    """
    portrait_raw = visual_identity.get("primary_portrait")
    if portrait_raw is None:
        return [], None, False

    try:
        binding = PortraitBinding.from_dict(portrait_raw)
    except CharacterMediaValidationError as exc:
        raise AuthoringVcpVisualMappingError(
            f"primary_portrait binding is invalid: {exc}"
        ) from exc

    if binding.publishability is not MediaPublishability.PUBLISHABLE:
        return [], None, False

    root = media_root if media_root is not None else media_root_next_to(store.root)
    media = CharacterMediaStore(root)
    try:
        content = media.read_portrait_bytes(
            character_id, binding.asset_sha256, binding.format
        )
    except CharacterMediaError as exc:
        raise AuthoringVcpVisualMappingError(
            f"PUBLISHABLE primary_portrait managed bytes unavailable: {exc}"
        ) from exc

    if len(content) != binding.byte_length:
        raise AuthoringVcpVisualMappingError(
            "PUBLISHABLE primary_portrait byte_length does not match managed bytes"
        )

    # Re-validate ACTUAL managed bytes against the immutable binding. Never
    # trust revision-declared format/MIME: re-sniff and require exact equality.
    try:
        info = inspect_image(content)
    except CharacterMediaValidationError as exc:
        raise AuthoringVcpVisualMappingError(
            f"PUBLISHABLE primary_portrait managed bytes are invalid: {exc}"
        ) from exc
    if info.sha256 != binding.asset_sha256:
        raise AuthoringVcpVisualMappingError(
            "PUBLISHABLE primary_portrait SHA mismatch"
        )
    if info.byte_length != binding.byte_length:
        raise AuthoringVcpVisualMappingError(
            "PUBLISHABLE primary_portrait byte_length mismatch"
        )
    if info.format != binding.format:
        raise AuthoringVcpVisualMappingError(
            "PUBLISHABLE primary_portrait format mismatch: "
            f"actual {info.format!r} != binding {binding.format!r}"
        )
    if info.mime_type != binding.mime_type:
        raise AuthoringVcpVisualMappingError(
            "PUBLISHABLE primary_portrait MIME mismatch: "
            f"actual {info.mime_type!r} != binding {binding.mime_type!r}"
        )

    ext = format_extension(info.format)
    relative_path = f"assets/portrait/{binding.asset_sha256}.{ext}"
    asset_ref = {
        "assetId": binding.asset_sha256,
        "relativePath": relative_path,
        "sha256": binding.asset_sha256,
        "byteLength": binding.byte_length,
        "mediaType": binding.mime_type,
        "semanticRole": _PRIMARY_PORTRAIT_SEMANTIC_ROLE,
    }
    portrait_file = PortraitPackageFile(
        relative_path=relative_path,
        content=content,
        sha256=binding.asset_sha256,
        byte_length=binding.byte_length,
        media_type=binding.mime_type,
        semantic_role=_PRIMARY_PORTRAIT_SEMANTIC_ROLE,
    )
    return [asset_ref], portrait_file, True


def compile_authoring_revision_to_vcp_domains(
    store: CharacterAuthoringStore,
    *,
    character_id: str,
    version_id: str,
    revision_id: str,
    snapshot_hash: str,
    media_root: Path | str | None = None,
) -> AuthoringVcpDomainCompilation:
    """Compile one exact immutable Authoring revision into VCP domains.

    The operation reads only through ``store.load_revision`` and independently
    re-verifies the snapshot hash; it does not inspect or follow character or
    version pointers and performs no publication or package materialization.

    Output is the six required domains plus, when ``semantic.sexology`` carries
    meaningful content, the optional ``intimacy`` domain (OD-LAB-VCP-INTIMACY-
    MAPPING-01).
    """

    try:
        source = SourceProvenance(
            source_character_id=character_id,
            source_version_id=version_id,
            source_revision_id=revision_id,
            source_snapshot_hash=snapshot_hash,
        )
    except PublicationValidationError as exc:
        raise AuthoringVcpDomainCompilationError(
            "invalid exact Character Authoring source coordinate"
        ) from exc

    record = _load_exact_revision(store, source)

    try:
        validate_slice1_visual_identity(record.semantic)
    except PublicationValidationError as exc:
        raise AuthoringVcpVisualMappingError(
            "authoring visual_identity contains unresolved references that are "
            "not package-ready in Slice B"
        ) from exc

    semantic = record.semantic.to_dict()
    appearance = semantic["appearance"]
    appearance_is_populated = _has_semantic_content(appearance)

    asset_refs, primary_portrait_file, portrait_populated = _resolve_primary_portrait(
        source.source_character_id,
        semantic["visual_identity"],
        store,
        media_root,
    )

    visual_identity_content: dict[str, Any] = {}
    if appearance_is_populated:
        visual_identity_content["identityDescription"] = appearance
    visual_identity_content["assetRefs"] = asset_refs
    visual_identity_content["promptRefs"] = []
    visual_identity_populated = appearance_is_populated or portrait_populated

    # OD-VCHAR-REC-01: biography joins core_identity; appearance becomes
    # visual_identity.identityDescription. A PUBLISHABLE Primary Portrait
    # additionally populates visual_identity.assetRefs.
    structured_by_domain: dict[str, Mapping[str, Any]] = {
        "core_identity": {
            "identity": semantic["identity"],
            "biography": semantic["biography"],
        },
        "psychology": semantic["psychology"],
        "speech": semantic["speech"],
        "relationships": semantic["character_relations"],
        "visual_identity": (
            visual_identity_content if visual_identity_populated else {}
        ),
        "interaction_boundaries": semantic["boundaries"],
    }

    # OD-LAB-VCP-INTIMACY-MAPPING-01: sexology is OPTIONAL. It compiles to the
    # VCP optional ``intimacy`` domain ONLY when it carries meaningful content;
    # an absent or fully-empty sexology omits the domain entirely. Intimacy is
    # appended AFTER the six required domains and never enters REQUIRED_DOMAIN_IDS.
    sexology = semantic.get("sexology")
    intimacy_populated = isinstance(sexology, Mapping) and _has_semantic_content(
        sexology
    )

    domain_list = [
        _domain(
            domain_id,
            structured_by_domain[domain_id],
            populated=(
                visual_identity_populated
                if domain_id == "visual_identity"
                else _has_semantic_content(structured_by_domain[domain_id])
            ),
        )
        for domain_id in _DOMAIN_ORDER
    ]
    if intimacy_populated:
        domain_list.append(_domain("intimacy", sexology, populated=True))
    domains = tuple(domain_list)

    validation = validate_required_domains(domains)
    if not validation.ok:
        issue = validation.issues[0]
        raise AuthoringVcpDomainCompilationError(
            f"compiled VCP domains are invalid: {issue.code} at "
            f"{issue.location}: {issue.message}"
        )

    return AuthoringVcpDomainCompilation(
        source=source,
        domains=domains,
        primary_portrait_file=primary_portrait_file,
    )


__all__ = [
    "AuthoringVcpDomainCompilation",
    "AuthoringVcpDomainCompilationError",
    "AuthoringVcpSourcePinMismatchError",
    "AuthoringVcpVisualMappingError",
    "compile_authoring_revision_to_vcp_domains",
]
