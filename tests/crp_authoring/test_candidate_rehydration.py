#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict ``CandidateCharacterPackage`` rehydration tests (character-agnostic)."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping as MappingABC
from datetime import datetime
from enum import Enum

import pytest

from services.crp_authoring import (
    CandidateCharacterPackage,
    ClaimType,
    Confidence,
    ContradictionRecord,
    PackageStatus,
    RoleClaim,
    SourceType,
    compute_package_hash,
)
from services.crp_authoring.candidate_rehydration import (
    rehydrate_candidate_package,
    rehydrate_contradiction_record,
    rehydrate_role_claim,
)
from services.crp_authoring.errors import CrpValidationError

from tests.crp_authoring.conftest import (
    make_claim,
    make_contradiction,
    make_package,
    utc_now,
)


# Local mirror of the production ``_to_jsonable`` transport form (stdlib only),
# so these tests exercise rehydration as the exact inverse of the real serializer.
def _to_jsonable(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float")
        return value
    if isinstance(value, (str, int)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, MappingABC):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(v) for v in value]
    raise TypeError(f"cannot serialize {type(value)!r}")


def _rich_package() -> CandidateCharacterPackage:
    fact = make_claim(
        claim_id="claim-001", claim_type=ClaimType.FACT,
        target_module_or_layer="psychology.P0",
    )
    second = make_claim(
        claim_id="claim-002", claim_type=ClaimType.FACT,
        target_module_or_layer="psychology.P1",
    )
    unknown = make_claim(
        claim_id="unknown-001", claim_type=ClaimType.UNKNOWN,
        confidence=Confidence.UNKNOWN,
        target_module_or_layer="identity_biography.birth_date",
    )
    contradiction = make_contradiction(
        contradiction_id="crd-001", claim_ids=("claim-001", "claim-002"),
    )
    return make_package(
        package_id="pkg-rehyd-001",
        subject_id="char-subject-1",
        claims=(fact, second),
        contradictions=(contradiction,),
        unknowns=(unknown,),
        psychology_candidate={"P0": (fact,)},
        provenance_manifest={"psychology.P0": ("claim-001",)},
        created_at=utc_now(),
        status=PackageStatus.DRAFT,
    )


def _serialized_rich() -> dict:
    return _to_jsonable(_rich_package())


class TestRehydration:
    def test_t1_valid_package_rehydrates_to_typed_instance(self):
        pkg = rehydrate_candidate_package(_serialized_rich())
        assert isinstance(pkg, CandidateCharacterPackage)

    def test_t2_role_claims_are_typed(self):
        pkg = rehydrate_candidate_package(_serialized_rich())
        assert pkg.claims
        assert all(isinstance(c, RoleClaim) for c in pkg.claims)

    def test_t3_contradictions_are_typed(self):
        pkg = rehydrate_candidate_package(_serialized_rich())
        assert pkg.contradictions
        assert all(isinstance(c, ContradictionRecord) for c in pkg.contradictions)

    def test_t4_unknowns_are_preserved_and_typed(self):
        pkg = rehydrate_candidate_package(_serialized_rich())
        assert len(pkg.unknowns) == 1
        assert isinstance(pkg.unknowns[0], RoleClaim)
        assert pkg.unknowns[0].claim_type is ClaimType.UNKNOWN

    def test_t5_enums_restore_to_exact_instances(self):
        pkg = rehydrate_candidate_package(_serialized_rich())
        assert pkg.claims[0].claim_type is ClaimType.FACT
        assert pkg.claims[0].confidence is Confidence.KNOWN
        assert pkg.status is PackageStatus.DRAFT
        assert pkg.claims[0].source_type_summary[0] is SourceType.OWNER_DIRECT

    def test_t6_datetime_restores(self):
        original = _rich_package()
        pkg = rehydrate_candidate_package(_to_jsonable(original))
        assert isinstance(pkg.created_at, datetime)
        assert pkg.created_at == original.created_at

    def test_t7_invalid_enum_fails_closed(self):
        data = _serialized_rich()
        data["claims"][0]["claim_type"] = "NOT_A_CLAIM_TYPE"
        with pytest.raises(CrpValidationError):
            rehydrate_candidate_package(data)

    def test_t8_missing_required_field_fails_closed(self):
        data = _serialized_rich()
        data.pop("package_id")
        with pytest.raises(CrpValidationError):
            rehydrate_candidate_package(data)

    def test_t9_malformed_nested_claim_fails_closed(self):
        data = _serialized_rich()
        data["claims"][0]["claim_type"] = 123  # wrong primitive type
        with pytest.raises(CrpValidationError):
            rehydrate_candidate_package(data)

    def test_t10_package_hash_preserved(self):
        original = _rich_package()
        pkg = rehydrate_candidate_package(_to_jsonable(original))
        assert compute_package_hash(pkg) == compute_package_hash(original)


class TestNestedRehydrationDirect:
    def test_role_claim_direct(self):
        claim = make_claim(claim_id="claim-001", claim_type=ClaimType.FACT)
        out = rehydrate_role_claim(_to_jsonable(claim))
        assert isinstance(out, RoleClaim)
        assert out.claim_id == "claim-001"

    def test_contradiction_direct(self):
        record = make_contradiction(claim_ids=("a", "b"))
        out = rehydrate_contradiction_record(_to_jsonable(record))
        assert isinstance(out, ContradictionRecord)
        assert out.contradiction_id == record.contradiction_id
