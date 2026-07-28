#!/usr/bin/env python3
"""Dataset schema validation tests using jsonschema."""

import json
import uuid
from pathlib import Path

import pytest

try:
    import jsonschema
except ImportError:
    jsonschema = None

from services.persona_authoring import PacTrainingExample
from .test_storage import _make_example


SCHEMA_PATH = Path("services/persona_authoring/schemas/pac_training_example_v1.json")


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.skipif(jsonschema is None, reason="jsonschema not installed")
class TestDatasetSchema:
    def test_valid_record_passes(self):
        schema = _load_schema()
        ex = _make_example()
        data = ex.to_dict()
        jsonschema.validate(instance=data, schema=schema)

    def test_missing_schema_version_fails(self):
        schema = _load_schema()
        ex = _make_example()
        data = ex.to_dict()
        del data["schema_version"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_missing_character_id_fails(self):
        schema = _load_schema()
        ex = _make_example()
        data = ex.to_dict()
        del data["character_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_empty_approved_output_fails(self):
        schema = _load_schema()
        ex = _make_example(approved_output="")
        data = ex.to_dict()
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_wrong_provenance_fails(self):
        schema = _load_schema()
        ex = _make_example()
        ex = PacTrainingExample(
            example_id=ex.example_id,
            created_at=ex.created_at,
            character_id=ex.character_id,
            authoring_session_id=ex.authoring_session_id,
            provider=ex.provider,
            model=ex.model,
            canon_snapshot=ex.canon_snapshot,
            context=ex.context,
            model_output_raw=ex.model_output_raw,
            approved_output=ex.approved_output,
            provenance="invalid_provenance",
        )
        data = ex.to_dict()
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_wrong_provider_fails(self):
        schema = _load_schema()
        ex = _make_example()
        ex = PacTrainingExample(
            example_id=ex.example_id,
            created_at=ex.created_at,
            character_id=ex.character_id,
            authoring_session_id=ex.authoring_session_id,
            provider="invalid",
            model=ex.model,
            canon_snapshot=ex.canon_snapshot,
            context=ex.context,
            model_output_raw=ex.model_output_raw,
            approved_output=ex.approved_output,
            provenance="human-edited",
        )
        data = ex.to_dict()
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_fmrd_key_not_fmdr_works(self):
        """Canonical keys are fmdr_* not fmrd_*."""
        schema = _load_schema()
        # The schema uses "fmdr_valid" -- verify that "fmrd_valid" would be rejected
        # because additionalProperties is false and "fmrd_valid" is not in the schema.
        ex = _make_example()
        data = ex.to_dict()
        data["gates"] = {"fmrd_valid": True, "speech_uniqueness_pass": True, "canon_reviewed_by_human": True}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_additional_properties_rejected(self):
        schema = _load_schema()
        ex = _make_example()
        data = ex.to_dict()
        data["unknown_field"] = "should be rejected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)

    def test_invalid_uuid_fails(self):
        schema = _load_schema()
        ex = _make_example()
        data = ex.to_dict()
        data["example_id"] = "not-a-uuid"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=data, schema=schema)


class TestPacTrainingExampleSelfValidation:
    def test_enum_values_valid(self):
        ex = _make_example()
        errors = ex.validate_enum_values()
        assert not errors

    def test_invalid_provenance_detected(self):
        ex = _make_example()
        ex = PacTrainingExample(
            example_id=ex.example_id,
            created_at=ex.created_at,
            character_id=ex.character_id,
            authoring_session_id=ex.authoring_session_id,
            provider=ex.provider,
            model=ex.model,
            canon_snapshot=ex.canon_snapshot,
            context=ex.context,
            model_output_raw=ex.model_output_raw,
            approved_output=ex.approved_output,
            provenance="bad_value",
        )
        errors = ex.validate_enum_values()
        assert len(errors) > 0

    def test_empty_approved_output_detected(self):
        ex = _make_example(approved_output="")
        errors = ex.validate_enum_values()
        assert any("approved_output" in e for e in errors)