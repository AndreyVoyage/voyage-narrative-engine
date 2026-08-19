#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP S2A -- permission model tests."""

from __future__ import annotations

from services.crp_authoring import (
    ClaimType,
    PERMISSIONS_BY_ROLE,
    Permission,
    SourceType,
)
from services.crp_authoring.permissions import permission_violations

from tests.crp_authoring.conftest import make_claim


class TestPermissions:
    def test_r1_may_not_emit_psychology(self) -> None:
        # A psychology-targeted claim needs EMIT_CLAIMS_PSYCHOLOGY; R1 lacks it.
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P2")
        violations = permission_violations((claim,), PERMISSIONS_BY_ROLE["R1"])
        assert violations

    def test_r2_can_emit_psychology(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P2")
        assert permission_violations((claim,), PERMISSIONS_BY_ROLE["R2"]) == ()

    def test_r4_can_emit_voice(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.OBSERVATION,
                           source_type_summary=(SourceType.OBSERVATION,),
                           target_module_or_layer="voice.lexicon")
        assert permission_violations((claim,), PERMISSIONS_BY_ROLE["R4"]) == ()

    def test_unknown_claim_requires_emit_unknown(self) -> None:
        # R1 has EMIT_CLAIMS_UNKNOWN; R2 does not.
        unknown = make_claim(claim_id="c1", claim_type=ClaimType.UNKNOWN,
                             source_type_summary=(SourceType.MODEL_INFERENCE,),
                             target_module_or_layer="psychology.P0")
        assert permission_violations((unknown,), PERMISSIONS_BY_ROLE["R1"]) == ()
        assert permission_violations((unknown,), PERMISSIONS_BY_ROLE["R2"])


class TestPermissionVocabulary:
    def test_closed_least_privilege_vocabulary(self) -> None:
        # No broad todo-permissions exist in the closed set.
        broad = ["read_everything", "write_persona", "write_canon",
                 "access_pac", "access_sandbox"]
        known = {p.value for p in Permission}
        assert not any(name in known for name in broad)


class TestIntimacyPermission:
    def test_emit_claims_intimacy_exists(self) -> None:
        assert Permission.EMIT_CLAIMS_INTIMACY.value == "EMIT_CLAIMS_INTIMACY"

    def test_r3_may_emit_intimacy(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.OBSERVATION,
                           source_type_summary=(SourceType.OBSERVATION,),
                           target_module_or_layer="intimacy.boundaries")
        assert permission_violations((claim,), PERMISSIONS_BY_ROLE["R3"]) == ()

    def test_r2_cannot_emit_intimacy(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.OBSERVATION,
                           source_type_summary=(SourceType.OBSERVATION,),
                           target_module_or_layer="intimacy.boundaries")
        assert permission_violations((claim,), PERMISSIONS_BY_ROLE["R2"])

    def test_r3_cannot_emit_psychology(self) -> None:
        claim = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                           source_type_summary=(SourceType.OWNER_DIRECT,),
                           target_module_or_layer="psychology.P3")
        assert permission_violations((claim,), PERMISSIONS_BY_ROLE["R3"])


class TestBroadCorePermissions:
    """Slice 2: five new emit verbs + family mapping (no real-role grants)."""

    def test_five_new_permission_verbs_exist(self) -> None:
        assert Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY.value == "EMIT_CLAIMS_IDENTITY_BIOGRAPHY"
        assert Permission.EMIT_CLAIMS_BEHAVIOR.value == "EMIT_CLAIMS_BEHAVIOR"
        assert Permission.EMIT_CLAIMS_RELATIONSHIPS.value == "EMIT_CLAIMS_RELATIONSHIPS"
        assert Permission.EMIT_CLAIMS_BOUNDARIES.value == "EMIT_CLAIMS_BOUNDARIES"
        assert Permission.EMIT_CLAIMS_SEED_MEMORY.value == "EMIT_CLAIMS_SEED_MEMORY"

    def _allowed(self, *permissions):
        return frozenset(permissions)

    def test_identity_biography_requires_matching_verb(self) -> None:
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="identity_biography.name")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY)) == ()
        assert permission_violations((c,), self._allowed())

    def test_behavior_requires_matching_verb(self) -> None:
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="behavior.social")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_BEHAVIOR)) == ()
        assert permission_violations((c,), self._allowed())

    def test_relationships_requires_matching_verb(self) -> None:
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="relationships.counterpart")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_RELATIONSHIPS)) == ()
        assert permission_violations((c,), self._allowed())

    def test_boundaries_requires_matching_verb(self) -> None:
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="boundaries.general")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_BOUNDARIES)) == ()
        assert permission_violations((c,), self._allowed())

    def test_seed_memory_requires_matching_verb(self) -> None:
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="seed_memory.event1")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_SEED_MEMORY)) == ()
        assert permission_violations((c,), self._allowed())

    def test_cross_family_no_authorization(self) -> None:
        # EMIT_CLAIMS_BEHAVIOR must not authorize relationships.*.
        c = make_claim(claim_id="c1", claim_type=ClaimType.FACT,
                       source_type_summary=(SourceType.OWNER_DIRECT,),
                       target_module_or_layer="relationships.counterpart")
        assert permission_violations(
            (c,), self._allowed(Permission.EMIT_CLAIMS_BEHAVIOR))

    def test_no_real_role_gained_broad_core_grants(self) -> None:
        # Slice 2 must not grant the new verbs to real roles.
        for role in ("R1", "R2", "R3", "R4"):
            perms = PERMISSIONS_BY_ROLE[role]
            assert Permission.EMIT_CLAIMS_IDENTITY_BIOGRAPHY not in perms
            assert Permission.EMIT_CLAIMS_BEHAVIOR not in perms
            assert Permission.EMIT_CLAIMS_RELATIONSHIPS not in perms
            assert Permission.EMIT_CLAIMS_BOUNDARIES not in perms
            assert Permission.EMIT_CLAIMS_SEED_MEMORY not in perms
