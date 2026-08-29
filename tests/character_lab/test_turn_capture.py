#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turn-artifact capture tests (offline, stdlib only)."""

from __future__ import annotations

import hashlib
import json

from services.character_lab import (
    AssemblyItem,
    AssemblyManifest,
    TurnCapture,
    build_assembly_hash,
    compute_request_hash,
    verify_segment_delivered,
)


def _make_body(messages, model="deepseek-v4-pro"):
    return json.dumps({"model": model, "messages": messages}, ensure_ascii=False).encode("utf-8")


def _manifest():
    return AssemblyManifest(
        variant_id="KIRA_BETA_V1_CURRENT",
        variant_version=1,
        items=(AssemblyItem("system.role_instruction", "Ты — Кира, персонаж.", {}),),
    )


class TestRequestHash:
    def test_request_hash_is_sha256_of_exact_bytes(self):
        body = _make_body([{"role": "user", "content": "Привет."}])
        assert compute_request_hash(body) == hashlib.sha256(body).hexdigest()


class TestTurnCaptureArtifacts:
    def test_request_json_is_exact_body_bytes(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        assembly_hash = build_assembly_hash(manifest)
        rec = cap.recorder(
            turn_id="turn-1",
            manifest=manifest,
            assembly_hash=assembly_hash,
            attribution={"provider_id": "deepseek"},
        )
        body = _make_body([{"role": "system", "content": "Ты — Кира, персонаж."}])
        payload = json.loads(body.decode("utf-8"))
        rec({"event": "request", "payload": payload, "body": body})
        assert (cap.turn_dir("turn-1") / "request.json").read_bytes() == body

    def test_manifest_request_hash_binding(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        assembly_hash = build_assembly_hash(manifest)
        rec = cap.recorder(
            turn_id="turn-1", manifest=manifest, assembly_hash=assembly_hash
        )
        body = _make_body([{"role": "user", "content": "Привет."}])
        rec({"event": "request", "payload": json.loads(body.decode()), "body": body})
        man = cap.read_manifest("turn-1")
        assert man["request_hash"] == compute_request_hash(body)
        assert man["assembly_hash"] == assembly_hash
        assert cap.read_request_hash("turn-1") == compute_request_hash(body)

    def test_success_response_captured(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        rec = cap.recorder(
            turn_id="turn-1", manifest=manifest, assembly_hash=build_assembly_hash(manifest)
        )
        data = {
            "id": "cmpl-1",
            "model": "deepseek-v4-pro",
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        }
        rec({"event": "response", "data": data})
        assert cap.read_response("turn-1") == data

    def test_error_artifact_written(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        rec = cap.recorder(
            turn_id="turn-1", manifest=manifest, assembly_hash=build_assembly_hash(manifest)
        )
        rec({"event": "error", "error_type": "url_error", "detail": "boom"})
        assert (cap.turn_dir("turn-1") / "error.json").exists()


class TestDeliveryVerification:
    def test_segment_delivered_uses_captured_request(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        rec = cap.recorder(
            turn_id="turn-1", manifest=manifest, assembly_hash=build_assembly_hash(manifest)
        )
        body = _make_body([{"role": "user", "content": "Уникальный вопрос."}])
        rec({"event": "request", "payload": json.loads(body.decode()), "body": body})
        request_text = (cap.turn_dir("turn-1") / "request.json").read_text(encoding="utf-8")
        assert verify_segment_delivered(segment_text="Уникальный вопрос.", request_body_text=request_text) is True
        assert verify_segment_delivered(segment_text="Не существует", request_body_text=request_text) is False

    def test_verify_rejects_non_json(self):
        assert verify_segment_delivered(segment_text="x", request_body_text="not json") is False


class TestSecretSafety:
    def test_no_secret_material_in_artifacts(self, tmp_path):
        cap = TurnCapture(tmp_path)
        manifest = _manifest()
        rec = cap.recorder(
            turn_id="turn-1",
            manifest=manifest,
            assembly_hash=build_assembly_hash(manifest),
            attribution={"credential_env": "DEEPSEEK_API_KEY"},
        )
        body = _make_body([{"role": "user", "content": "Привет."}])
        rec({"event": "request", "payload": json.loads(body.decode()), "body": body})
        rec({"event": "response", "data": {"id": "cmpl-1", "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}})
        combined = ""
        for name in ("request.json", "manifest.json", "response.json"):
            combined += (cap.turn_dir("turn-1") / name).read_text(encoding="utf-8")
        assert "Bearer" not in combined
        assert "Authorization" not in combined
        assert "SUPER_SECRET_SENTINEL" not in combined
