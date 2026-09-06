#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the OrderedASS multi-scene project-candidate builder."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import OrderedASS, build_ordered_ass  # noqa: E402
from services.scene_body import (  # noqa: E402
    AUTHORING_SCHEMA_VERSION,
    ChoiceEntry,
    ChoiceOption,
    ChoiceTarget,
    Participant,
    SceneBody,
    TextEntry,
    VisualChangeEvent,
)
from tools.vne_to_renpy import (  # noqa: E402
    ORDERED_ASS_CANDIDATE_FILENAME,
    OrderedProjectExportError,
    build_ordered_project_candidate,
)
from tools.vne_to_renpy.ordered_asset_resolver import OrderedAssetResolutionError  # noqa: E402
from tools.vne_to_renpy.ordered_ass_exporter import scene_start_label  # noqa: E402

SCENE_ID_A = "SC_900"
SCENE_ID_B = "SC_901"


def _narrative(entry_id="e1", text="Hello.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="NARRATIVE", text=text)


def _choice(entry_id="c1", option_id="o1", target_kind="SCENE", target_id=SCENE_ID_B) -> ChoiceEntry:
    return ChoiceEntry(
        entry_id=entry_id,
        options=(ChoiceOption(
            option_id=option_id, display_text="Next",
            target=ChoiceTarget(target_kind=target_kind, target_id=target_id),
        ),),
    )


def _ass(scene_id: str, ass_id: str | None = None, entries=()) -> OrderedASS:
    body = SceneBody(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id=scene_id,
        location_id="yoga_hall",
        participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
        content_rating="PG",
        entries=entries or (_narrative(),),
    )
    return build_ordered_ass(
        body, ass_id=ass_id or "ass_{}".format(scene_id), version=1,
        source_ref="x.json", source_hash="0" * 64,
    )


def _build(scenes, reading_mode="classic_vn", character_symbols=None):
    return build_ordered_project_candidate(
        scenes,
        reading_mode=reading_mode,
        character_symbols=character_symbols if character_symbols is not None else {"KIRA": "kira"},
        registry_path=Path("dummy_reg.json"),
        repo_root=Path("dummy_repo"),
    )


@pytest.fixture
def resolver_calls(monkeypatch):
    from services.production_media_asset_binding import ResolvedAsset
    calls: list[list[str]] = []

    def fake(asset_ids, *, registry_path, repo_root):
        calls.append(list(asset_ids))
        return {
            aid: ResolvedAsset(
                asset_id=aid,
                relative_path="novel/game/images/story/{}.png".format(aid),
                renpy_image_name=aid,
            )
            for aid in asset_ids
        }

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake,
    )
    return calls


# ---------------------------------------------------------------------------
# Input / identity
# ---------------------------------------------------------------------------

def test_single_scene(resolver_calls):
    c = _build((_ass(SCENE_ID_A),))
    assert c.scene_ids == (SCENE_ID_A,)
    assert c.candidate_filename == ORDERED_ASS_CANDIDATE_FILENAME
    assert len(c.source_sha256) == 64


def test_multiple_scenes_canonical_order(resolver_calls):
    c = _build((_ass(SCENE_ID_B, "ass_b"), _ass(SCENE_ID_A, "ass_a")))
    assert c.scene_ids == (SCENE_ID_A, SCENE_ID_B)
    assert c.ass_ids == ("ass_a", "ass_b")


def test_empty_tuple_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build(())


def test_non_ordered_ass_member_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build((_ass(SCENE_ID_A), {"scene_id": "x"}))  # type: ignore[arg-type]


def test_duplicate_scene_id_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build((_ass(SCENE_ID_A, "ass_a"), _ass(SCENE_ID_A, "ass_b")))


def test_duplicate_ass_id_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build((_ass(SCENE_ID_A, "ass_same"), _ass(SCENE_ID_B, "ass_same")))


def test_reversed_caller_order_identical_source(resolver_calls):
    a = _build((_ass(SCENE_ID_A, "ass_a"), _ass(SCENE_ID_B, "ass_b")))
    b = _build((_ass(SCENE_ID_B, "ass_b"), _ass(SCENE_ID_A, "ass_a")))
    assert a.source == b.source
    assert a.source_sha256 == b.source_sha256


def test_no_global_start(resolver_calls):
    c = _build((_ass(SCENE_ID_A),))
    for line in c.source.split("\n"):
        assert line.strip() != "label start:"
        assert not line.strip().startswith("label start")


def test_source_sha256_exact(resolver_calls):
    c = _build((_ass(SCENE_ID_A), _ass(SCENE_ID_B, "ass_b")))
    assert c.source_sha256 == hashlib.sha256(c.source.encode("utf-8")).hexdigest()


def test_lf_newlines_and_single_final_newline(resolver_calls):
    c = _build((_ass(SCENE_ID_A),))
    assert "\r" not in c.source
    assert c.source.endswith("\n")
    assert not c.source.endswith("\n\n")


def test_no_timestamps_or_absolute_paths(resolver_calls):
    c = _build((_ass(SCENE_ID_A),))
    assert "2026" not in c.source
    assert "C:" not in c.source
    assert "C:\\" not in c.source


# ---------------------------------------------------------------------------
# Cross-scene / known scene set
# ---------------------------------------------------------------------------

def test_cross_scene_choice_jump_resolves(resolver_calls):
    a = _ass(SCENE_ID_A, "ass_a", (_narrative("e1"), _choice("c1", target_id=SCENE_ID_B)))
    b = _ass(SCENE_ID_B, "ass_b")
    c = _build((a, b))
    assert "jump {}".format(scene_start_label(SCENE_ID_B)) in c.source


def test_unknown_scene_target_raises(resolver_calls):
    from tools.vne_to_renpy import OrderedExportError
    a = _ass(SCENE_ID_A, "ass_a", (_choice("c1", target_id="SC_999"),))
    with pytest.raises(OrderedExportError):
        _build((a,))


def test_no_graph_traversal(resolver_calls):
    # self-referential choice renders without reachability/cycle rejection
    a = _ass(SCENE_ID_A, "ass_a", (_choice("c1", target_kind="ENTRY", target_id="c1"),))
    c = _build((a,))
    assert "jump" in c.source


def test_batch_label_uniqueness(resolver_calls):
    a = _ass(SCENE_ID_A, "ass_a", (_narrative("e1"), _narrative("e2")))
    b = _ass(SCENE_ID_B, "ass_b", (_narrative("e1"),))
    c = _build((a, b))
    # distinct scene_ids produce distinct start labels
    assert scene_start_label(SCENE_ID_A) != scene_start_label(SCENE_ID_B)


# ---------------------------------------------------------------------------
# Asset union / resolver
# ---------------------------------------------------------------------------

def _visual(entry_id="v1", asset_id="asset_one") -> VisualChangeEvent:
    return VisualChangeEvent(entry_id=entry_id, operation="SET", asset_id=asset_id)


def test_complete_sorted_unique_asset_union(resolver_calls):
    a = _ass(SCENE_ID_A, "ass_a", (_visual("v1", "asset_bravo"), _visual("v2", "asset_alpha")))
    b = _ass(SCENE_ID_B, "ass_b", (_visual("v1", "asset_alpha"),))
    _build((a, b))
    assert resolver_calls == [["asset_alpha", "asset_bravo"]]


def test_resolver_called_exactly_once(resolver_calls):
    a = _ass(SCENE_ID_A, "ass_a", (_visual("v1", "asset_one"),))
    b = _ass(SCENE_ID_B, "ass_b", (_visual("v1", "asset_two"),))
    _build((a, b))
    assert len(resolver_calls) == 1


def test_cross_scene_collision_propagates(monkeypatch):
    def fake(asset_ids, *, registry_path, repo_root):
        raise OrderedAssetResolutionError("collision")

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake,
    )
    a = _ass(SCENE_ID_A, "ass_a", (_visual("v1", "asset_one"),))
    with pytest.raises(OrderedAssetResolutionError):
        _build((a,))


def test_same_resolved_mapping_used_for_all_renders(monkeypatch):
    resolved = {"asset_one": object()}
    render_seen: list[dict] = []

    def fake_resolve(asset_ids, *, registry_path, repo_root):
        return resolved

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake_resolve,
    )

    import tools.vne_to_renpy.ordered_ass_project_exporter as mod

    def fake_render(scene, *, reading_mode, character_symbols, known_scene_ids, resolved_assets):
        render_seen.append({"resolved_assets": resolved_assets})
        return "# scene {}\n".format(scene.scene_id)

    monkeypatch.setattr(mod, "render_ordered_ass", fake_render)
    _build((_ass(SCENE_ID_A, "ass_a"), _ass(SCENE_ID_B, "ass_b")))
    assert len(render_seen) == 2
    assert all(r["resolved_assets"] is resolved for r in render_seen)


def test_reading_mode_and_character_mapping_propagated(monkeypatch):
    seen: list[dict] = []

    def fake_resolve(asset_ids, *, registry_path, repo_root):
        return {}

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake_resolve,
    )
    import tools.vne_to_renpy.ordered_ass_project_exporter as mod

    def fake_render(scene, *, reading_mode, character_symbols, known_scene_ids, resolved_assets):
        seen.append({"reading_mode": reading_mode, "character_symbols": dict(character_symbols),
                     "known_scene_ids": known_scene_ids})
        return "# scene {}\n".format(scene.scene_id)

    monkeypatch.setattr(mod, "render_ordered_ass", fake_render)
    _build((_ass(SCENE_ID_A, "ass_a"),), reading_mode="psychological",
           character_symbols={"KIRA": "k", "OLGA": "o"})
    assert seen[0]["reading_mode"] == "psychological"
    assert seen[0]["character_symbols"] == {"KIRA": "k", "OLGA": "o"}
    assert seen[0]["known_scene_ids"] == frozenset({SCENE_ID_A})


def test_character_mapping_insertion_order_does_not_affect_output(resolver_calls):
    m1 = {"KIRA": "kira", "OLGA": "olga"}
    m2 = {"OLGA": "olga", "KIRA": "kira"}
    a = _ass(SCENE_ID_A, "ass_a", (_narrative("e1"),))
    c1 = _build((a,), character_symbols=m1)
    c2 = _build((a,), character_symbols=m2)
    assert c1.source == c2.source


# ---------------------------------------------------------------------------
# Header / ass_id comment / identity
# ---------------------------------------------------------------------------

def test_stable_header(resolver_calls):
    c = _build((_ass(SCENE_ID_A, "ass_a"), _ass(SCENE_ID_B, "ass_b")))
    assert c.source.startswith("# AUTO-GENERATED OrderedASS Ren'Py project candidate.\n")
    assert "# reading_mode: classic_vn" in c.source
    assert "# scene_count: 2" in c.source


def test_raw_unsafe_ass_id_not_emitted(resolver_calls):
    unsafe = "ass evil; rm -rf \"quoted\" [x]"
    a = _ass(SCENE_ID_A, unsafe)
    c = _build((a,))
    assert unsafe not in c.source
    # the record comment contains an encoded token, never the raw ass_id
    assert "accepted_ass:" in c.source


def test_ass_id_encoding_deterministic(resolver_calls):
    a1 = _ass(SCENE_ID_A, "ass_one")
    a2 = _ass(SCENE_ID_A, "ass_one")
    c1 = _build((a1,))
    c2 = _build((a2,))
    assert c1.source == c2.source


def _ass_direct(scene_id, ass_id, version=1, content_hash=None, entries=()) -> OrderedASS:
    from services.ass import Participant as AssParticipant, Provenance
    return OrderedASS(
        schema_version="ass/0.2",
        ass_id=ass_id,
        version=version,
        scene_id=scene_id,
        location_id="yoga_hall",
        participants=(AssParticipant("KIRA", "protagonist", True),),
        ordered_flow=entries or (_narrative(),),
        content_rating="PG",
        provenance=Provenance(
            source_kind="scene_body_ordered_acceptance", source_ref="x.json",
            source_hash="0" * 64, source_schema_version="scene_body/1.0",
        ),
        content_hash=content_hash if content_hash is not None else "0" * 64,
    )


def test_invalid_version_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build((_ass_direct(SCENE_ID_A, "ass_a", version=0),))


def test_invalid_content_hash_rejected(resolver_calls):
    with pytest.raises(OrderedProjectExportError):
        _build((_ass_direct(SCENE_ID_A, "ass_a", content_hash="not-hex"),))


def test_builder_is_pure_no_filesystem_write(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_resolve(asset_ids, *, registry_path, repo_root):
        return {}

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake_resolve,
    )
    _build((_ass(SCENE_ID_A, "ass_a"),))
    assert sorted(p.name for p in tmp_path.iterdir()) == []
