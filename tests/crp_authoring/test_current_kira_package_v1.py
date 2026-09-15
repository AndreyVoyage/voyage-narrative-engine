#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for ``tools/materialize_current_kira_package_v1.py`` -- the NEW /
ACTUAL Kira (current, HUMAN_APPROVED CRP acceptance) Package V1 materializer.

All materialization happens ONLY inside pytest ``tmp_path`` (auto-cleaned).
No persistent package is created anywhere under this repository,
``LOCAL_STORAGE``, or AppData. No network, no provider calls.

Requires ``voyage_character_platform`` importable (the VCP worktree's
``src`` on ``PYTHONPATH`` -- test-environment concern only, never
hardcoded in product source):

    PYTHONPATH=<repo_root>;<vcp_worktree>/src  py -3 -m pytest ...
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from services.character_companion.character_import import verify_character_package_v1
from services.character_lab.grounding import render_accepted_grounding
from services.crp_authoring.candidate_rehydration import rehydrate_candidate_package
from services.crp_authoring.errors import CrpValidationError

import tools.materialize_current_kira_package_v1 as kira_tool

from voyage_character_platform import verify_materialized_package

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEAD = "9d8e2162dd505e19f7a1047738b9b948776e3634"

_SOURCE_RELATIVE_PATHS = (
    kira_tool.ACCEPTANCE_RELATIVE_PATH,
    kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH,
    kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH,
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256_bytes(data: bytes, *, label: str = "test-fixture") -> str:
    return _sha256_bytes(kira_tool._canonicalize_source_lock_bytes(data, label=label))


def _canonical_sha256_file(path: Path) -> str:
    return _canonical_sha256_bytes(path.read_bytes(), label=path.name)


def _git_head_blob(relative_path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout


def _to_lf(data: bytes) -> bytes:
    """Test-only helper: collapse CRLF -> LF (same rule the tool uses)."""
    return data.replace(b"\r\n", b"\n")


def _to_crlf(data: bytes) -> bytes:
    """Test-only helper: expand every LF -> CRLF (starting from a pure-LF form,
    so this never produces CRCRLF or other double-conversion artifacts)."""
    return _to_lf(data).replace(b"\n", b"\r\n")


def _all_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _package_json(root: Path) -> dict:
    return json.loads((root / "package.json").read_bytes().decode("utf-8"))


def _write_fake_repo(
    base: Path, *, acceptance_bytes: bytes, candidate_bytes: bytes, extension_bytes: bytes
) -> Path:
    (base / "accepted" / "kira").mkdir(parents=True, exist_ok=True)
    (
        base / "character_packages" / "kira" / "extensions" / "dimension_semantics"
    ).mkdir(parents=True, exist_ok=True)
    (base / kira_tool.ACCEPTANCE_RELATIVE_PATH).write_bytes(acceptance_bytes)
    (base / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH).write_bytes(candidate_bytes)
    (base / kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH).write_bytes(extension_bytes)
    return base


def _real_source_bytes() -> dict[str, bytes]:
    return {
        "acceptance": (REPO_ROOT / kira_tool.ACCEPTANCE_RELATIVE_PATH).read_bytes(),
        "candidate": (REPO_ROOT / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH).read_bytes(),
        "extension": (
            REPO_ROOT / kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH
        ).read_bytes(),
    }


# ---------------------------------------------------------------------------
# CANONICAL_EOL_SOURCE_LOCK: mechanically derived from the trusted committed
# HEAD blob, re-verified independently of the tool's own internal constants,
# and re-verified reproducible under both an LF and a CRLF checkout.
# ---------------------------------------------------------------------------

def test_canonical_head_hash_matches_committed_source():
    """CANONICAL HEAD HASH TEST -- the three EXPECTED_*_CANONICAL_SHA256
    constants must equal sha256(canonicalize(git show HEAD:<path>)), i.e.
    they are mechanically derived from the approved committed KIRA source,
    never invented."""
    assert REPO_ROOT.name == "vne-current-kira-package-v1"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert head == EXPECTED_HEAD

    acceptance_blob = _git_head_blob(kira_tool.ACCEPTANCE_RELATIVE_PATH)
    candidate_blob = _git_head_blob(kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH)
    extension_blob = _git_head_blob(kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH)

    assert _canonical_sha256_bytes(acceptance_blob) == kira_tool.EXPECTED_ACCEPTANCE_CANONICAL_SHA256
    assert _canonical_sha256_bytes(candidate_blob) == kira_tool.EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256
    assert _canonical_sha256_bytes(extension_blob) == kira_tool.EXPECTED_DIMENSION_SEMANTICS_CANONICAL_SHA256


def test_current_working_tree_canonical_bytes_match_head_blob_canonical_bytes():
    """The current (possibly CRLF-checked-out) working tree must canonicalize
    to exactly the same bytes as the committed HEAD blob -- i.e. the working
    tree and HEAD are the SAME content, only EOL representation may differ."""
    for relative_path in _SOURCE_RELATIVE_PATHS:
        wt_bytes = (REPO_ROOT / relative_path).read_bytes()
        blob_bytes = _git_head_blob(relative_path)
        assert _canonical_sha256_bytes(wt_bytes) == _canonical_sha256_bytes(
            blob_bytes
        ), f"canonical mismatch for {relative_path}"


def test_exact_three_source_files_exist_with_expected_canonical_hashes():
    acceptance = REPO_ROOT / kira_tool.ACCEPTANCE_RELATIVE_PATH
    candidate = REPO_ROOT / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH
    extension = REPO_ROOT / kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH

    assert acceptance.is_file()
    assert candidate.is_file()
    assert extension.is_file()

    assert _canonical_sha256_file(acceptance) == kira_tool.EXPECTED_ACCEPTANCE_CANONICAL_SHA256
    assert _canonical_sha256_file(candidate) == kira_tool.EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256
    assert _canonical_sha256_file(extension) == kira_tool.EXPECTED_DIMENSION_SEMANTICS_CANONICAL_SHA256


def test_lf_source_accepted(tmp_path):
    """LF SOURCE ACCEPTED: an all-LF copy of the exact real content loads
    successfully through the full identity/binding gate."""
    real = _real_source_bytes()
    fake_repo = _write_fake_repo(
        tmp_path / "lf_repo",
        acceptance_bytes=_to_lf(real["acceptance"]),
        candidate_bytes=_to_lf(real["candidate"]),
        extension_bytes=_to_lf(real["extension"]),
    )

    source = kira_tool.load_and_verify_current_kira_source(fake_repo)
    assert source.candidate.subject_id == "kira"


def test_crlf_source_accepted(tmp_path):
    """CRLF SOURCE ACCEPTED: an all-CRLF copy of the exact real content loads
    successfully through the full identity/binding gate."""
    real = _real_source_bytes()
    fake_repo = _write_fake_repo(
        tmp_path / "crlf_repo",
        acceptance_bytes=_to_crlf(real["acceptance"]),
        candidate_bytes=_to_crlf(real["candidate"]),
        extension_bytes=_to_crlf(real["extension"]),
    )

    source = kira_tool.load_and_verify_current_kira_source(fake_repo)
    assert source.candidate.subject_id == "kira"


def test_lf_and_crlf_canonical_source_lock_equal(tmp_path):
    """LF/CRLF CANONICAL LOCK EQUALITY: the same content checked out as LF
    vs CRLF produces the exact same canonical source lock."""
    real = _real_source_bytes()

    lf_repo = _write_fake_repo(
        tmp_path / "lf_repo",
        acceptance_bytes=_to_lf(real["acceptance"]),
        candidate_bytes=_to_lf(real["candidate"]),
        extension_bytes=_to_lf(real["extension"]),
    )
    crlf_repo = _write_fake_repo(
        tmp_path / "crlf_repo",
        acceptance_bytes=_to_crlf(real["acceptance"]),
        candidate_bytes=_to_crlf(real["candidate"]),
        extension_bytes=_to_crlf(real["extension"]),
    )

    lf_source = kira_tool.load_and_verify_current_kira_source(lf_repo)
    crlf_source = kira_tool.load_and_verify_current_kira_source(crlf_repo)

    # source_candidate_bytes holds the CANONICALIZED lock bytes.
    assert _sha256_bytes(lf_source.source_candidate_bytes) == _sha256_bytes(
        crlf_source.source_candidate_bytes
    )
    assert lf_source.source_candidate_raw == crlf_source.source_candidate_raw
    assert lf_source.acceptance_raw == crlf_source.acceptance_raw
    assert lf_source.dimension_semantics_raw == crlf_source.dimension_semantics_raw


def test_lf_and_crlf_package_identity_equal(tmp_path):
    """LF/CRLF PACKAGE EQUALITY: materializing from an LF source copy and a
    CRLF source copy of the exact same content produces the same packageHash,
    the same manifest bytes, and every package-relative file byte-identical."""
    real = _real_source_bytes()

    lf_repo = _write_fake_repo(
        tmp_path / "lf_repo",
        acceptance_bytes=_to_lf(real["acceptance"]),
        candidate_bytes=_to_lf(real["candidate"]),
        extension_bytes=_to_lf(real["extension"]),
    )
    crlf_repo = _write_fake_repo(
        tmp_path / "crlf_repo",
        acceptance_bytes=_to_crlf(real["acceptance"]),
        candidate_bytes=_to_crlf(real["candidate"]),
        extension_bytes=_to_crlf(real["extension"]),
    )

    lf_dest = tmp_path / "lf_package"
    crlf_dest = tmp_path / "crlf_package"

    lf_result = kira_tool.materialize_current_kira_package_v1(lf_dest, repo_root=lf_repo)
    crlf_result = kira_tool.materialize_current_kira_package_v1(
        crlf_dest, repo_root=crlf_repo
    )

    assert lf_result.package_hash == crlf_result.package_hash

    lf_bytes = _all_file_bytes(lf_dest)
    crlf_bytes = _all_file_bytes(crlf_dest)
    assert set(lf_bytes) == set(crlf_bytes)
    for path in lf_bytes:
        assert lf_bytes[path] == crlf_bytes[path], f"byte mismatch: {path}"

    # Also matches materializing directly from the real repo checkout.
    real_dest = tmp_path / "real_package"
    real_result = kira_tool.materialize_current_kira_package_v1(
        real_dest, repo_root=REPO_ROOT
    )
    assert real_result.package_hash == lf_result.package_hash


def test_exact_acceptance_id_subject_and_semantic_hash():
    source = kira_tool.load_and_verify_current_kira_source(REPO_ROOT)
    record = source.acceptance_raw["acceptance_record"]

    assert record["acceptance_id"] == "kira-accepted-package-001"
    assert record["subject_id"] == "kira"
    assert record["package_hash"] == kira_tool.EXPECTED_ACCEPTED_SEMANTIC_HASH
    assert record["decision"] == "HUMAN_APPROVED"


def test_candidate_package_id_version_and_subject():
    source = kira_tool.load_and_verify_current_kira_source(REPO_ROOT)

    assert source.candidate.subject_id == "kira"
    assert source.candidate.package_id == "kira-r4-canonical-run-1-package"
    assert isinstance(source.candidate.package_version, int)
    # DRAFT is what the source actually contains; must not be rewritten.
    assert source.candidate.status.value == "DRAFT"


def test_dimension_extension_binding_to_accepted_hash():
    source = kira_tool.load_and_verify_current_kira_source(REPO_ROOT)
    record = source.acceptance_raw["acceptance_record"]

    assert source.dimension_semantics_raw["character_id"] == "kira"
    assert (
        source.dimension_semantics_raw["target_accepted_source_hash"]
        == record["package_hash"]
    )


def test_dimension_extension_binding_mismatch_fails_closed(tmp_path):
    # Real repo copy with only the extension file tampered -- exercises the
    # actual load_and_verify_current_kira_source binding check end-to-end
    # (not just the canonical lock, which stays satisfied since we recompute
    # and substitute the tool's own expected-hash constant for the tampered
    # bytes via monkeypatch, isolating the binding check specifically).
    real = _real_source_bytes()

    extension_raw = json.loads(real["extension"].decode("utf-8"))
    extension_raw["target_accepted_source_hash"] = "0" * 64
    tampered_extension_bytes = json.dumps(extension_raw, ensure_ascii=False).encode(
        "utf-8"
    )

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=real["acceptance"],
        candidate_bytes=real["candidate"],
        extension_bytes=tampered_extension_bytes,
    )

    tampered_canonical_sha = _canonical_sha256_bytes(tampered_extension_bytes)

    with patch.object(
        kira_tool, "EXPECTED_DIMENSION_SEMANTICS_CANONICAL_SHA256", tampered_canonical_sha
    ):
        with pytest.raises(kira_tool.SourceLockError, match="not bound"):
            kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_source_lock_fails_closed_on_any_non_eol_byte_change(tmp_path):
    real = _real_source_bytes()

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=real["acceptance"],
        candidate_bytes=real["candidate"] + b" ",  # one extra byte, not an EOL change
        extension_bytes=real["extension"],
    )

    with pytest.raises(kira_tool.SourceLockError):
        kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_non_eol_whitespace_change_rejected(tmp_path):
    """NON-EOL WHITESPACE CHANGE REJECTED: inserting a single extra space
    between JSON tokens (valid JSON, not a CRLF/LF difference) must still
    fail the canonical lock -- canonicalization is CRLF<->LF only."""
    real = _real_source_bytes()
    original = real["candidate"]

    # Insert one extra space right after the first '{' -- still valid JSON,
    # not any kind of newline, so the canonical lock must reject it.
    brace_index = original.index(b"{")
    mutated = original[: brace_index + 1] + b" " + original[brace_index + 1 :]
    assert mutated != original
    assert json.loads(mutated.decode("utf-8")) == json.loads(original.decode("utf-8"))

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=real["acceptance"],
        candidate_bytes=mutated,
        extension_bytes=real["extension"],
    )

    with pytest.raises(kira_tool.SourceLockError):
        kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_bare_cr_rejected():
    with pytest.raises(kira_tool.SourceLockError, match="bare CR"):
        kira_tool._canonicalize_source_lock_bytes(
            b'{"a": 1}\r"mid-file bare CR"\n', label="synthetic"
        )

    # A lone trailing CR (never followed by LF) must also fail closed.
    with pytest.raises(kira_tool.SourceLockError, match="bare CR"):
        kira_tool._canonicalize_source_lock_bytes(b'{"a": 1}\r', label="synthetic")

    # Sanity: a normal CRLF file canonicalizes without error.
    assert kira_tool._canonicalize_source_lock_bytes(
        b'{"a": 1}\r\n', label="synthetic"
    ) == b'{"a": 1}\n'


def test_bare_cr_in_real_source_shape_rejected(tmp_path):
    """Same bare-CR rule, exercised end-to-end against a realistic file."""
    real = _real_source_bytes()
    lf_candidate = _to_lf(real["candidate"])
    # Inject one lone CR (no following LF) mid-file.
    injected = lf_candidate[:200] + b"\r" + lf_candidate[200:]

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=_to_lf(real["acceptance"]),
        candidate_bytes=injected,
        extension_bytes=_to_lf(real["extension"]),
    )

    with pytest.raises(kira_tool.SourceLockError, match="bare CR"):
        kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_acceptance_content_change_rejected(tmp_path):
    """ACCEPTANCE CONTENT CHANGE REJECTED: a semantic edit to
    ACCEPTANCE.json (not merely an EOL change) must fail the canonical lock."""
    real = _real_source_bytes()
    acceptance_raw = json.loads(real["acceptance"].decode("utf-8"))
    acceptance_raw["acceptance_record"]["reason"] = (
        acceptance_raw["acceptance_record"]["reason"] + " (tampered)"
    )
    tampered_bytes = json.dumps(acceptance_raw, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    assert tampered_bytes != real["acceptance"]

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=tampered_bytes,
        candidate_bytes=real["candidate"],
        extension_bytes=real["extension"],
    )

    with pytest.raises(kira_tool.SourceLockError):
        kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_extension_content_change_rejected(tmp_path):
    """EXTENSION CONTENT CHANGE REJECTED: a semantic edit to the
    dimension-semantics extension (not merely an EOL change, and not the
    binding field) must fail the canonical lock."""
    real = _real_source_bytes()
    extension_raw = json.loads(real["extension"].decode("utf-8"))
    extension_raw["description"] = extension_raw["description"] + " (tampered)"
    tampered_bytes = json.dumps(extension_raw, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    assert tampered_bytes != real["extension"]

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=real["acceptance"],
        candidate_bytes=real["candidate"],
        extension_bytes=tampered_bytes,
    )

    with pytest.raises(kira_tool.SourceLockError):
        kira_tool.load_and_verify_current_kira_source(fake_repo)


def test_old_kira_package_hash_is_refused_if_ever_matched(tmp_path):
    # End-to-end: an ACCEPTANCE.json whose package_hash resolves to the OLD
    # Kira package identity must be refused, even if it otherwise looks
    # structurally valid (real, untouched source_candidate.json /
    # extension). EXPECTED_ACCEPTED_SEMANTIC_HASH is patched to the OLD
    # hash purely so the earlier semantic-hash-match gate does not mask the
    # OLD_KIRA_CONTAMINATION guard being tested here.
    real = _real_source_bytes()

    acceptance_raw = json.loads(real["acceptance"].decode("utf-8"))
    acceptance_raw["acceptance_record"]["package_hash"] = kira_tool.OLD_KIRA_PACKAGE_HASH
    tampered_acceptance_bytes = json.dumps(acceptance_raw, ensure_ascii=False).encode(
        "utf-8"
    )

    fake_repo = _write_fake_repo(
        tmp_path / "fake_repo",
        acceptance_bytes=tampered_acceptance_bytes,
        candidate_bytes=real["candidate"],
        extension_bytes=real["extension"],
    )

    tampered_acceptance_canonical_sha = _canonical_sha256_bytes(tampered_acceptance_bytes)

    with patch.object(
        kira_tool, "EXPECTED_ACCEPTANCE_CANONICAL_SHA256", tampered_acceptance_canonical_sha
    ), patch.object(
        kira_tool, "EXPECTED_ACCEPTED_SEMANTIC_HASH", kira_tool.OLD_KIRA_PACKAGE_HASH
    ):
        with pytest.raises(kira_tool.SourceLockError, match="OLD Kira"):
            kira_tool.load_and_verify_current_kira_source(fake_repo)


# ---------------------------------------------------------------------------
# Materialization: identity, domain mapping, full preservation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def materialized_once(tmp_path_factory):
    dest = tmp_path_factory.mktemp("kira_pkg_once") / "package"
    result = kira_tool.materialize_current_kira_package_v1(dest, repo_root=REPO_ROOT)
    return dest, result


def test_exact_package_identity(materialized_once):
    root, result = materialized_once
    meta = _package_json(root)

    assert meta["characterId"] == "kira"
    assert meta["releaseId"] == "crp-import-v1"
    assert meta["displayName"] == "Кира — актуальная CRP"
    assert meta["authorityClass"] == "LEGACY_COMPAT"
    assert meta["packageOrigin"] == "LEGACY_IMPORT"
    assert "acceptedAggregateHash" not in meta
    assert "acceptanceRecordHash" not in meta


def test_no_release_id_forbidden_substrings():
    for forbidden in ("latest", "current", "active", "legacy-compat-v2"):
        assert forbidden not in kira_tool.RELEASE_ID


def test_no_character_platform_acceptance_generated(materialized_once):
    root, result = materialized_once

    assert not (root / "provenance" / "acceptance.json").exists()
    assert "provenance/acceptance.json" not in {
        entry.path for entry in result.manifest.files
    }


def test_correct_domain_mapping(materialized_once):
    root, _ = materialized_once
    source_raw = json.loads(
        (REPO_ROOT / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH).read_bytes().decode("utf-8")
    )

    core_identity = json.loads((root / "domains" / "core_identity.json").read_bytes())
    assert (
        core_identity["content"]["structured"]["crpV1"]["identity_biography_candidate"]
        == source_raw["identity_biography_candidate"]
    )

    psychology = json.loads((root / "domains" / "psychology.json").read_bytes())
    assert (
        psychology["content"]["structured"]["crpV1"]["psychology_candidate"]
        == source_raw["psychology_candidate"]
    )
    assert (
        psychology["content"]["structured"]["crpV1"]["behavior_candidate"]
        == source_raw["behavior_candidate"]
    )

    speech = json.loads((root / "domains" / "speech.json").read_bytes())
    assert (
        speech["content"]["structured"]["crpV1"]["voice_candidate"]
        == source_raw["voice_candidate"]
    )

    relationships = json.loads((root / "domains" / "relationships.json").read_bytes())
    assert (
        relationships["content"]["structured"]["crpV1"]["relationships_candidate"]
        == source_raw["relationships_candidate"]
    )

    boundaries = json.loads(
        (root / "domains" / "interaction_boundaries.json").read_bytes()
    )
    assert (
        boundaries["content"]["structured"]["crpV1"]["boundaries_candidate"]
        == source_raw["boundaries_candidate"]
    )
    assert (
        boundaries["content"]["structured"]["crpV1"]["intimacy_candidate"]
        == source_raw["intimacy_candidate"]
    )


def test_visual_identity_explicitly_empty(materialized_once):
    root, _ = materialized_once
    visual = json.loads((root / "domains" / "visual_identity.json").read_bytes())

    assert visual["contentState"] == "EXPLICITLY_EMPTY"
    assert visual["content"]["structured"] == {}
    assert visual["content"]["legacyPayload"] == []
    assert visual["provenanceRefs"] == []


def test_no_snapshot_or_portrait_or_asset_imported(materialized_once):
    root, result = materialized_once

    assets = json.loads((root / "assets" / "asset_index.json").read_bytes())
    prompts = json.loads((root / "prompts" / "prompt_index.json").read_bytes())

    assert assets == {"assets": []}
    assert prompts == {"prompts": []}

    for entry in result.manifest.files:
        assert not entry.path.startswith("assets/references/")
        assert "snapshot" not in entry.path.lower()
        assert "portrait" not in entry.path.lower()


def test_no_runtime_memory_or_session_state_files(materialized_once):
    root, result = materialized_once
    paths = {entry.path for entry in result.manifest.files}

    expected = {
        "assets/asset_index.json",
        "domains/core_identity.json",
        "domains/interaction_boundaries.json",
        "domains/psychology.json",
        "domains/relationships.json",
        "domains/speech.json",
        "domains/visual_identity.json",
        "package.json",
        "prompts/prompt_index.json",
        "provenance/contradictions.json",
        "provenance/provenance.json",
        "provenance/source_acceptance.json",
        "provenance/source_candidate.json",
        "extensions/dimension_semantics/v1.json",
        "unknowns/unknowns.json",
    }

    assert paths == expected

    for forbidden in ("sqlite", "runtime_memory", "runtime_state", "session"):
        assert not any(forbidden in p.lower() for p in paths)


def test_full_candidate_preservation_including_nulls_and_empties(materialized_once):
    root, _ = materialized_once
    original_bytes = (
        REPO_ROOT / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH
    ).read_bytes()
    original = json.loads(original_bytes.decode("utf-8"))
    embedded = json.loads(
        (root / "provenance" / "source_candidate.json").read_bytes().decode("utf-8")
    )

    assert embedded == original
    assert embedded["lineage"] is None
    assert embedded["audit_result"] is None
    assert embedded["seed_memory_candidate"] == {}
    assert embedded["role_result_refs"] == []
    assert embedded["behavioral_validation_refs"] == []
    assert len(embedded["claims"]) == len(original["claims"]) == 258
    assert len(embedded["contradictions"]) == len(original["contradictions"]) == 5
    assert len(embedded["unknowns"]) == len(original["unknowns"]) == 14
    assert embedded["status"] == "DRAFT"


def test_source_acceptance_and_extension_embedded_verbatim(materialized_once):
    root, _ = materialized_once

    original_acceptance = json.loads(
        (REPO_ROOT / kira_tool.ACCEPTANCE_RELATIVE_PATH).read_bytes().decode("utf-8")
    )
    embedded_acceptance = json.loads(
        (root / "provenance" / "source_acceptance.json").read_bytes().decode("utf-8")
    )
    assert embedded_acceptance == original_acceptance

    original_extension = json.loads(
        (REPO_ROOT / kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH)
        .read_bytes()
        .decode("utf-8")
    )
    embedded_extension = json.loads(
        (root / "extensions" / "dimension_semantics" / "v1.json")
        .read_bytes()
        .decode("utf-8")
    )
    assert embedded_extension == original_extension


def test_contradictions_and_unknowns_routed_and_preserved(materialized_once):
    root, _ = materialized_once
    contradictions = json.loads(
        (root / "provenance" / "contradictions.json").read_bytes()
    )["contradictions"]
    unknowns = json.loads((root / "unknowns" / "unknowns.json").read_bytes())["unknowns"]

    assert len(contradictions) == 5
    assert len(unknowns) == 14

    ids_seen = {c["contradictionId"] for c in contradictions}
    assert ids_seen == {
        "r2-contradiction-0001",
        "r2-contradiction-0002",
        "r4-contra-0001",
        "r4-contra-0002",
        "r4-contra-0003",
    }

    for record in contradictions:
        assert record["domainId"] in (
            "core_identity",
            "psychology",
            "speech",
            "relationships",
            "interaction_boundaries",
        )
        assert record["provenanceRefs"]

    for record in unknowns:
        assert record["domainId"] in (
            "core_identity",
            "psychology",
            "speech",
            "relationships",
            "interaction_boundaries",
        )
        assert record["provenanceRefs"]


def test_provenance_records_reference_source_candidate(materialized_once):
    root, _ = materialized_once
    provenance = json.loads((root / "provenance" / "provenance.json").read_bytes())[
        "provenance"
    ]

    assert len(provenance) == 7

    for record in provenance:
        assert record["sourceRelativePath"] == "provenance/source_candidate.json"
        # The provenance sourceSha256 is the CANONICAL (EOL-normalized) lock,
        # not a raw-working-tree-bytes hash -- reproducible across checkouts.
        assert record["sourceSha256"] == kira_tool.EXPECTED_SOURCE_CANDIDATE_CANONICAL_SHA256
        assert record["authoringMethod"] == "CRP"


# ---------------------------------------------------------------------------
# Negative: ambiguous/unresolvable routing must fail closed
# ---------------------------------------------------------------------------

def test_unrouteable_module_prefix_fails_closed():
    from services.crp_authoring.contracts import (
        ClaimStatus,
        ClaimType,
        Confidence,
        RoleClaim,
        SourceType,
    )

    bad_claim = RoleClaim(
        claim_id="bad-1",
        subject_id="kira",
        role_id="R1",
        claim="unrouteable",
        claim_type=ClaimType.FACT,
        source_evidence_ids=("ev-1",),
        source_type_summary=(SourceType.OWNER_DIRECT,),
        confidence=Confidence.KNOWN,
        rationale_summary="test",
        status=ClaimStatus.PROPOSED,
        target_module_or_layer="totally_unknown_module.field",
    )

    with pytest.raises(kira_tool.AmbiguousRoutingError):
        kira_tool._module_of(bad_claim)


def test_contradiction_spanning_two_domains_fails_closed():
    from services.crp_authoring.contracts import (
        ClaimStatus,
        ClaimType,
        Confidence,
        ContradictionRecord as CrpContradictionRecord,
        RoleClaim,
        ResolutionStatus,
        Severity,
        SourceType,
    )
    from services.crp_authoring.candidate_package import CandidateCharacterPackage, PackageStatus
    from datetime import datetime, timezone

    def claim(claim_id, module):
        return RoleClaim(
            claim_id=claim_id,
            subject_id="kira",
            role_id="R1",
            claim="x",
            claim_type=ClaimType.FACT,
            source_evidence_ids=("ev-1",),
            source_type_summary=(SourceType.OWNER_DIRECT,),
            confidence=Confidence.KNOWN,
            rationale_summary="test",
            status=ClaimStatus.PROPOSED,
            target_module_or_layer=module,
        )

    claims = (
        claim("c1", "identity_biography.age"),
        claim("c2", "voice.register"),
    )
    contradiction = CrpContradictionRecord(
        contradiction_id="cross-domain-1",
        subject_id="kira",
        claim_ids=("c1", "c2"),
        source_evidence_ids=(),
        description="spans two domains",
        severity=Severity.MATERIAL,
        resolution_status=ResolutionStatus.OPEN,
        requires_human=False,
        created_by="test",
    )
    package = CandidateCharacterPackage(
        package_id="pkg-1",
        subject_id="kira",
        package_version=0,
        source_snapshot_id="snap-1",
        role_result_refs=(),
        claims=claims,
        contradictions=(contradiction,),
        unknowns=(),
        psychology_candidate={},
        voice_candidate={},
        validation_results={},
        audit_result=None,
        provenance_manifest={},
        created_at=datetime.now(timezone.utc),
        status=PackageStatus.DRAFT,
    )

    index = kira_tool._build_claim_module_index(package)

    with pytest.raises(kira_tool.AmbiguousRoutingError):
        kira_tool._route_contradictions(package, index)


# ---------------------------------------------------------------------------
# Output safety
# ---------------------------------------------------------------------------

def test_output_requires_explicit_destination_no_default():
    import inspect

    sig = inspect.signature(kira_tool.materialize_current_kira_package_v1)
    assert sig.parameters["destination"].default is inspect.Parameter.empty


def test_forbidden_default_destinations_rejected(tmp_path):
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()

    for forbidden in (
        fake_repo / "accepted" / "kira" / "pkg",
        fake_repo / "character_packages" / "kira" / "pkg",
        fake_repo,
    ):
        with pytest.raises(kira_tool.CurrentKiraPackageMaterializationError):
            kira_tool._reject_unsafe_destination(forbidden, fake_repo)


def test_destination_must_not_already_exist(materialized_once):
    root, _ = materialized_once

    with pytest.raises(Exception):
        kira_tool.materialize_current_kira_package_v1(root, repo_root=REPO_ROOT)


def test_tool_module_not_imported_by_companion_runtime():
    import services.character_companion.service as companion_service
    import services.character_companion.catalog as companion_catalog

    for module in (companion_service, companion_catalog):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "materialize_current_kira_package_v1" not in source


# ---------------------------------------------------------------------------
# Twin materialization: fully deterministic, no timestamps in identity
# ---------------------------------------------------------------------------

def test_twin_materialization_is_byte_identical(tmp_path):
    one = tmp_path / "one" / "package"
    two = tmp_path / "two" / "package"

    result_one = kira_tool.materialize_current_kira_package_v1(one, repo_root=REPO_ROOT)
    result_two = kira_tool.materialize_current_kira_package_v1(two, repo_root=REPO_ROOT)

    assert result_one.package_hash == result_two.package_hash

    bytes_one = _all_file_bytes(one)
    bytes_two = _all_file_bytes(two)

    assert set(bytes_one) == set(bytes_two)
    for path in bytes_one:
        assert bytes_one[path] == bytes_two[path], f"byte mismatch: {path}"


# ---------------------------------------------------------------------------
# Platform (VCP) and S6 (Companion character_import) verification
# ---------------------------------------------------------------------------

def test_platform_verification(materialized_once):
    root, result = materialized_once
    verified = verify_materialized_package(root)
    assert verified.package_hash == result.package_hash


def test_s6_character_import_verification(materialized_once):
    root, result = materialized_once
    verified = verify_character_package_v1(root)

    assert verified.character_id == "kira"
    assert verified.release_id == "crp-import-v1"
    assert verified.authority_class == "LEGACY_COMPAT"
    assert verified.package_origin == "LEGACY_IMPORT"
    assert verified.package_hash == result.package_hash


# ---------------------------------------------------------------------------
# Package-only recovery: block original source access during recovery
# ---------------------------------------------------------------------------

def _blocked_read_bytes(self: Path, *args, **kwargs):
    resolved = self.resolve()
    for forbidden_dir in (REPO_ROOT / "accepted", REPO_ROOT / "character_packages"):
        forbidden_dir = forbidden_dir.resolve()
        if resolved == forbidden_dir or forbidden_dir in resolved.parents:
            raise AssertionError(
                f"package-only recovery attempted to read the ORIGINAL source: {resolved}"
            )
    return _REAL_READ_BYTES(self, *args, **kwargs)


_REAL_READ_BYTES = Path.read_bytes


def test_package_only_candidate_acceptance_extension_recovery_and_grounding_equality(
    tmp_path,
):
    dest = tmp_path / "package"
    kira_tool.materialize_current_kira_package_v1(dest, repo_root=REPO_ROOT)

    # Ground truth, computed BEFORE any source access is blocked.
    current_raw = json.loads(
        (REPO_ROOT / kira_tool.SOURCE_CANDIDATE_RELATIVE_PATH).read_bytes().decode("utf-8")
    )
    current_candidate = rehydrate_candidate_package(current_raw)
    current_grounding = render_accepted_grounding(current_candidate)

    current_acceptance_bytes = (
        REPO_ROOT / kira_tool.ACCEPTANCE_RELATIVE_PATH
    ).read_bytes()
    current_extension_bytes = (
        REPO_ROOT / kira_tool.DIMENSION_SEMANTICS_RELATIVE_PATH
    ).read_bytes()

    assert len(current_grounding) == 29965

    # Package-only recovery phase: original source access is actively
    # blocked (raises if the recovery code below ever touches it).
    with patch.object(Path, "read_bytes", _blocked_read_bytes):
        recovered_raw = json.loads(
            (dest / "provenance" / "source_candidate.json")
            .read_bytes()
            .decode("utf-8")
        )
        recovered_candidate = rehydrate_candidate_package(recovered_raw)
        recovered_grounding = render_accepted_grounding(recovered_candidate)

        recovered_acceptance_bytes = (
            dest / "provenance" / "source_acceptance.json"
        ).read_bytes()
        recovered_extension_bytes = (
            dest / "extensions" / "dimension_semantics" / "v1.json"
        ).read_bytes()

    # Exact content equality -- not merely length.
    assert recovered_raw == current_raw
    assert isinstance(recovered_candidate, type(current_candidate))
    assert recovered_grounding == current_grounding
    assert len(recovered_grounding) == 29965

    assert json.loads(recovered_acceptance_bytes.decode("utf-8")) == json.loads(
        current_acceptance_bytes.decode("utf-8")
    )
    assert json.loads(recovered_extension_bytes.decode("utf-8")) == json.loads(
        current_extension_bytes.decode("utf-8")
    )


# ---------------------------------------------------------------------------
# Negative: a changed claim (IDs unchanged) must be rejected by the full
# source-file SHA lock, independent of any internal semantic/package hash.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("eol_transform", [_to_lf, _to_crlf], ids=["lf", "crlf"])
def test_changed_claim_text_with_unchanged_ids_is_rejected_by_canonical_lock(
    tmp_path, eol_transform
):
    real = _real_source_bytes()
    original_candidate_bytes = real["candidate"]
    original = json.loads(original_candidate_bytes.decode("utf-8"))

    mutated = json.loads(original_candidate_bytes.decode("utf-8"))
    first_claim = mutated["claims"][0]
    assert first_claim["claim_id"] == original["claims"][0]["claim_id"]
    first_claim["claim"] = first_claim["claim"] + " MUTATED"

    mutated_bytes = json.dumps(mutated, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    # Confirm the mutation actually changed the bytes (sanity, not the point).
    assert mutated_bytes != original_candidate_bytes

    fake_repo = _write_fake_repo(
        tmp_path / f"fake_repo_{eol_transform.__name__}",
        acceptance_bytes=eol_transform(real["acceptance"]),
        candidate_bytes=eol_transform(mutated_bytes),
        extension_bytes=eol_transform(real["extension"]),
    )

    # The tool's independent canonical (EOL-normalized) full-file SHA-256
    # lock rejects this even though claim_id / package_id / subject_id are
    # all unchanged and any ID-keyed or partial hash could plausibly miss
    # the edit -- in both an LF and a CRLF checkout of the mutated file.
    with pytest.raises(kira_tool.SourceLockError):
        kira_tool.load_and_verify_current_kira_source(fake_repo)
