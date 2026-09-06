#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Character Lab adapter -- first proof the Character Core contract
works with the existing implementation (offline, fake provider only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_core import (
    CharacterDebugService,
    CharacterService,
    SessionPurpose,
    SessionPurposeNotImplementedError,
)
from services.character_lab.app import CharacterLabApp
from services.character_lab.service_adapter import (
    CharacterLabDebugAdapter,
    CharacterLabServiceAdapter,
    MemoryOperationError,
    RuntimeStateMutationError,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"


def _fake_provider_factory(response="[KIRA] тест"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps({"model": "fake", "messages": messages}, ensure_ascii=False).encode("utf-8")
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}, "body": body})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake", "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def _make_app(tmp_path, availability="CONFIGURED"):
    return CharacterLabApp(
        acceptance_root=_REPO_ROOT / "accepted",
        data_root=tmp_path / "data",
        provider_factory=_fake_provider_factory() if availability == "CONFIGURED" else None,
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        provider_availability=availability,
    )


def _adapter(tmp_path, **kw):
    app = _make_app(tmp_path, **kw)
    return CharacterLabServiceAdapter(app), CharacterLabDebugAdapter(app), app


def _testing_session(svc, variant_id="KIRA_BETA_V1_CURRENT", workspace_id=None):
    """Convenience: create_test_workspace() -> workspace_id -> create_session(...)."""
    ws = svc.get_workspace(workspace_id) if workspace_id else svc.create_test_workspace()
    session = svc.create_session("kira", variant_id, SessionPurpose.TESTING, ws.workspace_id)
    return session, ws


class TestProtocolConformance:
    def test_service_adapter_satisfies_character_service_protocol(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        assert isinstance(svc, CharacterService)

    def test_debug_adapter_satisfies_debug_service_protocol(self, tmp_path):
        _, dbg, _ = _adapter(tmp_path)
        assert isinstance(dbg, CharacterDebugService)

    def test_service_adapter_is_not_a_debug_service(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        assert not isinstance(svc, CharacterDebugService)


class TestCatalog:
    def test_list_characters_exposes_kira(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        chars = svc.list_characters()
        assert any(c.character_id == "kira" and c.supported for c in chars)

    def test_kira_package_ref_keeps_real_identity(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        kira = svc.get_character("kira")
        ref = kira.package_ref
        assert ref.acceptance_decision == "HUMAN_APPROVED"
        assert ref.candidate_status == "DRAFT"
        assert ref.source_hash == EXPECTED_HASH
        assert ref.character_id == "kira"

    def test_unknown_character_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.get_character("nika")

    def test_variants_expose_beta_and_grounded(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        variants = {v.variant_id: v for v in svc.list_variants("kira")}
        assert variants["KIRA_BETA_V1_CURRENT"].implemented is True
        assert variants["KIRA_GROUNDED_V2"].implemented is True

    def test_experimental_remains_unavailable(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        variants = {v.variant_id: v for v in svc.list_variants("kira")}
        assert variants["EXPERIMENTAL"].implemented is False

    def test_capabilities_reflect_provider_configured(self, tmp_path):
        svc, _, _ = _adapter(tmp_path, availability="CONFIGURED")
        caps = svc.capabilities("kira")
        assert caps.has("chat") and caps.has("provider_configured")

    def test_capabilities_without_provider(self, tmp_path):
        svc, _, _ = _adapter(tmp_path, availability="NOT CONFIGURED")
        caps = svc.capabilities("kira")
        assert caps.has("chat")            # capability exists conceptually
        assert not caps.has("provider_configured")


class TestWorkspaces:
    def test_list_workspaces_exposes_existing_summaries(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        workspaces = svc.list_workspaces()
        # the CLEAN_TEST workspace CharacterLabApp auto-opens on launch
        assert any(w.workspace_kind == "CLEAN_TEST" and w.selected for w in workspaces)
        assert {w.workspace_id for w in workspaces} == {
            w["workspace_id"] for w in app.list_workspaces()["workspaces"]
        }

    def test_create_test_workspace_creates_isolated_clean_test(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        before_ids = {w.workspace_id for w in svc.list_workspaces()}
        ws = svc.create_test_workspace()
        assert ws.workspace_kind == "CLEAN_TEST"
        assert ws.workspace_id not in before_ids
        after_ids = {w.workspace_id for w in svc.list_workspaces()}
        assert ws.workspace_id in after_ids

    def test_get_workspace_resolves_it(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        resolved = svc.get_workspace(ws.workspace_id)
        assert resolved.workspace_id == ws.workspace_id
        assert resolved.workspace_kind == "CLEAN_TEST"

    def test_get_workspace_unknown_id_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.get_workspace("test-doesnotexist000000000000")

    def test_normal_is_addressable_separately(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        workspaces = {w.workspace_id: w for w in svc.list_workspaces()}
        assert "normal" in workspaces
        assert workspaces["normal"].workspace_kind == "NORMAL"
        # not auto-selected -- the auto-opened default is CLEAN_TEST
        assert workspaces["normal"].selected is False
        resolved = svc.get_workspace("normal")
        assert resolved.workspace_kind == "NORMAL"

    def test_workspace_paths_not_exposed(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        for field_name in ("workspace_id", "workspace_kind", "display_name"):
            value = getattr(ws, field_name)
            assert "\\" not in value and "/" not in value
            assert "sqlite3" not in value.lower()
        assert not hasattr(ws, "root") and not hasattr(ws, "path")


class TestSessionPurposeBoundary:
    def test_testing_session_creation_works(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        session, ws = _testing_session(svc, "KIRA_BETA_V1_CURRENT")
        assert session.character_id == "kira"
        assert session.variant_id == "KIRA_BETA_V1_CURRENT"
        assert session.purpose is SessionPurpose.TESTING
        assert session.workspace.workspace_id == ws.workspace_id
        assert session.workspace.workspace_kind == "CLEAN_TEST"

    def test_create_session_requires_an_existing_workspace_id(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING,
                               "test-doesnotexist000000000000")

    def test_create_session_never_silently_creates_a_workspace(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        before = {w.workspace_id for w in svc.list_workspaces()}
        with pytest.raises(KeyError):
            svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, "bogus")
        after = {w.workspace_id for w in svc.list_workspaces()}
        assert before == after  # no new workspace materialized on failure

        ws = svc.create_test_workspace()
        before2 = {w.workspace_id for w in svc.list_workspaces()}
        svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        after2 = {w.workspace_id for w in svc.list_workspaces()}
        assert before2 == after2  # a successful create_session adds no workspace either

    @pytest.mark.parametrize("purpose", [
        SessionPurpose.AUTHORING, SessionPurpose.GAME_RUNTIME, SessionPurpose.COMPANION,
    ])
    def test_unsupported_purposes_raise_explicitly(self, tmp_path, purpose):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        with pytest.raises(SessionPurposeNotImplementedError) as exc_info:
            svc.create_session("kira", "KIRA_BETA_V1_CURRENT", purpose, ws.workspace_id)
        assert exc_info.value.purpose is purpose

    def test_unsupported_purpose_never_silently_maps_to_testing(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        before = svc.list_characters()
        with pytest.raises(SessionPurposeNotImplementedError):
            svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.AUTHORING, ws.workspace_id)
        after = svc.list_characters()
        assert before == after  # no observable state change


class TestChatThroughExistingRuntime:
    def test_send_message_uses_existing_runtime_path(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        session, _ = _testing_session(svc, "KIRA_GROUNDED_V2")
        turn = svc.send_message(session.session_id, "Привет.")
        assert turn.response == "[KIRA] тест"
        assert turn.turn_id
        # proves it went through RuntimeService/TurnCapture, not a shortcut
        detail = app.turn_detail(turn.turn_id)
        assert detail["request"]["request_hash"] == turn.request_hash

    def test_turn_preserves_variant_and_session_identity(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        session, _ = _testing_session(svc, "KIRA_BETA_V1_CURRENT")
        turn = svc.send_message(session.session_id, "Привет.")
        assert turn.session_id == session.session_id
        assert turn.variant_id == "KIRA_BETA_V1_CURRENT"
        assert turn.character_id == "kira"

    def test_chat_unavailable_without_provider_raises(self, tmp_path):
        svc, _, _ = _adapter(tmp_path, availability="NOT CONFIGURED")
        session, _ = _testing_session(svc, "KIRA_BETA_V1_CURRENT")
        with pytest.raises(RuntimeError):
            svc.send_message(session.session_id, "Привет.")


class TestSameWorkspaceMultipleSessions:
    def test_two_sessions_created_in_the_same_workspace(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        s1 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        s2 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        assert s1.session_id != s2.session_id
        assert s1.workspace.workspace_id == ws.workspace_id
        assert s2.workspace.workspace_id == ws.workspace_id

    def test_cross_session_memory_visible_by_workspace(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        s1 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        svc.send_message(s1.session_id, "Я живу в Праге.")

        s2 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        turn2 = svc.send_message(s2.session_id, "Где я живу?")

        # memory is workspace-scoped: session 2's request carries session 1's
        # message as prior-session memory (existing Beta v1 semantics), and
        # get_memory(workspace_id) shows events from BOTH sessions.
        mem = svc.get_memory(ws.workspace_id)
        assert mem.event_count == 4
        assert {e.session_id for e in mem.events} == {s1.session_id, s2.session_id}
        assert any("Праге" in e.meaning for e in mem.events)
        assert turn2.session_id == s2.session_id

    def test_runtime_state_shared_by_workspace_across_sessions(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        s1 = svc.create_session("kira", "KIRA_GROUNDED_V2", SessionPurpose.TESTING, ws.workspace_id)
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "20"})

        s2 = svc.create_session("kira", "KIRA_GROUNDED_V2", SessionPurpose.TESTING, ws.workspace_id)
        state = svc.get_runtime_state(ws.workspace_id)
        assert state.current_count == 1
        assert state.current[0].value_int == 20
        # readable regardless of which session in the workspace was last active
        svc.get_session(s1.session_id)
        state_again = svc.get_runtime_state(ws.workspace_id)
        assert state_again.current_count == 1


class TestSeparateWorkspaceIsolation:
    def test_a_different_clean_test_stays_isolated(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws1 = svc.create_test_workspace()
        s1 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws1.workspace_id)
        svc.send_message(s1.session_id, "Секрет только для ws1.")

        ws2 = svc.create_test_workspace()
        assert ws2.workspace_id != ws1.workspace_id
        s2 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws2.workspace_id)
        svc.send_message(s2.session_id, "Другое сообщение в ws2.")

        mem1 = svc.get_memory(ws1.workspace_id)
        mem2 = svc.get_memory(ws2.workspace_id)
        assert not any("ws2" in e.meaning for e in mem1.events)
        assert not any("ws1" in e.meaning for e in mem2.events)
        assert mem1.workspace_id == ws1.workspace_id
        assert mem2.workspace_id == ws2.workspace_id

    def test_runtime_state_isolated_across_workspaces(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        ws1 = svc.create_test_workspace()
        svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws1.workspace_id)
        app.runtime_state_set({"key": "living.city", "value": "Prague"})

        ws2 = svc.create_test_workspace()
        svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws2.workspace_id)
        state2 = svc.get_runtime_state(ws2.workspace_id)
        assert state2.current_count == 0

        state1 = svc.get_runtime_state(ws1.workspace_id)
        assert state1.current_count == 1


class TestMemoryStateScene:
    def test_memory_readable_through_adapter(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        session, ws = _testing_session(svc, "KIRA_BETA_V1_CURRENT")
        svc.send_message(session.session_id, "Уникальное сообщение.")
        mem = svc.get_memory(ws.workspace_id)
        assert mem.event_count == 2
        assert mem.causal_order == "seq"
        assert {e.event_type for e in mem.events} == {"USER_MESSAGE", "CHARACTER_MESSAGE"}

    def test_get_memory_unknown_workspace_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.get_memory("test-doesnotexist000000000000")

    def test_runtime_state_readable_through_adapter(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        session, ws = _testing_session(svc, "KIRA_GROUNDED_V2")
        app.runtime_state_set({"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "20"})
        state = svc.get_runtime_state(ws.workspace_id)
        assert state.current_count == 1
        assert state.current[0].domain == "RELATIONSHIP"
        assert state.current[0].value_int == 20
        assert set(state.domains_active) == {"FACT", "RELATIONSHIP", "PSYCHOLOGY"}

    def test_scene_set_get_clear_through_adapter(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        session, _ = _testing_session(svc, "KIRA_BETA_V1_CURRENT")
        assert svc.get_scene(session.session_id).active is False
        set_result = svc.set_scene(
            session.session_id, title="Т", location="Л", participants=["А"],
            current_situation="сейчас",
        )
        assert set_result.active is True and set_result.title == "Т"
        got = svc.get_scene(session.session_id)
        assert got.active is True and got.location == "Л"
        cleared = svc.clear_scene(session.session_id)
        assert cleared.active is False

    def test_scene_stays_session_scoped_not_shared_across_sessions(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        s1 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        svc.set_scene(s1.session_id, title="ТолькоS1", location="L", current_situation="now")
        s2 = svc.create_session("kira", "KIRA_BETA_V1_CURRENT", SessionPurpose.TESTING, ws.workspace_id)
        assert svc.get_scene(s2.session_id).active is False
        assert svc.get_scene(s1.session_id).active is True


class TestDebugAdapter:
    def test_debug_turn_lookup_works(self, tmp_path):
        svc, dbg, _ = _adapter(tmp_path)
        session, _ = _testing_session(svc, "KIRA_GROUNDED_V2")
        turn = svc.send_message(session.session_id, "Привет.")

        turns = dbg.list_turns(session.session_id)
        assert any(t.turn_id == turn.turn_id for t in turns)

        bundle = dbg.get_turn_debug(turn.turn_id)
        assert bundle.turn.turn_id == turn.turn_id
        assert bundle.manifest.turn_id == turn.turn_id
        pkg_items = [i for i in bundle.manifest.items if i.kind == "system.package_grounding"]
        assert pkg_items and pkg_items[0].selected and pkg_items[0].delivered

        manifest_only = dbg.get_context_manifest(turn.turn_id)
        assert manifest_only == bundle.manifest

        request_only = dbg.get_request_capture(turn.turn_id)
        assert request_only.request_hash == turn.request_hash
        assert request_only.raw_request_json  # exact captured bytes, not chain-of-thought


class TestPackageUnchanged:
    def test_accepted_package_untouched_by_adapter_use(self, tmp_path):
        from services.crp_authoring import compute_package_hash
        from services.character_lab.source_loader import build_repo_source_loader
        from services.character_runtime import load_accepted_character

        svc, _, _ = _adapter(tmp_path)
        session, _ = _testing_session(svc, "KIRA_GROUNDED_V2")
        svc.send_message(session.session_id, "Привет.")

        loader = build_repo_source_loader(acceptance_root=_REPO_ROOT / "accepted")
        acc = load_accepted_character(
            "kira", acceptance_root=_REPO_ROOT / "accepted", source_loader=loader
        )
        assert compute_package_hash(acc.package) == EXPECTED_HASH


class TestRuntimeStateMutation:
    def test_set_fact_through_adapter(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        entry = svc.set_runtime_state(ws.workspace_id, "FACT", "current.test_status", "react-state-smoke")
        assert entry.domain == "FACT"
        assert entry.key == "current.test_status"
        assert entry.value == "react-state-smoke"
        assert entry.value_int is None

    def test_relationship_set_adjust_remove(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        svc.set_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust", "30")
        adjusted = svc.adjust_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust", 10)
        assert adjusted.value_int == 40
        svc.remove_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust")
        state = svc.get_runtime_state(ws.workspace_id)
        assert all(not (e.domain == "RELATIONSHIP" and e.key == "andrey.trust") for e in state.current)

    def test_psychology_set_adjust_remove(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        svc.set_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", "40")
        adjusted = svc.adjust_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", -15)
        assert adjusted.value_int == 25

    def test_out_of_range_adjust_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        svc.set_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", "90")
        with pytest.raises(RuntimeStateMutationError):
            svc.adjust_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", 20)

    def test_adjust_after_remove_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        svc.set_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust", "30")
        svc.remove_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust")
        with pytest.raises(RuntimeStateMutationError):
            svc.adjust_runtime_state(ws.workspace_id, "RELATIONSHIP", "andrey.trust", 1)

    def test_append_only_semantics_preserved(self, tmp_path):
        svc, _, app = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        svc.set_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", "40")
        svc.set_runtime_state(ws.workspace_id, "PSYCHOLOGY", "stress", "55")
        app.select_workspace(ws.workspace_id)
        data = app.runtime_state()
        stress = [h for h in data["history"] if h["domain"] == "PSYCHOLOGY" and h["key"] == "stress"]
        assert [h["action"] for h in stress] == ["SET", "SET"]
        assert [h["value"] for h in stress] == ["40", "55"]

    def test_source_kind_is_operator_confirmed_and_source_ref_is_annotation(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        ws = svc.create_test_workspace()
        entry = svc.set_runtime_state(ws.workspace_id, "FACT", "k", "v", source_ref="react-character-lab")
        assert entry.source_kind == "OPERATOR_CONFIRMED"
        assert entry.source_ref == "react-character-lab"

    def test_unknown_workspace_rejects_explicitly(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.set_runtime_state("test-0000000000000000", "FACT", "k", "v")


class TestConsolidatedMemory:
    """Operator-driven Consolidated Memory through the contract adapter.

    Offline, fake provider only. The backend (ConsolidatedMemoryBackend) stays
    authoritative; the adapter only translates.
    """

    def _seed_user_event(self, svc, text="Я люблю зелёный чай.", workspace_id=None):
        session, ws = _testing_session(svc, workspace_id=workspace_id)
        svc.send_message(session.session_id, text)
        return ws.workspace_id

    def _events(self, svc, workspace_id):
        return svc.list_memory_events(workspace_id).events

    def _eligible(self, svc, workspace_id):
        return next(e for e in self._events(svc, workspace_id) if e.eligible_for_promotion)

    def test_list_memory_events_workspace_scoped_with_eligibility(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        events = self._events(svc, wid)
        user_event = next(e for e in events if e.event_type == "USER_MESSAGE")
        char_event = next(e for e in events if e.event_type == "CHARACTER_MESSAGE")
        assert user_event.eligible_for_promotion is True
        assert user_event.ineligibility_reason is None
        assert char_event.eligible_for_promotion is False
        assert char_event.ineligibility_reason == "not_a_user_message"

    def test_eligible_user_stated_event_becomes_pending_candidate(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        event = self._eligible(svc, wid)
        candidate = svc.propose_memory_promotion(wid, event.event_id, "SEMANTIC")
        assert candidate.decision_status == "PENDING"
        assert candidate.source_event_id == event.event_id
        assert candidate.memory_kind == "SEMANTIC"
        assert candidate.epistemic_kind == "USER_REPORT"
        listed = svc.list_memory_promotion_candidates(wid)
        assert [c.candidate_id for c in listed] == [candidate.candidate_id]

    def test_character_utterance_promotion_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        char_event = next(
            e for e in self._events(svc, wid) if e.event_type == "CHARACTER_MESSAGE"
        )
        with pytest.raises(MemoryOperationError) as exc:
            svc.propose_memory_promotion(wid, char_event.event_id, "SEMANTIC")
        assert exc.value.code == "ineligible_event"

    def test_missing_event_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        with pytest.raises(MemoryOperationError) as exc:
            svc.propose_memory_promotion(wid, "evt-nope", "SEMANTIC")
        assert exc.value.code == "unknown_event"

    def test_approve_creates_active_user_report_record(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        event = self._eligible(svc, wid)
        candidate = svc.propose_memory_promotion(wid, event.event_id, "EPISODIC")
        decided = svc.decide_memory_promotion(wid, candidate.candidate_id, "APPROVE")
        assert decided.decision_status == "APPROVED"
        records = svc.list_consolidated_memory(wid)
        assert len(records) == 1
        rec = records[0]
        assert rec.status == "ACTIVE"
        assert rec.epistemic_kind == "USER_REPORT"
        assert rec.meaning == event.meaning
        assert rec.basis_event_ids == (event.event_id,)

    def test_reject_creates_no_record(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        event = self._eligible(svc, wid)
        candidate = svc.propose_memory_promotion(wid, event.event_id, "SEMANTIC")
        decided = svc.decide_memory_promotion(wid, candidate.candidate_id, "REJECT")
        assert decided.decision_status == "REJECTED"
        assert svc.list_consolidated_memory(wid) == ()

    def test_second_decision_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        event = self._eligible(svc, wid)
        candidate = svc.propose_memory_promotion(wid, event.event_id, "SEMANTIC")
        svc.decide_memory_promotion(wid, candidate.candidate_id, "REJECT")
        with pytest.raises(MemoryOperationError) as exc:
            svc.decide_memory_promotion(wid, candidate.candidate_id, "APPROVE")
        assert exc.value.code == "already_decided"

    def test_duplicate_active_record_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid = self._seed_user_event(svc)
        event = self._eligible(svc, wid)
        first = svc.propose_memory_promotion(wid, event.event_id, "SEMANTIC")
        svc.decide_memory_promotion(wid, first.candidate_id, "APPROVE")
        second = svc.propose_memory_promotion(wid, event.event_id, "SEMANTIC")
        with pytest.raises(MemoryOperationError) as exc:
            svc.decide_memory_promotion(wid, second.candidate_id, "APPROVE")
        assert exc.value.code == "duplicate_record"

    def _two_records(self, svc):
        wid = self._seed_user_event(svc, "Я люблю зелёный чай.")
        session, _ = _testing_session(svc, workspace_id=wid)
        svc.send_message(session.session_id, "Я люблю травяной чай.")
        for e in self._events(svc, wid):
            if not e.eligible_for_promotion:
                continue
            cand = svc.propose_memory_promotion(wid, e.event_id, "SEMANTIC")
            svc.decide_memory_promotion(wid, cand.candidate_id, "APPROVE")
        records = svc.list_consolidated_memory(wid)
        assert len(records) == 2
        return wid, records

    def test_standalone_supersedes_marks_target_superseded(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid, records = self._two_records(svc)
        newer, older = records[1], records[0]
        relation = svc.create_consolidated_memory_relation(
            wid, newer.record_id, older.record_id, "SUPERSEDES"
        )
        assert relation.kind == "SUPERSEDES"
        after = {r.record_id: r for r in svc.list_consolidated_memory(wid)}
        assert after[newer.record_id].status == "ACTIVE"
        assert after[older.record_id].status == "SUPERSEDED"
        assert after[older.record_id].superseded_by_record_id == newer.record_id

    def test_standalone_conflicts_with_keeps_both_active(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid, records = self._two_records(svc)
        a, b = records[0], records[1]
        svc.create_consolidated_memory_relation(wid, a.record_id, b.record_id, "CONFLICTS_WITH")
        after = {r.record_id: r for r in svc.list_consolidated_memory(wid)}
        assert after[a.record_id].status == "ACTIVE"
        assert after[b.record_id].status == "ACTIVE"
        assert after[a.record_id].conflict_record_ids == (b.record_id,)
        assert after[b.record_id].conflict_record_ids == (a.record_id,)

    def test_self_relation_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid, records = self._two_records(svc)
        with pytest.raises(MemoryOperationError) as exc:
            svc.create_consolidated_memory_relation(
                wid, records[0].record_id, records[0].record_id, "SUPERSEDES"
            )
        assert exc.value.code == "self_relation"

    def test_cross_workspace_relation_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        _, records_a = self._two_records(svc)
        wid_b = self._seed_user_event(svc, "В другой области.")
        foreign = records_a[0].record_id
        event_b = self._eligible(svc, wid_b)
        cand_b = svc.propose_memory_promotion(wid_b, event_b.event_id, "SEMANTIC")
        svc.decide_memory_promotion(wid_b, cand_b.candidate_id, "APPROVE")
        rec_b = svc.list_consolidated_memory(wid_b)[0]
        with pytest.raises(MemoryOperationError) as exc:
            svc.create_consolidated_memory_relation(
                wid_b, rec_b.record_id, foreign, "SUPERSEDES"
            )
        assert exc.value.code == "unknown_record"

    def test_workspace_isolation_preserved(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        wid_a, _ = self._two_records(svc)
        wid_b = self._seed_user_event(svc, "В другой области.")
        assert len(svc.list_consolidated_memory(wid_a)) == 2
        assert svc.list_consolidated_memory(wid_b) == ()

    def test_unknown_workspace_rejected(self, tmp_path):
        svc, _, _ = _adapter(tmp_path)
        with pytest.raises(KeyError):
            svc.list_memory_events("test-0000000000000000")
