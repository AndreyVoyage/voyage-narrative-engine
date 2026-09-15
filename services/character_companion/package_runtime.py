#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Character Package V1 -> neutral runtime-definition adapter.

The adapter has exact-binding semantics only. It does not discover a latest
release, install or activate packages, select a character, or touch sessions,
memory, runtime policy, catalog, provider configuration, or production data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.character_companion.character_import.package_v1 import (
    CANONICAL_JSON_V1,
    CharacterPackageV1Error,
    PackageFileDescriptor,
    VerifiedCharacterPackage,
    verify_character_package_v1,
)
from services.character_core.dimensions import (
    DimensionDefinitionError,
    DimensionSet,
)
from services.character_runtime.definition import (
    RuntimeCharacterDefinition,
    RuntimeDefinitionAdapterIdentity,
    RuntimeDefinitionError,
    RuntimeDefinitionSourceKind,
    RuntimeDimensionSemantics,
    RuntimePackageIdentity,
)
from services.crp_authoring.acceptance_store import (
    ACCEPTANCE_ARTIFACT_TYPE,
    ACCEPTANCE_SCHEMA_VERSION,
    acceptance_record_from_jsonable,
)
from services.crp_authoring.auditor_checks import compute_package_hash
from services.crp_authoring.candidate_package import PackageStatus
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package
from services.crp_authoring.errors import CrpValidationError

__all__ = [
    "CRP_IMPORT_SOURCE_KIND",
    "ExactPackageRuntimeBinding",
    "PACKAGE_RUNTIME_ADAPTER_ID",
    "PACKAGE_RUNTIME_ADAPTER_VERSION",
    "PackageRuntimeError",
    "load_runtime_character_definition",
]


PACKAGE_RUNTIME_ADAPTER_ID = "character-package-v1-crp-import"
PACKAGE_RUNTIME_ADAPTER_VERSION = "1"
CRP_IMPORT_SOURCE_KIND = RuntimeDefinitionSourceKind.PACKAGE_V1_CRP_IMPORT

_SOURCE_CANDIDATE_PATH = "provenance/source_candidate.json"
_SOURCE_ACCEPTANCE_PATH = "provenance/source_acceptance.json"
_DIMENSION_SEMANTICS_PATH = "extensions/dimension_semantics/v1.json"
_VISUAL_IDENTITY_PATH = "domains/visual_identity.json"

_REQUIRED_PROFILE = {
    _SOURCE_CANDIDATE_PATH: "SOURCE_CANDIDATE_RECORD",
    _SOURCE_ACCEPTANCE_PATH: "SOURCE_ACCEPTANCE_RECORD",
    _DIMENSION_SEMANTICS_PATH: "DIMENSION_SEMANTICS_EXTENSION",
    _VISUAL_IDENTITY_PATH: "DOMAIN",
}
_DIMENSION_EXTENSION_REQUIRED_FIELDS = frozenset(
    {
        "character_id",
        "extension_type",
        "extension_version",
        "target_accepted_source_hash",
        "dimensions",
    }
)
_DIMENSION_EXTENSION_OPTIONAL_FIELDS = frozenset(
    {"core_contract_version", "description"}
)
_VISUAL_IDENTITY_FIELDS = frozenset(
    {
        "content",
        "contentState",
        "domainId",
        "domainSchemaVersion",
        "provenanceRefs",
    }
)


class PackageRuntimeError(RuntimeError):
    """The exact package cannot truthfully produce this runtime definition."""


def _non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PackageRuntimeError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ExactPackageRuntimeBinding:
    """Caller-supplied exact Package V1 identity; there is no latest lookup."""

    package_root: Path
    expected_character_id: str
    expected_release_id: str
    expected_package_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_root", Path(self.package_root))
        _non_empty(self.expected_character_id, "expected_character_id")
        _non_empty(self.expected_release_id, "expected_release_id")
        _non_empty(self.expected_package_hash, "expected_package_hash")


def _descriptor(
    package: VerifiedCharacterPackage,
    relative_path: str,
    semantic_role: str,
) -> PackageFileDescriptor:
    matches = tuple(item for item in package.files if item.path == relative_path)
    if len(matches) != 1:
        raise PackageRuntimeError(
            f"CRP-import profile requires exactly one {relative_path!r} descriptor"
        )
    item = matches[0]
    if (
        not item.required
        or item.normalization != CANONICAL_JSON_V1
        or item.semantic_role != semantic_role
    ):
        raise PackageRuntimeError(
            f"{relative_path!r} is not the required canonical {semantic_role} descriptor"
        )
    return item


def _read_descriptor_bound_json(
    package: VerifiedCharacterPackage,
    relative_path: str,
    semantic_role: str,
) -> tuple[dict[str, Any], str]:
    """Read once, then bind the exact consumed bytes back to S6's descriptor.

    S6 has already validated the whole package and canonical JSON. The bounded
    length/SHA check here closes the verify-then-read gap for the bytes this
    adapter semantically consumes.
    """

    item = _descriptor(package, relative_path, semantic_role)
    path = package.root.joinpath(*relative_path.split("/"))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PackageRuntimeError(
            f"verified package file {relative_path!r} is no longer readable"
        ) from exc
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != item.byte_length or digest != item.sha256.lower():
        raise PackageRuntimeError(
            f"verified package file {relative_path!r} changed after S6 verification"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageRuntimeError(f"{relative_path!r} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise PackageRuntimeError(f"{relative_path!r} root must be an object")
    return payload, digest


def _load_source_acceptance(payload: dict[str, Any]):
    expected_fields = {"artifact_type", "schema_version", "acceptance_record"}
    if set(payload) != expected_fields:
        raise PackageRuntimeError(
            "source acceptance envelope has missing or unknown fields"
        )
    if payload["artifact_type"] != ACCEPTANCE_ARTIFACT_TYPE:
        raise PackageRuntimeError("source acceptance has wrong artifact_type")
    if payload["schema_version"] != ACCEPTANCE_SCHEMA_VERSION:
        raise PackageRuntimeError("source acceptance has wrong schema_version")
    try:
        return acceptance_record_from_jsonable(payload["acceptance_record"])
    except CrpValidationError as exc:
        raise PackageRuntimeError(f"source acceptance is invalid: {exc}") from exc


def _load_dimension_semantics(
    payload: dict[str, Any],
) -> RuntimeDimensionSemantics:
    actual_fields = set(payload)
    missing = _DIMENSION_EXTENSION_REQUIRED_FIELDS - actual_fields
    unknown = actual_fields - (
        _DIMENSION_EXTENSION_REQUIRED_FIELDS | _DIMENSION_EXTENSION_OPTIONAL_FIELDS
    )
    if missing or unknown:
        raise PackageRuntimeError(
            "dimension semantics extension has missing or unknown fields: "
            f"missing={sorted(missing)!r}, unknown={sorted(unknown)!r}"
        )
    character_id = payload["character_id"]
    extension_type = payload["extension_type"]
    extension_version = payload["extension_version"]
    target_hash = payload["target_accepted_source_hash"]
    core_version = payload.get("core_contract_version")
    description = payload.get("description")
    if not isinstance(character_id, str) or not character_id.strip():
        raise PackageRuntimeError("dimension semantics character_id is invalid")
    if extension_type != "dimension_semantics":
        raise PackageRuntimeError("dimension semantics extension_type is unsupported")
    if isinstance(extension_version, bool) or extension_version != 1:
        raise PackageRuntimeError("dimension semantics extension_version is unsupported")
    if not isinstance(target_hash, str) or not target_hash.strip():
        raise PackageRuntimeError("dimension semantics target hash is invalid")
    if core_version is not None and (
        not isinstance(core_version, str) or not core_version.strip()
    ):
        raise PackageRuntimeError("dimension semantics core contract version is invalid")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        raise PackageRuntimeError("dimension semantics description is invalid")
    raw_dimensions = payload["dimensions"]
    try:
        dimension_set = DimensionSet.from_dicts(raw_dimensions)
    except DimensionDefinitionError as exc:
        raise PackageRuntimeError(f"dimension semantics content is invalid: {exc}") from exc
    try:
        return RuntimeDimensionSemantics(
            character_id=character_id,
            extension_type=extension_type,
            extension_version=extension_version,
            target_accepted_source_hash=target_hash,
            core_contract_version=core_version,
            dimension_set=dimension_set,
        )
    except RuntimeDefinitionError as exc:
        raise PackageRuntimeError(f"dimension semantics binding is invalid: {exc}") from exc


def _load_visual_identity_state(payload: dict[str, Any]) -> str:
    if set(payload) != _VISUAL_IDENTITY_FIELDS:
        raise PackageRuntimeError("visual identity domain has missing or unknown fields")
    if payload["domainId"] != "visual_identity":
        raise PackageRuntimeError("visual identity domain has wrong domainId")
    if payload["domainSchemaVersion"] != "1.0":
        raise PackageRuntimeError("visual identity domain schema is unsupported")
    if payload["contentState"] != "EXPLICITLY_EMPTY":
        raise PackageRuntimeError(
            "S8A supports only EXPLICITLY_EMPTY visual identity; visual binding belongs to S8C"
        )
    if payload["content"] != {"legacyPayload": [], "structured": {}}:
        raise PackageRuntimeError(
            "EXPLICITLY_EMPTY visual identity contains unexpected authored content"
        )
    if payload["provenanceRefs"] != []:
        raise PackageRuntimeError(
            "EXPLICITLY_EMPTY visual identity contains unexpected provenance refs"
        )
    return "EXPLICITLY_EMPTY"


def _runtime_definition_hash(
    *,
    package: VerifiedCharacterPackage,
    source_acceptance,
    candidate,
    dimension_semantics: RuntimeDimensionSemantics,
    visual_identity_state: str,
    consumed_digests: dict[str, str],
) -> str:
    """Hash a path-free canonical identity document for this exact adapter view."""

    material = {
        "adapter": {
            "id": PACKAGE_RUNTIME_ADAPTER_ID,
            "version": PACKAGE_RUNTIME_ADAPTER_VERSION,
        },
        "candidate": {
            "descriptorSha256": consumed_digests[_SOURCE_CANDIDATE_PATH],
            "packageId": candidate.package_id,
            "packageVersion": candidate.package_version,
            "status": candidate.status.value,
            "subjectId": candidate.subject_id,
        },
        "dimensionSemantics": {
            "characterId": dimension_semantics.character_id,
            "coreContractVersion": dimension_semantics.core_contract_version,
            "descriptorSha256": consumed_digests[_DIMENSION_SEMANTICS_PATH],
            "extensionType": dimension_semantics.extension_type,
            "extensionVersion": dimension_semantics.extension_version,
            "targetAcceptedSourceHash": (
                dimension_semantics.target_accepted_source_hash
            ),
        },
        "hashContract": "RUNTIME_CHARACTER_DEFINITION_V1",
        "package": {
            "authorityClass": package.authority_class,
            "characterId": package.character_id,
            "displayName": package.display_name,
            "manifestSchemaVersion": package.manifest_schema_version,
            "packageHash": package.package_hash,
            "packageOrigin": package.package_origin,
            "packageSchemaVersion": package.package_schema_version,
            "releaseId": package.release_id,
        },
        "sourceAcceptance": {
            "acceptanceId": source_acceptance.acceptance_id,
            "acceptedSemanticHash": source_acceptance.package_hash,
            "decision": source_acceptance.decision.value,
            "descriptorSha256": consumed_digests[_SOURCE_ACCEPTANCE_PATH],
            "packageId": source_acceptance.package_id,
            "packageVersion": source_acceptance.package_version,
            "subjectId": source_acceptance.subject_id,
        },
        "sourceKind": CRP_IMPORT_SOURCE_KIND.value,
        "visualIdentity": {
            "contentState": visual_identity_state,
            "descriptorSha256": consumed_digests[_VISUAL_IDENTITY_PATH],
        },
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _verify_exact_identity(
    package: VerifiedCharacterPackage,
    binding: ExactPackageRuntimeBinding,
) -> None:
    if package.character_id != binding.expected_character_id:
        raise PackageRuntimeError(
            f"package characterId {package.character_id!r} does not match exact binding"
        )
    if package.release_id != binding.expected_release_id:
        raise PackageRuntimeError(
            f"package releaseId {package.release_id!r} does not match exact binding"
        )
    if package.package_hash != binding.expected_package_hash.lower():
        raise PackageRuntimeError("packageHash does not match exact binding")
    if package.authority_class != "LEGACY_COMPAT":
        raise PackageRuntimeError(
            "CRP-import runtime profile requires package authority LEGACY_COMPAT"
        )
    if package.package_origin != "LEGACY_IMPORT":
        raise PackageRuntimeError(
            "CRP-import runtime profile requires package origin LEGACY_IMPORT"
        )


def load_runtime_character_definition(
    binding: ExactPackageRuntimeBinding,
) -> RuntimeCharacterDefinition:
    """Verify an exact CRP-import Package V1 and return its neutral definition."""

    if not isinstance(binding, ExactPackageRuntimeBinding):
        raise PackageRuntimeError("binding must be an ExactPackageRuntimeBinding")
    try:
        verified = verify_character_package_v1(
            binding.package_root,
            expected_package_hash=binding.expected_package_hash,
        )
    except CharacterPackageV1Error as exc:
        raise PackageRuntimeError(f"Package V1 verification failed: {exc}") from exc
    _verify_exact_identity(verified, binding)

    payloads: dict[str, dict[str, Any]] = {}
    digests: dict[str, str] = {}
    for relative_path, semantic_role in _REQUIRED_PROFILE.items():
        payload, digest = _read_descriptor_bound_json(
            verified, relative_path, semantic_role
        )
        payloads[relative_path] = payload
        digests[relative_path] = digest

    try:
        candidate = rehydrate_candidate_package(payloads[_SOURCE_CANDIDATE_PATH])
    except CrpValidationError as exc:
        raise PackageRuntimeError(f"source Candidate is invalid: {exc}") from exc
    source_acceptance = _load_source_acceptance(payloads[_SOURCE_ACCEPTANCE_PATH])
    dimension_semantics = _load_dimension_semantics(
        payloads[_DIMENSION_SEMANTICS_PATH]
    )
    visual_identity_state = _load_visual_identity_state(
        payloads[_VISUAL_IDENTITY_PATH]
    )

    if source_acceptance.decision is not PackageStatus.HUMAN_APPROVED:
        raise PackageRuntimeError("source acceptance is not HUMAN_APPROVED")
    if source_acceptance.subject_id != candidate.subject_id:
        raise PackageRuntimeError("source acceptance subject does not match Candidate")
    if source_acceptance.package_id != candidate.package_id:
        raise PackageRuntimeError("source acceptance package_id does not match Candidate")
    if source_acceptance.package_version != candidate.package_version:
        raise PackageRuntimeError("source acceptance package_version does not match Candidate")
    accepted_semantic_hash = compute_package_hash(candidate)
    if source_acceptance.package_hash != accepted_semantic_hash:
        raise PackageRuntimeError(
            "source acceptance semantic hash does not match the rehydrated Candidate"
        )
    if candidate.subject_id != verified.character_id:
        raise PackageRuntimeError("package characterId does not match embedded Candidate")
    if dimension_semantics.character_id != verified.character_id:
        raise PackageRuntimeError(
            "package characterId does not match dimension semantics extension"
        )
    if dimension_semantics.target_accepted_source_hash != accepted_semantic_hash:
        raise PackageRuntimeError(
            "dimension semantics accepted-source hash does not match source acceptance"
        )

    # Re-run the existing whole-package gate after semantic reads. Together
    # with descriptor-bound consumed bytes above, this detects bounded TOCTOU
    # changes without forking S6 verification.
    try:
        post_read = verify_character_package_v1(
            binding.package_root,
            expected_package_hash=binding.expected_package_hash,
        )
    except CharacterPackageV1Error as exc:
        raise PackageRuntimeError(
            f"Package V1 changed during runtime-definition load: {exc}"
        ) from exc
    _verify_exact_identity(post_read, binding)
    if post_read.files != verified.files or post_read.package_hash != verified.package_hash:
        raise PackageRuntimeError("Package V1 identity changed during runtime-definition load")

    runtime_hash = _runtime_definition_hash(
        package=verified,
        source_acceptance=source_acceptance,
        candidate=candidate,
        dimension_semantics=dimension_semantics,
        visual_identity_state=visual_identity_state,
        consumed_digests=digests,
    )
    try:
        return RuntimeCharacterDefinition(
            source_kind=CRP_IMPORT_SOURCE_KIND,
            package_identity=RuntimePackageIdentity(
                character_id=verified.character_id,
                release_id=verified.release_id,
                display_name=verified.display_name,
                package_hash=verified.package_hash,
                authority_class=verified.authority_class,
                package_origin=verified.package_origin,
                package_schema_version=verified.package_schema_version,
                manifest_schema_version=verified.manifest_schema_version,
            ),
            adapter_identity=RuntimeDefinitionAdapterIdentity(
                adapter_id=PACKAGE_RUNTIME_ADAPTER_ID,
                adapter_version=PACKAGE_RUNTIME_ADAPTER_VERSION,
            ),
            source_acceptance=source_acceptance,
            candidate=candidate,
            dimension_semantics=dimension_semantics,
            visual_identity_state=visual_identity_state,
            runtime_definition_hash=runtime_hash,
        )
    except RuntimeDefinitionError as exc:
        raise PackageRuntimeError(f"runtime definition is inconsistent: {exc}") from exc
