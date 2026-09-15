#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Materialize the CURRENT / ACTUAL Kira Character Package V1 (design/authoring
tool only -- NOT a runtime module).

NEW / ACTUAL KIRA
==================
This tool reads the current, HUMAN_APPROVED CRP acceptance record for Kira --
rebuilt after the AI-role update, tested in Character Lab, and presently the
accepted Kira Companion -- and materializes it as a Package V1 directory via
``voyage_character_platform.materialize_legacy_compat_package``.

It is NOT sourced from, and must never read, the OLD Kira package
(``releaseId=legacy-compat-v1``, ``packageHash=
c2194c215effbefff76a42362e1a9adef45076b8e794dd1fb76bcf3788047ac9``). This
tool never opens, globs, or otherwise touches that package or any file under
``accepted/`` or ``character_packages/`` other than the three exact files
named below.

Exact, hardcoded allowed source files (repo-relative to THIS repository's own
root -- never a sibling worktree path):

    accepted/kira/ACCEPTANCE.json
    accepted/kira/source_candidate.json
    character_packages/kira/extensions/dimension_semantics/v1.json

Each is locked to an exact expected SHA-256 via a CANONICAL_EOL_SOURCE_LOCK
(see ``_canonicalize_source_lock_bytes``): the ONLY normalization applied
before hashing is physical CRLF (``\\r\\n``) -> LF (``\\n``) line-ending
collapse. Nothing else is touched -- no JSON reordering, no reserialization,
no Unicode normalization, no whitespace/indentation change, no trailing- or
final-newline change. A bare CR byte not immediately followed by LF is not
treated as an equivalent newline representation; it FAILS CLOSED. This makes
the lock reproducible across a clean LF checkout and a Windows CRLF checkout
of the exact same committed content, while remaining exactly as sensitive as
a raw-byte lock to every other kind of change (a changed claim, a changed
space, a changed null, a reordered array, ...). A semantic/content hash found
*inside* a file is never trusted as a substitute for this independent lock --
if the file's canonicalized bytes change even while some internal hash still
matches, materialization FAILS CLOSED.

Package identity (LEGACY_COMPAT / LEGACY_IMPORT is a *technical* Package V1
authority label describing that this package was IMPORTED from the earlier
CRP acceptance system into the newer Package V1 mechanism -- it does **not**
mean "old Kira personality"; the content is the new/actual, HUMAN_APPROVED
Kira):

    characterId    = "kira"
    releaseId      = "crp-import-v1"
    displayName    = "Кира — актуальная CRP"
    authorityClass = LEGACY_COMPAT
    packageOrigin  = LEGACY_IMPORT

This tool does NOT invent a Character Platform ``ACCEPTED_RELEASE``
acceptance (no ``provenance/acceptance.json``, no ``acceptedAggregateHash``,
no ``acceptanceRecordHash``). The original HUMAN_APPROVED CRP acceptance
record is preserved as source evidence in ``provenance/source_acceptance.json``.

Full source preservation is CONTENT-FAITHFUL CANONICAL PRESERVATION, not raw
byte-faithful preservation: the source JSON files are parsed and the exact
parsed ``source_candidate`` Candidate (every claim, contradiction, unknown,
null, empty object/array, and array ordering -- semantically/deep equal to
the source) is re-emitted via the Character Platform's deterministic
Package V1 canonical JSON serializer as ``provenance/source_candidate.json``,
and likewise the full dimension-semantics extension as
``extensions/dimension_semantics/v1.json``. The embedded package files'
raw bytes are therefore NOT asserted to equal the original filesystem
source's raw bytes (canonical JSON formatting differs from whatever
formatting/line-endings the source file happened to use) -- what is
asserted, and verified by tests, is that the embedded *parsed JSON content*
is exactly, deeply equal to the source's parsed content. Package V1 domain
envelopes (``domains/*.json``) are a deterministic, explicit *projection* of
that same Candidate into the six required domains -- never a rewrite, never
a summary that drops information.

Domain routing (deterministic, derived from each claim/unknown's own
``target_module_or_layer`` prefix -- see ``MODULE_TO_DOMAIN`` below):

    core_identity          <- identity_biography_candidate
    psychology             <- psychology_candidate, behavior_candidate
    speech                 <- voice_candidate
    relationships          <- relationships_candidate
    interaction_boundaries <- boundaries_candidate, intimacy_candidate
    visual_identity        <- EXPLICITLY_EMPTY (no complete approved visual
                               identity contract in this source; this does
                               NOT mean Kira has no appearance)

Contradictions and unknowns are routed to exactly one of the six domains by
resolving their referenced claim(s)' ``target_module_or_layer`` prefix
through the same table. If a contradiction's claims resolve to more than one
domain, or any claim/unknown reference cannot be resolved, materialization
FAILS CLOSED (``AmbiguousRoutingError``) rather than guessing.

Memory boundary: only AUTHORED content (biography, psychology, relationship
history, boundaries, ``seed_memory_candidate``) is ever read or packaged.
This tool never searches for, reads, or references runtime memory
(``runtime_memory.sqlite3`` etc.), session/state rows, or any
accumulated user-specific data.

Output safety: the destination directory is a REQUIRED explicit argument
with no implicit/default value, and this tool refuses to write under this
repository's own ``accepted/`` or ``character_packages/`` directories, or
directly at the repository root.

This module must not be imported by Companion runtime, catalog, session, or
memory code -- it is an authoring/build-time tool only.

Standard library plus ``voyage_character_platform`` (Character Platform
Package V1 foundation) only. No network, no provider calls, no canon access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from services.crp_authoring.candidate_package import CandidateCharacterPackage
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package
from services.crp_authoring.contracts import RoleClaim
from services.crp_authoring.errors import CrpValidationError

from voyage_character_platform import (
    AuthorityClass,
    ContentState,
    ContradictionRecord,
    DomainEnvelope,
    MaterializedPackage,
    PackageMetadata,
    PackageOrigin,
    ProvenanceRecord,
    REQUIRED_DOMAIN_IDS,
    AuthoringMethod,
    UnknownRecord,
    materialize_legacy_compat_package,
)
from voyage_character_platform.materializer import SupplementalJsonFile


class CurrentKiraPackageMaterializationError(RuntimeError):
    """Fail-closed error for this tool: source lock, binding, or routing failure."""


class SourceLockError(CurrentKiraPackageMaterializationError):
    """A required source file's raw bytes do not match its expected SHA-256,
    or an expected identity/binding field inside it does not match."""


class AmbiguousRoutingError(CurrentKiraPackageMaterializationError):
    """A contradiction or unknown could not be routed to exactly one domain
    deterministically. Never guessed; the caller must resolve the source
    data (this tool will not silently pick a domain)."""


# ---------------------------------------------------------------------------
# Exact, hardcoded source locations and locks (THIS repository only; never a
# sibling worktree, never "the latest Kira", never Character Canon, never
# the old package).
# ---------------------------------------------------------------------------

ACCEPTANCE_RELATIVE_PATH = "accepted/kira/ACCEPTANCE.json"
SOURCE_CANDIDATE_RELATIVE_PATH = "accepted/kira/source_candidate.json"
DIMENSION_SEMANTICS_RELATIVE_PATH = (
    "character_packages/kira/extensions/dimension_semantics/v1.json"
)

# CANONICAL_EOL_SOURCE_LOCK values: SHA-256 of each file's committed HEAD
# blob (commit 9d8e2162dd505e19f7a1047738b9b948776e3634) after applying ONLY
# the CRLF->LF collapse in _canonicalize_source_lock_bytes -- never the raw
# working-tree bytes of any one particular checkout. ACCEPTANCE.json and
# dimension_semantics/v1.json's HEAD blobs are already LF-only, so their
# canonical lock is unchanged from a plain raw-byte hash; source_candidate.json's
# HEAD blob is LF-only but a Windows CRLF checkout of the same commit is not,
# which is exactly the reproducibility defect this lock fixes -- see
# docs/character_companion/CURRENT_KIRA_CHARACTER_PACKAGE_V1_MAPPING.md.
EXPECTED_ACCEPTANCE_CANONICAL_SHA256 = (
    "42ce4fa0838bee25477d0f6ba24552170014088c060b50a6dd7a29de5d9fcb34"
)
EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256 = (
    "abffecab28b50d260f440c2bd6561bcae95e7c3d52f887d7d71569f1e842188d"
)
EXPECTED_DIMENSION_SEMANTICS_CANONICAL_SHA256 = (
    "84463aeb31f32c4b2e41c8fa64a0824b2889abeb9c3eb32315ac016da2fdda20"
)

EXPECTED_ACCEPTANCE_ID = "kira-accepted-package-001"
EXPECTED_SUBJECT_ID = "kira"
EXPECTED_ACCEPTED_SEMANTIC_HASH = (
    "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"
)

# Old/legacy Kira package identity. This tool must never treat these as a
# content source; listed here only so the guard below has something exact
# to refuse.
OLD_KIRA_RELEASE_ID = "legacy-compat-v1"
OLD_KIRA_PACKAGE_HASH = (
    "c2194c215effbefff76a42362e1a9adef45076b8e794dd1fb76bcf3788047ac9"
)

CHARACTER_ID = "kira"
RELEASE_ID = "crp-import-v1"
DISPLAY_NAME = "Кира — актуальная CRP"
PACKAGE_SCHEMA_VERSION = "1.0"
DOMAIN_SCHEMA_VERSION = "1.0"

SOURCE_CANDIDATE_SUPPLEMENTAL_PATH = "provenance/source_candidate.json"
SOURCE_ACCEPTANCE_SUPPLEMENTAL_PATH = "provenance/source_acceptance.json"
DIMENSION_SEMANTICS_SUPPLEMENTAL_PATH = "extensions/dimension_semantics/v1.json"

# Deterministic module-prefix -> Package V1 required-domain routing. This is
# the ONLY routing table; it is derived from, and must stay a subset of, the
# actual `target_module_or_layer` prefixes used by the current Kira source
# (identity_biography / psychology / behavior / voice / relationships /
# boundaries / intimacy). Any other prefix is unrouteable -> fail closed.
MODULE_TO_DOMAIN: Mapping[str, str] = {
    "identity_biography": "core_identity",
    "psychology": "psychology",
    "behavior": "psychology",
    "voice": "speech",
    "relationships": "relationships",
    "boundaries": "interaction_boundaries",
    "intimacy": "interaction_boundaries",
}

# Package-V1 domain_id -> the source_candidate top-level field name(s) that
# populate that domain's structured.crpV1 content, and the module name each
# field corresponds to (for building matching provenance ids).
DOMAIN_SOURCE_FIELDS: Mapping[str, tuple[str, ...]] = {
    "core_identity": ("identity_biography_candidate",),
    "psychology": ("psychology_candidate", "behavior_candidate"),
    "speech": ("voice_candidate",),
    "relationships": ("relationships_candidate",),
    "interaction_boundaries": ("boundaries_candidate", "intimacy_candidate"),
    "visual_identity": (),
}

FIELD_TO_MODULE: Mapping[str, str] = {
    "identity_biography_candidate": "identity_biography",
    "psychology_candidate": "psychology",
    "behavior_candidate": "behavior",
    "voice_candidate": "voice",
    "relationships_candidate": "relationships",
    "boundaries_candidate": "boundaries",
    "intimacy_candidate": "intimacy",
}


def _provenance_id_for_module(module: str) -> str:
    return f"source-candidate-{module}"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonicalize_source_lock_bytes(data: bytes, *, label: str) -> bytes:
    """CANONICAL_EOL_SOURCE_LOCK normalization -- and NOTHING else.

    Collapses physical CRLF (``\\r\\n``) to LF (``\\n``) only. Every CR byte
    in ``data`` MUST be immediately followed by LF; a bare CR (any other
    newline convention, or a stray CR byte) is NOT treated as an equivalent
    representation and FAILS CLOSED instead of being silently normalized.

    Deliberately does NOT: reorder JSON, strip/add whitespace or
    indentation, normalize Unicode, normalize JSON numbers, add/remove a
    final newline, touch nulls, reorder/alter arrays or strings, or parse
    and reserialize JSON. It is a pure byte-level CRLF<->LF equivalence,
    nothing broader -- every other byte difference (a changed claim, an
    added/removed space, a changed null, a reordered array element, ...)
    still changes the resulting hash.
    """
    position = 0
    length = len(data)

    while True:
        index = data.find(b"\r", position)

        if index == -1:
            break

        if index + 1 >= length or data[index + 1 : index + 2] != b"\n":
            raise SourceLockError(
                f"{label}: bare CR byte at offset {index} is not CRLF -- "
                "refusing to treat it as an equivalent newline representation "
                "(FAIL CLOSED; only CRLF<->LF is an allowed equivalence)."
            )

        position = index + 2

    return data.replace(b"\r\n", b"\n")


@dataclass(frozen=True)
class LockedKiraSource:
    """The three exact, hash-locked source files -- CANONICAL_EOL_SOURCE_LOCK
    (CRLF->LF collapsed) bytes, parsed JSON, and the rehydrated typed
    Candidate. Nothing else is ever read.

    ``source_candidate_bytes`` holds the CANONICALIZED bytes (not
    necessarily identical to the working-tree file's raw bytes -- only its
    CRLF/LF representation may differ); this is what
    ``EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256`` and every downstream
    ``sourceSha256`` provenance reference are computed from.
    """

    repo_root: Path
    acceptance_raw: dict
    source_candidate_bytes: bytes
    source_candidate_raw: dict
    candidate: CandidateCharacterPackage
    dimension_semantics_raw: dict


def _read_and_lock(repo_root: Path, relative_path: str, expected_canonical_sha256: str) -> bytes:
    path = repo_root / relative_path
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SourceLockError(
            f"Required current-Kira source file is not readable: {relative_path} ({exc})"
        ) from exc

    canonical = _canonicalize_source_lock_bytes(data, label=relative_path)
    actual = _sha256_bytes(canonical)

    if actual.lower() != expected_canonical_sha256.lower():
        raise SourceLockError(
            "Current-Kira source file canonical (CRLF<->LF-normalized) bytes do "
            "not match the expected CANONICAL_EOL_SOURCE_LOCK -- FAILING CLOSED "
            "rather than trusting any internal semantic hash: "
            f"{relative_path} expected canonical sha256={expected_canonical_sha256} "
            f"actual canonical sha256={actual}"
        )

    return canonical


def load_and_verify_current_kira_source(repo_root: Path) -> LockedKiraSource:
    """Load and verify the three exact allowed current-Kira source files.

    Verifies, independently of any content-internal hash:
      - raw-byte SHA-256 of all three files against hardcoded expectations;
      - acceptance_id / subject_id / accepted package_hash inside ACCEPTANCE.json;
      - subject_id / package_id consistency inside source_candidate.json,
        and that it rehydrates through the strict typed Candidate path;
      - the dimension-semantics extension's ``target_accepted_source_hash``
        binds to exactly the same accepted package_hash (dimension extension
        binding).

    Raises SourceLockError (fail closed) on any mismatch. Never reads the old
    Kira package, Character Canon, or any other file.
    """

    repo_root = repo_root.resolve()

    acceptance_bytes = _read_and_lock(
        repo_root, ACCEPTANCE_RELATIVE_PATH, EXPECTED_ACCEPTANCE_CANONICAL_SHA256
    )
    source_candidate_bytes = _read_and_lock(
        repo_root, SOURCE_CANDIDATE_RELATIVE_PATH, EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256
    )
    dimension_semantics_bytes = _read_and_lock(
        repo_root,
        DIMENSION_SEMANTICS_RELATIVE_PATH,
        EXPECTED_DIMENSION_SEMANTICS_CANONICAL_SHA256,
    )

    try:
        acceptance_raw = json.loads(acceptance_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLockError(f"ACCEPTANCE.json is not valid UTF-8 JSON: {exc}") from exc

    try:
        source_candidate_raw = json.loads(source_candidate_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLockError(
            f"source_candidate.json is not valid UTF-8 JSON: {exc}"
        ) from exc

    try:
        dimension_semantics_raw = json.loads(dimension_semantics_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceLockError(
            f"dimension_semantics/v1.json is not valid UTF-8 JSON: {exc}"
        ) from exc

    if not isinstance(acceptance_raw, dict) or "acceptance_record" not in acceptance_raw:
        raise SourceLockError("ACCEPTANCE.json does not contain an acceptance_record")

    record = acceptance_raw["acceptance_record"]

    if record.get("acceptance_id") != EXPECTED_ACCEPTANCE_ID:
        raise SourceLockError(
            "ACCEPTANCE.json acceptance_id mismatch: "
            f"expected {EXPECTED_ACCEPTANCE_ID!r}, got {record.get('acceptance_id')!r}"
        )

    if record.get("subject_id") != EXPECTED_SUBJECT_ID:
        raise SourceLockError(
            "ACCEPTANCE.json subject_id mismatch: "
            f"expected {EXPECTED_SUBJECT_ID!r}, got {record.get('subject_id')!r}"
        )

    accepted_package_hash = record.get("package_hash")

    if accepted_package_hash != EXPECTED_ACCEPTED_SEMANTIC_HASH:
        raise SourceLockError(
            "ACCEPTANCE.json package_hash (accepted semantic hash) mismatch: "
            f"expected {EXPECTED_ACCEPTED_SEMANTIC_HASH!r}, got {accepted_package_hash!r}"
        )

    if record.get("decision") != "HUMAN_APPROVED":
        raise SourceLockError(
            "ACCEPTANCE.json decision is not HUMAN_APPROVED -- refusing to "
            f"materialize: {record.get('decision')!r}"
        )

    if accepted_package_hash == OLD_KIRA_PACKAGE_HASH or record.get("package_id") == OLD_KIRA_RELEASE_ID:
        raise SourceLockError(
            "ACCEPTANCE.json resolves to the OLD Kira package identity -- refusing "
            "(BLOCKED_OLD_KIRA_CONTAMINATION)."
        )

    try:
        candidate = rehydrate_candidate_package(source_candidate_raw)
    except CrpValidationError as exc:
        raise SourceLockError(
            f"source_candidate.json failed strict typed Candidate rehydration: {exc}"
        ) from exc

    if candidate.subject_id != EXPECTED_SUBJECT_ID:
        raise SourceLockError(
            "source_candidate.json subject_id mismatch: "
            f"expected {EXPECTED_SUBJECT_ID!r}, got {candidate.subject_id!r}"
        )

    if candidate.package_id != record.get("package_id"):
        raise SourceLockError(
            "source_candidate.json package_id does not match ACCEPTANCE.json "
            f"package_id: {candidate.package_id!r} != {record.get('package_id')!r}"
        )

    if not isinstance(dimension_semantics_raw, dict):
        raise SourceLockError("dimension_semantics/v1.json root must be an object")

    if dimension_semantics_raw.get("character_id") != EXPECTED_SUBJECT_ID:
        raise SourceLockError(
            "dimension_semantics/v1.json character_id mismatch: "
            f"expected {EXPECTED_SUBJECT_ID!r}, "
            f"got {dimension_semantics_raw.get('character_id')!r}"
        )

    target_hash = dimension_semantics_raw.get("target_accepted_source_hash")

    if target_hash != accepted_package_hash:
        raise SourceLockError(
            "dimension_semantics/v1.json is not bound to the current accepted "
            f"package hash: target_accepted_source_hash={target_hash!r} != "
            f"ACCEPTANCE.json package_hash={accepted_package_hash!r}"
        )

    return LockedKiraSource(
        repo_root=repo_root,
        acceptance_raw=acceptance_raw,
        source_candidate_bytes=source_candidate_bytes,
        source_candidate_raw=source_candidate_raw,
        candidate=candidate,
        dimension_semantics_raw=dimension_semantics_raw,
    )


# ---------------------------------------------------------------------------
# Deterministic routing: claims/unknowns/contradictions -> Package V1 domains
# ---------------------------------------------------------------------------

def _module_of(claim: RoleClaim) -> str:
    target = claim.target_module_or_layer
    module = target.split(".", 1)[0]

    if module not in MODULE_TO_DOMAIN:
        raise AmbiguousRoutingError(
            f"claim {claim.claim_id!r} has an unrouteable target_module_or_layer "
            f"prefix {module!r} (from {target!r}); refusing to guess a domain."
        )

    return module


def _build_claim_module_index(candidate: CandidateCharacterPackage) -> dict[str, str]:
    index: dict[str, str] = {}

    for claim in tuple(candidate.claims) + tuple(candidate.unknowns):
        index[claim.claim_id] = _module_of(claim)

    return index


def _route_unknowns(candidate: CandidateCharacterPackage) -> tuple[UnknownRecord, ...]:
    records = []

    for unknown in candidate.unknowns:
        module = _module_of(unknown)
        domain = MODULE_TO_DOMAIN[module]

        records.append(
            UnknownRecord(
                unknown_id=unknown.claim_id,
                domain_id=domain,
                description=unknown.claim,
                provenance_refs=(_provenance_id_for_module(module),),
            )
        )

    return tuple(records)


def _route_contradictions(
    candidate: CandidateCharacterPackage,
    claim_module_index: Mapping[str, str],
) -> tuple[ContradictionRecord, ...]:
    records = []

    for contradiction in candidate.contradictions:
        modules: set[str] = set()

        for claim_id in contradiction.claim_ids:
            module = claim_module_index.get(claim_id)

            if module is None:
                raise AmbiguousRoutingError(
                    f"contradiction {contradiction.contradiction_id!r} references "
                    f"claim_id {claim_id!r} which is not present in claims/unknowns; "
                    "refusing to guess a domain."
                )

            modules.add(module)

        domains = {MODULE_TO_DOMAIN[module] for module in modules}

        if len(domains) != 1:
            raise AmbiguousRoutingError(
                f"contradiction {contradiction.contradiction_id!r} spans more than "
                f"one Package V1 domain ({sorted(domains)!r}) via modules "
                f"{sorted(modules)!r}; refusing to guess a single domain."
            )

        (domain,) = domains
        provenance_refs = tuple(
            sorted(_provenance_id_for_module(module) for module in modules)
        )

        records.append(
            ContradictionRecord(
                contradiction_id=contradiction.contradiction_id,
                domain_id=domain,
                description=contradiction.description,
                provenance_refs=provenance_refs,
            )
        )

    return tuple(records)


def _build_provenance_records(source_relative_path: str, source_sha256: str) -> tuple[ProvenanceRecord, ...]:
    records = []

    for field, module in FIELD_TO_MODULE.items():
        records.append(
            ProvenanceRecord(
                provenance_id=_provenance_id_for_module(module),
                authoring_method=AuthoringMethod.CRP,
                source_ref=f"{SOURCE_CANDIDATE_RELATIVE_PATH}:{field}",
                source_relative_path=source_relative_path,
                source_sha256=source_sha256,
                routing_decision=(
                    f"source_candidate.{field} -> module {module!r} -> domain "
                    f"{MODULE_TO_DOMAIN[module]!r} (target_module_or_layer prefix match)"
                ),
            )
        )

    return tuple(records)


def _build_domains(source_candidate_raw: dict) -> tuple[DomainEnvelope, ...]:
    domains = []

    for domain_id in sorted(REQUIRED_DOMAIN_IDS):
        fields = DOMAIN_SOURCE_FIELDS[domain_id]

        if not fields:
            domains.append(
                DomainEnvelope(
                    domain_id=domain_id,
                    domain_schema_version=DOMAIN_SCHEMA_VERSION,
                    content_state=ContentState.EXPLICITLY_EMPTY,
                    provenance_refs=(),
                    structured={},
                    legacy_payload=(),
                )
            )
            continue

        structured = {
            "crpV1": {field: source_candidate_raw[field] for field in fields}
        }
        provenance_refs = tuple(
            sorted(_provenance_id_for_module(FIELD_TO_MODULE[field]) for field in fields)
        )

        domains.append(
            DomainEnvelope(
                domain_id=domain_id,
                domain_schema_version=DOMAIN_SCHEMA_VERSION,
                content_state=ContentState.POPULATED,
                provenance_refs=provenance_refs,
                structured=structured,
                legacy_payload=(),
            )
        )

    return tuple(domains)


# ---------------------------------------------------------------------------
# Output safety
# ---------------------------------------------------------------------------

def _reject_unsafe_destination(destination: Path, repo_root: Path) -> None:
    resolved = destination.resolve()
    repo_root = repo_root.resolve()

    forbidden = {repo_root, (repo_root / "accepted").resolve(), (repo_root / "character_packages").resolve()}

    for candidate_forbidden in forbidden:
        if resolved == candidate_forbidden or candidate_forbidden in resolved.parents:
            raise CurrentKiraPackageMaterializationError(
                "Refusing forbidden output destination (would write under this "
                f"repository's own source-of-truth path or repo root): {resolved}"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def materialize_current_kira_package_v1(
    destination: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> MaterializedPackage:
    """Materialize the current/actual, HUMAN_APPROVED Kira as a Package V1
    directory at the explicit, caller-supplied ``destination``.

    ``destination`` MUST NOT already exist (enforced by
    ``materialize_legacy_compat_package`` itself) and must not resolve under
    this repository's own ``accepted/`` or ``character_packages/`` trees, or
    at the repository root.
    """

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]

    repo_root = Path(repo_root)
    destination = Path(destination)

    _reject_unsafe_destination(destination, repo_root)

    source = load_and_verify_current_kira_source(repo_root)

    claim_module_index = _build_claim_module_index(source.candidate)

    domains = _build_domains(source.source_candidate_raw)
    provenance = _build_provenance_records(
        SOURCE_CANDIDATE_SUPPLEMENTAL_PATH,
        _sha256_bytes(source.source_candidate_bytes),
    )
    contradictions = _route_contradictions(source.candidate, claim_module_index)
    unknowns = _route_unknowns(source.candidate)

    metadata = PackageMetadata(
        package_schema_version=PACKAGE_SCHEMA_VERSION,
        character_id=CHARACTER_ID,
        release_id=RELEASE_ID,
        display_name=DISPLAY_NAME,
        authority_class=AuthorityClass.LEGACY_COMPAT,
        package_origin=PackageOrigin.LEGACY_IMPORT,
    )

    supplemental_json = {
        SOURCE_CANDIDATE_SUPPLEMENTAL_PATH: SupplementalJsonFile(
            payload=source.source_candidate_raw,
            semantic_role="SOURCE_CANDIDATE_RECORD",
        ),
        SOURCE_ACCEPTANCE_SUPPLEMENTAL_PATH: SupplementalJsonFile(
            payload=source.acceptance_raw,
            semantic_role="SOURCE_ACCEPTANCE_RECORD",
        ),
        DIMENSION_SEMANTICS_SUPPLEMENTAL_PATH: SupplementalJsonFile(
            payload=source.dimension_semantics_raw,
            semantic_role="DIMENSION_SEMANTICS_EXTENSION",
        ),
    }

    return materialize_legacy_compat_package(
        destination,
        metadata=metadata,
        domains=domains,
        provenance=provenance,
        unknowns=unknowns,
        contradictions=contradictions,
        supplemental_json=supplemental_json,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the current/actual, HUMAN_APPROVED Kira Character "
            "Package V1. --output is required; there is no implicit "
            "destination."
        )
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Explicit destination directory (must not already exist).",
    )
    args = parser.parse_args(argv)

    result = materialize_current_kira_package_v1(args.output)

    print(
        json.dumps(
            {
                "root": str(result.root),
                "packageHash": result.package_hash,
                "fileCount": len(result.manifest.files),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
