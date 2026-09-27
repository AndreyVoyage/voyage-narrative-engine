"""Slice B exact Character Authoring revision -> VCP domain tests."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests._vcp_dependency_gate import require_pinned_vcp

require_pinned_vcp()  # hard VCP dependency gate (replaces silent importorskip)

from services.character_authoring import (
    CharacterAuthoringNotFoundError,
    CharacterAuthoringStore,
    CharacterSemantic,
)
from services.character_publication.vcp_domains import (
    AuthoringVcpDomainCompilationError,
    AuthoringVcpSourcePinMismatchError,
    AuthoringVcpVisualMappingError,
    compile_authoring_revision_to_vcp_domains,
)
from voyage_character_platform.canonical_json import canonical_json_bytes
from voyage_character_platform.contracts import ContentState, DomainEnvelope
from voyage_character_platform.package_v1 import get_domain_schema_version_v1
from voyage_character_platform.validation import validate_required_domains

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_DOMAIN_IDS = (
    "core_identity",
    "psychology",
    "speech",
    "relationships",
    "visual_identity",
    "interaction_boundaries",
)


def distinctive_semantic(*, name: str = "IDENTITY_SENTINEL") -> dict:
    return {
        "identity": {"display_name": name, "kind": "IDENTITY_KIND_SENTINEL"},
        "biography": "BIOGRAPHY_SENTINEL",
        "psychology": {
            "personality": ["PSYCHOLOGY_SENTINEL"],
            "behavioral_traits": ["BEHAVIOR_SENTINEL"],
            "emotional_tendencies": ["EMOTION_SENTINEL"],
            "goals_motivations": ["GOAL_SENTINEL"],
        },
        "speech": {
            "speech_style": "SPEECH_SENTINEL",
            "register": "REGISTER_SENTINEL",
        },
        "character_relations": {
            "relational_tendencies": ["RELATIONSHIP_SENTINEL"],
            "attachment_traits": ["ATTACHMENT_SENTINEL"],
        },
        "appearance": {
            "descriptors": ["APPEARANCE_SENTINEL"],
            "height_cm": 181,
        },
        "boundaries": {"principles": ["BOUNDARY_SENTINEL"]},
        "visual_identity": {},
    }


def empty_semantic() -> dict:
    return {
        "identity": {},
        "biography": "",
        "psychology": {
            "personality": [],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "", "register": None},
        "character_relations": {
            "relational_tendencies": [],
            "attachment_traits": [],
        },
        "appearance": {},
        "boundaries": {},
        "visual_identity": {"references": []},
    }


def build_revision(
    tmp_path: Path,
    *,
    semantic: dict | None = None,
    revision_id: str = "revision-r1",
):
    store = CharacterAuthoringStore(tmp_path / "authoring")
    store.create_character("atlas")
    pointer = store.create_version(
        "atlas", "version-v1", version_label="Version 1"
    )
    record = store.persist_revision(
        "atlas",
        "version-v1",
        revision_id,
        distinctive_semantic() if semantic is None else semantic,
    )
    return store, pointer, record


def compile_record(store, record):
    return compile_authoring_revision_to_vcp_domains(
        store,
        character_id=record.character_id,
        version_id=record.version_id,
        revision_id=record.revision_id,
        snapshot_hash=record.snapshot_hash,
    )


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def by_id(result) -> dict[str, DomainEnvelope]:
    return {domain.domain_id: domain for domain in result.domains}


def test_exact_source_pin_loads_and_is_preserved(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    result = compile_record(store, record)

    assert result.source.to_dict() == {
        "source_character_id": "atlas",
        "source_version_id": "version-v1",
        "source_revision_id": "revision-r1",
        "source_snapshot_hash": record.snapshot_hash,
    }


def test_wrong_snapshot_hash_fails_closed(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    with pytest.raises(AuthoringVcpSourcePinMismatchError):
        compile_authoring_revision_to_vcp_domains(
            store,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash="f" * 64,
        )

    assert store.load_revision(
        "atlas", "version-v1", "revision-r1"
    ).snapshot_hash == record.snapshot_hash


def test_compiler_does_not_follow_selected_or_latest_revision(tmp_path):
    store, pointer, first = build_revision(tmp_path)
    second = store.persist_revision(
        "atlas",
        "version-v1",
        "revision-r2",
        distinctive_semantic(name="LATEST_POINTER_SENTINEL"),
    )
    store.update_version_pointer(
        replace(pointer, selected_revision_id=second.revision_id)
    )

    result = compile_record(store, first)

    assert by_id(result)["core_identity"].structured["identity"][
        "display_name"
    ] == "IDENTITY_SENTINEL"
    assert result.source.source_revision_id == "revision-r1"


def test_compilation_is_read_only_and_deterministic(tmp_path):
    store, _pointer, record = build_revision(tmp_path)
    before = files_under(store.root)

    first = compile_record(store, record)
    second = compile_record(store, record)

    assert first == second
    assert [domain.to_dict() for domain in first.domains] == [
        domain.to_dict() for domain in second.domains
    ]
    assert files_under(store.root) == before


def test_output_is_exactly_the_six_required_domains(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    result = compile_record(store, record)

    assert tuple(domain.domain_id for domain in result.domains) == (
        EXPECTED_DOMAIN_IDS
    )
    assert "intimacy" not in by_id(result)
    assert len(result.domains) == 6
    assert validate_required_domains(result.domains).ok


def test_distinctive_source_values_map_only_to_ratified_owners(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    domains = by_id(compile_record(store, record))

    assert domains["core_identity"].structured == {
        "identity": {
            "display_name": "IDENTITY_SENTINEL",
            "kind": "IDENTITY_KIND_SENTINEL",
        },
        "biography": "BIOGRAPHY_SENTINEL",
    }
    assert domains["psychology"].structured == record.semantic.to_dict()[
        "psychology"
    ]
    assert domains["speech"].structured == record.semantic.to_dict()["speech"]
    assert domains["relationships"].structured == record.semantic.to_dict()[
        "character_relations"
    ]
    assert domains["visual_identity"].structured == {
        "identityDescription": record.semantic.to_dict()["appearance"],
        "assetRefs": [],
        "promptRefs": [],
    }
    assert domains["interaction_boundaries"].structured == (
        record.semantic.to_dict()["boundaries"]
    )

    owners = {
        "BIOGRAPHY_SENTINEL": "core_identity",
        "PSYCHOLOGY_SENTINEL": "psychology",
        "SPEECH_SENTINEL": "speech",
        "RELATIONSHIP_SENTINEL": "relationships",
        "APPEARANCE_SENTINEL": "visual_identity",
        "BOUNDARY_SENTINEL": "interaction_boundaries",
    }
    serialized = {
        domain_id: json.dumps(domain.to_dict(), sort_keys=True)
        for domain_id, domain in domains.items()
    }
    for sentinel, owner in owners.items():
        assert [
            domain_id
            for domain_id, payload in serialized.items()
            if sentinel in payload
        ] == [owner]


def test_content_states_follow_actual_mapped_content(tmp_path):
    populated_store, _pointer, populated_record = build_revision(tmp_path / "p")
    empty_store, _pointer, empty_record = build_revision(
        tmp_path / "e", semantic=empty_semantic()
    )

    populated = by_id(compile_record(populated_store, populated_record))
    empty = by_id(compile_record(empty_store, empty_record))

    assert all(
        domain.content_state is ContentState.POPULATED
        for domain in populated.values()
    )
    assert empty["visual_identity"].content_state is ContentState.EXPLICITLY_EMPTY
    assert empty["visual_identity"].structured == {}
    assert (
        empty["interaction_boundaries"].content_state
        is ContentState.EXPLICITLY_EMPTY
    )
    assert all(
        domain.content_state is ContentState.EXPLICITLY_EMPTY
        for domain in empty.values()
    )
    assert validate_required_domains(tuple(empty.values())).ok


def test_empty_appearance_alone_makes_only_visual_explicitly_empty(tmp_path):
    semantic = distinctive_semantic()
    semantic["appearance"] = {}
    semantic["visual_identity"] = {"references": []}
    store, _pointer, record = build_revision(tmp_path, semantic=semantic)

    domains = by_id(compile_record(store, record))

    assert domains["visual_identity"].content_state is (
        ContentState.EXPLICITLY_EMPTY
    )
    assert domains["visual_identity"].structured == {}
    assert all(
        domain.content_state is ContentState.POPULATED
        for domain_id, domain in domains.items()
        if domain_id != "visual_identity"
    )


def test_every_domain_version_comes_from_vcp_authority(tmp_path, monkeypatch):
    store, _pointer, record = build_revision(tmp_path)
    from services.character_publication import vcp_domains as compiler_module

    calls: list[str] = []
    authoritative_lookup = get_domain_schema_version_v1

    def recording_lookup(domain_id: str) -> str:
        calls.append(domain_id)
        return authoritative_lookup(domain_id)

    monkeypatch.setattr(
        compiler_module.vcp_package_v1,
        "get_domain_schema_version_v1",
        recording_lookup,
    )

    result = compile_record(store, record)

    assert tuple(calls) == EXPECTED_DOMAIN_IDS
    assert all(
        domain.domain_schema_version
        == authoritative_lookup(domain.domain_id)
        for domain in result.domains
    )


def test_domains_use_empty_provenance_and_no_legacy_payload(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    result = compile_record(store, record)

    assert all(domain.provenance_refs == () for domain in result.domains)
    assert all(domain.legacy_payload == () for domain in result.domains)


@pytest.mark.parametrize(
    "visual_identity",
    [
        {"reference_asset_id": "raw-local-portrait"},
        {"references": [{"asset_id": "unregistered-portrait"}]},
        {"assetRefs": ["not-proven-package-ready"]},
    ],
)
def test_unresolved_authoring_visual_references_fail_closed(
    tmp_path, visual_identity
):
    semantic = distinctive_semantic()
    semantic["visual_identity"] = visual_identity
    store, _pointer, record = build_revision(tmp_path, semantic=semantic)

    with pytest.raises(AuthoringVcpVisualMappingError):
        compile_record(store, record)


def test_raw_visual_references_fail_closed_even_without_appearance(tmp_path):
    semantic = empty_semantic()
    semantic["visual_identity"] = {
        "references": [{"path": "local_runs/raw/portrait.png"}]
    }
    store, _pointer, record = build_revision(tmp_path, semantic=semantic)

    with pytest.raises(AuthoringVcpVisualMappingError):
        compile_record(store, record)


class PinOnlyStore:
    """Store double exposing only exact revision loads; pointer reads fail."""

    def __init__(self, delegate=None, *, record=None):
        self._delegate = delegate
        self._record = record
        self.calls: list[tuple[str, str, str]] = []

    def load_revision(self, character_id, version_id, revision_id):
        self.calls.append((character_id, version_id, revision_id))
        if self._record is not None:
            return self._record
        return self._delegate.load_revision(
            character_id, version_id, revision_id
        )

    def __getattr__(self, name):
        raise AssertionError(f"compiler must not access store.{name}")


def test_compiler_reads_only_the_exact_revision(tmp_path):
    store, _pointer, record = build_revision(tmp_path)
    pin_only = PinOnlyStore(store)

    result = compile_record(pin_only, record)

    assert pin_only.calls == [("atlas", "version-v1", "revision-r1")]
    assert result.source.source_snapshot_hash == record.snapshot_hash


def test_snapshot_hash_of_another_real_revision_fails_closed(tmp_path):
    store, _pointer, first = build_revision(tmp_path)
    second = store.persist_revision(
        "atlas",
        "version-v1",
        "revision-r2",
        distinctive_semantic(name="OTHER_REVISION_SENTINEL"),
    )
    assert second.snapshot_hash != first.snapshot_hash

    with pytest.raises(AuthoringVcpSourcePinMismatchError):
        compile_authoring_revision_to_vcp_domains(
            store,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash=second.snapshot_hash,
        )


def test_missing_revision_does_not_fall_back(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    with pytest.raises(CharacterAuthoringNotFoundError):
        compile_authoring_revision_to_vcp_domains(
            store,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-missing",
            snapshot_hash=record.snapshot_hash,
        )


def test_record_whose_semantic_does_not_hash_to_pin_fails_closed(tmp_path):
    store, _pointer, record = build_revision(tmp_path)
    tampered = replace(
        record,
        semantic=CharacterSemantic.from_dict(
            distinctive_semantic(name="TAMPERED_SENTINEL")
        ),
    )
    assert tampered.snapshot_hash == record.snapshot_hash

    with pytest.raises(AuthoringVcpSourcePinMismatchError):
        compile_record(PinOnlyStore(record=tampered), record)


def test_non_revision_record_from_store_fails_closed(tmp_path):
    _store, _pointer, record = build_revision(tmp_path)

    with pytest.raises(AuthoringVcpDomainCompilationError):
        compile_record(PinOnlyStore(record=record.to_dict()), record)


def test_invalid_source_coordinate_fails_before_loading(tmp_path):
    store, _pointer, record = build_revision(tmp_path)
    pin_only = PinOnlyStore(store)

    with pytest.raises(AuthoringVcpDomainCompilationError):
        compile_authoring_revision_to_vcp_domains(
            pin_only,
            character_id="atlas",
            version_id="version-v1",
            revision_id="revision-r1",
            snapshot_hash="not-a-hash",
        )
    assert pin_only.calls == []


def test_envelopes_are_canonical_vcp_json_without_legacy_payload(tmp_path):
    store, _pointer, record = build_revision(tmp_path)

    first = compile_record(store, record)
    second = compile_record(store, record)

    for left, right in zip(first.domains, second.domains):
        payload = left.to_dict()
        assert payload["content"]["legacyPayload"] == []
        assert payload["provenanceRefs"] == []
        assert canonical_json_bytes(payload) == canonical_json_bytes(
            right.to_dict()
        )


def test_compiler_is_not_reexported_or_loaded_at_lab_startup():
    import services.character_publication as publication

    assert not hasattr(publication, "compile_authoring_revision_to_vcp_domains")

    probe = (
        "import sys\n"
        "import services.character_publication\n"
        "import services.character_lab_application\n"
        "assert 'voyage_character_platform' not in sys.modules\n"
        "assert 'services.character_publication.vcp_domains' "
        "not in sys.modules\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
