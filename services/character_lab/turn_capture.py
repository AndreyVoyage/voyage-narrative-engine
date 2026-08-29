#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append-only turn-artifact capture for Character Lab (Slice 1).

Writes per-turn artifacts under a caller-supplied root (tests use temporary
directories; runtime artifacts are never written into Git-controlled paths).

Layout:

    <root>/turns/<turn_id>/
        request.json     # exact transport body bytes
        manifest.json    # assembly manifest bound to request_hash
        response.json    # parsed provider response JSON (on success)
        error.json       # error diagnostic (on failure)

The recorder returned by ``TurnCapture.recorder(...)`` is designed to be passed
to ``tools.crp_provider_adapter.build_provider_callable(config, recorder=...)``,
which threads it into ``tools.llm_provider._post_json`` so it observes the exact
body bytes immediately before transport.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

RECORDER_EVENT_REQUEST = "request"
RECORDER_EVENT_RESPONSE = "response"
RECORDER_EVENT_ERROR = "error"

REQUEST_FILENAME = "request.json"
MANIFEST_FILENAME = "manifest.json"
RESPONSE_FILENAME = "response.json"
ERROR_FILENAME = "error.json"

Recorder = Callable[[dict], None]


def compute_request_hash(body: bytes) -> str:
    """Authoritative request identity: SHA-256 over the exact transport body."""
    return hashlib.sha256(body).hexdigest()


def verify_segment_delivered(*, segment_text: str, request_body_text: str) -> bool:
    """Mechanically check a selected segment is present in the captured request.

    ``request_body_text`` is the decoded captured request body (UTF-8). The check
    parses the body and looks for ``segment_text`` inside a message ``content``.
    It does NOT claim causal influence; it only proves presence.
    """
    if not isinstance(segment_text, str) or not isinstance(request_body_text, str):
        return False
    try:
        payload = json.loads(request_body_text)
    except (json.JSONDecodeError, TypeError):
        return False
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and segment_text in content:
            return True
    return False


class TurnCapture:
    """Append-only artifact writer for one runtime run."""

    def __init__(self, root) -> None:
        self.root = Path(root)

    def turn_dir(self, turn_id: str) -> Path:
        return self.root / "turns" / turn_id

    def recorder(
        self,
        *,
        turn_id: str,
        manifest,
        assembly_hash: str,
        attribution=None,
    ) -> Recorder:
        """Return a recorder callable bound to one turn's manifest/attribution.

        The returned callable consumes the events emitted by the provider seam:
        ``{"event": "request", "payload": ..., "body": ...}``,
        ``{"event": "response", "data": ...}``,
        ``{"event": "error", ...}``.
        """

        def recv(event: dict) -> None:
            kind = event.get("event")
            if kind == RECORDER_EVENT_REQUEST:
                body = event["body"]
                request_hash = compute_request_hash(body)
                self._write_request(
                    turn_id, body, manifest, assembly_hash, request_hash, attribution
                )
            elif kind == RECORDER_EVENT_RESPONSE:
                self._write_response(turn_id, event.get("data"))
            elif kind == RECORDER_EVENT_ERROR:
                self._write_error(turn_id, event)

        return recv

    def read_request_hash(self, turn_id: str):
        manifest = self.read_manifest(turn_id)
        if not manifest:
            return None
        return manifest.get("request_hash")

    def read_manifest(self, turn_id: str):
        path = self.turn_dir(turn_id) / MANIFEST_FILENAME
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def read_response(self, turn_id: str):
        path = self.turn_dir(turn_id) / RESPONSE_FILENAME
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _write_request(
        self, turn_id, body, manifest, assembly_hash, request_hash, attribution
    ) -> None:
        directory = self.turn_dir(turn_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / REQUEST_FILENAME).write_bytes(body)
        payload = {
            "variant_id": manifest.variant_id,
            "variant_version": manifest.variant_version,
            "assembly_hash": assembly_hash,
            "request_hash": request_hash,
            "items": [
                {"kind": item.kind, "text": item.text, "meta": dict(item.meta)}
                for item in manifest.items
            ],
        }
        if attribution:
            payload["provider"] = attribution
        (directory / MANIFEST_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_response(self, turn_id, data) -> None:
        directory = self.turn_dir(turn_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / RESPONSE_FILENAME).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    def _write_error(self, turn_id, event) -> None:
        directory = self.turn_dir(turn_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / ERROR_FILENAME).write_text(
            json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
