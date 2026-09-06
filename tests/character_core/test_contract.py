#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Core contract tests -- transport-neutral, stdlib-only shape."""

from __future__ import annotations

import inspect

from services.character_core.contract import (
    CharacterDebugService,
    CharacterService,
    KNOWN_CAPABILITIES,
    SessionPurpose,
    SessionPurposeNotImplementedError,
)
import services.character_core.contract as contract_module


class TestSessionPurpose:
    def test_defines_exactly_the_four_recognized_purposes(self):
        assert {p.name for p in SessionPurpose} == {
            "TESTING", "AUTHORING", "GAME_RUNTIME", "COMPANION",
        }

    def test_values_are_stable_strings(self):
        assert SessionPurpose.TESTING.value == "TESTING"
        assert SessionPurpose.AUTHORING.value == "AUTHORING"
        assert SessionPurpose.GAME_RUNTIME.value == "GAME_RUNTIME"
        assert SessionPurpose.COMPANION.value == "COMPANION"

    def test_not_implemented_error_carries_the_purpose(self):
        exc = SessionPurposeNotImplementedError(SessionPurpose.COMPANION)
        assert exc.purpose is SessionPurpose.COMPANION
        assert "COMPANION" in str(exc)
        assert isinstance(exc, NotImplementedError)


class TestContractIsTransportNeutral:
    def test_no_http_specific_concepts_anywhere_in_the_module(self):
        source = inspect.getsource(contract_module)
        low = source.lower()
        for forbidden in (
            "http://", "https://", "get /", "post /", "put /", "delete /",
            "status_code", "flask", "fastapi", "urllib", "requests.",
            "content-type", "endpoint", "route(",
        ):
            assert forbidden not in low, forbidden

    def test_contract_module_does_not_import_character_lab_or_runtime(self):
        import ast

        tree = ast.parse(inspect.getsource(contract_module))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for mod in imported:
            assert not mod.startswith("services.character_lab"), mod
            assert not mod.startswith("services.character_runtime"), mod
            assert mod != "sqlite3"

    def test_character_service_and_debug_service_are_distinct_protocols(self):
        assert CharacterService is not CharacterDebugService
        service_methods = {
            n for n in dir(CharacterService) if not n.startswith("_")
        }
        debug_methods = {
            n for n in dir(CharacterDebugService) if not n.startswith("_")
        }
        # a chat-facing consumer never needs debug-only operations
        assert "get_turn_debug" not in service_methods
        assert "get_context_manifest" not in service_methods
        assert "send_message" not in debug_methods
        assert "create_session" not in debug_methods

    def test_character_service_covers_the_minimum_v1_surface(self):
        required = {
            "list_characters", "get_character", "list_variants",
            "create_session", "get_session", "send_message",
            "get_memory", "get_runtime_state",
            "set_runtime_state", "adjust_runtime_state", "remove_runtime_state",
            "get_scene", "set_scene", "clear_scene",
        }
        present = {n for n in dir(CharacterService) if not n.startswith("_")}
        assert required <= present

    def test_debug_service_covers_the_minimum_v1_surface(self):
        required = {"list_turns", "get_turn_debug", "get_request_capture", "get_context_manifest"}
        present = {n for n in dir(CharacterDebugService) if not n.startswith("_")}
        assert required <= present


class TestKnownCapabilities:
    def test_known_capabilities_are_backend_agnostic_names(self):
        assert set(KNOWN_CAPABILITIES) >= {
            "chat", "memory", "runtime_state", "relationship_state",
            "psychology_state", "scene", "turn_debugger",
        }
        for name in KNOWN_CAPABILITIES:
            assert isinstance(name, str) and name


class TestConsolidatedMemoryContractSurface:
    """The V1 operator-driven Consolidated Memory surface on CharacterService."""

    def test_character_service_covers_consolidated_memory_v1(self):
        from services.character_core.contract import CharacterService

        required = {
            "list_memory_events", "list_memory_promotion_candidates",
            "propose_memory_promotion", "decide_memory_promotion",
            "list_consolidated_memory", "create_consolidated_memory_relation",
        }
        present = {n for n in dir(CharacterService) if not n.startswith("_")}
        assert required <= present

    def test_vocabulary_values_are_stable_strings(self):
        from services.character_core.contract import (
            CONSOLIDATED_RELATION_KINDS,
            EPISTEMIC_USER_REPORT,
            MEMORY_KINDS,
            PROMOTION_DECISIONS,
        )

        assert MEMORY_KINDS == ("EPISODIC", "SEMANTIC")
        assert PROMOTION_DECISIONS == ("APPROVE", "REJECT")
        assert CONSOLIDATED_RELATION_KINDS == ("SUPERSEDES", "CONFLICTS_WITH")
        assert EPISTEMIC_USER_REPORT == "USER_REPORT"
