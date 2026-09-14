#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Companion-owned controlled Character Canon import + local visual snapshot.

Character Canon is an AUTHORING SOURCE ONLY. This package reads it read-only
during an explicit import/update, COPIES the approved reference bytes and the
normalized physical identity into a Companion-owned, versioned local snapshot
under the Companion data root, and never depends on Character Canon again for
normal runtime.

Public surface:

    CharacterImportService(data_root)
        .import_character(canon_root, character_id, operation="add"|"update",
                         *, source_character_id=None)
            # character_id      = Companion-local identity (storage / catalog / manifest)
            # source_character_id = exact Character Canon identity (source boundary
            #                       only; defaults to character_id; never case-folded)
        .list_snapshot_versions(character_id)
        .load_snapshot(character_id, version)
        .load_active_snapshot(character_id)
        .active_version(character_id)
        .activate_snapshot(character_id, version)

See docs/character_companion/VISUAL_PIPELINE_VENDOR_PROVENANCE_V1.md for the
source-repo provenance of the vendored/adapted primitives.
"""

from __future__ import annotations

from .canon_model import CanonReference, CharacterCanonSnapshot, Provenance
from .canon_reader import SNAPSHOT_SCHEMA_VERSION as CANON_SNAPSHOT_SCHEMA_VERSION
from .canon_reader import read_character_canon
from .canon_status import is_known_canon_status, is_production_approved
from .errors import (
    AmbiguousCharacterError,
    AssetIdCollisionError,
    CanonFormatError,
    CanonRootMissingError,
    CanonStatusUnknownError,
    CharacterImportError,
    CharacterNotFoundError,
    CrossCharacterDuplicateError,
    FormatMismatchError,
    ProductionNotAllowedError,
    ReferenceImportError,
    ReferenceManifestError,
    ReferencePathSafetyError,
    ReferenceValidationError,
    SnapshotError,
    SnapshotNotFoundError,
    SnapshotOperationError,
    SnapshotValidationError,
    SourceValidationError,
    UnsupportedFormatError,
    UnsupportedUsageContextError,
)
from .local_snapshot import SNAPSHOT_SCHEMA_VERSION as LOCAL_SNAPSHOT_SCHEMA_VERSION
from .local_snapshot import (
    CharacterLocalSnapshot,
    PortraitRef,
    SnapshotReference,
    SnapshotStore,
)
from .physical import physical_profile_from_preset
from .package_importer import (
    PACKAGE_IMPORTED,
    PACKAGE_NO_OP_ALREADY_INSTALLED,
    TRUST_LOCAL_UNTRUSTED,
    CharacterPackageCollisionError,
    CharacterPackageImportError,
    CharacterPackageImportService,
    PackageImportResult,
)
from .package_management import (
    CharacterPackageManagementError,
    CharacterPackageManagementService,
    InstalledCharacter,
    InstalledPackageCorruptError,
    InstalledPackageNotFoundError,
    InstalledPackageRelease,
)
from .package_v1 import (
    CharacterPackageContractError,
    CharacterPackageIntegrityError,
    CharacterPackagePathError,
    CharacterPackageV1Error,
    PackageFileDescriptor,
    VerifiedCharacterPackage,
    verify_character_package_v1,
)
from .reference_importer import ImportResult as ReferenceImportOutcome
from .reference_importer import import_reference
from .service import (
    IMPORTED,
    NO_OP_UNCHANGED,
    UPDATED_NEW_VERSION,
    CharacterImportService,
    ImportResult,
)

__all__ = [
    "CharacterImportService",
    "ImportResult",
    "IMPORTED",
    "UPDATED_NEW_VERSION",
    "NO_OP_UNCHANGED",
    "read_character_canon",
    "CANON_SNAPSHOT_SCHEMA_VERSION",
    "LOCAL_SNAPSHOT_SCHEMA_VERSION",
    "CharacterCanonSnapshot",
    "CanonReference",
    "Provenance",
    "CharacterLocalSnapshot",
    "SnapshotReference",
    "PortraitRef",
    "SnapshotStore",
    "physical_profile_from_preset",
    "import_reference",
    "ReferenceImportOutcome",
    "is_known_canon_status",
    "is_production_approved",
    "CharacterImportError",
    "CanonRootMissingError",
    "CharacterNotFoundError",
    "AmbiguousCharacterError",
    "CanonFormatError",
    "CanonStatusUnknownError",
    "ReferencePathSafetyError",
    "ProductionNotAllowedError",
    "UnsupportedUsageContextError",
    "ReferenceValidationError",
    "ReferenceManifestError",
    "ReferenceImportError",
    "SourceValidationError",
    "UnsupportedFormatError",
    "FormatMismatchError",
    "CrossCharacterDuplicateError",
    "AssetIdCollisionError",
    "SnapshotError",
    "SnapshotNotFoundError",
    "SnapshotValidationError",
    "SnapshotOperationError",
    "CharacterPackageV1Error",
    "CharacterPackageContractError",
    "CharacterPackageIntegrityError",
    "CharacterPackagePathError",
    "PackageFileDescriptor",
    "VerifiedCharacterPackage",
    "verify_character_package_v1",
    "CharacterPackageImportError",
    "CharacterPackageCollisionError",
    "PackageImportResult",
    "CharacterPackageImportService",
    "PACKAGE_IMPORTED",
    "PACKAGE_NO_OP_ALREADY_INSTALLED",
    "TRUST_LOCAL_UNTRUSTED",
    "CharacterPackageManagementError",
    "InstalledPackageCorruptError",
    "InstalledPackageNotFoundError",
    "InstalledPackageRelease",
    "InstalledCharacter",
    "CharacterPackageManagementService",
]
