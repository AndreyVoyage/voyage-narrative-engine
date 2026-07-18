#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for services/persona_gateway/persona_catalog.py (N7 Persona
Data Gateway, P1b Option A: INJECTED_CATALOG_NO_REGISTRY).

All persona/manifest/module fixtures are synthetic, built under pytest's
``tmp_path`` via ``build_persona_root`` (see conftest.py). No real
persona canon under ``personas/`` is read by this file -- that is
covered separately by ``test_multi_character_compatibility.py``.
"""

from __future__ import annotations

import inspect
import os
from collections.abc import Mapping
from pathlib import Path

import pytest

from services.persona_gateway import persona_catalog as persona_catalog_module
from services.persona_gateway.errors import (
    CharacterNotFoundError,
    ManifestIntegrityError,
    UnsupportedExtensionError,
)
from services.persona_gateway.models import CharacterRef
from services.persona_gateway.persona_catalog import PersonaCatalog
from services.persona_gateway.persona_repository import PersonaRepository


# ---------------------------------------------------------------------
# Construction -- happy paths
# ---------------------------------------------------------------------

def test_one_valid_injected_character_constructs(build_persona_root):
    root = build_persona_root(character_id="kira", character_name="Кира")
    catalog = PersonaCatalog({"kira": root})
    refs = catalog.list_characters()
    assert len(refs) == 1
    assert refs[0].id == "kira"
    assert refs[0].name == "Кира"


def test_multiple_valid_injected_characters_construct_together(build_persona_root):
    root_a = build_persona_root(character_id="kira", character_name="Кира", root_name="kira_root")
    root_b = build_persona_root(character_id="marina", character_name="Марина", root_name="marina_root")
    catalog = PersonaCatalog({"kira": root_a, "marina": root_b})
    ids = [ref.id for ref in catalog.list_characters()]
    assert ids == ["kira", "marina"]


def test_deterministic_casefold_ordering(build_persona_root):
    root_z = build_persona_root(character_id="Zed", character_name="Zed", root_name="zed_root")
    root_a = build_persona_root(character_id="alice", character_name="Alice", root_name="alice_root")
    root_m = build_persona_root(character_id="Marina", character_name="Марина", root_name="marina_root")

    catalog = PersonaCatalog({"Zed": root_z, "alice": root_a, "Marina": root_m})
    ids = [ref.id for ref in catalog.list_characters()]
    # ascending by casefold(): "alice" < "marina" < "zed"
    assert ids == ["alice", "Marina", "Zed"]


def test_returned_display_names_come_from_manifests(build_persona_root):
    root = build_persona_root(character_id="kira", character_name="Кира")
    catalog = PersonaCatalog({"kira": root})
    manifest = catalog.get_character_manifest("kira")
    ref = catalog.list_characters()[0]
    assert ref.name == manifest.name == "Кира"


# ---------------------------------------------------------------------
# Lookup failures
# ---------------------------------------------------------------------

def test_unknown_character_raises_character_not_found(build_persona_root):
    root = build_persona_root(character_id="kira")
    catalog = PersonaCatalog({"kira": root})
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("someone_else")
    with pytest.raises(CharacterNotFoundError):
        catalog.get_character_manifest("someone_else")
    with pytest.raises(CharacterNotFoundError):
        catalog.read_module("someone_else", "core/IDENTITY.json")


def test_wrong_root_id_pairing_rejected_at_construction(build_persona_root):
    root = build_persona_root(character_id="kira")
    # inject under a key that does not match INDEX.json["id"] == "kira"
    with pytest.raises(CharacterNotFoundError):
        PersonaCatalog({"not_kira": root})


# ---------------------------------------------------------------------
# Input-shape validation
# ---------------------------------------------------------------------

def test_empty_mapping_rejected():
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({})


def test_non_mapping_input_rejected():
    with pytest.raises(TypeError):
        PersonaCatalog([("kira", Path("personas/kira"))])  # type: ignore[arg-type]


def test_non_mapping_input_rejected_for_none():
    with pytest.raises(TypeError):
        PersonaCatalog(None)  # type: ignore[arg-type]


def test_invalid_character_id_type_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({123: root})  # type: ignore[dict-item]


def test_blank_id_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"": root})


def test_leading_whitespace_id_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({" kira": root})


def test_trailing_whitespace_id_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira ": root})


# ---------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------

def test_invalid_max_characters_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_characters=0)
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_characters=-1)
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_characters="16")  # type: ignore[arg-type]


def test_bool_max_characters_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_characters=True)


def test_maximum_character_count_exceeded(build_persona_root):
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira": root_a, "marina": root_b}, max_characters=1)


def test_maximum_character_count_allows_exactly_at_cap(build_persona_root):
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")
    catalog = PersonaCatalog({"kira": root_a, "marina": root_b}, max_characters=2)
    assert len(catalog.list_characters()) == 2


def test_invalid_aggregate_limit_rejected(build_persona_root):
    root = build_persona_root(character_id="kira")
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_aggregate_manifest_entries=0)
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_aggregate_manifest_entries=True)
    with pytest.raises(ValueError):
        PersonaCatalog({"kira": root}, max_aggregate_manifest_entries="1024")  # type: ignore[arg-type]


def test_aggregate_manifest_entry_limit_exceeded(build_persona_root):
    # Each synthetic root has 3 modules (DEFAULT_MODULES); two characters
    # => 6 aggregate entries, which exceeds a deliberately tiny cap of 5.
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira": root_a, "marina": root_b}, max_aggregate_manifest_entries=5)


def test_aggregate_manifest_entry_limit_allows_exactly_at_cap(build_persona_root):
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")
    catalog = PersonaCatalog(
        {"kira": root_a, "marina": root_b}, max_aggregate_manifest_entries=6
    )
    assert len(catalog.list_characters()) == 2


# ---------------------------------------------------------------------
# Duplicate / collision handling
# ---------------------------------------------------------------------

class _DuplicateYieldingMapping(Mapping):
    """A minimal ``Mapping`` whose ``.items()``/iteration can yield the
    exact same key twice -- something a plain ``dict`` can never do
    (dict key uniqueness collapses literal duplicates before the
    catalog ever sees them). Used only to exercise the "exact duplicate"
    branch of the catalog's duplicate-id rejection where it is actually
    constructible."""

    def __init__(self, pairs):
        self._pairs = list(pairs)

    def __getitem__(self, key):
        for k, v in self._pairs:
            if k == key:
                return v
        raise KeyError(key)

    def __iter__(self):
        for k, _ in self._pairs:
            yield k

    def __len__(self):
        return len(self._pairs)

    def items(self):
        return list(self._pairs)


def test_exact_duplicate_id_rejected_where_constructible(build_persona_root):
    root = build_persona_root(character_id="kira")
    mapping = _DuplicateYieldingMapping([("kira", root), ("kira", root)])
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog(mapping)


def test_case_insensitive_collision_rejected(build_persona_root):
    root_lower = build_persona_root(character_id="kira", root_name="lower_root")
    root_upper_dir = build_persona_root(character_id="KIRA", root_name="upper_root")
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira": root_lower, "KIRA": root_upper_dir})


# ---------------------------------------------------------------------
# Immutability / isolation from caller input
# ---------------------------------------------------------------------

def test_caller_mapping_mutation_after_construction_has_no_effect(build_persona_root):
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")
    entries = {"kira": root_a}
    catalog = PersonaCatalog(entries)

    # Mutate the caller's own mapping after construction.
    entries["marina"] = root_b
    entries["kira"] = None  # even corrupt the existing value

    ids = [ref.id for ref in catalog.list_characters()]
    assert ids == ["kira"]
    assert catalog.get_repository("kira") is not None
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("marina")


def test_returned_character_tuple_is_immutable(build_persona_root):
    root = build_persona_root(character_id="kira")
    catalog = PersonaCatalog({"kira": root})
    refs = catalog.list_characters()
    assert isinstance(refs, tuple)
    with pytest.raises(AttributeError):
        refs.append(CharacterRef(id="x", name="y"))  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        refs[0] = CharacterRef(id="x", name="y")  # type: ignore[index]


# ---------------------------------------------------------------------
# Underlying repository error propagation (not caught/replaced)
# ---------------------------------------------------------------------

def test_invalid_manifest_propagates(tmp_path, write_json_file):
    root = tmp_path / "invalid_manifest_root"
    write_json_file(root / "INDEX.json", {"id": "kira", "name": "Кира"})  # no "modules"
    with pytest.raises(ManifestIntegrityError):
        PersonaCatalog({"kira": root})


def test_unsupported_extension_propagates(build_persona_root):
    modules = {
        "core/IDENTITY.json": {"version": "1.0.0"},
        "visual/PROMPT_BASE.txt": {"version": "1.0.0"},
    }
    content = {"core/IDENTITY.json": {"id": "kira_identity"}}
    root = build_persona_root(modules=modules, module_content=content)
    (root / "visual").mkdir(parents=True, exist_ok=True)
    (root / "visual" / "PROMPT_BASE.txt").write_text("not json", encoding="utf-8")

    with pytest.raises(UnsupportedExtensionError):
        PersonaCatalog({"kira": root})


# ---------------------------------------------------------------------
# No registry / no directory scan / no filesystem write / no import side effects
# ---------------------------------------------------------------------

def test_no_registry_reference_in_catalog_source():
    import ast

    tree = ast.parse(inspect.getsource(persona_catalog_module))
    # Drop the module docstring (an Expr wrapping a Constant str as the
    # first body statement) before scanning: it is documentation-only
    # prose explaining why no REGISTRY.json is read/written, not
    # production behavior. Nothing else in the module may mention it.
    body = tree.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    remaining_source = ast.unparse(ast.Module(body=body, type_ignores=[]))
    assert "REGISTRY" not in remaining_source


def test_no_personas_directory_scan(build_persona_root, monkeypatch):
    root = build_persona_root(character_id="kira")

    def _forbidden(*args, **kwargs):
        raise AssertionError("PersonaCatalog must not scan directories")

    monkeypatch.setattr(os, "walk", _forbidden)
    monkeypatch.setattr(os, "scandir", _forbidden)
    original_iterdir = Path.iterdir

    def _forbidden_iterdir(self):
        raise AssertionError("PersonaCatalog must not call Path.iterdir")

    monkeypatch.setattr(Path, "iterdir", _forbidden_iterdir)
    try:
        catalog = PersonaCatalog({"kira": root})
        catalog.list_characters()
        catalog.get_repository("kira")
        catalog.get_character_manifest("kira")
        catalog.read_module("kira", "core/IDENTITY.json")
    finally:
        monkeypatch.setattr(Path, "iterdir", original_iterdir)


def test_no_filesystem_write_side_effects(build_persona_root):
    root_a = build_persona_root(character_id="kira", root_name="a_root")
    root_b = build_persona_root(character_id="marina", root_name="b_root")

    def snapshot_tree(base: Path):
        entries = {}
        for path in sorted(base.rglob("*")):
            if path.is_file():
                entries[str(path.relative_to(base))] = path.read_bytes()
        return entries

    tmp_root = root_a.parent
    before = snapshot_tree(tmp_root)
    catalog = PersonaCatalog({"kira": root_a, "marina": root_b})
    catalog.list_characters()
    catalog.get_character_manifest("kira")
    catalog.read_module("kira", "core/IDENTITY.json")
    with pytest.raises(CharacterNotFoundError):
        catalog.get_repository("nobody")
    after = snapshot_tree(tmp_root)

    assert before == after
    assert before.keys() == after.keys()
    # No REGISTRY.json (or any other new file) may appear anywhere under
    # the shared temp root as a side effect of catalog construction/use.
    assert not any(name == "REGISTRY.json" for name in after)


def test_import_time_has_no_repository_access():
    # Re-import must not raise and must not perform any repository
    # construction of its own -- persona_catalog only *defines* the
    # PersonaCatalog class at import time.
    import importlib

    module = importlib.import_module("services.persona_gateway.persona_catalog")
    assert hasattr(module, "PersonaCatalog")
    # No module-level PersonaRepository instances should exist.
    for name, value in vars(module).items():
        assert not isinstance(value, PersonaRepository), (
            f"unexpected module-level PersonaRepository instance: {name}"
        )
