#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the OrderedASS -> Ren'Py source renderer v1."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ass import ASS, OrderedASS, Participant as AssParticipant, Provenance, build_ordered_ass  # noqa: E402
from services.production_media_asset_binding import ResolvedAsset  # noqa: E402
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
from tools.vne_to_renpy.ordered_ass_exporter import (  # noqa: E402
    READING_MODES,
    OrderedExportError,
    entry_label,
    render_ordered_ass,
    scene_end_label,
    scene_start_label,
)

SCENE_ID = "SC_900"
ASSET_ID = "kira_yoga_hall_pilot_image_01"
IMAGE_NAME = "kira_yoga_hall_pilot_image_01"


def _narrative(entry_id="e1", text="Narrative text.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="NARRATIVE", text=text)


def _dialogue(entry_id="e2", character_id="KIRA", text="Hello.") -> TextEntry:
    return TextEntry(entry_id=entry_id, presentation="DIALOGUE", text=text, character_id=character_id)


def _thought(entry_id="e3", character_id="KIRA", text="A thought.", visibility="hidden") -> TextEntry:
    return TextEntry(
        entry_id=entry_id, presentation="THOUGHT", text=text,
        character_id=character_id, thought_visibility=visibility,
    )


def _option(option_id, display_text, target_kind="SCENE", target_id="SC_901") -> ChoiceOption:
    return ChoiceOption(
        option_id=option_id, display_text=display_text,
        target=ChoiceTarget(target_kind=target_kind, target_id=target_id),
    )


def _choice(entry_id="c1", prompt=None, options=()) -> ChoiceEntry:
    return ChoiceEntry(entry_id=entry_id, prompt=prompt, options=options)


def _visual(entry_id="v1", operation="SET", asset_id=ASSET_ID, transition=None) -> VisualChangeEvent:
    return VisualChangeEvent(
        entry_id=entry_id, operation=operation, asset_id=asset_id, transition=transition
    )


def _body(**overrides) -> SceneBody:
    fields = dict(
        authoring_schema_version=AUTHORING_SCHEMA_VERSION,
        scene_id=SCENE_ID,
        location_id="yoga_hall",
        participants=(Participant(character_id="KIRA", role="protagonist", present=True),),
        content_rating="PG",
        entries=(_narrative(),),
    )
    fields.update(overrides)
    return SceneBody(**fields)


def _ass(entries=()) -> object:
    body = _body(entries=entries or (_narrative(),))
    return build_ordered_ass(body, ass_id="ass_1", version=1, source_ref="x.json", source_hash="0" * 64)


def _ass_direct(entries=()) -> OrderedASS:
    """Construct an OrderedASS directly (bypasses acceptance completeness)."""
    return OrderedASS(
        schema_version="ass/0.2",
        ass_id="ass_1",
        version=1,
        scene_id=SCENE_ID,
        location_id="yoga_hall",
        participants=(AssParticipant("KIRA", "protagonist", True),),
        ordered_flow=entries or (_narrative(),),
        content_rating="PG",
        provenance=Provenance(
            source_kind="scene_body_ordered_acceptance",
            source_ref="x.json",
            source_hash="0" * 64,
            source_schema_version="scene_body/1.0",
        ),
        content_hash="0" * 64,
    )


def _resolved(asset_id=ASSET_ID, image_name=IMAGE_NAME) -> ResolvedAsset:
    return ResolvedAsset(
        asset_id=asset_id,
        relative_path="novel/game/images/story/characters/kira/{}.png".format(image_name),
        renpy_image_name=image_name,
    )


def _render(ass, reading_mode="classic_vn", character_symbols=None, known_scene_ids=None,
            resolved_assets=None) -> str:
    return render_ordered_ass(
        ass,
        reading_mode=reading_mode,
        character_symbols=character_symbols if character_symbols is not None else {"KIRA": "kira"},
        known_scene_ids=known_scene_ids if known_scene_ids is not None else frozenset({SCENE_ID, "SC_901"}),
        resolved_assets=resolved_assets if resolved_assets is not None else {ASSET_ID: _resolved()},
    )


def _legacy_ass() -> ASS:
    return ASS(
        schema_version="ass/0.1",
        ass_id="ass_x",
        version=1,
        scene_id=SCENE_ID,
        location_id="yoga_hall",
        participants=(AssParticipant("KIRA", "protagonist", True),),
        ordered_beats=(),
        content_rating="PG",
        provenance=Provenance(
            source_kind="scenario_json_v2_import", source_ref="x.json",
            source_hash="0" * 64, source_schema_version="2.0",
        ),
        content_hash="0" * 64,
    )


# ---------------------------------------------------------------------------
# Type boundary
# ---------------------------------------------------------------------------

def test_ordered_ass_accepted():
    src = _render(_ass())
    assert "label " in src


def test_legacy_ass_rejected():
    with pytest.raises(OrderedExportError):
        _render(_legacy_ass())


def test_scene_body_rejected():
    with pytest.raises(OrderedExportError):
        _render(_body())


def test_dict_rejected():
    with pytest.raises(OrderedExportError):
        _render({"scene_id": "SC_900"})


def test_invalid_reading_mode_rejected():
    with pytest.raises(OrderedExportError):
        _render(_ass(), reading_mode="bogus")


# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------

def test_visual_set_emits_dedicated_slot():
    src = _render(_ass(entries=(_visual(),)))
    assert "show {} as vne_scene_visual".format(IMAGE_NAME) in src


def test_second_set_uses_same_slot():
    entries = (_visual("v1", asset_id="asset_one"), _visual("v2", asset_id="asset_two"))
    assets = {"asset_one": _resolved("asset_one", "img_one"), "asset_two": _resolved("asset_two", "img_two")}
    src = _render(_ass(entries=entries), resolved_assets=assets)
    assert "show img_one as vne_scene_visual" in src
    assert "show img_two as vne_scene_visual" in src
    assert src.count("vne_scene_visual") == 2


def test_visual_clear_emits_hide_slot():
    src = _render(_ass(entries=(_visual("v1", operation="CLEAR", asset_id=None),)))
    assert "hide vne_scene_visual" in src


def test_clear_before_set_deterministic():
    entries = (_visual("v1", operation="CLEAR", asset_id=None), _visual("v2"))
    a = _render(_ass(entries=entries))
    b = _render(_ass(entries=entries))
    assert a == b
    assert a.index("hide vne_scene_visual") < a.index("show {} as vne_scene_visual".format(IMAGE_NAME))


def test_no_bare_scene_statement():
    src = _render(_ass(entries=(_visual(), _narrative("e2"))))
    for line in src.split("\n"):
        stripped = line.strip()
        assert not stripped.startswith("scene ")
        assert stripped != "scene"


def test_no_custom_layer_or_placeholder():
    src = _render(_ass(entries=(_visual(), _visual("v2", operation="CLEAR", asset_id=None))))
    for forbidden in ("onlayer", "zorder", "behind", "black", "bg black", "placeholder"):
        assert forbidden not in src


def test_text_between_visuals_no_extra_statements():
    entries = (_visual("v1"), _narrative("e2"), _visual("v2", operation="CLEAR", asset_id=None))
    src = _render(_ass(entries=entries))
    assert src.count("vne_scene_visual") == 2


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def test_transition_absent_no_with_line():
    src = _render(_ass(entries=(_visual(transition=None),)))
    assert "with " not in src


def test_transition_cut_no_with_line():
    src = _render(_ass(entries=(_visual(transition="cut"),)))
    assert "with " not in src


def test_transition_fade_emits_with_fade():
    src = _render(_ass(entries=(_visual(transition="fade"),)))
    assert "with fade" in src
    assert src.index("show") < src.index("with fade")


def test_transition_dissolve_emits_with_dissolve():
    src = _render(_ass(entries=(_visual(operation="CLEAR", asset_id=None, transition="dissolve"),)))
    assert "with dissolve" in src


@pytest.mark.parametrize("transition", ["wipe", "fade\njump bad", 'fade" ; python:', "Fade", "dissolve "])
def test_unknown_or_malicious_transition_fails(transition):
    with pytest.raises(OrderedExportError):
        _render(_ass(entries=(_visual(transition=transition),)))


# ---------------------------------------------------------------------------
# Thought visibility matrix (9 combinations)
# ---------------------------------------------------------------------------

_THOUGHT_EXPECT = {
    "classic_vn": {"hidden": False, "revealed": False, "always": True},
    "psychological": {"hidden": False, "revealed": True, "always": True},
    "mind_reading": {"hidden": True, "revealed": True, "always": True},
}


@pytest.mark.parametrize("reading_mode", ["classic_vn", "psychological", "mind_reading"])
@pytest.mark.parametrize("visibility", ["hidden", "revealed", "always"])
def test_thought_visibility_matrix(reading_mode, visibility):
    entries = (_thought("e1", character_id="KIRA", visibility=visibility),)
    src = _render(_ass(entries=entries), reading_mode=reading_mode)
    expected_visible = _THOUGHT_EXPECT[reading_mode][visibility]
    label = entry_label(SCENE_ID, "e1")
    assert ("label {}:".format(label)) in src
    if expected_visible:
        assert 'narrator "A thought."' in src
        assert "    pass" not in src.split("label {}:".format(label))[1].split("\n\n")[0]
    else:
        assert 'narrator "A thought."' not in src
        # invisible thought preserves the control-flow anchor as label + pass
        block = src.split("label {}:".format(label))[1].split("\n\n")[0]
        assert "pass" in block


def test_invisible_thought_still_jump_target():
    entries = (
        _thought("e1", character_id="KIRA", visibility="hidden"),
        _choice("c1", options=(_option("o1", "Go", target_kind="ENTRY", target_id="e1"),)),
    )
    src = _render(_ass(entries=entries), reading_mode="classic_vn")
    label = entry_label(SCENE_ID, "e1")
    assert "label {}:".format(label) in src
    assert "jump {}".format(label) in src


def test_thought_only_character_needs_no_mapping():
    body = _body(
        participants=(Participant(character_id="GHOST", role="", present=True),),
        entries=(_thought("e1", character_id="GHOST", visibility="always"),),
    )
    ass = build_ordered_ass(body, ass_id="ass_1", version=1, source_ref="x", source_hash="0" * 64)
    src = _render(ass, character_symbols={})
    assert 'narrator "A thought."' in src


def test_no_runtime_reading_mode_state():
    src = _render(_ass(entries=(_thought("e1", character_id="KIRA", visibility="hidden"),)))
    for forbidden in ("$ reading_mode", "default reading_mode", "define reading_mode", "reading_mode ="):
        assert forbidden not in src
    # the only mention is the deterministic header comment
    assert "# reading_mode: classic_vn" in src


def test_no_diagnostic_thought_prefix():
    src = _render(_ass(entries=(_thought("e1", character_id="KIRA", visibility="always"),)))
    assert "thought:" not in src
    assert "visibility=" not in src


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def test_narrative_emits_narrator():
    src = _render(_ass(entries=(_narrative("e1", "Kira walks in."),)))
    assert 'narrator "Kira walks in."' in src


def test_dialogue_uses_mapped_symbol():
    src = _render(_ass(entries=(_dialogue("e1", character_id="KIRA", text="Hi"),)))
    assert 'kira "Hi"' in src


def test_missing_dialogue_mapping_rejected():
    with pytest.raises(OrderedExportError):
        _render(_ass(entries=(_dialogue("e1", character_id="KIRA"),)), character_symbols={})


@pytest.mark.parametrize("symbol", ["1bad", "has space", "bad-dash", "def", "label", "narrator", "None", "class"])
def test_invalid_or_reserved_symbol_rejected(symbol):
    with pytest.raises(OrderedExportError):
        _render(_ass(), character_symbols={"KIRA": symbol})


def test_duplicate_symbol_rejected():
    with pytest.raises(OrderedExportError):
        _render(_ass(), character_symbols={"KIRA": "kira", "OLGA": "kira"})


# ---------------------------------------------------------------------------
# Choice
# ---------------------------------------------------------------------------

def test_choice_inline_position_preserved():
    entries = (_narrative("e1"), _choice("c1", options=(_option("o1", "A"),)), _narrative("e3"))
    src = _render(_ass(entries=entries))
    assert src.index(entry_label(SCENE_ID, "e1")) < src.index(entry_label(SCENE_ID, "c1"))
    assert src.index(entry_label(SCENE_ID, "c1")) < src.index(entry_label(SCENE_ID, "e3"))


def test_choice_prompt_none_no_prompt_line():
    src = _render(_ass(entries=(_choice("c1", prompt=None, options=(_option("o1", "A"),)),)))
    block = src.split("label {}:".format(entry_label(SCENE_ID, "c1")))[1]
    assert "menu:" in block
    assert 'narrator "' not in block


def test_choice_prompt_empty_emits_empty_narrator():
    src = _render(_ass(entries=(_choice("c1", prompt="", options=(_option("o1", "A"),)),)))
    assert 'narrator ""' in src


def test_choice_prompt_nonempty_emits_narrator():
    src = _render(_ass(entries=(_choice("c1", prompt="What next?", options=(_option("o1", "A"),)),)))
    assert 'narrator "What next?"' in src


def test_choice_option_order_exact():
    entries = (_choice("c1", options=(_option("o1", "Alpha"), _option("o2", "Beta")),),)
    src = _render(_ass(entries=entries))
    assert src.index('"Alpha":') < src.index('"Beta":')


def test_choice_entry_target_jump():
    entries = (
        _narrative("e1"),
        _choice("c1", options=(_option("o1", "Back", target_kind="ENTRY", target_id="e1"),)),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(entry_label(SCENE_ID, "e1")) in src


def test_choice_scene_target_jump():
    entries = (_choice("c1", options=(_option("o1", "Next", target_kind="SCENE", target_id="SC_901"),)),)
    src = _render(_ass(entries=entries))
    assert "jump {}".format(scene_start_label("SC_901")) in src


def test_choice_forward_backward_self_targets_allowed():
    entries = (
        _narrative("e1"),
        _choice("c1", options=(
            _option("o1", "Fwd", target_kind="ENTRY", target_id="e3"),
            _option("o2", "Back", target_kind="ENTRY", target_id="e1"),
            _option("o3", "Self", target_kind="ENTRY", target_id="c1"),
        )),
        _narrative("e3"),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(entry_label(SCENE_ID, "e3")) in src
    assert "jump {}".format(entry_label(SCENE_ID, "e1")) in src
    assert "jump {}".format(entry_label(SCENE_ID, "c1")) in src


def test_unknown_entry_target_fails():
    entries = (_choice("c1", options=(_option("o1", "X", target_kind="ENTRY", target_id="NOPE"),)),)
    with pytest.raises(OrderedExportError):
        _render(_ass_direct(entries=entries))


def test_unknown_scene_target_fails():
    entries = (_choice("c1", options=(_option("o1", "X", target_kind="SCENE", target_id="SC_999"),)),)
    with pytest.raises(OrderedExportError):
        _render(_ass(entries=entries))


def test_no_graph_analysis():
    # A self-referential and a non-terminating cycle are rendered without any
    # reachability/cycle rejection.
    entries = (
        _choice("c1", options=(_option("o1", "Loop", target_kind="ENTRY", target_id="c1"),)),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(entry_label(SCENE_ID, "c1")) in src


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def test_scene_labels_deterministic_base32():
    a = scene_start_label("SC_900")
    b = scene_start_label("SC_900")
    assert a == b
    assert a.startswith("vne_scene_")
    assert a.endswith("_start")
    assert a == a.lower()


def test_unicode_scene_and_entry_ids():
    label = entry_label("\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u0436", "\u0441\u0446\u0435\u043d\u0430")
    assert label.isascii()
    assert label.startswith("vne_scene_")
    assert "_entry_" in label


def test_punctuation_ids_encoded():
    label = entry_label("scene:1", "entry/a+b")
    assert label.isascii()
    assert ":" not in label
    assert "/" not in label


def test_collision_pair_distinct():
    assert scene_start_label("scene-a") != scene_start_label("scene_a")
    assert entry_label("S", "scene-a") != entry_label("S", "scene_a")


def test_label_identity_independent_of_position():
    entries_a = (_narrative("e1"), _narrative("e2"))
    entries_b = (_narrative("e2"), _narrative("e1"))
    assert entry_label(SCENE_ID, "e1") == entry_label(SCENE_ID, "e1")
    # reorder does not change the label identity of a given entry
    src_a = _render(_ass(entries=entries_a))
    src_b = _render(_ass(entries=entries_b))
    assert "label {}:".format(entry_label(SCENE_ID, "e1")) in src_a
    assert "label {}:".format(entry_label(SCENE_ID, "e1")) in src_b


def test_scene_end_label_returns():
    src = _render(_ass())
    assert "label {}:".format(scene_end_label(SCENE_ID)) in src
    assert "    return" in src


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

def test_escape_quotes():
    src = _render(_ass(entries=(_narrative("e1", 'Say "hi" now.'),)))
    assert 'narrator "Say \\"hi\\" now."' in src


def test_escape_backslash():
    src = _render(_ass(entries=(_narrative("e1", "a\\b"),)))
    assert "a\\\\b" in src


def test_escape_newline_variants_flatten():
    src_crlf = _render(_ass(entries=(_narrative("e1", "a\r\nb"),)))
    src_cr = _render(_ass(entries=(_narrative("e1", "a\rb"),)))
    src_lf = _render(_ass(entries=(_narrative("e1", "a\nb"),)))
    assert src_crlf == src_cr == src_lf
    assert 'narrator "a b"' in src_crlf


def test_escape_interpolation_brackets():
    src = _render(_ass(entries=(_narrative("e1", "[{【"),)))
    assert 'narrator "[[{{【【"' in src


@pytest.mark.parametrize("bad", ["a\tb", "a\0b", "a\x1bb", "a\x7fb", "a\x85b"])
def test_control_character_rejected(bad):
    with pytest.raises(OrderedExportError):
        _render(_ass(entries=(_narrative("e1", bad),)))


def test_escape_applied_to_choice_prompt_and_option():
    entries = (_choice("c1", prompt="Pick [one]", options=(_option("o1", "{two}"),)),)
    src = _render(_ass(entries=entries))
    assert 'narrator "Pick [[one]"' in src
    assert '"{{two}":' in src


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_equivalent_inputs_byte_identical():
    def make():
        entries = (_narrative("e1", "Hello."), _dialogue("e2", "KIRA", "Hi"), _visual("v1"))
        return _render(_ass(entries=entries))
    a = make()
    b = make()
    assert a == b
    assert isinstance(a, str)


def test_no_timestamp_or_path_in_source():
    src = _render(_ass())
    assert "2026" not in src
    assert "C:" not in src
    assert "C:\\" not in src


def test_header_has_stable_fields_only():
    src = _render(_ass())
    assert "# OrderedASS scene SC_900" in src
    assert "# reading_mode: classic_vn" in src
    # no process-specific or time-dependent metadata
    assert "ass_id" not in src.split("\n\n")[0]


# ---------------------------------------------------------------------------
# next_target -- explicit successor contract (OD-ORDEREDASS-CONTROL-FLOW-01)
# ---------------------------------------------------------------------------

def _label_line(entry_id: str) -> str:
    return "label {}:".format(entry_label(SCENE_ID, entry_id))


def _entry_block(src: str, entry_id: str) -> str:
    """Return the exact rendered lines for one entry: from its own label up
    to (but excluding) the next ``label `` line."""
    start_marker = _label_line(entry_id) + "\n"
    start = src.index(start_marker) + len(start_marker)
    rest = src[start:]
    next_label_pos = rest.find("\nlabel ")
    return rest[:next_label_pos] if next_label_pos != -1 else rest


def test_next_target_none_preserves_fallthrough():
    entries = (_narrative("e1"), _narrative("e2"))
    src = _render(_ass(entries=entries))
    assert "jump" not in _entry_block(src, "e1")


def test_next_target_entry_emits_jump():
    entries = (
        TextEntry(entry_id="e1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="ENTRY", target_id="e2")),
        _narrative("e2"),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(entry_label(SCENE_ID, "e2")) in _entry_block(src, "e1")


def test_next_target_scene_emits_jump():
    entries = (
        TextEntry(entry_id="e1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="SCENE", target_id="SC_901")),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(scene_start_label("SC_901")) in _entry_block(src, "e1")


def test_next_target_end_emits_jump_to_scene_end():
    entries = (
        TextEntry(entry_id="e1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="END")),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(scene_end_label(SCENE_ID)) in _entry_block(src, "e1")


def test_visual_next_target_end_emits_jump():
    entries = (
        VisualChangeEvent(entry_id="v1", operation="CLEAR", asset_id=None,
                           next_target=ChoiceTarget(target_kind="END")),
    )
    src = _render(_ass(entries=entries))
    assert "jump {}".format(scene_end_label(SCENE_ID)) in _entry_block(src, "v1")


def test_hidden_thought_next_target_still_honored():
    entries = (
        TextEntry(entry_id="e1", presentation="THOUGHT", text="A", character_id="KIRA",
                  thought_visibility="hidden", next_target=ChoiceTarget(target_kind="END")),
    )
    src = _render(_ass(entries=entries))
    block = _entry_block(src, "e1")
    # hidden-thought behavior unchanged: still a bare "pass" anchor line...
    assert "    pass" in block
    # ...and the explicit successor is still honored after it.
    assert "jump {}".format(scene_end_label(SCENE_ID)) in block


def test_next_target_unknown_entry_rejected():
    entries = (
        TextEntry(entry_id="e1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="ENTRY", target_id="NOPE")),
    )
    with pytest.raises(OrderedExportError):
        _render(_ass_direct(entries=entries))


def test_next_target_unknown_scene_rejected():
    entries = (
        TextEntry(entry_id="e1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="SCENE", target_id="SC_999")),
    )
    with pytest.raises(OrderedExportError):
        _render(_ass_direct(entries=entries), known_scene_ids=frozenset({SCENE_ID}))


# ---------------------------------------------------------------------------
# Multibranch fixture (test-only; NOT SC_017 authority) -- Stage 10
# ---------------------------------------------------------------------------

def test_three_branch_choice_structural_isolation():
    """A genuine 3-option ChoiceEntry with 3 distinct multi-entry branches,
    each terminated explicitly via next_target=END. Proves the generated
    Ren'Py never relies on accidental fallthrough between branches.

    Test-only fixture. Does not create or represent SC_017 authority.
    """
    entries = (
        ChoiceEntry(
            entry_id="c1", prompt="Pick",
            options=(
                _option("o1", "Branch A", target_kind="ENTRY", target_id="a1"),
                _option("o2", "Branch B", target_kind="ENTRY", target_id="b1"),
                _option("o3", "Branch C", target_kind="ENTRY", target_id="c1_start"),
            ),
        ),
        TextEntry(entry_id="a1", presentation="NARRATIVE", text="Branch A first."),
        TextEntry(entry_id="a2", presentation="NARRATIVE", text="Branch A second.",
                  next_target=ChoiceTarget(target_kind="END")),
        TextEntry(entry_id="b1", presentation="NARRATIVE", text="Branch B first."),
        TextEntry(entry_id="b2", presentation="NARRATIVE", text="Branch B second.",
                  next_target=ChoiceTarget(target_kind="END")),
        TextEntry(entry_id="c1_start", presentation="NARRATIVE", text="Branch C first."),
        TextEntry(entry_id="c2", presentation="NARRATIVE", text="Branch C second.",
                  next_target=ChoiceTarget(target_kind="END")),
    )
    ass = _ass(entries=entries)  # requires acceptance-completeness to pass
    src = _render(ass)

    # All 3 menu options present.
    assert '"Branch A":' in src
    assert '"Branch B":' in src
    assert '"Branch C":' in src

    # Each option jumps to its own, distinct branch start.
    assert "jump {}".format(entry_label(SCENE_ID, "a1")) in src
    assert "jump {}".format(entry_label(SCENE_ID, "b1")) in src
    assert "jump {}".format(entry_label(SCENE_ID, "c1_start")) in src

    # Each branch's final entry explicitly jumps to scene_end (no fallthrough).
    end_label = scene_end_label(SCENE_ID)
    for final_id in ("a2", "b2", "c2"):
        block = _entry_block(src, final_id)
        assert block.strip().splitlines()[-1] == "    jump {}".format(end_label)

    # No branch's rendered block contains another branch's own label -- proves
    # branch A/B never silently continue into a sibling branch's content.
    a_block = _entry_block(src, "a1") + _entry_block(src, "a2")
    for other in ("b1", "b2", "c1_start", "c2"):
        assert entry_label(SCENE_ID, other) not in a_block
    b_block = _entry_block(src, "b1") + _entry_block(src, "b2")
    for other in ("a1", "a2", "c1_start", "c2"):
        assert entry_label(SCENE_ID, other) not in b_block


# ---------------------------------------------------------------------------
# Convergent branches (test-only) -- Stage 11
# ---------------------------------------------------------------------------

def test_convergent_branches_render_to_shared_join():
    """Two branches explicitly converge on one shared join entry via
    next_target=ENTRY, without any renderer-side inference."""
    entries = (
        ChoiceEntry(
            entry_id="c1", prompt="Pick",
            options=(
                _option("o1", "Branch A", target_kind="ENTRY", target_id="a1"),
                _option("o2", "Branch B", target_kind="ENTRY", target_id="b1"),
            ),
        ),
        TextEntry(entry_id="a1", presentation="NARRATIVE", text="A",
                  next_target=ChoiceTarget(target_kind="ENTRY", target_id="join")),
        TextEntry(entry_id="b1", presentation="NARRATIVE", text="B",
                  next_target=ChoiceTarget(target_kind="ENTRY", target_id="join")),
        TextEntry(entry_id="join", presentation="NARRATIVE", text="Shared continuation."),
    )
    ass = _ass(entries=entries)
    src = _render(ass)

    join_label = entry_label(SCENE_ID, "join")
    assert "jump {}".format(join_label) in _entry_block(src, "a1")
    assert "jump {}".format(join_label) in _entry_block(src, "b1")
    # join is the last ordered_flow entry: falls through to scene_end as-is.
    assert "jump" not in _entry_block(src, "join")
