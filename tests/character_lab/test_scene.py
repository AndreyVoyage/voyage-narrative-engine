#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PART S + PART I -- Scene Setup (offline, fake provider)."""

from __future__ import annotations

import json
from pathlib import Path

from kira_chat_cli import KiraChatCLI
from services.character_lab import (
    BetaV1CurrentPolicy,
    CharacterLabApp,
    new_scene,
    render_scene_block,
    scene_hash,
)
from services.crp_authoring import (
    AcceptanceRecord,
    CandidateCharacterPackage,
    PackageStatus,
    compute_package_hash,
)
from services.crp_authoring.acceptance_store import write_acceptance_record
from datetime import datetime, timezone

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCENE_PAYLOAD = {
    "title": "Тест вечеринки",
    "location": "вечеринка",
    "participants": ["Андрей", "Кира", "Сергей"],
    "prior_events": ["Андрей и Кира пришли вместе."],
    "current_situation": "Сергей подходит к Кире и приглашает её танцевать.",
}


def _fake_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {"choices": [{"message": {"content": response}, "finish_reason": "stop"}]}})
            return response
        return provider
    return factory


def _make_app(tmp_path):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        provider_factory=_fake_provider_factory(),
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        provider_availability="CONFIGURED",
    )


# --- hermetic package for the exact Beta-v1 no-scene freeze comparison --------
def _hermetic_cli(tmp_path):
    package = CandidateCharacterPackage(
        package_id="pkg-test", subject_id="kira", package_version=0,
        source_snapshot_id="snap", role_result_refs=(), claims=(), contradictions=(),
        unknowns=(), psychology_candidate={}, voice_candidate={}, validation_results={},
        audit_result=None, provenance_manifest={},
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        status=PackageStatus.DRAFT,
    )
    acc_root = tmp_path / "accepted"
    write_acceptance_record(AcceptanceRecord(
        acceptance_id="acc", package_id="pkg-test", package_version=0, subject_id="kira",
        package_hash=compute_package_hash(package), audit_id=None,
        decision=PackageStatus.HUMAN_APPROVED, decided_by="owner",
        decided_at="2026-08-29T00:00:00+00:00", reason=None,
    ), acc_root)
    cli = KiraChatCLI(
        acceptance_root=acc_root, source_loader=lambda sid: package,
        memory_root=tmp_path / "memory", provider=lambda m: "x", subject_id="kira",
    )
    cli.start()
    return cli


class TestSceneObject:
    def test_scene_has_exactly_six_content_fields(self):
        scene = new_scene(**_SCENE_PAYLOAD)
        keys = set(vars(scene).keys())
        assert keys == {
            "scene_id", "title", "location", "participants",
            "prior_events", "current_situation", "created_at",
        }

    def test_render_block_is_pure_projection(self):
        scene = new_scene(**_SCENE_PAYLOAD)
        block = render_scene_block(scene)
        assert block.startswith("СЦЕНА\n")
        assert "Сергей подходит к Кире" in block
        for injected in ("чувствует", "хочет", "решает", "Kira feels", "attraction"):
            assert injected not in block


class TestSceneLifecycle:
    def test_2_3_4_create_read_clear(self, tmp_path):
        app = _make_app(tmp_path)
        assert app.get_scene()["active"] is False
        res = app.set_scene(_SCENE_PAYLOAD)
        assert res["ok"] is True
        got = app.get_scene()
        assert got["active"] is True
        assert got["scene"]["title"] == "Тест вечеринки"
        assert got["scene"]["participants"] == ["Андрей", "Кира", "Сергей"]
        app.clear_scene()
        assert app.get_scene()["active"] is False

    def test_5_scene_scoped_to_session_and_workspace(self, tmp_path):
        app = _make_app(tmp_path)
        app.set_scene(_SCENE_PAYLOAD)
        assert app.get_scene()["active"] is True
        app.new_session()
        assert app.get_scene()["active"] is False  # new session -> empty scene
        app.new_clean_test()
        assert app.get_scene()["active"] is False  # new workspace -> empty scene

    def test_5b_scene_restored_on_session_reselect(self, tmp_path):
        app = _make_app(tmp_path)
        first_session = app.loaded_state()["session_id"]
        app.set_scene(_SCENE_PAYLOAD)
        app.new_session()
        assert app.get_scene()["active"] is False
        app.select_session(first_session)
        assert app.get_scene()["active"] is True

    def test_11_new_clean_test_starts_without_previous_scene(self, tmp_path):
        app = _make_app(tmp_path)
        app.set_scene(_SCENE_PAYLOAD)
        app.new_clean_test()
        assert app.get_scene()["scene"] is None


class TestSceneSafetyAndDelivery:
    def test_6_and_7_no_package_change_no_auto_memory(self, tmp_path):
        app = _make_app(tmp_path)
        before = app.loaded_state()["runtime_loaded_package_hash"]
        app.set_scene(_SCENE_PAYLOAD)
        assert app.loaded_state()["runtime_loaded_package_hash"] == before
        # setting a scene creates no runtime-memory rows
        assert app.memory()["event_count"] == 0

    def test_8_9_10_scene_selected_delivered_and_captured_in_turn(self, tmp_path):
        app = _make_app(tmp_path)
        app.set_scene(_SCENE_PAYLOAD)
        r = app.chat("Что мне делать?")
        assert r["scene_present"] is True
        detail = app.turn_detail(r["turn_id"])
        # selected: manifest carries a system.scene segment
        scene_items = [i for i in detail["manifest"]["items"] if i["kind"] == "system.scene"]
        assert len(scene_items) == 1
        # delivered: mechanically verified against the captured request bytes
        assert scene_items[0]["delivered"] is True
        assert "Сергей подходит к Кире" in detail["request"]["raw"]
        # turn artifact records scene identity + hash + content
        assert detail["scene"]["present"] is True
        assert detail["scene"]["scene_id"] == app.get_scene()["scene"]["scene_id"]
        assert detail["scene"]["scene_hash"] == scene_hash(new_scene(
            scene_id=app.get_scene()["scene"]["scene_id"],
            created_at=app.get_scene()["scene"]["created_at"],
            **_SCENE_PAYLOAD,
        ))
        # variant identity unchanged
        assert detail["variant_id"] == "KIRA_BETA_V1_CURRENT"


class TestBetaV1SceneFreeze:
    def test_1_no_scene_is_byte_identical_to_historical_cli(self, tmp_path):
        cli = _hermetic_cli(tmp_path)
        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        expected_system = cli._build_system_prompt()
        no_scene = policy.assemble_context(
            runtime_context=ctx, session_id=cli.session.session_id,
            history=[], user_message="Привет.",
        )
        assert no_scene.messages[0]["content"] == expected_system
        assert len(no_scene.messages) == 2  # system + user, exactly as historical
        assert all(m["role"] != "system" or i == 0 for i, m in enumerate(no_scene.messages))

    def test_scene_adds_separate_system_block_only(self, tmp_path):
        cli = _hermetic_cli(tmp_path)
        policy = BetaV1CurrentPolicy()
        ctx = cli.session.build_runtime_context()
        expected_system = cli._build_system_prompt()
        scene = new_scene(**_SCENE_PAYLOAD)
        with_scene = policy.assemble_context(
            runtime_context=ctx, session_id=cli.session.session_id,
            history=[], user_message="Привет.", scene=scene,
        )
        # historical system message is unchanged; the scene is an ADDITIONAL
        # separate system message, not a rewrite.
        assert with_scene.messages[0]["content"] == expected_system
        assert with_scene.messages[1] == {"role": "system", "content": render_scene_block(scene)}
        assert with_scene.messages[-1] == {"role": "user", "content": "Привет."}
