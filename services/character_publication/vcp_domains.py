"""Deterministic pre-publication compilation of Authoring revisions to VCP.

This bounded module deliberately is not re-exported from
``services.character_publication``.  Importing the existing Character Lab
application therefore does not make the VCP distribution an unconditional
runtime dependency before operational dependency wiring is authorized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from services.character_authoring import (
    CharacterAuthoringStore,
    RevisionRecord,
    compute_snapshot_hash,
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
class AuthoringVcpDomainCompilation:
    """Exact Authoring source coordinate and its six VCP domain envelopes."""

    source: SourceProvenance
    domains: tuple[DomainEnvelope, ...]


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


def compile_authoring_revision_to_vcp_domains(
    store: CharacterAuthoringStore,
    *,
    character_id: str,
    version_id: str,
    revision_id: str,
    snapshot_hash: str,
) -> AuthoringVcpDomainCompilation:
    """Compile one exact immutable Authoring revision into six VCP domains.

    The operation reads only through ``store.load_revision`` and independently
    re-verifies the snapshot hash; it does not inspect or follow character or
    version pointers and performs no publication or package materialization.
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

    # OD-VCHAR-REC-01: biography joins core_identity; appearance becomes
    # visual_identity.identityDescription with zero package asset/prompt refs.
    structured_by_domain: dict[str, Mapping[str, Any]] = {
        "core_identity": {
            "identity": semantic["identity"],
            "biography": semantic["biography"],
        },
        "psychology": semantic["psychology"],
        "speech": semantic["speech"],
        "relationships": semantic["character_relations"],
        "visual_identity": (
            {
                "identityDescription": appearance,
                "assetRefs": [],
                "promptRefs": [],
            }
            if appearance_is_populated
            else {}
        ),
        "interaction_boundaries": semantic["boundaries"],
    }

    domains = tuple(
        _domain(
            domain_id,
            structured_by_domain[domain_id],
            populated=(
                appearance_is_populated
                if domain_id == "visual_identity"
                else _has_semantic_content(structured_by_domain[domain_id])
            ),
        )
        for domain_id in _DOMAIN_ORDER
    )

    validation = validate_required_domains(domains)
    if not validation.ok:
        issue = validation.issues[0]
        raise AuthoringVcpDomainCompilationError(
            f"compiled VCP domains are invalid: {issue.code} at "
            f"{issue.location}: {issue.message}"
        )

    return AuthoringVcpDomainCompilation(source=source, domains=domains)


__all__ = [
    "AuthoringVcpDomainCompilation",
    "AuthoringVcpDomainCompilationError",
    "AuthoringVcpSourcePinMismatchError",
    "AuthoringVcpVisualMappingError",
    "compile_authoring_revision_to_vcp_domains",
]
