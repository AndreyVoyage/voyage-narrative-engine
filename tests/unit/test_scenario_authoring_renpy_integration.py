#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.5 Scenario Authoring -> Ren'Py export integration tests (T01-T13 + vertical)."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import OrderedASS  # noqa: E402
from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CHARACTER_PROVENANCE_MANUAL,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_TEXT,
    AuthoredChoice,
    Card,
    CardConnection,
    CharacterReference,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    Project,
    ProjectStore,
    ProjectionConfig,
    SceneMembership,
    Slide,
    SpeakerOverride,
    UnsupportedProjectionError,
    Utterance,
    export_project_to_renpy,
)
from tools.vne_to_renpy.ordered_asset_resolver import OrderedAssetResolutionError  # noqa: E402
from tools.vne_to_renpy.ordered_ass_exporter import entry_label, scene_start_label  # noqa: E402
from tools.vne_to_renpy.ordered_ass_project_exporter import STORY_ENTRY_LABEL  # noqa: E402

_SCHEMA = SCENARIO_AUTHORING_SCHEMA_VERSION


def _utt(utt_id="utt_a", text="Hello", speakers=(), portions=()):
    return Utterance(utterance_id=utt_id, text=text, speaker_ids=speakers, portions=portions)


def _text_item(item_id="item_1", text="Hello", speakers=(), portions=()):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_TEXT,
        utterance=_utt("{0}_u".format(item_id), text=text, speakers=speakers, portions=portions),
    )


def _choice_item(item_id="item_ch", choice_id="ch_1", options=(), prompt="Choose:"):
    return ContentItem(
        item_id=item_id,
        kind=CONTENT_KIND_CHOICE,
        choice=AuthoredChoice(choice_id=choice_id, prompt=prompt, options=options),
    )


def _slide(slide_id="slide_1", items=(), background=None):
    return Slide(slide_id=slide_id, content_items=items, background=background)


def _card(card_id="card_a", slides=None, connections=()):
    return Card(
        card_id=card_id,
        slides=slides if slides is not None else (_slide(),),
        connections=connections,
    )


def _conn(connection_id, target, label=None, choice_id=None):
    return CardConnection(connection_id=connection_id, target_card_id=target, label=label, choice_id=choice_id)


def _membership(scene_id, card_ids, location_id="loc_x", content_rating="pg"):
    return SceneMembership(
        scene_id=scene_id, card_ids=tuple(card_ids), location_id=location_id, content_rating=content_rating,
    )


def _config(scenes, transitions=()):
    return ProjectionConfig(scenes=tuple(scenes), supported_scene_transitions=tuple(transitions))


def _project(cards, start, characters=()):
    return Project(schema_version=_SCHEMA, project_id="proj_alpha", cards=cards, start_card_id=start, characters=characters)


def _export(project, config, *, reading_mode="classic_vn", character_symbols=None):
    return export_project_to_renpy(
        project,
        config,
        reading_mode=reading_mode,
        character_symbols=character_symbols if character_symbols is not None else {},
        registry_path=Path("dummy_reg.json"),
        repo_root=Path("dummy_repo"),
    )


def _export_with_paths(project, config, registry_path, repo_root, *, character_symbols=None):
    return export_project_to_renpy(
        project,
        config,
        reading_mode="classic_vn",
        character_symbols=character_symbols if character_symbols is not None else {},
        registry_path=Path(registry_path),
        repo_root=Path(repo_root),
    )


@pytest.fixture
def resolver_spy(monkeypatch):
    calls = []

    def fake(asset_ids, *, registry_path, repo_root):
        calls.append(list(asset_ids))
        return {}

    monkeypatch.setattr(
        "tools.vne_to_renpy.ordered_ass_project_exporter.resolve_ordered_assets_for_renpy",
        fake,
    )
    return calls


_PNG_DATA = b"\x89PNG\r\n\x1a\n" + b"fake-bytes-for-hash" * 4


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _asset_record(asset_id, relative_path):
    return {
        "asset_id": asset_id,
        "type": "background",
        "relative_path": relative_path,
        "source_kind": "manual",
        "imported_hash": _sha(_PNG_DATA),
        "format": "png",
        "mime_type": "image/png",
    }


def _registry_setup(records):
    repo_root = Path(tempfile.mkdtemp(prefix="vne_se15_renpy_"))
    registry_path = repo_root / "registry.json"
    for rec in records:
        p = repo_root / rec["relative_path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_PNG_DATA)
    registry_path.write_text(json.dumps({"assets": records}), encoding="utf-8")
    return repo_root, registry_path


def test_t01_valid_project_loads_through_w1_then_exports(tmp_path, resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "Hello."),)),))
    project = _project((card_a,), "card_a")
    store = ProjectStore(tmp_path)
    store.save(project)
    loaded = store.load()

    result = _export(loaded, _config((_membership("scene_1", ("card_a",)),)))
    assert result.source
    assert result.scene_ids == ("scene_1",)
    assert result.story_sequence.start_scene_id == "scene_1"


def test_t02_explicit_projection_configuration_respected(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "A"),)),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "B"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((
        _membership("scene_b", ("card_b",)),
        _membership("scene_a", ("card_a",)),
    ))
    result = _export(project, config)

    # Scene order follows the explicit config order, not card order.
    assert result.scene_ids == ("scene_b", "scene_a")
    # The start scene is the scene that owns the start card.
    assert result.story_sequence.start_scene_id == "scene_a"
    assert "jump {0}".format(scene_start_label("scene_a")) in result.source


def test_t03_existing_scene_body_ass_validation_invoked(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "Hello."),)),))
    project = _project((card_a,), "card_a")
    result = _export(project, _config((_membership("scene_1", ("card_a",)),)))

    assert len(result.ordered_ass_scenes) == 1
    ass = result.ordered_ass_scenes[0]
    assert isinstance(ass, OrderedASS)
    assert ass.schema_version == "ass/0.2"
    assert len(ass.content_hash) == 64
    # The ordered flow preserves the projected entry ids (no semantic loss).
    assert [e.entry_id for e in ass.ordered_flow] == ["card_a.slide_1.item_1"]


def test_t04_complete_utterance_text_preserved(resolver_spy):
    text = "Hello there, Kira."
    utt = Utterance(
        utterance_id="utt_hello",
        text=text,
        speaker_ids=(),
        portions=(
            DisplayPortion(portion_id="por_1", start_offset=0, end_offset=5),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=len(text)),
        ),
    )
    item = ContentItem(item_id="item_hello", kind=CONTENT_KIND_TEXT, utterance=utt)
    card_a = _card("card_a", slides=(_slide("slide_1", items=(item,)),))
    project = _project((card_a,), "card_a")
    result = _export(project, _config((_membership("scene_1", ("card_a",)),)))

    # The complete authoritative text is exported (never segmented away).
    assert 'narrator "Hello there, Kira."' in result.source
    assert len(result.portion_manifests) == 1
    assert result.portion_manifests[0].utterance_id == "utt_hello"
    assert [p.portion_id for p in result.portion_manifests[0].portions] == ["por_1", "por_2"]


def test_t05_choice_destinations_survive(resolver_spy):
    choice = _choice_item("item_ch", "ch_1", options=(
        ChoiceOption(option_id="opt_left", label="Go left", target_connection_id="conn_left"),
        ChoiceOption(option_id="opt_right", label="Go right", target_connection_id="conn_right"),
    ))
    card_a = _card("card_a", slides=(_slide("slide_1", items=(choice,)),), connections=(
        _conn("conn_left", "card_b", choice_id="ch_1"),
        _conn("conn_right", "card_c", choice_id="ch_1"),
    ))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "Left."),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_c", "Right."),)),))
    project = _project((card_a, card_b, card_c), "card_a")
    result = _export(project, _config((_membership("scene_1", ("card_a", "card_b", "card_c")),)))

    src = result.source
    assert "menu:" in src
    assert '"Go left":' in src
    assert '"Go right":' in src
    assert "jump {0}".format(entry_label("scene_1", "card_b.slide_1.item_b")) in src
    assert "jump {0}".format(entry_label("scene_1", "card_c.slide_1.item_c")) in src


def test_t06_correct_start_scene_preserved(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "A"),)),))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "B"),)),))
    project = _project((card_a, card_b), "card_b")
    config = _config((
        _membership("scene_a", ("card_a",)),
        _membership("scene_b", ("card_b",)),
    ))
    result = _export(project, config)

    assert result.story_sequence.start_scene_id == "scene_b"
    assert "label {0}:".format(STORY_ENTRY_LABEL) in result.source
    assert "jump {0}".format(scene_start_label("scene_b")) in result.source


def test_t07_supported_cross_scene_continuation_works(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_a", "A"),)),), connections=(
        _conn("conn_ab", "card_b"),
    ))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_b", "B"),)),))
    project = _project((card_a, card_b), "card_a")
    config = _config((
        _membership("scene_a", ("card_a",)),
        _membership("scene_b", ("card_b",)),
    ), transitions=(("scene_a", "scene_b"),))
    result = _export(project, config)

    # Linear continuation from card_a (scene_a) to card_b (scene_b start card).
    assert "jump {0}".format(scene_start_label("scene_b")) in result.source


def test_t08_unsupported_content_fails_explicitly(resolver_spy):
    # A group-speaker utterance (2 speakers) is not representable in OrderedASS.
    item = ContentItem(
        item_id="item_group",
        kind=CONTENT_KIND_TEXT,
        utterance=Utterance(utterance_id="utt_group", text="Together.", speaker_ids=("kira", "olga")),
    )
    card_a = _card("card_a", slides=(_slide("slide_1", items=(item,)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))

    with pytest.raises(UnsupportedProjectionError, match="group-speaker"):
        _export(project, config)


def test_t09_no_source_project_mutation(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "Hello."),)),))
    project = _project((card_a,), "card_a")
    before = project.to_dict()

    _export(project, _config((_membership("scene_1", ("card_a",)),)))

    assert project.to_dict() == before


def test_t10_equivalent_input_produces_equivalent_deterministic_export(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "Hello."),)),))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))

    r1 = _export(project, config)
    r2 = _export(project, config)

    assert r1.source == r2.source
    assert r1.source_sha256 == r2.source_sha256
    assert r1.source_sha256 == hashlib.sha256(r1.source.encode("utf-8")).hexdigest()


def test_t11_existing_exporter_actually_called(resolver_spy):
    card_a = _card("card_a", slides=(_slide("slide_1", items=(_text_item("item_1", "Hello."),)),))
    project = _project((card_a,), "card_a")
    result = _export(project, _config((_membership("scene_1", ("card_a",)),)))

    # The real exporter is the only caller of the asset resolver (once, empty set).
    assert resolver_spy == [[]]
    # The output carries the real exporter's deterministic header and labels.
    assert result.source.startswith("# AUTO-GENERATED OrderedASS Ren'Py project candidate.\n")
    assert "label {0}:".format(scene_start_label("scene_1")) in result.source


def test_t12_display_portions_represented_where_ratified_contract_supports(resolver_spy):
    text = "Hello there, Kira."
    utt = Utterance(
        utterance_id="utt_hello",
        text=text,
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                portion_id="por_1", start_offset=0, end_offset=5,
                overrides=(SpeakerOverride(character_id="kira", emotion="neutral"),),
            ),
            DisplayPortion(
                portion_id="por_2", start_offset=5, end_offset=len(text),
                overrides=(SpeakerOverride(character_id="kira", emotion="happy"),),
            ),
        ),
    )
    item = ContentItem(item_id="item_hello", kind=CONTENT_KIND_TEXT, utterance=utt)
    card_a = _card("card_a", slides=(_slide("slide_1", items=(item,)),))
    project = _project(
        (card_a,), "card_a",
        characters=(CharacterReference("kira", CHARACTER_PROVENANCE_MANUAL, name="Kira"),),
    )
    result = _export(
        project, _config((_membership("scene_1", ("card_a",)),)), character_symbols={"kira": "kira"},
    )

    # The whole authoritative text is exported (dialogue, complete).
    assert 'kira "Hello there, Kira."' in result.source
    # Portions are carried as the technical-candidate sidecar, not discarded.
    assert len(result.portion_manifests) == 1
    assert result.portion_manifests[0].utterance_id == "utt_hello"
    # Per-portion segmentation is NOT silently merged into the exported source.
    assert "por_1" not in result.source
    assert "por_2" not in result.source


def test_t13_missing_media_fails_explicitly():
    # A background asset_id that cannot be resolved must fail closed.
    card_a = _card("card_a", slides=(
        _slide("slide_1", background=MediaReference(asset_id="bg_missing"), items=(_text_item("item_1", "Hello."),)),
    ))
    project = _project((card_a,), "card_a")
    config = _config((_membership("scene_1", ("card_a",)),))

    # A real registry that does NOT contain bg_missing.
    repo_root, registry_path = _registry_setup([
        _asset_record("bg_other", "novel/game/images/story/bg_other.png"),
    ])

    with pytest.raises(OrderedAssetResolutionError):
        _export_with_paths(project, config, registry_path, repo_root)


def test_vertical_multi_card_authoring_example_export():
    # Two scenes, a background, narration, dialogue, a branch choice, a linear
    # continuation, and a cross-scene transition -- exported with real media.
    intro = _text_item("item_intro", "Welcome to the beach.")
    choice = _choice_item("item_ch", "ch_1", prompt="Where to?", options=(
        ChoiceOption(option_id="opt_left", label="Stay on the sand", target_connection_id="conn_left"),
        ChoiceOption(option_id="opt_right", label="Enter the water", target_connection_id="conn_right"),
    ))
    card_a = _card("card_a", slides=(
        _slide("slide_1", background=MediaReference(asset_id="bg_beach"), items=(intro,)),
        _slide("slide_2", items=(choice,)),
    ), connections=(
        _conn("conn_left", "card_b", choice_id="ch_1"),
        _conn("conn_right", "card_c", choice_id="ch_1"),
    ))
    card_b = _card("card_b", slides=(_slide("slide_1", items=(_text_item("item_stay", "You stayed on the sand."),)),))
    card_c = _card("card_c", slides=(_slide("slide_1", items=(_text_item("item_water", "The water is cold.", speakers=("kira",)),)),))
    project = _project(
        (card_a, card_b, card_c), "card_a",
        characters=(CharacterReference("kira", CHARACTER_PROVENANCE_MANUAL, name="Kira"),),
    )
    config = _config((
        _membership("scene_1", ("card_a", "card_b")),
        _membership("scene_2", ("card_c",)),
    ), transitions=(("scene_1", "scene_2"),))

    repo_root, registry_path = _registry_setup([
        _asset_record("bg_beach", "novel/game/images/story/bg_beach.png"),
    ])
    result = _export_with_paths(
        project, config, registry_path, repo_root, character_symbols={"kira": "kira"},
    )

    src = result.source
    assert src.startswith("# AUTO-GENERATED OrderedASS Ren'Py project candidate.\n")
    # Story entry jumps to the start scene.
    assert "label {0}:".format(STORY_ENTRY_LABEL) in src
    assert "jump {0}".format(scene_start_label("scene_1")) in src
    # The background resolves to a real show statement.
    assert "show bg_beach as vne_scene_visual" in src
    # Narration and dialogue are preserved verbatim.
    assert 'narrator "Welcome to the beach."' in src
    assert 'narrator "You stayed on the sand."' in src
    assert 'kira "The water is cold."' in src
    # Branch choice destinations survive (same-scene ENTRY + cross-scene SCENE).
    assert "menu:" in src
    assert '"Stay on the sand":' in src
    assert '"Enter the water":' in src
    assert "jump {0}".format(entry_label("scene_1", "card_b.slide_1.item_stay")) in src
    assert "jump {0}".format(scene_start_label("scene_2")) in src
