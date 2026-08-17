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