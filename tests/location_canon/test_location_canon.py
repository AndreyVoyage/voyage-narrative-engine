#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Location Canon v0 tests -- pilot load, immutable model, hash, validation,
portability, and ASS location_id compatibility."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from services.location_canon import (
    LocationCanon,
    LocationCanonValidationError,
    LocationNotFoundError,
    compute_content_hash,
    load_location,
)
from services.location_canon.hashing import compute_content_hash as _hash


# ---------------------------------------------------------------------------
# A. Pilot load
# ---------------------------------------------------------------------------


def test_yoga_hall_loads(yoga_hall):
    assert yoga_hall.location_id == "yoga_hall"
    assert yoga_hall.schema_version == "location/0.1"
    assert len(yoga_hall.content_hash) == 64


# ---------------------------------------------------------------------------
# B. Owner facts preserved exactly
# ---------------------------------------------------------------------------


def test_yoga_hall_owner_facts(yoga_hall):
    assert yoga_hall.tier == "premium"
    assert set(yoga_hall.scale) == {"small", "intimate"}
    assert "yoga" in yoga_hall.identity
    assert "wellness" in yoga_hall.identity
    assert set(yoga_hall.palette) == {"warm", "sophisticated", "harmonious"}


def test_yoga_hall_exactly_two_treadmills(yoga_hall):
    # Persistent cardio-corner fixed feature with exactly two treadmills.
    assert yoga_hall.treadmill_count == 2
    treadmills = next(f for f in yoga_hall.fixed_features if f.feature_id == "treadmills")
    assert treadmills.count == 2


def test_no_invented_facts(yoga_hall):
    # None of the explicitly-forbidden invented facts may be present.
    forbidden = {
        "city", "country", "dimensions", "floor_area", "ceiling_height",
        "brand", "model", "mirrors_count", "furniture", "plants",
        "lighting_fixtures", "reception", "lockers", "window_orientation",
        "exterior_view", "architectural_style", "machines", "rgb", "hex",
        "material_species", "sergey", "kira",
    }
    feature_ids = {f.feature_id for f in yoga_hall.fixed_features}
    assert feature_ids.isdisjoint(forbidden)
    assert "sergey" not in json.dumps(yoga_hall.to_dict()).lower()
    assert "kira" not in json.dumps(yoga_hall.to_dict()).lower()


# ---------------------------------------------------------------------------
# C. Deep immutability
# ---------------------------------------------------------------------------


def test_immutable_dataclass(yoga_hall):
    with pytest.raises(dataclasses.FrozenInstanceError):
        yoga_hall.tier = "budget"  # type: ignore[misc]


def test_scale_identity_palette_are_tuples(yoga_hall):
    assert isinstance(yoga_hall.scale, tuple)
    assert isinstance(yoga_hall.identity, tuple)
    assert isinstance(yoga_hall.palette, tuple)


def test_payload_mutation_does_not_affect_canon(yoga_hall):
    stored = yoga_hall.content_hash
    payload = yoga_hall.semantic_payload()
    payload["tier"] = "budget"
    payload["identity"].append("spa")
    payload["fixed_features"][0]["label"] = "hacked"

    assert yoga_hall.tier == "premium"
    assert "spa" not in yoga_hall.identity
    assert compute_content_hash(yoga_hall.semantic_payload()) == stored


def test_to_dict_mutation_does_not_affect_canon(yoga_hall):
    stored = yoga_hall.content_hash
    envelope = yoga_hall.to_dict()
    envelope["tier"] = "budget"
    envelope["scale"].append("huge")

    assert yoga_hall.tier == "premium"
    assert "huge" not in yoga_hall.scale
    assert yoga_hall.content_hash == stored


def test_fixed_features_tuple_immutable(yoga_hall):
    assert isinstance(yoga_hall.fixed_features, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        yoga_hall.fixed_features = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# D. Hash determinism
# ---------------------------------------------------------------------------


def test_same_semantics_same_hash(repo_root):
    a = load_location(repo_root, "yoga_hall")
    b = load_location(repo_root, "yoga_hall")
    assert a.content_hash == b.content_hash


def test_semantic_change_changes_hash(yoga_hall, repo_root):
    # A different tier is a semantic change.
    other = LocationCanon(
        schema_version=yoga_hall.schema_version,
        location_id=yoga_hall.location_id,
        tier="budget",
        scale=yoga_hall.scale,
        identity=yoga_hall.identity,
        palette=yoga_hall.palette,
        fixed_features=yoga_hall.fixed_features,
        content_hash="",
    )
    other_hash = _hash(other.semantic_payload())
    assert other_hash != yoga_hall.content_hash


def test_provenance_does_not_affect_hash(yoga_hall):
    payload = yoga_hall.semantic_payload()
    assert "provenance" not in payload
    assert "schema_version" not in payload


# ---------------------------------------------------------------------------
# E. Validation
# ---------------------------------------------------------------------------


def _write_location(tmp_path: Path, location_id: str, payload: dict) -> Path:
    locations = tmp_path / "scenarios" / "locations"
    locations.mkdir(parents=True, exist_ok=True)
    path = locations / f"{location_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


_BASE = {
    "schema_version": "location/0.1",
    "location_id": "test_room",
    "tier": "premium",
    "scale": ["small"],
    "identity": ["studio"],
    "palette": ["warm"],
    "fixed_features": [{"feature_id": "wall", "label": "wall"}],
}


def test_wrong_schema_rejected(tmp_path):
    payload = dict(_BASE, schema_version="location/9.9")
    _write_location(tmp_path, "test_room", payload)
    with pytest.raises(LocationCanonValidationError):
        load_location(tmp_path, "test_room")


def test_invalid_location_id_rejected(tmp_path):
    payload = dict(_BASE, location_id="INVALID ID")
    _write_location(tmp_path, "INVALID ID", payload)
    with pytest.raises((LocationCanonValidationError, LocationNotFoundError)):
        load_location(tmp_path, "INVALID ID")


def test_missing_location_id_rejected(tmp_path):
    payload = {k: v for k, v in _BASE.items() if k != "location_id"}
    _write_location(tmp_path, "test_room", payload)
    with pytest.raises(LocationCanonValidationError):
        load_location(tmp_path, "test_room")


def test_malformed_fixed_features_rejected(tmp_path):
    payload = dict(_BASE, fixed_features=[{"feature_id": "wall"}])
    _write_location(tmp_path, "test_room", payload)
    with pytest.raises(LocationCanonValidationError):
        load_location(tmp_path, "test_room")


def test_unknown_location_rejected(repo_root):
    with pytest.raises(LocationNotFoundError):
        load_location(repo_root, "does_not_exist")


# ---------------------------------------------------------------------------
# F. Portability
# ---------------------------------------------------------------------------


def test_no_absolute_path_in_canon(yoga_hall):
    envelope = yoga_hall.to_dict()
    assert yoga_hall.provenance.source_ref == "scenarios/locations/yoga_hall.json"
    assert "\\" not in yoga_hall.provenance.source_ref
    assert not yoga_hall.provenance.source_ref.startswith("/")
    assert "C:" not in yoga_hall.provenance.source_ref.upper()
    assert "\\" not in json.dumps(envelope)


# ---------------------------------------------------------------------------
# G. ASS location_id compatibility
# ---------------------------------------------------------------------------


def test_ass_location_id_compatibility(repo_root, yoga_hall):
    # ASS accepts explicit location_id = "yoga_hall"; Location Canon resolves
    # the same stable id. No free-text guessing, no ASS mutation involved.
    from services.ass import import_scene

    fixture = repo_root / "tests" / "fixtures" / "ass" / "SC_029_SYNTHETIC.v2.json"
    source = json.loads(fixture.read_text(encoding="utf-8"))
    ass = import_scene(
        source,
        ass_id="ass_test",
        version=1,
        location_id="yoga_hall",
        source_ref="scenarios/SC_029_SYNTHETIC.v2.json",
    )
    # Both resolve the same stable location_id, no guessing, no coupling.
    assert ass.location_id == "yoga_hall"
    assert yoga_hall.location_id == "yoga_hall"
    assert ass.location_id == yoga_hall.location_id


# ---------------------------------------------------------------------------
# H. Gym location canon (B4-L2)
# ---------------------------------------------------------------------------


def test_gym_loads(gym):
    assert gym.location_id == "gym"
    assert gym.schema_version == "location/0.1"
    assert len(gym.content_hash) == 64


def test_gym_owner_facts(gym):
    assert gym.tier == "standard"
    assert set(gym.scale) == {"medium"}
    assert set(gym.identity) == {"gym", "strength_training", "cardio", "stretching"}
    assert set(gym.palette) == {"neutral"}
    assert {f.feature_id for f in gym.fixed_features} == {"mirrored_wall", "treadmill"}


def test_gym_treadmill_has_no_count(gym):
    treadmill = next(f for f in gym.fixed_features if f.feature_id == "treadmill")
    assert treadmill.count is None


def test_gym_no_invented_facts(gym):
    forbidden = {
        "rack", "free_weight_zone", "strength_machines", "floor_material",
        "windows", "room_dimensions", "brand", "model", "lighting_fixtures",
        "equipment_counts", "barbell", "red_mat", "phone", "mirrors_count",
        "machines", "furniture", "plants", "city", "country", "dimensions",
        "rgb", "hex", "sergey", "kira",
    }
    feature_ids = {f.feature_id for f in gym.fixed_features}
    assert feature_ids.isdisjoint(forbidden)
    assert "sergey" not in json.dumps(gym.to_dict()).lower()
    assert "kira" not in json.dumps(gym.to_dict()).lower()
    assert "barbell" not in json.dumps(gym.to_dict()).lower()
    assert "red mat" not in json.dumps(gym.to_dict()).lower()


def test_gym_distinct_from_yoga_hall(gym, yoga_hall):
    assert gym.location_id != yoga_hall.location_id
    assert gym.content_hash != yoga_hall.content_hash
    assert set(gym.identity) != set(yoga_hall.identity)


def test_gym_ass_location_id_compatibility(repo_root, gym):
    from services.ass import import_scene

    fixture = repo_root / "tests" / "fixtures" / "ass" / "SC_029_SYNTHETIC.v2.json"
    source = json.loads(fixture.read_text(encoding="utf-8"))
    ass = import_scene(
        source,
        ass_id="ass_test_gym",
        version=1,
        location_id="gym",
        source_ref="scenarios/SC_029_SYNTHETIC.v2.json",
    )
    assert ass.location_id == "gym"
    assert gym.location_id == "gym"
    assert ass.location_id == gym.location_id
