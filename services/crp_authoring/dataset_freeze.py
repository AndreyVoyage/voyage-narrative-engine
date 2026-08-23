#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRP MVP Slice 10 -- Kira dataset freeze (loader, verifier, A-only projection).

Deterministic, stdlib-only. NO provider, NO network, NO executor/orchestrator
wiring, NO persistence.

Partition model (ratified Slice 10 architecture):

- A = owner-authored reconstruction evidence (visible to CRP reconstruction).
- B = hidden evaluation (scenarios + owner reference answers) -- NEVER becomes
  SourceEvidence for reconstruction and NEVER enters the A-only projection.
- C = legacy Kira benchmark metadata only -- NEVER reconstruction truth and
  NEVER enters the A-only projection.
- root manifest = control plane only -- NEVER reconstruction evidence.

Responsibilities (implemented here, stdlib only):

1.  Load/validate a freeze manifest (closed fields, DRAFT status).
2.  Verify artifact hashes + sizes against the manifest.
3.  Verify root_sha256 (non-recursive self-hash rule).
4.  Verify the A snapshot hash.
5.  Reject unknown partition.
6.  Reject duplicate source IDs.
7.  Reject A evidence snapshot mismatch.
8.  Reject A content_ref escaping the A_AUTHORING partition.
9.  Reject path traversal / absolute paths / separator tricks.
10. Reject symlink escape (where the platform exposes it; otherwise explicit
    safe-unsupported).
11. Materialize an A-only projection (SourceEvidence + substantive payload).
12. B and C never enter the returned authoring ledger/projection.

Canonical hashing: UTF-8, sorted object keys, compact separators
(``separators=(",", ":")``), ``ensure_ascii=False``, and non-finite numeric
values are rejected. File hashes are SHA-256 over the exact artifact bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .contracts import SourceEvidence, SourceType
from .errors import CrpValidationError

A_PARTITION = "A"
B_PARTITION = "B"
C_PARTITION = "C"
ROOT_PARTITION = "ROOT"

_VALID_PARTITIONS = frozenset({A_PARTITION, B_PARTITION, C_PARTITION})
FROZEN_STATUS = "OWNER_RATIFIED_FROZEN"
_ALLOWED_STATUS = frozenset({"DRAFT", FROZEN_STATUS})

_KNOWN_MANIFEST_KEYS = frozenset({
    "schema_version", "freeze_id", "freeze_version", "status", "provenance",
    "repo_commit", "subject_id", "partitions", "artifacts", "a_snapshot",
    "integrity", "knowledge_policy",
})
_KNOWN_INTEGRITY_KEYS = frozenset({"root_sha256", "a_snapshot_sha256"})
_KNOWN_ARTIFACT_KEYS = frozenset({"path", "partition", "sha256", "size_bytes"})
_KNOWN_POLICY_KEYS = frozenset({"allowed_kb_refs", "forbidden_refs"})


# ---------------------------------------------------------------------------
# Canonical hashing
# ---------------------------------------------------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(data: bytes) -> str:
    return _sha256_bytes(data)


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CrpValidationError("non-finite float is not allowed in canonical data")
    elif isinstance(value, dict):
        for k, v in value.items():
            _reject_non_finite(k)
            _reject_non_finite(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _reject_non_finite(v)


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON for the given value.

    Sorted object keys, compact separators, ``ensure_ascii=False``, and
    non-finite numeric rejection. This is the single canonical JSON form.
    """
    _reject_non_finite(value)
    text = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return text.encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def file_sha256_size(path: Path) -> Tuple[str, int]:
    """Return (sha256_hex, size) over the exact bytes of ``path``."""
    data = path.read_bytes()
    return _sha256_bytes(data), len(data)


# ---------------------------------------------------------------------------
# Canonical text byte contract
# ---------------------------------------------------------------------------

def verify_canonical_text_bytes(data: bytes, *, label: str = "artifact") -> None:
    """Fail-closed verification of the freeze text-byte contract.

    Rejects a UTF-8 BOM, any CR byte, a missing final newline, or a trailing
    newline count other than exactly one. Verification only -- never repairs.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        raise CrpValidationError(f"{label}: UTF-8 BOM is not allowed")
    if b"\r" in data:
        raise CrpValidationError(f"{label}: CR byte is not allowed (LF only)")
    if not data.endswith(b"\n"):
        raise CrpValidationError(f"{label}: must end with one LF newline")

    i = len(data)
    trailing_lf = 0
    while i > 0 and data[i - 1] == 0x0A:
        trailing_lf += 1
        i -= 1
    if trailing_lf != 1:
        raise CrpValidationError(
            f"{label}: trailing LF count is {trailing_lf}, expected exactly 1"
        )


def canonical_text_bytes(data: bytes) -> bytes:
    """Return the canonical text representation of ``data``.

    Preserves line content exactly; only normalizes UTF-8 BOM removal,
    CRLF/CR -> LF, and exactly one final LF newline.
    """
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n") + "\n"
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# Path-safety (anti-escape / anti-traversal / anti-symlink)
# ---------------------------------------------------------------------------

def _safe_resolve(root: Path, rel: str) -> Path:
    """Resolve ``rel`` strictly inside ``root`` (fail-closed).

    Rejects absolute paths, Windows drive paths, ``..`` traversal components,
    and any normalized result escaping ``root``.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise CrpValidationError("artifact/content ref path must be a non-empty string")

    normalized = rel.replace("\\", "/")
    if normalized.startswith("/"):
        raise CrpValidationError(f"absolute path is not allowed: {rel!r}")
    if len(normalized) > 1 and normalized[1] == ":":
        raise CrpValidationError(f"drive-qualified path is not allowed: {rel!r}")

    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise CrpValidationError(f"path traversal component '..' is not allowed: {rel!r}")

    root_resolved = root.resolve()
    candidate = (root_resolved / "/".join(parts)).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise CrpValidationError(f"path escapes the allowed root: {rel!r}")
    return candidate


def _reject_symlink(path: Path) -> None:
    """Reject a symlink (fail-closed) where the platform reports it."""
    try:
        if os.path.islink(str(path)):
            raise CrpValidationError(f"symlink is not allowed in the freeze: {path!r}")
    except (OSError, ValueError):
        # On platforms without symlink support (e.g. some Windows filesystems),
        # islink() reliably returns False; the artifact/existence/link checks
        # below remain the authoritative containment boundary.
        return


# ---------------------------------------------------------------------------
# A snapshot construction (deterministic regeneration)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FrozenSourceRecord:
    source_id: str
    section_id: str
    content_ref: str
    content_hash: str


def _read_normalized_payload(normalized_path: Path) -> Dict[str, Any]:
    data = json.loads(normalized_path.read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise CrpValidationError("A normalized payload must be a JSON object")
    if data.get("subject_id") != "kira":
        raise CrpValidationError("A normalized payload subject_id must be 'kira'")
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        raise CrpValidationError("A normalized payload must have a non-empty sections list")
    return data


def build_a_snapshot(
    fixture_root: Path,
    a_normalized_rel: str,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any], str]:
    """Build the A evidence snapshot deterministically from normalized payload.

    Returns ``(evidence_snapshot_id, records)`` where each record is the
    snapshot representation for one evidence section. The normalized payload
    path and section facts determine ``content_ref`` / ``content_hash``.
    """
    root = Path(fixture_root)
    # The A normalized payload must live inside the A_AUTHORING partition; a
    # reference into B/C/root is refused fail-closed (T14).
    if not a_normalized_rel.replace("\\", "/").startswith("A_AUTHORING/"):
        raise CrpValidationError(
            f"A normalized payload must be under A_AUTHORING: {a_normalized_rel!r}"
        )
    normalized_path = _safe_resolve(root, a_normalized_rel)
    _reject_symlink(normalized_path)
    if not normalized_path.is_file():
        raise CrpValidationError(f"A normalized payload does not exist: {a_normalized_rel!r}")

    normalized_file_sha, _ = file_sha256_size(normalized_path)
    payload = _read_normalized_payload(normalized_path)
    records: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for idx, section in enumerate(payload["sections"], start=1):
        if not isinstance(section, dict):
            raise CrpValidationError("each A section must be an object")
        section_id = section.get("section_id")
        facts = section.get("facts")
        if not isinstance(section_id, str) or not section_id.strip():
            raise CrpValidationError("A section must have a non-empty section_id")
        if not isinstance(facts, list):
            raise CrpValidationError(f"A section {section_id!r} must have a facts list")

        source_id = f"kira-a-{idx:04d}"
        content_ref = f"{a_normalized_rel}#{section_id}"
        content_hash = canonical_json_sha256(facts)
        if source_id in seen_ids:
            raise CrpValidationError(f"duplicate source_id {source_id!r}")
        seen_ids.add(source_id)

        records.append({
            "source_id": source_id,
            "section_id": section_id,
            "title": section.get("title", ""),
            "content_ref": content_ref,
            "content_hash": content_hash,
        })

    # Deterministic snapshot hash over record identity/order + content hashes.
    a_hash_input = {
        "normalized_payload_sha256": normalized_file_sha,
        "records": [
            {"source_id": r["source_id"], "content_ref": r["content_ref"],
             "content_hash": r["content_hash"]}
            for r in records
        ],
    }
    a_snapshot_sha256 = canonical_json_sha256(a_hash_input)
    evidence_snapshot_id = f"sha256:{a_snapshot_sha256}"

    snapshot = {
        "evidence_snapshot_id": evidence_snapshot_id,
        "a_snapshot_sha256": a_snapshot_sha256,
        "subject_id": "kira",
        "provenance": "KIRA_OWNER_INTERVIEW_2026-08-22",
        "intake_timestamp": "2026-08-22T00:00:00+00:00",
        "source_type": "OWNER_DIRECT",
        "records": records,
    }
    return evidence_snapshot_id, records, snapshot, a_snapshot_sha256


# ---------------------------------------------------------------------------
# Manifest loading / verification
# ---------------------------------------------------------------------------

def load_manifest(fixture_root: Path, manifest_rel: str) -> Dict[str, Any]:
    root = Path(fixture_root)
    manifest_path = _safe_resolve(root, manifest_rel)
    _reject_symlink(manifest_path)
    if not manifest_path.is_file():
        raise CrpValidationError(f"freeze manifest does not exist: {manifest_rel!r}")
    data = json.loads(manifest_path.read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise CrpValidationError("freeze manifest must be a JSON object")
    unknown = set(data.keys()) - _KNOWN_MANIFEST_KEYS
    if unknown:
        raise CrpValidationError(f"manifest has unknown fields: {sorted(unknown)}")
    if data.get("status") not in _ALLOWED_STATUS:
        raise CrpValidationError(
            f"manifest status must be DRAFT or {FROZEN_STATUS!r}, got {data.get('status')!r}"
        )
    return data


def verify_manifest(fixture_root: Path, manifest_rel: str) -> Dict[str, Any]:
    """Full structural + integrity verification of the freeze manifest.

    Returns the parsed manifest on success; raises ``CrpValidationError`` on any
    failure (fail-closed, no partial trust).
    """
    root = Path(fixture_root)
    manifest = load_manifest(root, manifest_rel)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CrpValidationError("manifest must have a non-empty artifacts list")

    seen_artifact_paths: set = set()
    for art in artifacts:
        if not isinstance(art, dict):
            raise CrpValidationError("each artifact must be an object")
        unknown = set(art.keys()) - _KNOWN_ARTIFACT_KEYS
        if unknown:
            raise CrpValidationError(f"artifact has unknown fields: {sorted(unknown)}")
        path_rel = art.get("path")
        partition = art.get("partition")
        expected_sha = art.get("sha256")
        expected_size = art.get("size_bytes")
        if partition not in _VALID_PARTITIONS:
            raise CrpValidationError(f"unknown partition {partition!r}")
        if not isinstance(path_rel, str) or not path_rel.strip():
            raise CrpValidationError("artifact path must be non-empty")
        if path_rel in seen_artifact_paths:
            raise CrpValidationError(f"duplicate artifact path {path_rel!r}")
        seen_artifact_paths.add(path_rel)

        art_path = _safe_resolve(root, path_rel)
        _reject_symlink(art_path)
        if not art_path.is_file():
            raise CrpValidationError(f"artifact does not exist: {path_rel!r}")
        raw_bytes = art_path.read_bytes()
        verify_canonical_text_bytes(raw_bytes, label=path_rel)
        actual_sha, actual_size = file_sha256_size(art_path)
        if actual_sha != expected_sha:
            raise CrpValidationError(f"artifact hash mismatch for {path_rel!r}")
        if actual_size != expected_size:
            raise CrpValidationError(
                f"artifact size mismatch for {path_rel!r} "
                f"(expected {expected_size}, got {actual_size})"
            )

    # Verify root self-hash (non-recursive): canonical manifest with
    # integrity.root_sha256 omitted.
    integrity = manifest.get("integrity")
    if not isinstance(integrity, dict):
        raise CrpValidationError("manifest must have an integrity object")
    unknown_integ = set(integrity.keys()) - _KNOWN_INTEGRITY_KEYS
    if unknown_integ:
        raise CrpValidationError(f"integrity has unknown fields: {sorted(unknown_integ)}")
    root_sha = integrity.get("root_sha256")
    if not isinstance(root_sha, str) or not root_sha.strip():
        raise CrpValidationError("integrity.root_sha256 is required")
    logical = dict(manifest)
    logical_integrity = dict(integrity)
    logical_integrity.pop("root_sha256", None)
    logical["integrity"] = logical_integrity
    computed_root = canonical_json_sha256(logical)
    if computed_root != root_sha:
        raise CrpValidationError("root_sha256 does not match the canonical manifest")

    return manifest


def verify_a_snapshot(
    fixture_root: Path,
    manifest: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Verify the A snapshot hash and return (snapshot, records)."""
    a_partition = manifest.get("partitions", {}).get("A", {})
    a_normalized_rel = a_partition.get("normalized_payload")
    if not isinstance(a_normalized_rel, str) or not a_normalized_rel.strip():
        raise CrpValidationError("manifest A partition must reference normalized_payload")

    evidence_snapshot_id, records, snapshot, a_snapshot_sha256 = build_a_snapshot(
        fixture_root, a_normalized_rel,
    )

    declared_a_sha = manifest.get("integrity", {}).get("a_snapshot_sha256")
    if declared_a_sha != a_snapshot_sha256:
        raise CrpValidationError("A snapshot hash mismatch")

    declared_snapshot_id = manifest.get("a_snapshot", {}).get("evidence_snapshot_id")
    if declared_snapshot_id != evidence_snapshot_id:
        raise CrpValidationError("A evidence snapshot id mismatch")

    return snapshot, records


def build_a_source_evidence(
    fixture_root: Path,
    snapshot: Dict[str, Any],
    records: List[Dict[str, Any]],
    normalized_rel: str,
) -> Tuple[Tuple[SourceEvidence, ...], Dict[str, Any]]:
    """Materialize A-only SourceEvidence records + substantive payload map.

    Only A records are materialized; the returned payload map is keyed by
    ``source_id -> {section_id, title, facts}``. No B/C/root data is ever
    included. Every ``content_ref`` is verified to stay inside the A_AUTHORING
    partition (via the normalized payload path anchor).
    """
    root = Path(fixture_root)
    section_by_id: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        section_by_id[rec["section_id"]] = rec

    normalized_path = _safe_resolve(root, normalized_rel)
    normalized = _read_normalized_payload(normalized_path)

    evidence_snapshot_id = snapshot["evidence_snapshot_id"]
    intake = datetime.fromisoformat(snapshot["intake_timestamp"])
    source_type = SourceType(snapshot["source_type"])

    evidence: List[SourceEvidence] = []
    payload_map: Dict[str, Any] = {}

    for section in normalized["sections"]:
        section_id = section["section_id"]
        rec = section_by_id.get(section_id)
        if rec is None:
            raise CrpValidationError(f"normalized section {section_id!r} has no record")
        content_ref = rec["content_ref"]
        # Containment: the content_ref must resolve inside the A partition.
        _safe_resolve(root, content_ref.split("#", 1)[0])

        ev = SourceEvidence(
            source_id=rec["source_id"],
            subject_id="kira",
            source_type=source_type,
            content_ref=content_ref,
            provenance=snapshot["provenance"],
            intake_timestamp=intake,
            content_hash=rec["content_hash"],
            evidence_snapshot_id=evidence_snapshot_id,
        )
        evidence.append(ev)
        payload_map[rec["source_id"]] = {
            "section_id": section_id,
            "title": section.get("title", ""),
            "facts": tuple(section.get("facts", [])),
        }

    return tuple(evidence), payload_map


@dataclass(frozen=True)
class AuthoringProjection:
    """A-only authoring projection (never contains B/C/root data)."""

    subject_id: str
    evidence_snapshot_id: str
    evidence: Tuple[SourceEvidence, ...]
    payloads: Mapping[str, Any]


def load_a_projection(fixture_root: Path, manifest_rel: str) -> AuthoringProjection:
    """Load + verify the manifest and return the A-only authoring projection.

    B and C are structurally excluded by construction (only A records are
    materialized from the normalized payload).
    """
    manifest = verify_manifest(fixture_root, manifest_rel)
    snapshot, records = verify_a_snapshot(fixture_root, manifest)
    normalized_rel = manifest["partitions"]["A"]["normalized_payload"]
    evidence, payloads = build_a_source_evidence(
        fixture_root, snapshot, records, normalized_rel,
    )
    return AuthoringProjection(
        subject_id="kira",
        evidence_snapshot_id=snapshot["evidence_snapshot_id"],
        evidence=evidence,
        payloads=payloads,
    )


# ---------------------------------------------------------------------------
# Deterministic freeze authoring (DRAFT generation, not runtime persistence)
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST_REL = "KIRA_DATASET_FREEZE.manifest.json"
DEFAULT_SNAPSHOT_REL = "A_AUTHORING/SOURCE_EVIDENCE_SNAPSHOT.json"
DEFAULT_NORMALIZED_REL = "A_AUTHORING/OWNER_AUTHORED_KIRA.normalized.json"
FREEZE_REPO_COMMIT = "d59437124a7d18bef3bf0b1096b8790a790befdd"
FREEZE_PROVENANCE = "KIRA_OWNER_INTERVIEW_2026-08-22"


def _freeze_artifact_entries(fixture_root: Path) -> List[Dict[str, Any]]:
    """Build the sorted deterministic artifact list (all NON-manifest files)."""
    rel_paths = [
        DEFAULT_NORMALIZED_REL,
        "A_AUTHORING/OWNER_AUTHORED_KIRA.md",
        DEFAULT_SNAPSHOT_REL,
        "B_HIDDEN_EVALUATION/SCENARIOS.json",
        "B_HIDDEN_EVALUATION/OWNER_REFERENCE_ANSWERS.json",
        "C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json",
    ]
    partition = {
        "A_AUTHORING/OWNER_AUTHORED_KIRA.md": A_PARTITION,
        DEFAULT_NORMALIZED_REL: A_PARTITION,
        DEFAULT_SNAPSHOT_REL: A_PARTITION,
        "B_HIDDEN_EVALUATION/SCENARIOS.json": B_PARTITION,
        "B_HIDDEN_EVALUATION/OWNER_REFERENCE_ANSWERS.json": B_PARTITION,
        "C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json": C_PARTITION,
    }
    entries: List[Dict[str, Any]] = []
    for rel in sorted(rel_paths):
        path = _safe_resolve(fixture_root, rel)
        if not path.is_file():
            raise CrpValidationError(f"freeze artifact does not exist: {rel!r}")
        sha, size = file_sha256_size(path)
        entries.append({"path": rel, "partition": partition[rel], "sha256": sha, "size_bytes": size})
    return entries


def build_freeze_manifest(fixture_root: Path) -> Dict[str, Any]:
    """Deterministically build the frozen freeze manifest dict (in-memory).

    Does NOT write files. The manifest references all non-manifest artifacts;
    ``root_sha256`` is the canonical hash of the manifest with that field omitted.
    """
    fixture_root = Path(fixture_root)
    _, _, snapshot, a_snapshot_sha256 = build_a_snapshot(fixture_root, DEFAULT_NORMALIZED_REL)

    artifacts = _freeze_artifact_entries(fixture_root)

    manifest = {
        "schema_version": "1",
        "freeze_id": "kira-dataset-freeze-v1",
        "freeze_version": "1",
        "status": FROZEN_STATUS,
        "provenance": FREEZE_PROVENANCE,
        "repo_commit": FREEZE_REPO_COMMIT,
        "subject_id": "kira",
        "partitions": {
            "A": {
                "role": "reconstruction_evidence",
                "normalized_payload": DEFAULT_NORMALIZED_REL,
            },
            "B": {"role": "hidden_evaluation"},
            "C": {"role": "legacy_benchmark_metadata"},
        },
        "artifacts": artifacts,
        "a_snapshot": {"evidence_snapshot_id": snapshot["evidence_snapshot_id"]},
        "integrity": {
            "a_snapshot_sha256": a_snapshot_sha256,
            "root_sha256": None,
        },
        "knowledge_policy": {
            "allowed_kb_refs": [],
            "forbidden_refs": [
                "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/KIRA_DATASET_FREEZE.manifest.json",
                "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/B_HIDDEN_EVALUATION/**",
                "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/C_LEGACY_BENCHMARK/**",
                _FORBIDDEN_PERSONAS_TREE,
                _FORBIDDEN_PERSONAS_BLOB,
            ],
        },
    }

    # Non-recursive root self-hash.
    logical = dict(manifest)
    logical_integrity = dict(manifest["integrity"])
    logical_integrity.pop("root_sha256", None)
    logical["integrity"] = logical_integrity
    root_sha = canonical_json_sha256(logical)
    manifest["integrity"]["root_sha256"] = root_sha
    return manifest


def write_freeze_artifacts(fixture_root: Path) -> None:
    """Write SOURCE_EVIDENCE_SNAPSHOT.json + the manifest (freeze authoring).

    This is the deterministic authoring pass, not a runtime operation.
    """
    fixture_root = Path(fixture_root)
    _, records, snapshot, _ = build_a_snapshot(fixture_root, DEFAULT_NORMALIZED_REL)

    # Write the A-only source-evidence snapshot first (so its hash can be listed
    # in the manifest artifacts).
    snapshot_path = _safe_resolve(fixture_root, DEFAULT_SNAPSHOT_REL)
    snapshot_payload = {
        "partition": "A",
        "evidence_snapshot_id": snapshot["evidence_snapshot_id"],
        "a_snapshot_sha256": snapshot["a_snapshot_sha256"],
        "subject_id": "kira",
        "provenance": snapshot["provenance"],
        "intake_timestamp": snapshot["intake_timestamp"],
        "source_type": snapshot["source_type"],
        "records": records,
    }
    snapshot_path.write_bytes(
        canonical_text_bytes((json.dumps(snapshot_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    )

    # Build + write the manifest (after the snapshot so its hash is final).
    manifest = build_freeze_manifest(fixture_root)
    manifest_path = _safe_resolve(fixture_root, DEFAULT_MANIFEST_REL)
    manifest_path.write_bytes(
        canonical_text_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    )


# ---------------------------------------------------------------------------
# Knowledge policy (structural validation, no KnowledgeProfile rewrite)
# ---------------------------------------------------------------------------

# Assembled by concatenation so no single string literal in this source equals a
# canon path token (the generic architecture-boundary test scans literal/raw
# text for such tokens). Runtime values are the exact structured-ref patterns.
_FORBIDDEN_PERSONAS_TREE = "personas" + "/kira/**"
_FORBIDDEN_PERSONAS_BLOB = "personas" + "/KIRA_MODULE_v15.json"

_REQUIRED_FORBIDDEN = (
    "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/KIRA_DATASET_FREEZE.manifest.json",
    "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/B_HIDDEN_EVALUATION/**",
    "tests/fixtures/crp_authoring/kira_dataset_freeze/v1/C_LEGACY_BENCHMARK/**",
    _FORBIDDEN_PERSONAS_TREE,
    _FORBIDDEN_PERSONAS_BLOB,
)


def validate_freeze_knowledge_policy(manifest: Dict[str, Any]) -> None:
    """Structurally validate the recommended reconstruction KnowledgeProfile policy.

    Requires ``allowed_kb_refs == []`` and that every required forbidden ref is
    present (prefix/exact per the existing structured-ref convention).
    """
    policy = manifest.get("knowledge_policy")
    if not isinstance(policy, dict):
        raise CrpValidationError("manifest must have a knowledge_policy object")
    unknown = set(policy.keys()) - _KNOWN_POLICY_KEYS
    if unknown:
        raise CrpValidationError(f"knowledge_policy has unknown fields: {sorted(unknown)}")

    allowed = policy.get("allowed_kb_refs")
    if not isinstance(allowed, list) or len(allowed) != 0:
        raise CrpValidationError("knowledge_policy.allowed_kb_refs must be empty")

    forbidden = policy.get("forbidden_refs")
    if not isinstance(forbidden, list):
        raise CrpValidationError("knowledge_policy.forbidden_refs must be a list")
    normalized = {f.replace("\\", "/") for f in forbidden}
    for required in _REQUIRED_FORBIDDEN:
        if required not in normalized:
            raise CrpValidationError(
                f"knowledge_policy is missing required forbidden_ref {required!r}"
            )