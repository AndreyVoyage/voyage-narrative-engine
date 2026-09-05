#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIRA_GROUNDED_V2 -- focused behavior tests (offline, no provider calls).

Covers only directly-changed behavior: the deterministic Accepted Character
grounding renderer, the GroundedV2Policy assembly/memory contract, the minimal
backend variant registry, and the observability a grounded turn must expose.
Beta v1 byte-behavior compatibility is re-checked here at the policy boundary.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.character_lab import (
    CharacterLabApp,
    GROUNDING_HEADER,
    GroundedV2Policy,
    KIRA_BETA_V1_CURRENT,
    KIRA_GROUNDED_V2,
    BetaV1CurrentPolicy,
    RuntimeService,
    TurnCapture,
    UnknownVariantError,
    build_policy,
    render_accepted_grounding,
    verify_segment_delivered,
)
from services.character_lab.source_loader import build_repo_source_loader
from services.character_runtime import (
    RuntimeEvent,
    RuntimeMemoryBackend,
    load_accepted_character,
)
from services.crp_authoring import compute_package_hash

from tests.fixtures.character_core.synthetic_dimensions import synthetic_dimension_set

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACCEPTED_ROOT = _REPO_ROOT / "accepted"
EXPECTED_HASH = "e26f83dafa26e61af82f29b654b592300c8f3f7bd295d07bd4d2b6527ae3eebd"

# A fact that is NOT anywhere in the accepted KIRA package.
FABRICATED_SENTINEL = "Kira owns a pet iguana named Boris."


# --------------------------------------------------------------------------- helpers

def _accepted():
    loader = build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT)
    return load_accepted_character(
        "kira", acceptance_root=_ACCEPTED_ROOT, source_loader=loader
    )


def _service():
    loader = build_repo_source_loader(acceptance_root=_ACCEPTED_ROOT)
    return RuntimeService(acceptance_root=_ACCEPTED_ROOT, source_loader=loader)


def _recording_provider_factory(response="[KIRA] ответ"):
    def factory(recorder):
        def provider(messages):
            body = json.dumps(
                {"model": "fake", "messages": messages}, ensure_ascii=False
            ).encode("utf-8")
            if recorder:
                recorder({"event": "request",
                          "payload": {"model": "fake", "messages": messages},
                          "body": body})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake", "model": "fake",
                    "choices": [{"message": {"content": response},
                                 "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def _grounded_turn(tmp_path, *, scene=None, turn_id="turn-g1"):
    service = _service()
    cap = TurnCapture(tmp_path / "capture")
    result = service.turn(
        "kira",
        policy=GroundedV2Policy(),
        history=[],
        user_message="Расскажи о себе.",
        provider=None,
        provider_factory=_recording_provider_factory(),
        memory_root=tmp_path / "mem",
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        capture=cap,
        turn_id=turn_id,
        scene=scene,
    )
    return service, cap, result


def _make_app(tmp_path):
    return CharacterLabApp(
        acceptance_root=_ACCEPTED_ROOT,
        data_root=tmp_path / "data",
        provider_factory=_recording_provider_factory(),
        provider_info={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
        provider_availability="CONFIGURED",
    )


def _system_text(messages):
    return "\n".join(m["content"] for m in messages if m["role"] == "system")


# --------------------------------------------------------------------------- renderer

class TestGroundingRenderer:
    def test_deterministic_and_uses_only_distilled_sections(self):
        pkg = _accepted().package
        a = render_accepted_grounding(pkg)
        b = render_accepted_grounding(pkg)
        assert a == b
        assert GROUNDING_HEADER in a
        assert "ACCEPTED CHARACTER GROUNDING" in a
        # No raw JSON dump of the claims collection.
        assert '"claim_id"' not in a and '"source_evidence_ids"' not in a
        assert "role_result_refs" not in a

    def test_measured_length_is_practical(self):
        pkg = _accepted().package
        size = len(render_accepted_grounding(pkg))
        # ~30k chars (~9k tokens): heavy but usable as a grounding segment.
        assert 5_000 < size < 60_000, size

    def test_unknowns_preserved_as_not_established(self):
        block = render_accepted_grounding(_accepted().package)
        assert "НЕИЗВЕСТНО / НЕ УСТАНОВЛЕНО" in block
        assert "Exact birth date for Kira is UNKNOWN." in block
        assert "не выдумыв" in block  # explicit "do not invent" guidance

    def test_contradictions_preserved(self):
        block = render_accepted_grounding(_accepted().package)
        assert "ПРОТИВОРЕЧИЯ / CONTRADICTIONS" in block
        # both poles kept, not resolved away
        assert "voluntary" in block.lower()

    def test_no_fabricated_sentinel_fact(self):
        block = render_accepted_grounding(_accepted().package)
        assert FABRICATED_SENTINEL not in block
        assert "iguana" not in block.lower()

    def test_empty_boilerplate_omitted(self):
        block = render_accepted_grounding(_accepted().package)
        # seed_memory_candidate is empty in the accepted package -> no header.
        assert "[]" not in block
        assert "SEED_MEMORY" not in block.upper()


# --------------------------------------------------------------------------- registry

class TestVariantRegistry:
    def test_grounded_v2_resolves(self):
        policy = build_policy(KIRA_GROUNDED_V2)
        assert isinstance(policy, GroundedV2Policy)
        assert policy.variant_id == KIRA_GROUNDED_V2

    def test_beta_v1_resolves(self):
        assert isinstance(build_policy(KIRA_BETA_V1_CURRENT), BetaV1CurrentPolicy)

    def test_experimental_disabled(self):
        with pytest.raises(UnknownVariantError):
            build_policy("EXPERIMENTAL")

    def test_unknown_variant_rejected(self):
        with pytest.raises(UnknownVariantError):
            build_policy("NOT_A_VARIANT")


# --------------------------------------------------------------------------- beta v1

class TestBetaV1Unchanged:
    def test_beta_v1_ignores_grounded_context_keys(self):
        """Adding accepted_package / causal_memory keys must not move a byte."""
        acc = _accepted()
        base_ctx = {
            "subject_id": "kira",
            "source_candidate_hash": acc.source_candidate_hash,
            "package_id": acc.package.package_id,
            "package_version": acc.package.package_version,
            "package_status": acc.package.status.value,
            "runtime_memory": [],
        }
        augmented = dict(base_ctx)
        augmented["accepted_package"] = acc.package
        augmented["causal_memory"] = [
            {"event_id": "e1", "session_id": "s", "event_type": "USER_MESSAGE",
             "meaning": "x", "created_at": "2026-01-01T00:00:00+00:00",
             "seq": 1, "provenance": "USER_STATED"},
        ]
        policy = BetaV1CurrentPolicy()
        a = policy.assemble_context(runtime_context=base_ctx, session_id="sid",
                                    history=[], user_message="Привет.")
        b = policy.assemble_context(runtime_context=augmented, session_id="sid",
                                    history=[], user_message="Привет.")
        assert list(a.messages) == list(b.messages)
        assert a.manifest == b.manifest

    def test_beta_v1_turn_has_no_grounding_segment(self, tmp_path):
        service = _service()
        result = service.turn(
            "kira", policy=BetaV1CurrentPolicy(), history=[],
            user_message="Привет.", provider=lambda m: "ok",
            memory_root=tmp_path / "mem",
        )
        kinds = {m["role"] for m in result.messages}
        assert kinds == {"system", "user"}
        assert GROUNDING_HEADER not in _system_text(result.messages)


# --------------------------------------------------------------------------- assembly

class TestGroundedV2Assembly:
    def test_segments_in_fixed_order_and_independently_visible(self, tmp_path):
        scene_app = _make_app(tmp_path)
        scene_app.set_scene({
            "title": "Парк", "location": "аллея", "participants": ["Кира"],
            "prior_events": [], "current_situation": "УникальнаяСценаМаркер42.",
        })
        scene = scene_app._active_scene()
        _, cap, result = _grounded_turn(tmp_path, scene=scene)
        manifest = cap.read_manifest("turn-g1")
        kinds = [i["kind"] for i in manifest["items"]]
        assert kinds[0] == "system.role_instruction"
        assert kinds[1] == "system.package_grounding"
        assert "system.scene" in kinds
        # scene stays a separate segment, not folded into grounding
        grounding_item = next(i for i in manifest["items"]
                              if i["kind"] == "system.package_grounding")
        assert "УникальнаяСценаМаркер42" not in grounding_item["text"]
        assert result.variant_id == KIRA_GROUNDED_V2

    def test_scene_remains_separate_segment(self, tmp_path):
        app = _make_app(tmp_path)
        app.select_variant(KIRA_GROUNDED_V2)
        app.set_scene({
            "title": "T", "location": "L", "participants": ["A"],
            "prior_events": [], "current_situation": "СценаОтдельно.",
        })
        r = app.chat("Привет.")
        detail = app.turn_detail(r["turn_id"])
        kinds = [i["kind"] for i in detail["manifest"]["items"]]
        assert "system.scene" in kinds
        assert "system.package_grounding" in kinds
        scene_item = next(i for i in detail["manifest"]["items"]
                          if i["kind"] == "system.scene")
        assert scene_item["delivered"] is True

    def test_grounded_request_contains_accepted_package_grounding(self, tmp_path):
        _, cap, result = _grounded_turn(tmp_path)
        request_text = (cap.turn_dir("turn-g1") / "request.json").read_text("utf-8")
        assert GROUNDING_HEADER in request_text
        # a distinctive accepted claim is actually delivered
        assert "Kira is 26 years old." in request_text

    def test_accepted_hash_stable_through_grounded_turn(self, tmp_path):
        acc = _accepted()
        assert compute_package_hash(acc.package) == EXPECTED_HASH
        _, _, result = _grounded_turn(tmp_path)
        assert result.accepted_source_hash == EXPECTED_HASH
        assert result.package_hash_after == EXPECTED_HASH
        assert result.package_hash_unchanged is True

    def test_unknowns_stay_unknown_in_request(self, tmp_path):
        _, cap, _ = _grounded_turn(tmp_path)
        request_text = (cap.turn_dir("turn-g1") / "request.json").read_text("utf-8")
        assert "НЕ УСТАНОВЛЕНО" in request_text
        assert "Exact birth date for Kira is UNKNOWN." in request_text

    def test_no_fabricated_sentinel_in_request(self, tmp_path):
        _, cap, _ = _grounded_turn(tmp_path)
        request_text = (cap.turn_dir("turn-g1") / "request.json").read_text("utf-8")
        assert FABRICATED_SENTINEL not in request_text


# --------------------------------------------------------------------------- memory

def _seed(memory_root, rows):
    backend = RuntimeMemoryBackend(memory_root, "kira")
    try:
        for eid, sid, etype, meaning, created_at, prov in rows:
            backend.record_event(
                RuntimeEvent(event_id=eid, subject_id="kira", session_id=sid,
                             event_type=etype, meaning=meaning, created_at=created_at),
                provenance=prov,
            )
    finally:
        backend.close()


class TestGroundedV2Memory:
    def _run(self, tmp_path):
        mem_root = tmp_path / "mem"
        # Insertion order (=> seq order) deliberately disagrees with created_at.
        _seed(mem_root, [
            ("evt-u-late", "s-old", "USER_MESSAGE", "USER_FACT_SEQ1",
             "2026-08-20T00:00:00+00:00", "USER_STATED"),
            ("evt-u-early", "s-old", "USER_MESSAGE", "USER_FACT_SEQ2",
             "2026-08-01T00:00:00+00:00", "USER_STATED"),
            ("evt-char", "s-old", "CHARACTER_MESSAGE", "CHAR_UTTERANCE_SECRET",
             "2026-08-02T00:00:00+00:00", "CHARACTER_UTTERANCE"),
            ("evt-legacy", "s-old", "USER_MESSAGE", "LEGACY_UNCLASSIFIED_SECRET",
             "2026-08-03T00:00:00+00:00", None),
        ])
        service = _service()
        cap = TurnCapture(tmp_path / "capture")
        result = service.turn(
            "kira", policy=GroundedV2Policy(), history=[],
            user_message="Привет.", provider=None,
            provider_factory=_recording_provider_factory(),
            memory_root=mem_root, capture=cap, turn_id="turn-mem",
            provider_info={"provider_id": "p", "model": "m"},
        )
        return cap, result

    def test_user_stated_included_as_user_reported(self, tmp_path):
        cap, result = self._run(tmp_path)
        sys_text = _system_text(result.messages)
        assert "ПАМЯТЬ / MEMORY" in sys_text
        assert "со слов собеседника" in sys_text
        assert "USER_FACT_SEQ1" in sys_text and "USER_FACT_SEQ2" in sys_text

    def test_uses_causal_seq_order_not_created_at(self, tmp_path):
        cap, result = self._run(tmp_path)
        sys_text = _system_text(result.messages)
        assert sys_text.index("USER_FACT_SEQ1") < sys_text.index("USER_FACT_SEQ2")
        manifest = cap.read_manifest("turn-mem")
        mem_items = [i for i in manifest["items"] if i["kind"] == "system.memory_line"]
        seqs = [i["meta"]["seq"] for i in mem_items]
        assert seqs == sorted(seqs)
        assert all(i["meta"]["provenance"] == "USER_STATED" for i in mem_items)

    def test_character_utterance_not_canonical_grounding(self, tmp_path):
        cap, result = self._run(tmp_path)
        assert "CHAR_UTTERANCE_SECRET" not in _system_text(result.messages)
        request_text = (cap.turn_dir("turn-mem") / "request.json").read_text("utf-8")
        assert "CHAR_UTTERANCE_SECRET" not in request_text

    def test_legacy_unclassified_not_canonical_grounding(self, tmp_path):
        cap, result = self._run(tmp_path)
        assert "LEGACY_UNCLASSIFIED_SECRET" not in _system_text(result.messages)
        request_text = (cap.turn_dir("turn-mem") / "request.json").read_text("utf-8")
        assert "LEGACY_UNCLASSIFIED_SECRET" not in request_text

    def test_memory_rows_not_mutated(self, tmp_path):
        cap, result = self._run(tmp_path)
        backend = RuntimeMemoryBackend(tmp_path / "mem", "kira")
        try:
            rows = {e.event_id: e for e in backend.load_events_causal("kira")}
        finally:
            backend.close()
        assert rows["evt-char"].provenance == "CHARACTER_UTTERANCE"
        assert rows["evt-legacy"].provenance is None
        assert rows["evt-u-late"].meaning == "USER_FACT_SEQ1"

    def test_memory_segment_omitted_when_no_user_stated(self, tmp_path):
        _, cap, result = _grounded_turn(tmp_path, turn_id="turn-nomem")
        manifest = cap.read_manifest("turn-nomem")
        kinds = [i["kind"] for i in manifest["items"]]
        assert "system.memory_line" not in kinds
        assert "system.memory_grounding" not in kinds


# --------------------------------------------------------------------------- observability

class TestGroundedV2Observability:
    def test_package_segment_selected_and_delivered(self, tmp_path):
        app = _make_app(tmp_path)
        app.select_variant(KIRA_GROUNDED_V2)
        r = app.chat("Привет.")
        detail = app.turn_detail(r["turn_id"])
        items = {i["kind"]: i for i in detail["manifest"]["items"]}
        assert "system.package_grounding" in items
        assert items["system.package_grounding"]["selected"] is True
        assert items["system.package_grounding"]["delivered"] is True

    def test_delivered_proven_from_captured_request(self, tmp_path):
        _, cap, _ = _grounded_turn(tmp_path)
        manifest = cap.read_manifest("turn-g1")
        request_text = (cap.turn_dir("turn-g1") / "request.json").read_text("utf-8")
        grounding_item = next(i for i in manifest["items"]
                              if i["kind"] == "system.package_grounding")
        assert verify_segment_delivered(
            segment_text=grounding_item["text"], request_body_text=request_text
        )

    def test_memory_selected_delivered_when_present(self, tmp_path):
        mem_root = tmp_path / "data"
        app = CharacterLabApp(
            acceptance_root=_ACCEPTED_ROOT, data_root=mem_root,
            provider_factory=_recording_provider_factory(),
            provider_info={"provider_id": "p", "model": "m"},
            provider_availability="CONFIGURED",
        )
        _seed(app._current_workspace().memory_root, [
            ("evt-seed", "s-earlier", "USER_MESSAGE", "SEED_USER_FACT",
             "2026-08-10T00:00:00+00:00", "USER_STATED"),
        ])
        app.select_variant(KIRA_GROUNDED_V2)
        r = app.chat("Привет.")
        detail = app.turn_detail(r["turn_id"])
        mem_items = [i for i in detail["manifest"]["items"]
                     if i["kind"] == "system.memory_line"]
        assert mem_items
        assert all(i["selected"] and i["delivered"] for i in mem_items)


# --------------------------------------------------------------------------- app wiring

class TestGroundedV2AppSelection:
    def test_grounded_v2_selectable_and_affects_future_turns_only(self, tmp_path):
        app = _make_app(tmp_path)
        first = app.chat("Первый ход.")
        assert app.turn_detail(first["turn_id"])["variant_id"] == KIRA_BETA_V1_CURRENT

        sel = app.select_variant(KIRA_GROUNDED_V2)
        assert sel["ok"] is True
        assert app.loaded_state()["variant_id"] == KIRA_GROUNDED_V2

        second = app.chat("Второй ход.")
        second_detail = app.turn_detail(second["turn_id"])
        assert second_detail["variant_id"] == KIRA_GROUNDED_V2
        # historical artifact keeps its recorded variant
        assert app.turn_detail(first["turn_id"])["variant_id"] == KIRA_BETA_V1_CURRENT
        # and the grounded turn actually delivered the package grounding
        assert GROUNDING_HEADER in (second_detail["request"]["raw"] or "")

    def test_catalog_marks_grounded_v2_implemented_and_experimental_disabled(self, tmp_path):
        app = _make_app(tmp_path)
        variants = {v["id"]: v for v in app.catalog()["variants"]}
        assert variants[KIRA_GROUNDED_V2]["implemented"] is True
        assert variants["EXPERIMENTAL"]["implemented"] is False

    def test_experimental_selection_rejected_by_backend(self, tmp_path):
        app = _make_app(tmp_path)
        r = app.select_variant("EXPERIMENTAL")
        assert r["ok"] is False
        assert app.loaded_state()["variant_id"] == KIRA_BETA_V1_CURRENT


# --------------------------------------------------------------- dimension hook

class TestGroundedV2DimensionSemanticsHook:
    """DIMENSION_SEMANTICS_BEHAVIOR_RENDERING_FOUNDATION_V1.

    Smallest Grounded hook: when validated package dimension definitions are
    present in the runtime context, numeric RELATIONSHIP / PSYCHOLOGY lines
    carry value + generic band + package-declared meaning. When absent (the
    situation for the current KIRA package -- nothing populates the key), the
    raw numeric representation is byte-identical to before.
    """

    def _ctx(self, *, with_defs):
        acc = _accepted()
        ctx = {
            "subject_id": "kira",
            "source_candidate_hash": acc.source_candidate_hash,
            "package_id": acc.package.package_id,
            "package_version": acc.package.package_version,
            "package_status": acc.package.status.value,
            "runtime_memory": [],
            "causal_memory": [],
            "accepted_package": acc.package,
            "runtime_state": [
                {"domain": "RELATIONSHIP", "key": "andrey.trust", "value": "72", "seq": 1},
                {"domain": "PSYCHOLOGY", "key": "stress", "value": "72", "seq": 2},
            ],
        }
        if with_defs:
            ctx["dimension_definitions"] = synthetic_dimension_set()
        return ctx

    def test_supplied_definitions_produce_semantic_rendering(self):
        asm = GroundedV2Policy().assemble_context(
            runtime_context=self._ctx(with_defs=True),
            session_id="sid", history=[], user_message="hi",
        )
        sys_text = _system_text(asm.messages)
        assert "andrey.trust: 72 (band: VERY_HIGH)" in sys_text
        assert "strong trust toward this subject" in sys_text
        assert "stress: 72 (band: VERY_HIGH)" in sys_text
        assert "severe current stress" in sys_text

        rel_lines = [i for i in asm.manifest.items
                     if i.kind == "system.relationship_state_line"]
        assert rel_lines and rel_lines[0].meta.get("band") == "VERY_HIGH"
        assert rel_lines[0].meta.get("semantic_meaning") == "strong trust toward this subject"
        rel_block = next(i for i in asm.manifest.items
                         if i.kind == "system.relationship_state")
        assert rel_block.meta.get("semantics") == "PACKAGE_DEFINED"

    def test_absent_definitions_preserve_raw_grounded_behavior(self):
        asm = GroundedV2Policy().assemble_context(
            runtime_context=self._ctx(with_defs=False),
            session_id="sid", history=[], user_message="hi",
        )
        sys_text = _system_text(asm.messages)
        assert "- andrey.trust: 72" in sys_text
        assert "band:" not in sys_text
        assert "VERY_HIGH" not in sys_text
        rel_block = next(i for i in asm.manifest.items
                         if i.kind == "system.relationship_state")
        assert rel_block.meta.get("semantics") == "RAW"

    def test_absent_key_matches_explicit_none(self):
        policy = GroundedV2Policy()
        ctx_no_key = self._ctx(with_defs=False)
        ctx_none = dict(ctx_no_key, dimension_definitions=None)
        a = policy.assemble_context(runtime_context=ctx_no_key, session_id="s",
                                    history=[], user_message="hi")
        b = policy.assemble_context(runtime_context=ctx_none, session_id="s",
                                    history=[], user_message="hi")
        assert list(a.messages) == list(b.messages)

    def test_no_hardcoded_dimension_meaning_in_runtime_policy(self):
        import services.character_lab.runtime_policy as rp
        src = Path(rp.__file__).read_text(encoding="utf-8")
        low = src.lower()
        # Band literals belong only to Core; the policy asks Core for them.
        assert "very_high" not in low and "very_low" not in low
        # No id-driven branching / hard-coded dimension names.
        assert 'dimension_id ==' not in low
        assert '== "trust"' not in low and '== "stress"' not in low
