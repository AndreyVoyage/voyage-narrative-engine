#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for the playable exporter's optional build-time visual wiring.

Covers only ``build_parser`` / ``cmd_build`` / ``resolve_build_visual``:

  * optional, all-or-nothing ``--visual-*`` triplet;
  * ``--visual-registry`` alone (and partial triplets) fail closed;
  * distinct ``media_item_id`` / ``asset_id`` survive the plumbing;
  * real committed Registry resolves the KIRA asset exactly;
  * explicit ``statement_kind`` ("scene" | "show") reaches ``render_scene`` /
    the emitter, never inferred from Registry category / id / path;
  * one tmp_path writer integration proof through the real ``cmd_build`` flow;
  * committed ``novel/game/**/*.rpy`` is never written.

The production output-path safety gate (``assert_safe_output_path``) is NOT
modified; the single writer test monkeypatches it for the test process only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import renpy_v2_playable_exporter as exporter  # noqa: E402
from services.production_media_asset_binding import (  # noqa: E402
    AssetNotFoundError,
    ProductionMediaAssetBindingError,
    ResolvedAsset,
)

_COMMITTED_GENERATED_RPY = _REPO_ROOT / "novel" / "game" / "scenes_v2_generated.rpy"
_KIRA_REGISTRY = _REPO_ROOT / "scenarios" / "visual_assets" / "ASSET_REGISTRY.json"
_KIRA_ID = "kira_yoga_hall_pilot_image_01"
_KIRA_RELATIVE = (
    "novel/game/images/story/characters/kira/kira_yoga_hall_pilot_image_01.png"
)
_KIRA_IMAGE_NAME = "kira_yoga_hall_pilot_image_01"
_KIRA_LINE = "scene kira_yoga_hall_pilot_image_01"

_ACTIVE_TMP_DIRS: list = []


@pytest.fixture(scope="module", autouse=True)
def _guard_committed_generated_rpy():
    """Fail loudly if the milestone ever touches the committed generated .rpy."""
    before = (
        _COMMITTED_GENERATED_RPY.read_bytes()
        if _COMMITTED_GENERATED_RPY.exists()
        else None
    )
    yield
    for ctx in list(_ACTIVE_TMP_DIRS):
        try:
            ctx.cleanup()
        except Exception:
            pass
    _ACTIVE_TMP_DIRS.clear()
    after = (
        _COMMITTED_GENERATED_RPY.read_bytes()
        if _COMMITTED_GENERATED_RPY.exists()
        else None
    )
    assert after == before, "committed novel/game/scenes_v2_generated.rpy was modified"


def _ns(**overrides) -> argparse.Namespace:
    base = dict(
        scene="SC_UNUSED",
        output="novel/game/scenes_v2_generated.rpy",
        visual_media_item_id=None,
        visual_asset_id=None,
        visual_statement_kind=None,
        visual_registry=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _make_scene_and_json(scene: dict, prefix="vne_play_wiring_") -> tuple[dict, Path]:
    ctx = tempfile.TemporaryDirectory(prefix=prefix, dir=str(_REPO_ROOT))
    _ACTIVE_TMP_DIRS.append(ctx)
    path = Path(ctx.name) / "scene.v2.json"
    path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")
    return scene, path


def _write_registry(tmp_path: Path, records: list[dict]) -> Path:
    reg = tmp_path / "ASSET_REGISTRY.json"
    reg.write_text(json.dumps({"assets": records}, indent=2), encoding="utf-8")
    return reg


_SCENE = {
    "id": "SC_017",
    "name": "Сергей пишет снова",
    "schema_version": "2.0",
    "characters": [{"id": "kira", "display_name": "Кира", "present": True}],
    "entry_beats": [
        {"beat_id": "e1", "type": "narration", "narration": "Телефон загорается."},
    ],
    "choice_points": [
        {
            "id": "cp1",
            "prompt": "Что делает Кира?",
            "branches": [
                {"id": "1a", "option_text": "Показывает.", "beats": [], "effects": {}},
            ],
        }
    ],
    "safety": {"content_rating": "PG-13"},
}


# ---------------------------------------------------------------------------
# 1. No visual input -> text-only render unchanged
# ---------------------------------------------------------------------------


def test_no_visual_input_render_is_text_only():
    scene, path = _make_scene_and_json(_SCENE)
    none_asset, none_kind = exporter.resolve_build_visual(
        visual_media_item_id=None,
        visual_asset_id=None,
        visual_statement_kind=None,
        visual_registry=None,
    )
    assert (none_asset, none_kind) == (None, None)

    baseline = exporter.render_scene(scene, path)
    assert "\n    scene " not in baseline
    assert "\n    show " not in baseline
    assert _KIRA_LINE not in baseline


# ---------------------------------------------------------------------------
# 2. Parser accepts the full optional visual input
# ---------------------------------------------------------------------------


def test_parser_accepts_full_visual_input():
    ns = exporter.build_parser().parse_args(
        [
            "build",
            "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json",
            "--output",
            "novel/game/scenes_v2_generated.rpy",
            "--visual-media-item-id",
            "scene_media_need_017",
            "--visual-asset-id",
            _KIRA_ID,
            "--visual-statement-kind",
            "scene",
            "--visual-registry",
            "scenarios/visual_assets/ASSET_REGISTRY.json",
        ]
    )
    assert ns.visual_media_item_id == "scene_media_need_017"
    assert ns.visual_asset_id == _KIRA_ID
    assert ns.visual_statement_kind == "scene"
    assert ns.visual_registry == "scenarios/visual_assets/ASSET_REGISTRY.json"
    assert ns.func is exporter.cmd_build


def test_parser_rejects_unsupported_statement_kind():
    with pytest.raises(SystemExit):
        exporter.build_parser().parse_args(
            [
                "build",
                "SC_017",
                "--output",
                "novel/game/scenes_v2_generated.rpy",
                "--visual-statement-kind",
                "reveal",
            ]
        )


# ---------------------------------------------------------------------------
# 3. Partial triplet fails closed (helper + cmd_build)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kw",
    [
        dict(visual_asset_id="a"),
        dict(visual_media_item_id="m"),
        dict(visual_statement_kind="scene"),
        dict(visual_media_item_id="m", visual_asset_id="a"),
        dict(visual_asset_id="a", visual_statement_kind="scene"),
        dict(visual_media_item_id="m", visual_statement_kind="scene"),
    ],
)
def test_partial_triplet_fails_closed(kw):
    with pytest.raises(ValueError):
        exporter.resolve_build_visual(
            visual_media_item_id=kw.get("visual_media_item_id"),
            visual_asset_id=kw.get("visual_asset_id"),
            visual_statement_kind=kw.get("visual_statement_kind"),
            visual_registry=None,
        )


def test_cmd_build_partial_triplet_returns_failure(monkeypatch):
    monkeypatch.setattr(exporter, "assert_safe_output_path", lambda p: None)
    called = {"load_scene": False}
    monkeypatch.setattr(
        exporter,
        "load_scene",
        lambda *a, **k: called.__setitem__("load_scene", True),
    )
    rc = exporter.cmd_build(_ns(visual_asset_id="a"))
    assert rc == 1
    assert called["load_scene"] is False  # failed before scene load, no write


# ---------------------------------------------------------------------------
# 4. --visual-registry alone fails closed
# ---------------------------------------------------------------------------


def test_visual_registry_alone_fails_closed():
    with pytest.raises(ValueError):
        exporter.resolve_build_visual(
            visual_media_item_id=None,
            visual_asset_id=None,
            visual_statement_kind=None,
            visual_registry="scenarios/visual_assets/ASSET_REGISTRY.json",
        )


def test_cmd_build_visual_registry_alone_returns_failure(monkeypatch):
    monkeypatch.setattr(exporter, "assert_safe_output_path", lambda p: None)
    monkeypatch.setattr(
        exporter, "load_scene", lambda *a, **k: pytest.fail("load_scene reached")
    )
    rc = exporter.cmd_build(_ns(visual_registry=str(_KIRA_REGISTRY)))
    assert rc == 1


# ---------------------------------------------------------------------------
# 5. cmd_build passes DISTINCT media_item_id / asset_id to the existing adapter
# ---------------------------------------------------------------------------


def test_distinct_ids_passed_through_to_adapter(monkeypatch):
    seen = {}

    def _fake_resolve(*, media_item_id, asset_id, registry_path):
        seen["media_item_id"] = media_item_id
        seen["asset_id"] = asset_id
        seen["registry_path"] = registry_path
        return ResolvedAsset(
            asset_id=asset_id,
            relative_path="novel/game/images/story/cg/x.png",
            renpy_image_name="x",
        )

    import tools.vne_to_renpy as adapter_pkg

    monkeypatch.setattr(adapter_pkg, "resolve_media_asset_for_renpy", _fake_resolve)

    resolved, kind = exporter.resolve_build_visual(
        visual_media_item_id="scene_media_need_042",
        visual_asset_id="production_asset_abc",
        visual_statement_kind="scene",
        visual_registry=None,
    )
    assert seen["media_item_id"] == "scene_media_need_042"
    assert seen["asset_id"] == "production_asset_abc"
    assert seen["media_item_id"] != seen["asset_id"]
    # canonical default registry made explicit at resolution time
    assert seen["registry_path"] == _REPO_ROOT / exporter.DEFAULT_VISUAL_REGISTRY
    assert kind == "scene"
    assert resolved.asset_id == "production_asset_abc"


def test_unequal_ids_resolve_keyed_on_asset_id_via_tmp_registry(tmp_path):
    reg = _write_registry(
        tmp_path,
        [{"asset_id": "generic_cg_01", "relative_path": "novel/game/images/story/cg/abc.png"}],
    )
    resolved, kind = exporter.resolve_build_visual(
        visual_media_item_id="scene_media_need_999",
        visual_asset_id="generic_cg_01",
        visual_statement_kind="show",
        visual_registry=str(reg),
    )
    assert resolved.asset_id == "generic_cg_01"
    assert resolved.relative_path == "novel/game/images/story/cg/abc.png"
    assert resolved.renpy_image_name == "abc"
    assert kind == "show"


# ---------------------------------------------------------------------------
# 6. Real committed Registry resolves the KIRA asset exactly
# ---------------------------------------------------------------------------


def test_real_kira_registry_resolution():
    resolved, kind = exporter.resolve_build_visual(
        visual_media_item_id=_KIRA_ID,
        visual_asset_id=_KIRA_ID,
        visual_statement_kind="scene",
        visual_registry=None,
    )
    assert isinstance(resolved, ResolvedAsset)
    assert resolved.asset_id == _KIRA_ID
    assert resolved.relative_path == _KIRA_RELATIVE
    assert resolved.renpy_image_name == _KIRA_IMAGE_NAME
    assert kind == "scene"


# ---------------------------------------------------------------------------
# 7 + 8 + 9. Explicit scene reaches render_scene; exact line; insertion order
# ---------------------------------------------------------------------------


def test_explicit_scene_reaches_render_scene_exact_line_and_order():
    scene, path = _make_scene_and_json(_SCENE)
    resolved, kind = exporter.resolve_build_visual(
        visual_media_item_id=_KIRA_ID,
        visual_asset_id=_KIRA_ID,
        visual_statement_kind="scene",
        visual_registry=None,
    )
    text = exporter.render_scene(
        scene, path, visual_asset=resolved, visual_statement_kind=kind
    )

    assert text.count(_KIRA_LINE) == 1
    label_idx = text.find("label sc_017_v2_start:")
    visual_idx = text.find(f"    {_KIRA_LINE}")
    set_beat_idx = text.find("_vne_aside_set_scene_beat")
    narrator_idx = text.find("narrator ")
    assert label_idx >= 0
    assert label_idx < visual_idx < set_beat_idx < narrator_idx
    line = text.splitlines()[text[:visual_idx].count("\n")]
    assert line == f"    {_KIRA_LINE}"
    for forbidden in (" with ", " at ", " onlayer ", " zorder ", " behind "):
        assert forbidden not in line
    assert "hide " not in text


# ---------------------------------------------------------------------------
# 10 + 13. Generic explicit "show"; no category -> statement inference
# ---------------------------------------------------------------------------


def test_generic_show_via_build_wiring(tmp_path):
    scene, path = _make_scene_and_json(_SCENE)
    reg = _write_registry(
        tmp_path,
        [{"asset_id": "generic_cg_01", "relative_path": "novel/game/images/story/cg/abc.png"}],
    )
    resolved, kind = exporter.resolve_build_visual(
        visual_media_item_id="scene_media_need_777",
        visual_asset_id="generic_cg_01",
        visual_statement_kind="show",
        visual_registry=str(reg),
    )
    text = exporter.render_scene(
        scene, path, visual_asset=resolved, visual_statement_kind=kind
    )
    assert "\n    show abc\n" in text
    assert "\n    scene abc\n" not in text


def test_statement_kind_not_inferred_from_registry_category(tmp_path):
    # KIRA asset is Registry type "character"; asking for "show" must yield show,
    # asking for "scene" must yield scene -> the flag alone drives the verb.
    scene, path = _make_scene_and_json(_SCENE)
    for kind, verb in (("scene", "scene"), ("show", "show")):
        resolved, k = exporter.resolve_build_visual(
            visual_media_item_id=_KIRA_ID,
            visual_asset_id=_KIRA_ID,
            visual_statement_kind=kind,
            visual_registry=None,
        )
        text = exporter.render_scene(
            scene, path, visual_asset=resolved, visual_statement_kind=k
        )
        assert f"\n    {verb} {_KIRA_IMAGE_NAME}\n" in text


# ---------------------------------------------------------------------------
# 11. Unknown asset fails closed at the cmd_build boundary
# ---------------------------------------------------------------------------


def test_unknown_asset_fails_closed():
    with pytest.raises(AssetNotFoundError):
        exporter.resolve_build_visual(
            visual_media_item_id="scene_media_need_404",
            visual_asset_id="no_such_asset_zzz",
            visual_statement_kind="scene",
            visual_registry=None,
        )


def test_cmd_build_unknown_asset_returns_failure(monkeypatch):
    monkeypatch.setattr(exporter, "assert_safe_output_path", lambda p: None)
    monkeypatch.setattr(
        exporter, "load_scene", lambda *a, **k: pytest.fail("load_scene reached")
    )
    rc = exporter.cmd_build(
        _ns(
            visual_media_item_id="scene_media_need_404",
            visual_asset_id="no_such_asset_zzz",
            visual_statement_kind="scene",
        )
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# 12 (the single authorized writer integration test)
# ---------------------------------------------------------------------------


def test_cmd_build_writer_integration_tmp_path(tmp_path, monkeypatch):
    """The single authorized writer-level integration test.

    Full ``cmd_build`` flow into pytest ``tmp_path`` (production output-path
    gate bypassed for the test process only). Proves CLI/Namespace visual
    inputs -> resolution -> ``render_scene`` forwarding -> emitted KIRA source
    -> ``write_text``; and, with no visual inputs, byte-identical text-only
    output; and that nothing is written under committed ``novel/game``.
    """
    monkeypatch.setattr(exporter, "assert_safe_output_path", lambda p: None)
    scene_arg = "scenarios/SCENARIO_017_SERGEY_WRITES_AGAIN.v2.json"

    # (a) explicit KIRA visual build
    kira_out = tmp_path / "scenes_v2_generated.rpy"
    rc = exporter.cmd_build(
        _ns(
            scene=scene_arg,
            output=str(kira_out),
            visual_media_item_id=_KIRA_ID,
            visual_asset_id=_KIRA_ID,
            visual_statement_kind="scene",
        )
    )
    assert rc == 0
    generated = kira_out.read_text(encoding="utf-8")
    assert generated.count(_KIRA_LINE) == 1
    label_idx = generated.find("label sc_017_v2_start:")
    visual_idx = generated.find(f"    {_KIRA_LINE}")
    set_beat_idx = generated.find("_vne_aside_set_scene_beat")
    assert label_idx >= 0 and label_idx < visual_idx < set_beat_idx

    # (b) no visual inputs -> byte-identical to render_scene()
    text_out = tmp_path / "text_only.rpy"
    rc = exporter.cmd_build(_ns(scene=scene_arg, output=str(text_out)))
    assert rc == 0
    written = text_out.read_text(encoding="utf-8")
    scene_path, scene = exporter.load_scene(scene_arg)
    assert written == exporter.render_scene(scene, scene_path)
    assert "scene story" not in written and "show story" not in written

    # nothing leaked under a committed runtime path
    assert not (tmp_path / "novel").exists()
