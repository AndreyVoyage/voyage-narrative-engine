#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attachment Security Gateway (FOUNDATION ONLY -- no upload is enabled).

Nothing in the Companion UI calls this yet. It exists so the next multimodal
slice has a single, testable safety boundary already written. When invoked it:

- accepts only an explicit format allowlist (PNG/JPEG/WEBP/PDF/TXT/MD);
- verifies binary formats by magic-byte signature, not by filename extension;
- bounds-decodes text and rejects binary-as-text;
- enforces central byte/char size limits, fail-closed on oversize;
- produces a generated ``attachment_id`` -- the original filename never becomes
  a filesystem path;
- classifies content authority as ``USER_ATTACHMENT_DATA`` (never SYSTEM / TOOL
  / RUNTIME_CONTROL / STATE_WRITE);
- performs ZERO network I/O and ZERO shell/process execution.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "AttachmentError",
    "AcceptedAttachment",
    "AttachmentSecurityGateway",
    "AUTHORITY_USER_ATTACHMENT_DATA",
    "ALLOWLIST",
]

AUTHORITY_USER_ATTACHMENT_DATA = "USER_ATTACHMENT_DATA"

# Central safety limits.
MAX_FILE_BYTES = 12 * 1024 * 1024        # 12 MiB
MAX_IMAGE_BYTES = 8 * 1024 * 1024        # 8 MiB
MAX_TEXT_CHARS = 400_000
# Future archive limits -- represented but NOT parsed in this slice.
MAX_ARCHIVE_ENTRIES = 0
MAX_ARCHIVE_EXPANDED_BYTES = 0


@dataclass(frozen=True)
class _Format:
    content_type: str
    category: str          # "image" | "document"
    max_bytes: int
    signatures: Tuple[bytes, ...] = ()
    is_text: bool = False


ALLOWLIST: Dict[str, _Format] = {
    "png": _Format("image/png", "image", MAX_IMAGE_BYTES, (b"\x89PNG\r\n\x1a\n",)),
    "jpeg": _Format("image/jpeg", "image", MAX_IMAGE_BYTES, (b"\xff\xd8\xff",)),
    "webp": _Format("image/webp", "image", MAX_IMAGE_BYTES, ()),  # RIFF....WEBP, checked specially
    "pdf": _Format("application/pdf", "document", MAX_FILE_BYTES, (b"%PDF-",)),
    "txt": _Format("text/plain", "document", MAX_FILE_BYTES, is_text=True),
    "md": _Format("text/markdown", "document", MAX_FILE_BYTES, is_text=True),
}
# Formats named in the product doc that are NOT yet accepted.
FUTURE_FORMATS: Tuple[str, ...] = ("docx", "epub", "audio", "video")

_EXT_ALIAS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp",
              "pdf": "pdf", "txt": "txt", "md": "md", "markdown": "md"}


class AttachmentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AcceptedAttachment:
    attachment_id: str
    declared_name: str          # normalized display metadata only -- never a path
    content_type: str
    category: str
    size_bytes: int
    authority: str = AUTHORITY_USER_ATTACHMENT_DATA
    text_preview: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "attachmentId": self.attachment_id,
            "declaredName": self.declared_name,
            "contentType": self.content_type,
            "category": self.category,
            "sizeBytes": self.size_bytes,
            "authority": self.authority,
            "textPreview": self.text_preview,
        }


def _safe_display_name(raw: str) -> str:
    """A display-only label. Strips any path structure; the result is metadata,
    never used to build a filesystem path."""
    name = unicodedata.normalize("NFC", str(raw or "")).strip()
    # take only the final component, drop separators outright
    for sep in ("/", "\\"):
        if sep in name:
            name = name.rsplit(sep, 1)[-1]
    name = name.replace("\x00", "").replace("..", "_")
    name = "".join(c for c in name if c.isprintable() and c not in '<>:"|?*')
    return (name[:120] or "attachment")


def _looks_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    # crude control-char density check on a sample
    sample = data[:4096]
    if not sample:
        return False
    ctrl = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return ctrl / len(sample) > 0.02


class AttachmentSecurityGateway:
    """Stateless validator. Construct once, call :meth:`inspect` per file. No
    network, no disk writes, no subprocess -- ever."""

    def __init__(self, *, id_salt: str = "companion") -> None:
        self._salt = id_salt

    def is_future_format(self, fmt: str) -> bool:
        return (fmt or "").strip().lower() in FUTURE_FORMATS

    def inspect(self, *, filename: str, data: bytes, declared_format: Optional[str] = None) -> AcceptedAttachment:
        if not isinstance(data, (bytes, bytearray)):
            raise AttachmentError("invalid_request", "attachment data must be bytes")
        data = bytes(data)
        if len(data) == 0:
            raise AttachmentError("empty_file", "attachment is empty")
        if len(data) > MAX_FILE_BYTES:
            raise AttachmentError("too_large", "attachment exceeds the maximum size")

        ext = (declared_format or "").strip().lower()
        if not ext:
            ext = filename.rsplit(".", 1)[-1].strip().lower() if "." in (filename or "") else ""
        fmt_key = _EXT_ALIAS.get(ext)
        if fmt_key is None:
            if self.is_future_format(ext):
                raise AttachmentError("format_not_enabled", f"format {ext!r} is planned but not enabled yet")
            raise AttachmentError("format_not_allowed", f"format {ext!r} is not on the allowlist")
        fmt = ALLOWLIST[fmt_key]

        if len(data) > fmt.max_bytes:
            raise AttachmentError("too_large", f"{fmt.category} exceeds its maximum size")

        text_preview: Optional[str] = None
        if fmt.is_text:
            if _looks_binary(data):
                raise AttachmentError("binary_as_text", "file declared as text contains binary content")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                raise AttachmentError("bad_text_encoding", "text attachment is not valid UTF-8")
            if len(text) > MAX_TEXT_CHARS:
                raise AttachmentError("too_large", "text attachment exceeds the character limit")
            text_preview = text[:280]
        else:
            if not self._signature_ok(fmt_key, fmt, data):
                raise AttachmentError("signature_mismatch", "file content does not match its declared type")

        digest = hashlib.sha256(self._salt.encode() + data).hexdigest()[:32]
        return AcceptedAttachment(
            attachment_id=f"att-{digest}",
            declared_name=_safe_display_name(filename),
            content_type=fmt.content_type,
            category=fmt.category,
            size_bytes=len(data),
            authority=AUTHORITY_USER_ATTACHMENT_DATA,
            text_preview=text_preview,
        )

    @staticmethod
    def _signature_ok(fmt_key: str, fmt: _Format, data: bytes) -> bool:
        if fmt_key == "webp":
            return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        return any(data.startswith(sig) for sig in fmt.signatures)
