#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused tests for persisted SceneStillPlan replay (no semantic LLM call).

Hermetic: no network, no proposer, no image provider. Uses the real persisted
DeepSeek plan when available, otherwise the offline fixture plan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.scene_image_test_app as app  # noqa: E402
from services.scene_text_interpreter import (  # noqa: E402
    PlanLoadError,
    SceneStillPlan,
    load_scene_still_plan,
)
from services.scene_text_interpreter.hashing import compute_content_hash  # noqa: E402
from services.scene_text_interpreter.model import (  # noqa: E402
    DRAFT_STATUS,
    STILL_PLAN_SCHEMA_VERSION,
    ChosenStill,
    PlanBeat,
    StillCandidate,
)
from tests.test_scene_text_interpreter import _build_hermetic_auto  # noqa: E402

_SCRATCH = Path(
    "C:/Users/andrc/AppData/Local/Temp/claude/"
    "c--DEV-Narrative-vne-scene-aware-reference-selection-v0/"
    "d17b906e-1a33-4009-ab28-b2de350a8f86/scratchpad"
)
_REAL_PLAN = _SCRATCH / "real_llm_plan.json"
_OFFLINE_PLAN = _SCRATCH / "first_proof_plan.json"
_REAL_PLAN_HASH = "0a89fa2a50f19af059d21c8e7878400245d355b3b3eeb310aabd6a21d3085f8e"
_BUNDLE_HASH = "22022349938c46d8f9b7c4e62abab4552b5799f7a106da8657b2e02ce3c37e08"


def _base_plan_dict() -> dict:
    """A known-valid persisted plan payload (real DeepSeek plan preferred)."""
    src = _REAL_PLAN if _REAL_PLAN.exists() else _OFFLINE_PLAN
    if not src.exists():
        pytest.skip("no persisted plan available in the scratchpad")
    return json.loads(src.read_text(encoding="utf-8"))


def _recompute_hash(d: dict) -> str:
    plan = SceneStillPlan(
        schema_version=STILL_PLAN_SCHEMA_VERSION,
        status=DRAFT_STATUS,
        source_text_hash=d["source_text_hash"],
        characters_in_frame=tuple(d["characters_in_frame"]),
        provider_alias_by_character=dict(d["provider_alias_by_character"]),
        location_id=d["location_id"],
        scene_tags=tuple(d["scene_tags"]),
        beats=tuple(
            PlanBeat(
                index=b["index"],
                text_span=b["text_span"],
                actor_character_ids=tuple(b["actor_character_ids"]),
                action_phrase=b["action_phrase"],
                gaze_phrase=b.get("gaze_phrase"),
                positioning_phrase=b.get("positioning_phrase"),
                contact_flag=b.get("contact_flag", False),
            )
            for b in d["beats"]
        ),
        still_candidates=tuple(
            StillCandidate(
                beat_index=c["beat_index"],
                score=c["score"],
                rationale_tags=tuple(c.get("rationale_tags", [])),
            )
            for c in d["still_candidates"]
        ),
        chosen_still=ChosenStill(**d["chosen_still"]),
        evidence=d["evidence"],
        unresolved_items=tuple(d["unresolved_items"]),
        interpreter=d["interpreter"],
        content_hash="",
    )
    return compute_content_hash(plan.semantic_payload())


def _valid_plan(**overrides) -> dict:
    """A structurally valid plan dict with a CORRECT content_hash for its body."""
    d = _base_plan_dict()
    d.update(overrides)
    d["content_hash"] = _recompute_hash(d)
    return d


def _write(tmp_path: Path, d: dict, name: str = "plan.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# Strict load + hash integrity
# --------------------------------------------------------------------------


def test_valid_plan_loads_and_recomputes_hash(tmp_path):
    p = _write(tmp_path, _valid_plan())
    plan = load_scene_still_plan(p, repo_root=_REPO_ROOT)
    assert plan.status == "DRAFT"
    assert plan.content_hash == _recompute_hash(json.loads(p.read_text(encoding="utf-8")))
    assert plan.characters_in_frame == ("MARINA", "MAKSIM")
    assert plan.location_id == "gym"


@pytest.mark.skipif(not _REAL_PLAN.exists(), reason="real DeepSeek plan not persisted")
def test_real_persisted_plan_hash_matches_accepted_evidence(tmp_path):
    plan = load_scene_still_plan(_REAL_PLAN, repo_root=_REPO_ROOT)
    assert plan.content_hash == _REAL_PLAN_HASH


def test_tampered_body_without_rehash_fails(tmp_path):
    d = _valid_plan()
    d["location_id"] = "yoga_hall"  # body changed, stored hash now stale
    p = _write(tmp_path, d)
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_explicit_content_hash_mismatch_fails(tmp_path):
    d = _valid_plan()
    d["content_hash"] = "0" * 64
    p = _write(tmp_path, d)
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_wrong_schema_version_fails(tmp_path):
    d = _valid_plan()
    d["schema_version"] = "vne_scene_still_plan/9.9"
    p = _write(tmp_path, d)
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_non_draft_status_fails(tmp_path):
    d = _valid_plan()
    d["status"] = "ACCEPTED"
    p = _write(tmp_path, d)
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_missing_file_fails_closed(tmp_path):
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(tmp_path / "nope.json", repo_root=_REPO_ROOT)


# --------------------------------------------------------------------------
# Bridge invariants (run after hash verification)
# --------------------------------------------------------------------------


def test_one_character_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(
        characters_in_frame=["MARINA"],
        provider_alias_by_character={"MARINA": "Marina"},
    ))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_three_characters_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(
        characters_in_frame=["MARINA", "MAKSIM", "OLGA"],
        provider_alias_by_character={"MARINA": "Marina", "MAKSIM": "Maksim", "OLGA": "Olga"},
    ))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_unknown_character_id_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(
        characters_in_frame=["MARINA", "NOBODY"],
        provider_alias_by_character={"MARINA": "Marina", "NOBODY": "Nobody"},
    ))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_provider_alias_mismatch_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(
        provider_alias_by_character={"MARINA": "Marina", "MAKSIM": "Max"},
    ))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_invalid_location_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(location_id="casino"))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_unknown_scene_tag_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(scene_tags=["stretching", "sensual"]))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_scene_tag_duplicating_location_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(scene_tags=["gym", "stretching"]))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_unresolved_item_fails(tmp_path):
    p = _write(tmp_path, _valid_plan(unresolved_items=["who looks at whom"]))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


def test_chosen_still_beat_not_in_beats_fails(tmp_path):
    base = _base_plan_dict()
    p = _write(tmp_path, _valid_plan(
        chosen_still={"beat_index": 99, "visual_goal": base["chosen_still"]["visual_goal"]},
    ))
    with pytest.raises(PlanLoadError):
        load_scene_still_plan(p, repo_root=_REPO_ROOT)


# --------------------------------------------------------------------------
# Profile bridge + orchestrate reuse (no proposer, no provider)
# --------------------------------------------------------------------------


def test_replay_never_instantiates_a_proposer(tmp_path, monkeypatch):
    import services.scene_text_interpreter as sti
    import tools.scene_text_llm_adapter as adapter

    def boom(*a, **k):
        raise AssertionError("replay must not construct any proposer")

    monkeypatch.setattr(sti, "FixtureProposer", boom)
    monkeypatch.setattr(sti, "MockProposer", boom)
    monkeypatch.setattr(adapter.DeepSeekSceneTextProposer, "__init__", boom)

    p = _write(tmp_path, _valid_plan())
    profile, plan = app.profile_from_plan_file(p, repo_root=_REPO_ROOT)
    assert profile.mode == "auto"
    assert plan.content_hash == _recompute_hash(json.loads(p.read_text(encoding="utf-8")))


def test_replay_builds_auto_profile(tmp_path):
    p = _write(tmp_path, _valid_plan())
    profile, _ = app.profile_from_plan_file(p, repo_root=_REPO_ROOT)
    assert profile.mode == "auto"
    assert profile.references == ()
    assert profile.characters_in_frame == ("MARINA", "MAKSIM")
    assert profile.prompt_aliases == {"MARINA": "Marina", "MAKSIM": "Maksim"}
    assert profile.location_id == "gym"
    assert profile.scene_tags == ("stretching", "training", "neutral")


def test_replay_reaches_orchestrate_preview(tmp_path, monkeypatch, capsys):
    root, manifest = _build_hermetic_auto(tmp_path)

    def image_boom(*a, **k):
        raise AssertionError("image provider must not be called in replay preview")

    monkeypatch.setattr(app, "generate_conditioned_image_from_bundle", image_boom)

    p = _write(tmp_path, _valid_plan())
    code = app.run_preview(
        repo_root=root, manifest_path=manifest, plan_file=str(p)
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "PLAN_REPLAY_MODE=YES" in out
    assert "SEMANTIC_PROVIDER_CALLS=0" in out
    assert "REFERENCE_SELECTION_MODE=AUTO" in out
    assert "marina_face_01 [face]" in out and "marina_sports_01" not in out.split(
        "SELECTED_REFERENCES"
    )[1].split("REFERENCE BUNDLE")[0]
    assert "maksim_gym_01 [motion]" in out
    # exact bundle-hash correlation to _BUNDLE_HASH is proven by the real-asset
    # CLI run; the hermetic repo uses synthetic asset bytes, so here only assert
    # a bundle hash is present.
    assert "REFERENCE BUNDLE HASH=" in out
    assert "CHARACTER PHYSICAL IDENTITY" in out
    assert "PROVIDER_INTERNAL_ID_EXPOSURE=NO" in out
    assert "DRY_RUN_RESULT=PASS" in out
    assert "READY_FOR_LIVE_GENERATION=YES" in out


# --------------------------------------------------------------------------
# CLI mutual exclusivity / other modes intact
# --------------------------------------------------------------------------


def test_plan_file_rejects_scene_text_via_argparse():
    parser = app.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--plan-file", "x.json", "--scene-text", "y", "--preview"])


def test_plan_file_rejects_proposal_fixture_at_runtime(tmp_path, capsys):
    p = _write(tmp_path, _valid_plan())
    code = app.run_preview(
        repo_root=_REPO_ROOT,
        plan_file=str(p),
        proposal_fixture="whatever.json",
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "self-contained replay" in err


def test_existing_fixture_mode_still_works():
    fixture = (
        _REPO_ROOT / "tests/fixtures/scene_text_interpreter/first_proof_proposal.json"
    )
    text = (
        "Марина лежит на коврике в спортзале и делает растяжку.\n"
        "Максим находится рядом и наблюдает за её техникой.\n"
        "Марина поворачивает голову и смотрит на него."
    )
    profile, plan = app.profile_from_scene_text(
        text, repo_root=_REPO_ROOT, proposal_fixture=fixture
    )
    assert profile.mode == "auto"
    assert plan.chosen_still.beat_index == 3
