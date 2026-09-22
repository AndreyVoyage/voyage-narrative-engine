"""Public API for deterministic Character Authoring publication."""

from .errors import (
    CharacterPublicationError,
    PublicationNotApprovedError,
    PublicationPackageCollisionError,
    PublicationSourceCorruptError,
    PublicationStaleRevisionError,
    PublicationStaleSnapshotError,
    PublicationStorageError,
    PublicationValidationError,
)
from .hashing import canonical_runtime_package_bytes, compute_package_hash
from .model import (
    AuthoringRuntimePackage,
    COMPILER_PROFILE,
    PublishedRuntimePackage,
    RUNTIME_PACKAGE_SCHEMA_VERSION,
    SourceProvenance,
    VerifiedRuntimePackage,
    build_runtime_package,
    validate_slice1_visual_identity,
)
from .service import CharacterPublicationService
from .store import (
    CharacterPublicationStore,
    default_publication_root,
    verify_runtime_package,
)

__all__ = [
    "AuthoringRuntimePackage",
    "COMPILER_PROFILE",
    "CharacterPublicationError",
    "CharacterPublicationService",
    "CharacterPublicationStore",
    "PublicationNotApprovedError",
    "PublicationPackageCollisionError",
    "PublicationSourceCorruptError",
    "PublicationStaleRevisionError",
    "PublicationStaleSnapshotError",
    "PublicationStorageError",
    "PublicationValidationError",
    "PublishedRuntimePackage",
    "RUNTIME_PACKAGE_SCHEMA_VERSION",
    "SourceProvenance",
    "VerifiedRuntimePackage",
    "build_runtime_package",
    "canonical_runtime_package_bytes",
    "compute_package_hash",
    "default_publication_root",
    "validate_slice1_visual_identity",
    "verify_runtime_package",
]
