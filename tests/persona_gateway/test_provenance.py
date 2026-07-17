#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for services/persona_gateway/provenance.py."""

from __future__ import annotations

import hashlib

from services.persona_gateway.provenance import build_module_provenance


def test_content_hash_matches_raw_bytes_sha256():
    raw = b'{"id": "kira_identity"}'
    prov = build_module_provenance(
        character_id="kira", module_id="core/IDENTITY.json", raw_bytes=raw, version="1.0.0"
    )
    expected = hashlib.sha256(raw).hexdigest()
    assert prov.content_hash == expected
    assert prov.content_hash == prov.content_hash.lower()


def test_hash_is_deterministic_and_stable_across_calls():
    raw = b'{"a": 1}'
    prov1 = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=raw, version="1.0.0")
    prov2 = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=raw, version="1.0.0")
    assert prov1.content_hash == prov2.content_hash


def test_hash_changes_when_bytes_change():
    prov1 = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=b'{"a": 1}', version="1.0.0")
    prov2 = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=b'{"a": 2}', version="1.0.0")
    assert prov1.content_hash != prov2.content_hash


def test_source_is_stable_logical_identifier_not_absolute_path():
    prov = build_module_provenance(
        character_id="kira", module_id="levels/U2-A.json", raw_bytes=b"{}", version="1.0.0"
    )
    assert prov.source == "personas/kira/levels/U2-A.json"
    assert ":" not in prov.source or prov.source.count(":") == 0
    assert "\\" not in prov.source


def test_schema_is_none_and_read_only_true():
    prov = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=b"{}", version="1.0.0")
    assert prov.schema is None
    assert prov.read_only is True


def test_version_passthrough_and_none_allowed():
    prov_with_version = build_module_provenance(character_id="kira", module_id="x.json", raw_bytes=b"{}", version="9.9.9")
    assert prov_with_version.version == "9.9.9"

    prov_without_version = build_module_provenance(character_id="kira", module_id="x.json", raw_bytes=b"{}", version=None)
    assert prov_without_version.version is None


def test_provenance_never_contains_raw_source_bytes():
    raw = b'{"secret": "do-not-leak-me"}'
    prov = build_module_provenance(character_id="kira", module_id="core/IDENTITY.json", raw_bytes=raw, version="1.0.0")
    rendered = repr(prov)
    assert "do-not-leak-me" not in rendered
