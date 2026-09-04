#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused offline tests for the Scene Text Interpreter v0 + the CLI bridge.

Hermetic: no network, no real LLM, no image-provider call. The semantic
component is exercised through ``MockProposer`` / ``FixtureProposer`` so the
DETERMINISTIC trust boundary (grounding, allowlists, still selection, fail
closed) is what is actually under test.

    PROVIDER_CALLS = 0
    NETWORK = 0
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.scene_image_test_app as app  # noqa: E402
from services.reference_library import import_reference  # noqa: E402
from services.scene_text_interpreter import (  # noqa: E402
    AliasDataError,
    CharacterCountError,
    ConfidenceError,
    GroundingError,
    HallucinationError,
    LocationResolutionError,
    MockProposer,
    ProposalSchemaError,
    ProposedInterpretation,
    SceneTagError,
    StillSelectionError,
    UnresolvedItemsError,
    build_interpreter_input,
    interpret_scene_text,
    load_character_roster,
    load_location_roster,
    resolve_character,
    resolve_location,
    validate_and_build_plan,
)
from services.scene_text_interpreter.hashing import match_key  # noqa: E402

FIRST_PROOF_TEXT = (
    "Марина лежит на коврике в спортзале и делает растяжку.\n"
    "Максим находится рядом и наблюдает за её техникой.\n"
    "Марина поворачивает голову и смотрит на него."
)

_PROPOSAL_FIXTURE = _REPO_ROOT / "tests/fixtures/scene_text_interpreter/first_proof_proposal.json"

_PNG = b"\x89PNG\r\n\x1a\n"

# Every asset_id the real Reference Semantic Catalog references. The AUTO
# selector's catalog loader fails closed unless all of them exist in the
# manifest, so the hermetic AUTO repo synthesizes all of them (only the
# MARINA/MAKSIM bytes are ever read to build the bundle).
_CATALOG_ASSETS = [
    ("ANDREY_JUNIOR", "andrey_junior_face_01"),
    ("ANDREY_JUNIOR", "andrey_junior_face_support_01"),
    ("ANDREY_JUNIOR", "andrey_junior_body_01"),
    ("ANDREY_JUNIOR", "andrey_junior_gym_01"),
    ("OLGA", "olga_face_primary_01"),
    ("OLGA", "olga_face_canon_01"),
    ("OLGA", "olga_body_01"),
    ("OLGA", "olga_sports_01"),
    ("MARINA", "marina_face_01"),
    ("MARINA", "marina_face_support_01"),
    ("MARINA", "marina_body_01"),
    ("MARINA", "marina_sports_01"),
    ("MAKSIM", "maksim_face_01"),
    ("MAKSIM", "maksim_face_support_01"),
    ("MAKSIM", "maksim_body_01"),
    ("MAKSIM", "maksim_gym_01"),
]


def _base_proposal_dict() -> dict:
    """A fresh, deep copy of the recorded first-proof proposal payload."""
    data = json.loads(_PROPOSAL_FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data["proposal"])


def _mock(proposal_dict: dict) -> MockProposer:
    return MockProposer(ProposedInterpretation.from_dict(proposal_dict))


def _interpret(proposal_dict: dict, *, text: str = FIRST_PROOF_TEXT):
    return interpret_scene_text(text, repo_root=_REPO_ROOT, proposer=_mock(proposal_dict))


# ---------------------------------------------------------------------------
# Alias data (character)
# ---------------------------------------------------------------------------


def test_marina_russian_alias_resolves_to_marina():
    roster = load_character_roster(_REPO_ROOT)
    assert resolve_character("Марина", roster) == "MARINA"
    assert resolve_character("Марину", roster) == "MARINA"
    assert resolve_character("«Марина»", roster) == "MARINA"


def test_maksim_russian_alias_resolves_to_maksim():
    roster = load_character_roster(_REPO_ROOT)
    assert resolve_character("Максим", roster) == "MAKSIM"
    assert resolve_character("Максима", roster) == "MAKSIM"


def test_unknown_character_alias_returns_none():
    roster = load_character_roster(_REPO_ROOT)
    assert resolve_character("Владимир", roster) is None
    assert resolve_character("", roster) is None


def test_ambiguous_character_alias_data_fails(tmp_path):
    bad = {
        "schema_version": "vne_character_name_aliases/0.1",
        "characters": [
            {"character_id": "MARINA", "provider_alias": "Marina",
             "surface_aliases": ["Марина", "Саша"]},
            {"character_id": "MAKSIM", "provider_alias": "Maksim",
             "surface_aliases": ["Максим", "Саша"]},
        ],
    }
    p = tmp_path / "bad_char_aliases.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AliasDataError):
        load_character_roster(_REPO_ROOT, path=p)


def test_character_alias_unknown_roster_id_fails(tmp_path):
    bad = {
        "schema_version": "vne_character_name_aliases/0.1",
        "characters": [
            {"character_id": "NOBODY", "provider_alias": "Nobody",
             "surface_aliases": ["Никто"]},
        ],
    }
    p = tmp_path / "bad_roster_id.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AliasDataError):
        load_character_roster(_REPO_ROOT, path=p)


def test_provider_alias_must_be_latin(tmp_path):
    bad = {
        "schema_version": "vne_character_name_aliases/0.1",
        "characters": [
            {"character_id": "MARINA", "provider_alias": "Марина",
             "surface_aliases": ["Марина"]},
        ],
    }
    p = tmp_path / "cyrillic_provider_alias.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AliasDataError):
        load_character_roster(_REPO_ROOT, path=p)


# ---------------------------------------------------------------------------
# Alias data (location)
# ---------------------------------------------------------------------------


def test_sportzal_phrase_resolves_to_gym():
    roster = load_location_roster(_REPO_ROOT)
    src_key = match_key(FIRST_PROOF_TEXT)
    assert resolve_location(
        source_match_key=src_key, location_span="в спортзале", roster=roster
    ) == "gym"


def test_unknown_location_fails():
    roster = load_location_roster(_REPO_ROOT)
    with pytest.raises(LocationResolutionError):
        resolve_location(
            source_match_key=match_key("в кафе"),
            location_span="в кафе",
            roster=roster,
        )


def test_location_alias_invalid_canon_id_fails(tmp_path):
    bad = {
        "schema_version": "vne_location_aliases/0.1",
        "locations": [
            {"location_id": "casino", "surface_aliases": ["казино"]},
        ],
    }
    p = tmp_path / "bad_location_aliases.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AliasDataError):
        load_location_roster(_REPO_ROOT, path=p)


def test_ambiguous_location_fails():
    roster = load_location_roster(_REPO_ROOT)
    mixed = "Они начали в спортзале, потом перешли в зал для йоги."
    with pytest.raises(LocationResolutionError):
        resolve_location(
            source_match_key=match_key(mixed),
            location_span="в спортзале",
            roster=roster,
        )


# ---------------------------------------------------------------------------
# Proposal schema
# ---------------------------------------------------------------------------


def test_valid_proposal_parses():
    prop = ProposedInterpretation.from_dict(_base_proposal_dict())
    assert prop.confidence == "high"
    assert {c.character_id for c in prop.characters} == {"MARINA", "MAKSIM"}
    assert len(prop.beats) == 4
    assert len(prop.still_candidates) == 3


def test_malformed_proposal_missing_beats_fails():
    data = _base_proposal_dict()
    del data["beats"]
    with pytest.raises(ProposalSchemaError):
        ProposedInterpretation.from_dict(data)


def test_proposal_unknown_confidence_fails():
    data = _base_proposal_dict()
    data["confidence"] = "medium"
    with pytest.raises(ProposalSchemaError):
        ProposedInterpretation.from_dict(data)


def test_proposal_duplicate_beat_index_fails():
    data = _base_proposal_dict()
    data["beats"][1]["index"] = 0
    with pytest.raises(ProposalSchemaError):
        ProposedInterpretation.from_dict(data)


# ---------------------------------------------------------------------------
# Grounding + deterministic validation (fail closed)
# ---------------------------------------------------------------------------


def test_valid_plan_builds_from_first_proof():
    plan = _interpret(_base_proposal_dict())
    assert plan.status == "DRAFT"
    assert plan.characters_in_frame == ("MARINA", "MAKSIM")
    assert plan.location_id == "gym"
    assert plan.scene_tags == ("stretching", "training", "neutral")
    assert plan.provider_alias_by_character == {"MARINA": "Marina", "MAKSIM": "Maksim"}
    assert plan.unresolved_items == ()
    assert plan.chosen_still.beat_index == 3
    assert list(plan.evidence["character_spans"]["MARINA"]) == ["Марина"]
    assert plan.evidence["location_span"] == "в спортзале"
    # serializable form round-trips to plain lists
    assert plan.to_dict()["evidence"]["character_spans"]["MAKSIM"] == ["Максим"]
    # deterministic
    plan2 = _interpret(_base_proposal_dict())
    assert plan.content_hash == plan2.content_hash


def test_absent_character_span_rejected():
    data = _base_proposal_dict()
    data["characters"][0]["source_spans"] = ["Наталья"]
    with pytest.raises((GroundingError, HallucinationError)):
        _interpret(data)


def test_character_id_mismatch_rejected():
    data = _base_proposal_dict()
    # span says Марина, but the proposal labels it MAKSIM
    data["characters"][0]["character_id"] = "MAKSIM"
    data["characters"][1]["character_id"] = "MARINA"
    with pytest.raises(HallucinationError):
        _interpret(data)


def test_location_span_absent_rejected():
    data = _base_proposal_dict()
    data["location_span"] = "в бассейне"
    with pytest.raises((GroundingError, LocationResolutionError)):
        _interpret(data)


def test_invented_location_rejected():
    data = _base_proposal_dict()
    data["location_id"] = "yoga_hall"  # span still resolves to gym
    with pytest.raises(HallucinationError):
        _interpret(data)


def test_invented_action_rejected():
    data = _base_proposal_dict()
    data["beats"][0]["action_phrase"] = "кладёт руку ей на талию"
    with pytest.raises(GroundingError):
        _interpret(data)


def test_invented_contact_beat_rejected():
    data = _base_proposal_dict()
    data["beats"].append(
        {
            "index": 4,
            "text_span": "Максим находится рядом и наблюдает за её техникой",
            "actor_character_ids": ["MARINA", "MAKSIM"],
            "action_phrase": "наблюдает за её техникой",
            "positioning_phrase": "рука на талии",
            "contact_flag": True,
        }
    )
    with pytest.raises(GroundingError):
        _interpret(data)


def test_unknown_scene_tag_rejected():
    data = _base_proposal_dict()
    data["scene_tags"] = ["stretching", "sensual"]
    with pytest.raises(SceneTagError):
        _interpret(data)


def test_scene_tag_duplicating_location_rejected():
    data = _base_proposal_dict()
    data["scene_tags"] = ["gym", "stretching"]
    with pytest.raises(SceneTagError):
        _interpret(data)


def test_low_confidence_fails_closed():
    data = _base_proposal_dict()
    data["confidence"] = "low"
    with pytest.raises(ConfidenceError):
        _interpret(data)


def test_unresolved_items_fails_closed():
    data = _base_proposal_dict()
    data["unresolved_items"] = ["who turns to whom"]
    with pytest.raises(UnresolvedItemsError):
        _interpret(data)


def test_hallucinated_extra_character_rejected():
    data = _base_proposal_dict()
    data["characters"].append({"character_id": "OLGA", "source_spans": ["Ольга"]})
    with pytest.raises((GroundingError, HallucinationError)):
        _interpret(data)


def test_character_count_below_two_fails_closed():
    data = _base_proposal_dict()
    data["characters"] = [data["characters"][0]]
    data["beats"] = [b for b in data["beats"] if b["actor_character_ids"] == ["MARINA"]]
    data["still_candidates"] = [
        {"beat_index": 0, "rationale_tags": [], "visual_goal_text": "Marina stretches."}
    ]
    with pytest.raises(CharacterCountError):
        _interpret(data)


def test_unsupported_character_count_three_fails_closed(tmp_path):
    # A 3-character roster + a 3-name source: three grounded, resolvable
    # characters -> exceeds the v0 in-frame bound.
    roster_file = tmp_path / "roster3.json"
    roster_file.write_text(
        json.dumps(
            {
                "schema_version": "vne_character_name_aliases/0.1",
                "characters": [
                    {"character_id": "MARINA", "provider_alias": "Marina",
                     "surface_aliases": ["Марина"]},
                    {"character_id": "MAKSIM", "provider_alias": "Maksim",
                     "surface_aliases": ["Максим"]},
                    {"character_id": "OLGA", "provider_alias": "Olga",
                     "surface_aliases": ["Ольга"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    from dataclasses import replace

    text = (
        "Марина лежит на коврике в спортзале и делает растяжку. "
        "Максим находится рядом и наблюдает за её техникой. "
        "Ольга поворачивает голову и смотрит на него."
    )
    inp = build_interpreter_input(text, repo_root=_REPO_ROOT)
    inp = replace(
        inp, allowed_characters=load_character_roster(_REPO_ROOT, path=roster_file)
    )
    data = _base_proposal_dict()
    data["characters"].append({"character_id": "OLGA", "source_spans": ["Ольга"]})
    with pytest.raises(CharacterCountError):
        validate_and_build_plan(
            ProposedInterpretation.from_dict(data),
            inp,
            repo_root=_REPO_ROOT,
            interpreter_meta={"provider": "mock", "model": "mock", "mock": True},
        )


def test_still_candidate_unknown_beat_rejected():
    data = _base_proposal_dict()
    data["still_candidates"][0]["beat_index"] = 99
    with pytest.raises(StillSelectionError):
        _interpret(data)


def test_no_acceptable_still_fails_closed():
    # Only single-actor beats -> best score +2 < threshold +3.
    data = _base_proposal_dict()
    data["beats"] = [b for b in data["beats"] if b["index"] in (0, 1)]
    data["still_candidates"] = [
        {"beat_index": 0, "rationale_tags": [], "visual_goal_text": "Marina stretches on the mat."},
        {"beat_index": 1, "rationale_tags": [], "visual_goal_text": "Maksim observes nearby."},
    ]
    with pytest.raises(StillSelectionError):
        _interpret(data)


def test_contact_beat_barred_from_still_but_grounded_ok():
    data = _base_proposal_dict()
    # a grounded contact beat is allowed to exist, but can never be chosen
    data["beats"].append(
        {
            "index": 5,
            "text_span": "Максим находится рядом и наблюдает за её техникой",
            "actor_character_ids": ["MARINA", "MAKSIM"],
            "action_phrase": "наблюдает за её техникой",
            "positioning_phrase": "рядом",
            "contact_flag": True,
        }
    )
    data["still_candidates"].insert(
        0,
        {"beat_index": 5, "rationale_tags": ["contact_ambiguity"],
         "visual_goal_text": "A contact framing that must never win."},
    )
    plan = _interpret(data)
    assert plan.chosen_still.beat_index == 3
    assert all(c.beat_index != 5 for c in plan.still_candidates)


def test_deterministic_winner_is_highest_score():
    plan = _interpret(_base_proposal_dict())
    scores = [c.score for c in plan.still_candidates]
    assert scores == sorted(scores, reverse=True)
    assert plan.still_candidates[0].beat_index == plan.chosen_still.beat_index
    assert plan.still_candidates[0].score == 6


def test_visual_goal_naming_non_frame_character_rejected(tmp_path):
    # 3-character roster; only Marina + Maksim are in frame; the composed goal
    # names Kira -> fail closed.
    roster_file = tmp_path / "roster3.json"
    roster_file.write_text(
        json.dumps(
            {
                "schema_version": "vne_character_name_aliases/0.1",
                "characters": [
                    {"character_id": "MARINA", "provider_alias": "Marina",
                     "surface_aliases": ["Марина"]},
                    {"character_id": "MAKSIM", "provider_alias": "Maksim",
                     "surface_aliases": ["Максим"]},
                    {"character_id": "KIRA", "provider_alias": "Kira",
                     "surface_aliases": ["Кира"]},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    inp = build_interpreter_input(FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    from dataclasses import replace

    inp = replace(inp, allowed_characters=load_character_roster(_REPO_ROOT, path=roster_file))
    data = _base_proposal_dict()
    data["still_candidates"][0]["visual_goal_text"] = (
        "In a modern gym, Marina and Maksim train while Kira watches from the door."
    )
    with pytest.raises(HallucinationError):
        validate_and_build_plan(
            ProposedInterpretation.from_dict(data),
            inp,
            repo_root=_REPO_ROOT,
            interpreter_meta={"provider": "mock", "model": "mock", "mock": True},
        )


# ---------------------------------------------------------------------------
# Profile bridge (validated plan -> existing Profile, AUTO mode)
# ---------------------------------------------------------------------------


def test_profile_from_scene_text_builds_auto_profile():
    profile, plan = app.profile_from_scene_text(
        FIRST_PROOF_TEXT, repo_root=_REPO_ROOT, proposal_fixture=_PROPOSAL_FIXTURE
    )
    assert profile.mode == "auto"
    assert profile.references == ()
    assert profile.characters_in_frame == ("MARINA", "MAKSIM")
    assert profile.cast_override == {"KIRA": "MARINA", "SERGEY": "MAKSIM"}
    assert profile.prompt_aliases == {"MARINA": "Marina", "MAKSIM": "Maksim"}
    assert profile.location_id == "gym"
    assert profile.scene_tags == ("stretching", "training", "neutral")
    assert profile.scene_id == "SC_900"
    assert profile.branch_id == "B1"
    assert profile.fixture_ref == app.SCENE_TEXT_GENERIC_FIXTURE_REL
    assert profile.scene_intent == plan.chosen_still.visual_goal


def test_profile_from_scene_text_has_no_manual_reference_list():
    profile, _ = app.profile_from_scene_text(
        FIRST_PROOF_TEXT, repo_root=_REPO_ROOT, proposal_fixture=_PROPOSAL_FIXTURE
    )
    # AUTO_REFS stays responsible for references: no manual references[] at all.
    assert profile.mode == "auto"
    assert profile.references == ()
    assert profile.roles_by_asset_id == {}


def test_scene_text_mode_requires_proposal_fixture(capsys):
    code = app.run_preview(scene_text=FIRST_PROOF_TEXT, repo_root=_REPO_ROOT)
    err = capsys.readouterr().err
    assert code == 1
    assert "proposal-fixture" in err


# ---------------------------------------------------------------------------
# End-to-end OFFLINE: prose -> validated plan -> Profile -> orchestrate preview
# ---------------------------------------------------------------------------


def _build_hermetic_auto(tmp_path: Path) -> tuple[Path, Path]:
    """A fully isolated repo for the AUTO end-to-end path.

    Real catalog / physical profiles / alias tables / Location Canon / generic
    fixture are copied verbatim; every catalog asset is synthesized (only the
    MARINA/MAKSIM bytes are read to build the bundle).
    """
    root = tmp_path / "repo"
    (root / "scenarios" / "locations").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "fixtures" / "scene_image_test_app").mkdir(parents=True, exist_ok=True)
    (root / "authoring" / "scene_image_test_profiles").mkdir(parents=True, exist_ok=True)
    (root / "authoring" / "reference_library").mkdir(parents=True, exist_ok=True)
    src_dir = tmp_path / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)

    def _copy(rel: str) -> None:
        (root / rel).write_bytes((_REPO_ROOT / rel).read_bytes())

    _copy("scenarios/locations/gym.json")
    _copy("scenarios/locations/yoga_hall.json")
    _copy("authoring/reference_library/REFERENCE_SEMANTIC_CATALOG.json")
    _copy("authoring/scene_image_test_profiles/physical_profiles.json")
    _copy("authoring/scene_image_test_profiles/CHARACTER_NAME_ALIASES.json")
    _copy("authoring/scene_image_test_profiles/LOCATION_ALIASES.json")
    _copy("tests/fixtures/scene_image_test_app/GENERIC_2CHAR.v2.json")

    manifest = root / "authoring" / "reference_library" / "REFERENCE_LIBRARY_MANIFEST.json"
    for cid, aid in _CATALOG_ASSETS:
        payload = _PNG + aid.encode("utf-8")
        src = src_dir / f"{aid}.png"
        src.write_bytes(payload)
        import_reference(
            str(src),
            repo_root=root,
            manifest_path=manifest,
            asset_id=aid,
            character_id=cid,
            collection="scene_image_test_app",
        )
    return root, manifest


def test_scene_text_end_to_end_offline_preview(tmp_path, capsys):
    root, manifest = _build_hermetic_auto(tmp_path)
    code = app.run_preview(
        scene_text=FIRST_PROOF_TEXT,
        repo_root=root,
        manifest_path=manifest,
        proposal_fixture=str(_PROPOSAL_FIXTURE),
    )
    out = capsys.readouterr().out
    assert code == 0

    assert "RAW_TEXT_MODE=YES" in out
    assert "PLAN_STATUS=DRAFT" in out
    assert "SOURCE_LANGUAGE=ru" in out
    assert "RESOLVED_CHARACTERS=MARINA,MAKSIM" in out
    assert "RESOLVED_LOCATION=gym" in out
    assert "RESOLVED_SCENE_TAGS=stretching,training,neutral" in out
    assert "GROUNDING_VALID=YES" in out
    assert "UNRESOLVED_ITEMS=none" in out
    assert "CHOSEN_STILL_BEAT_INDEX=3" in out

    assert "REFERENCE_SELECTION_MODE=AUTO" in out
    selected = out.split("SELECTED_REFERENCES:")[1].split("REFERENCE BUNDLE HASH")[0]
    assert "marina_face_01 [face]" in selected
    assert "marina_body_01 [body]" in selected
    assert "marina_face_support_01 [expression]" in selected
    assert "marina_sports_01" not in selected
    assert "maksim_face_01 [face]" in selected
    assert "maksim_body_01 [body]" in selected
    assert "maksim_face_support_01 [expression]" in selected
    assert "maksim_gym_01 [motion]" in selected

    assert "CHARACTER PHYSICAL IDENTITY" in out
    assert "RELATIVE SCALE" in out
    assert "PROVIDER_INTERNAL_ID_EXPOSURE=NO" in out
    assert "DRY_RUN_RESULT=PASS" in out
    assert "READY_FOR_LIVE_GENERATION=YES" in out


def test_scene_text_end_to_end_hallucination_fails_closed(tmp_path, capsys):
    root, manifest = _build_hermetic_auto(tmp_path)
    bad = _base_proposal_dict()
    bad["characters"].append({"character_id": "OLGA", "source_spans": ["Ольга"]})
    fixture = tmp_path / "hallucinated_proposal.json"
    fixture.write_text(
        json.dumps({"interpreter": {"provider": "fixture", "model": "x", "mock": True},
                    "proposal": bad}, ensure_ascii=False),
        encoding="utf-8",
    )
    code = app.run_preview(
        scene_text=FIRST_PROOF_TEXT,
        repo_root=root,
        manifest_path=manifest,
        proposal_fixture=str(fixture),
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "DRY_RUN_RESULT=FAIL" in err
    assert "interpretation failed" in err
