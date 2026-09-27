"""OD-LAB-VCP-INTIMACY-MAPPING-01 tests: sexology -> optional intimacy domain.

These tests operate at the domain-compilation boundary only. They prove that a
revision carrying meaningful sexology compiles to the six required domains PLUS
an optional ``intimacy`` domain, and that absent/empty sexology yields exactly
the six required domains (no ``intimacy``).

NOTE: full publish -> .vchar verification with ``intimacy`` present is gated by
the VCP contract (VCP-PKG-001 rejects ``domains/intimacy.json`` for
ACCEPTED_RELEASE). That boundary is reported, not exercised here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._vcp_dependency_gate import require_pinned_vcp

require_pinned_vcp()  # hard VCP dependency gate (replaces silent importorskip)

from services.character_authoring import CharacterAuthoringStore
from services.character_publication.vcp_domains import (
    compile_authoring_revision_to_vcp_domains,
)
from voyage_character_platform.contracts import ContentState

EXPECTED_REQUIRED_DOMAIN_IDS = (
    "core_identity",
    "psychology",
    "speech",
    "relationships",
    "visual_identity",
    "interaction_boundaries",
)

SEXOLOGY_KEYS = (
    "intimacy_attitudes",
    "preferences",
    "emotional_dynamics",
    "communication",
    "vulnerabilities",
    "intimacy_boundaries",
)


def semantic(**extra) -> dict:
    data = {
        "identity": {"display_name": "Atlas"},
        "biography": "BIOGRAPHY",
        "psychology": {
            "personality": ["P"],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "", "register": None},
        "character_relations": {"relational_tendencies": [], "attachment_traits": []},
        "appearance": {},
        "boundaries": {},
        "visual_identity": {},
    }
    data.update(extra)
    return data


def sexology(**overrides) -> dict:
    value = {key: [] for key in SEXOLOGY_KEYS}
    value.update(overrides)
    return value


def build_revision(tmp_path: Path, data: dict):
    store = CharacterAuthoringStore(tmp_path / "authoring")
    store.create_character("atlas")
    store.create_version("atlas", "version-v1", version_label="V1")
    record = store.persist_revision("atlas", "version-v1", "revision-r1", data)
    return store, record


def compile_record(store, record):
    return compile_authoring_revision_to_vcp_domains(
        store,
        character_id="atlas",
        version_id="version-v1",
        revision_id="revision-r1",
        snapshot_hash=record.snapshot_hash,
    )


def test_sexology_maps_to_optional_intimacy_domain(tmp_path):
    store, record = build_revision(
        tmp_path, semantic(sexology=sexology(intimacy_attitudes=["tender"]))
    )
    result = compile_record(store, record)

    by_id = {domain.domain_id: domain for domain in result.domains}
    assert set(by_id) == set(EXPECTED_REQUIRED_DOMAIN_IDS) | {"intimacy"}
    assert by_id["intimacy"].content_state is ContentState.POPULATED
    assert by_id["intimacy"].domain_schema_version == "1.0"
    assert by_id["intimacy"].structured["intimacy_attitudes"] == ["tender"]


def test_no_sexology_produces_exactly_six_required_domains(tmp_path):
    store, record = build_revision(tmp_path, semantic())
    result = compile_record(store, record)
    assert tuple(d.domain_id for d in result.domains) == EXPECTED_REQUIRED_DOMAIN_IDS
    assert "intimacy" not in {d.domain_id for d in result.domains}


def test_empty_sexology_omits_intimacy_domain(tmp_path):
    store, record = build_revision(tmp_path, semantic(sexology=sexology()))
    result = compile_record(store, record)
    assert tuple(d.domain_id for d in result.domains) == EXPECTED_REQUIRED_DOMAIN_IDS
    assert "intimacy" not in {d.domain_id for d in result.domains}


def test_required_domain_ids_remain_exactly_six(tmp_path):
    store, record = build_revision(
        tmp_path, semantic(sexology=sexology(preferences=["slow"]))
    )
    result = compile_record(store, record)
    required = [d.domain_id for d in result.domains if d.domain_id != "intimacy"]
    assert required == list(EXPECTED_REQUIRED_DOMAIN_IDS)
