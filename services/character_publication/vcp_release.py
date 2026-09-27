"""Pure deterministic ACCEPTED_RELEASE logical-file compiler (LAB-L2).

Combines one exact immutable Authoring revision (through the Slice B domain
compiler), its LAB-L1 immutable ``ApprovalEvidence``, an explicit ``release_id``
and an explicit ``display_name`` into the exact Package V1 logical file mapping
that a later slice hands to ``materialize_package_v1``.

The module performs no filesystem writes, reads no clock, and creates no
manifest, ``packageHash``, ``.vchar``, release record, or current designation.
Like ``vcp_domains`` it is deliberately not re-exported from
``services.character_publication`` so importing the Lab does not make the VCP
distribution an unconditional runtime dependency.

Native Lab V1 provenance profile (OWNER ratified): the immutable authoring
source carries no factual VCP ``authoring_method``, so
``provenance/provenance.json`` is the canonical empty collection and no
``ProvenanceRecord`` is fabricated. ``decided_by`` is approval provenance and is
never reinterpreted as authorship.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from services.character_authoring import (
    APPROVAL_DECISION_HUMAN_APPROVED,
    ApprovalEvidence,
    CharacterAuthoringError,
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStore,
    validate_decided_at,
    validate_decided_by,
)

from .model import SourceProvenance
from .vcp_domains import (
    AuthoringVcpDomainCompilation,
    AuthoringVcpDomainCompilationError,
    compile_authoring_revision_to_vcp_domains,
)

from voyage_character_platform.canonical_json import (
    CanonicalizationError,
    canonical_json_bytes,
)
from voyage_character_platform.contracts import (
    AuthorityClass,
    DomainEnvelope,
    PackageMetadata,
    PackageOrigin,
)
from voyage_character_platform.hashing import sha256_bytes
from voyage_character_platform.package_v1 import (
    CANONICAL_JSON_NORMALIZATION,
    PACKAGE_SCHEMA_VERSION,
    PackageV1Error,
    PackageV1File,
    create_manifest,
)
from voyage_character_platform.validation import (
    REQUIRED_DOMAIN_IDS,
    validate_package_metadata,
)


AGGREGATE_CANDIDATE_ID_PREFIX = "vcprec1-"
AGGREGATE_CANDIDATE_ID_SCHEMA_VERSION = "vcp_aggregate_candidate_id/1.0"
AGGREGATE_SCHEMA_VERSION = "vcp_aggregate_candidate/1.0"

PACKAGE_PATH = "package.json"
ACCEPTANCE_PATH = "provenance/acceptance.json"
PROVENANCE_PATH = "provenance/provenance.json"
CONTRADICTIONS_PATH = "provenance/contradictions.json"
UNKNOWNS_PATH = "unknowns/unknowns.json"

# OD-VCP-OPTIONAL-ACCEPTED-DOMAINS-01: for Lab V1 the only accepted optional
# publication domain is intimacy. Unknown/future optional domains stay rejected.
ACCEPTED_OPTIONAL_DOMAIN_IDS = frozenset({"intimacy"})
ACCEPTED_DOMAIN_IDS = REQUIRED_DOMAIN_IDS | ACCEPTED_OPTIONAL_DOMAIN_IDS


class AuthoringVcpReleaseCompilationError(AuthoringVcpDomainCompilationError):
    """The release cannot be compiled from the supplied exact inputs."""


class AuthoringVcpApprovalEvidenceError(AuthoringVcpReleaseCompilationError):
    """Approval evidence is missing, invalid, or not bound to the source."""


@dataclass(frozen=True, slots=True)
class AuthoringVcpReleaseCompilation:
    """Deterministic logical ACCEPTED_RELEASE ready for ``materialize_package_v1``.

    ``files`` is the exact ``Mapping[str, PackageV1File]`` to materialize. It
    contains no ``manifest.json`` (Shared Core creates it) and no optional
    asset or prompt index under the zero-artifact V1 profile.
    """

    source: SourceProvenance
    approval: ApprovalEvidence
    metadata: PackageMetadata
    domains: tuple[DomainEnvelope, ...]
    domain_hashes_at_accept: Mapping[str, str]
    aggregate_candidate_id: str
    aggregate_hash: str
    acceptance_record_hash: str
    files: Mapping[str, PackageV1File]


def compute_aggregate_candidate_id(source: SourceProvenance) -> str:
    """OD-VCHAR-REC-02 native producer formula, from the exact source only."""

    digest = sha256_bytes(
        canonical_json_bytes(
            {
                "aggregate_candidate_id_schema_version": (
                    AGGREGATE_CANDIDATE_ID_SCHEMA_VERSION
                ),
                "character_id": source.source_character_id,
                "version_id": source.source_version_id,
                "revision_id": source.source_revision_id,
                "snapshot_hash": source.source_snapshot_hash,
            }
        )
    )
    return f"{AGGREGATE_CANDIDATE_ID_PREFIX}{digest}"


def compute_aggregate_hash(
    character_id: str,
    aggregate_candidate_id: str,
    domain_hashes_at_accept: Mapping[str, str],
) -> str:
    """OD-VCHAR-REC-02 namespaced aggregate descriptor hash."""

    return sha256_bytes(
        canonical_json_bytes(
            {
                "aggregate_schema_version": AGGREGATE_SCHEMA_VERSION,
                "characterId": character_id,
                "aggregateCandidateId": aggregate_candidate_id,
                "domainHashesAtAccept": dict(domain_hashes_at_accept),
            }
        )
    )


def _validated_text(value: object, field: str) -> str:
    """Return ``value`` unchanged if it is a valid, NFC, non-blank string."""

    if not isinstance(value, str) or not value.strip():
        raise AuthoringVcpReleaseCompilationError(
            f"{field} must be an explicitly supplied non-empty string"
        )
    if unicodedata.normalize("NFC", value) != value:
        raise AuthoringVcpReleaseCompilationError(
            f"{field} must already be NFC-normalized"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise AuthoringVcpReleaseCompilationError(
            f"{field} is not valid Unicode text"
        ) from exc
    return value


def _verify_approval_binding(
    source: SourceProvenance, approval: object
) -> ApprovalEvidence:
    if not isinstance(approval, ApprovalEvidence):
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence must be a LAB-L1 ApprovalEvidence"
        )
    if (
        approval.character_id != source.source_character_id
        or approval.version_id != source.source_version_id
        or approval.revision_id != source.source_revision_id
        or approval.snapshot_hash != source.source_snapshot_hash
    ):
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence is not bound to the exact character_id/"
            "version_id/revision_id/snapshot_hash being compiled"
        )
    if approval.decision != APPROVAL_DECISION_HUMAN_APPROVED:
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence decision must be HUMAN_APPROVED"
        )
    try:
        validate_decided_by(approval.decided_by)
        validate_decided_at(approval.decided_at)
    except CharacterAuthoringError as exc:
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence decided_by/decided_at are invalid"
        ) from exc
    return approval


def _domain_bytes(envelope: DomainEnvelope) -> bytes:
    return canonical_json_bytes(envelope.to_dict())


def _canonical_file(content: bytes, semantic_role: str) -> PackageV1File:
    return PackageV1File(
        content=content,
        semantic_role=semantic_role,
        normalization=CANONICAL_JSON_NORMALIZATION,
        required=True,
    )


def build_authoring_release_compilation(
    domain_compilation: AuthoringVcpDomainCompilation,
    approval_evidence: ApprovalEvidence,
    *,
    release_id: str,
    display_name: str,
) -> AuthoringVcpReleaseCompilation:
    """Compile the logical release from already-compiled exact inputs.

    Pure: the result depends only on the arguments.
    """

    if not isinstance(domain_compilation, AuthoringVcpDomainCompilation):
        raise AuthoringVcpReleaseCompilationError(
            "domain compilation must be a Slice B AuthoringVcpDomainCompilation"
        )
    source = domain_compilation.source
    approval = _verify_approval_binding(source, approval_evidence)
    release_id = _validated_text(release_id, "release_id")
    display_name = _validated_text(display_name, "display_name")

    domains = tuple(domain_compilation.domains)
    domain_ids = {domain.domain_id for domain in domains}
    if len(domain_ids) != len(domains):
        raise AuthoringVcpReleaseCompilationError(
            "domain compilation contains duplicate domain IDs"
        )
    if domain_ids != REQUIRED_DOMAIN_IDS and domain_ids != ACCEPTED_DOMAIN_IDS:
        raise AuthoringVcpReleaseCompilationError(
            "domain compilation must contain exactly the six required domains, "
            "optionally plus the accepted optional 'intimacy' domain"
        )

    try:
        domain_files = {
            domain.domain_id: _domain_bytes(domain) for domain in domains
        }
        domain_hashes = {
            domain_id: sha256_bytes(domain_files[domain_id])
            for domain_id in sorted(domain_files)
        }
        character_id = source.source_character_id
        aggregate_candidate_id = compute_aggregate_candidate_id(source)
        aggregate_hash = compute_aggregate_hash(
            character_id, aggregate_candidate_id, domain_hashes
        )
        acceptance_bytes = canonical_json_bytes(
            {
                "characterId": character_id,
                "aggregateCandidateId": aggregate_candidate_id,
                "aggregateHash": aggregate_hash,
                "domainHashesAtAccept": domain_hashes,
                "decision": approval.decision,
                "decidedBy": approval.decided_by,
                "decidedAt": approval.decided_at,
            }
        )
        acceptance_record_hash = sha256_bytes(acceptance_bytes)

        metadata = PackageMetadata(
            package_schema_version=PACKAGE_SCHEMA_VERSION,
            character_id=character_id,
            release_id=release_id,
            display_name=display_name,
            authority_class=AuthorityClass.ACCEPTED_RELEASE,
            package_origin=PackageOrigin.ACCEPTED_AGGREGATE,
            accepted_aggregate_hash=aggregate_hash,
            acceptance_record_hash=acceptance_record_hash,
        )
        validation = validate_package_metadata(metadata)
        if not validation.ok:
            issue = validation.issues[0]
            raise AuthoringVcpReleaseCompilationError(
                f"package metadata is invalid: {issue.code} at "
                f"{issue.location}: {issue.message}"
            )

        files: dict[str, PackageV1File] = {
            PACKAGE_PATH: _canonical_file(
                canonical_json_bytes(metadata.to_dict()), "PACKAGE_METADATA"
            ),
            ACCEPTANCE_PATH: _canonical_file(acceptance_bytes, "ACCEPTANCE"),
            PROVENANCE_PATH: _canonical_file(
                canonical_json_bytes({"provenance": []}), "PROVENANCE"
            ),
            CONTRADICTIONS_PATH: _canonical_file(
                canonical_json_bytes({"contradictions": []}), "CONTRADICTIONS"
            ),
            UNKNOWNS_PATH: _canonical_file(
                canonical_json_bytes({"unknowns": []}), "UNKNOWNS"
            ),
        }
        for domain_id, content in domain_files.items():
            files[f"domains/{domain_id}.json"] = _canonical_file(content, "DOMAIN")
        ordered_files = dict(sorted(files.items()))

        # Pure self-check through the authoritative Package V1 contract: path
        # safety, required file set, metadata, and acceptance-record binding.
        create_manifest(ordered_files)
    except AuthoringVcpReleaseCompilationError:
        raise
    except (PackageV1Error, CanonicalizationError, ValueError) as exc:
        raise AuthoringVcpReleaseCompilationError(
            f"release does not satisfy the Package V1 contract: {exc}"
        ) from exc

    return AuthoringVcpReleaseCompilation(
        source=source,
        approval=approval,
        metadata=metadata,
        domains=domains,
        domain_hashes_at_accept=MappingProxyType(domain_hashes),
        aggregate_candidate_id=aggregate_candidate_id,
        aggregate_hash=aggregate_hash,
        acceptance_record_hash=acceptance_record_hash,
        files=MappingProxyType(ordered_files),
    )


def compile_authoring_release(
    store: CharacterAuthoringStore,
    *,
    character_id: str,
    version_id: str,
    revision_id: str,
    snapshot_hash: str,
    release_id: str,
    display_name: str,
) -> AuthoringVcpReleaseCompilation:
    """Compile one exact approved Authoring revision into logical release files.

    Reads only ``store.load_revision`` (through Slice B) and
    ``store.load_approval_evidence``. It never follows character or version
    pointers, and an approved lifecycle state without LAB-L1 evidence cannot
    compile. Lifecycle gating is the caller's responsibility.
    """

    domain_compilation = compile_authoring_revision_to_vcp_domains(
        store,
        character_id=character_id,
        version_id=version_id,
        revision_id=revision_id,
        snapshot_hash=snapshot_hash,
    )
    source = domain_compilation.source
    try:
        approval = store.load_approval_evidence(
            source.source_character_id,
            source.source_version_id,
            source.source_revision_id,
        )
    except CharacterAuthoringNotFoundError as exc:
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence is missing for the exact revision; historical "
            "approvals without LAB-L1 evidence cannot be compiled"
        ) from exc
    except CharacterAuthoringError as exc:
        raise AuthoringVcpApprovalEvidenceError(
            "approval evidence failed integrity verification"
        ) from exc

    return build_authoring_release_compilation(
        domain_compilation,
        approval,
        release_id=release_id,
        display_name=display_name,
    )


__all__ = [
    "AGGREGATE_CANDIDATE_ID_PREFIX",
    "AGGREGATE_CANDIDATE_ID_SCHEMA_VERSION",
    "AGGREGATE_SCHEMA_VERSION",
    "ACCEPTANCE_PATH",
    "CONTRADICTIONS_PATH",
    "PACKAGE_PATH",
    "PROVENANCE_PATH",
    "UNKNOWNS_PATH",
    "AuthoringVcpApprovalEvidenceError",
    "AuthoringVcpReleaseCompilation",
    "AuthoringVcpReleaseCompilationError",
    "build_authoring_release_compilation",
    "compile_authoring_release",
    "compute_aggregate_candidate_id",
    "compute_aggregate_hash",
]
