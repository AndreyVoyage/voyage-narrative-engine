#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Media v0 -- deterministic, stdlib-only image validation.

Ratified limits (VCP-PKG-001 Section 13, FROZEN_BASELINE):

- maxSingleFileBytes = 64 MiB
- maxRasterDimension = 8192 x 8192
- Visual V1 allowlist: PNG / JPEG-JPG / WEBP (static only)
- Animated / multi-frame visual assets fail closed.

Format detection is magic-byte based (never filename extension alone). The
dimension/animation checks are lightweight header parses -- no Pillow, no
decode, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from services.reference_library.hashing import compute_sha256
from services.reference_library.importer import sniff_image_format as _sniff_rl

from .errors import (
    AnimatedImageError,
    MalformedImageError,
    OversizedAssetError,
    OversizedDimensionError,
    SourceValidationError,
    UnsupportedFormatError,
)
from .model import (
    MAX_ASSET_BYTES,
    MAX_RASTER_DIMENSION,
    SUPPORTED_FORMATS,
    format_mime_type,
)

FORMAT_PNG = "PNG"
FORMAT_JPEG = "JPEG"
FORMAT_WEBP = "WEBP"

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SOI = b"\xff\xd8"

# JPEG SOF markers that carry height/width (excluding DHT C4, JPG C8, DAC CC).
_JPEG_SOF_MARKERS = frozenset(
    {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
)


@dataclass(frozen=True)
class ValidatedImage:
    """Authoritative facts derived from actual image bytes."""

    format: str
    mime_type: str
    byte_length: int
    width: int
    height: int
    sha256: str


def sniff_image_format(data: bytes) -> Optional[str]:
    """Return the canonical format token (PNG/JPEG/WEBP) or None.

    Reuses the existing Reference Library magic-byte sniffing and maps its
    canonical keys onto the Character Media metadata tokens.
    """
    key = _sniff_rl(data)
    if key is None:
        return None
    return {"png": FORMAT_PNG, "jpg": FORMAT_JPEG, "webp": FORMAT_WEBP}[key]


def _u32be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def _u16be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def _png_dimensions(data: bytes) -> Tuple[int, int]:
    if len(data) < 8 or data[:8] != _PNG_SIG:
        raise MalformedImageError("PNG signature is invalid or missing")
    if len(data) < 8 + 8:
        raise MalformedImageError("PNG is missing a chunk header for IHDR")
    ihdr_length = _u32be(data, 8)
    if data[12:16] != b"IHDR":
        raise MalformedImageError("PNG first chunk is not IHDR")
    if ihdr_length != 13:
        raise MalformedImageError(
            f"PNG IHDR length must be exactly 13, got {ihdr_length}"
        )
    if len(data) < 8 + 8 + 13:
        raise MalformedImageError("PNG IHDR payload is truncated")
    width = _u32be(data, 16)
    height = _u32be(data, 20)
    if width == 0 or height == 0:
        raise MalformedImageError("PNG has a zero dimension")
    return width, height


def _png_is_animated(data: bytes) -> bool:
    """Detect APNG by scanning chunks; fail closed on malformed chunk bounds.

    Every chunk -- including IHDR and IEND -- first proves its complete
    structural bounds (declared length + CRC fit inside the buffer) before any
    semantic handling. IEND additionally requires a zero-length payload and a
    complete CRC.
    """
    offset = 8
    length = len(data)
    while offset + 8 <= length:
        chunk_length = _u32be(data, offset)
        chunk_type = data[offset + 4 : offset + 8]
        # Complete structural bounds proof BEFORE any semantic handling.
        chunk_end = offset + 12 + chunk_length  # 4 len + 4 type + data + 4 crc
        if chunk_end > length:
            raise MalformedImageError("PNG chunk extends beyond the byte buffer")
        if chunk_end <= offset:
            raise MalformedImageError("PNG chunk traversal does not advance")
        if chunk_type == b"IEND":
            if chunk_length != 0:
                raise MalformedImageError("PNG IEND payload must be empty")
            return False
        if chunk_type == b"acTL":
            return True
        offset = chunk_end
    raise MalformedImageError("PNG chunk stream is truncated (no IEND)")


def _jpeg_dimensions(data: bytes) -> Tuple[int, int]:
    if len(data) < 2 or data[0:2] != _JPEG_SOI:
        raise MalformedImageError("JPEG is missing the SOI marker")
    length = len(data)
    offset = 2
    while offset < length:
        if data[offset] != 0xFF:
            raise MalformedImageError("JPEG expected a 0xFF marker prefix")
        # Skip repeated 0xFF fill bytes.
        while offset < length and data[offset] == 0xFF:
            offset += 1
        if offset >= length:
            raise MalformedImageError("JPEG truncated after a marker prefix")
        marker = data[offset]
        offset += 1
        if marker == 0x00:
            continue  # stuffed byte inside entropy data
        if marker == 0xD9:  # EOI
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue  # standalone marker without a length field
        # Segment markers carry a 2-byte length.
        if offset + 2 > length:
            raise MalformedImageError("JPEG segment length field is truncated")
        segment_length = _u16be(data, offset)
        offset += 2
        if segment_length < 2:
            raise MalformedImageError("JPEG segment length is less than 2")
        segment_payload = segment_length - 2
        if offset + segment_payload > length:
            raise MalformedImageError("JPEG segment extends beyond the file")
        if marker in _JPEG_SOF_MARKERS:
            if segment_payload < 5:
                raise MalformedImageError("JPEG SOF segment payload is truncated")
            height = _u16be(data, offset + 1)
            width = _u16be(data, offset + 3)
            if width == 0 or height == 0:
                raise MalformedImageError("JPEG has a zero dimension")
            return width, height
        offset += segment_payload
    raise MalformedImageError("JPEG has no SOF marker with dimensions")


def _webp_container(data: bytes) -> int:
    """Validate the RIFF/WEBP header; return the exclusive container end."""
    if len(data) < 12:
        raise MalformedImageError("WEBP is too short for a RIFF header")
    if data[0:4] != b"RIFF":
        raise MalformedImageError("WEBP is missing the RIFF signature")
    if data[8:12] != b"WEBP":
        raise MalformedImageError("WEBP is missing the WEBP form type")
    container_size = int.from_bytes(data[4:8], "little")
    if container_size > len(data) - 8:
        raise MalformedImageError("WEBP RIFF size exceeds available bytes")
    return 8 + container_size


def _webp_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    """Return validated (fourcc, data) chunks; fail closed on malformed bounds.

    Traversal must structurally exhaust the declared RIFF container exactly:
    after the last chunk ``offset`` must equal ``container_end``. Any dangling
    byte or incomplete trailing chunk header (1..7 leftover bytes inside the
    declared container) fails closed.
    """
    container_end = _webp_container(data)
    chunks: list[tuple[bytes, bytes]] = []
    offset = 12
    while offset + 8 <= container_end:
        fourcc = data[offset : offset + 4]
        chunk_size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        data_end = data_start + chunk_size
        padded_end = data_end + (chunk_size & 1)
        if padded_end > container_end:
            raise MalformedImageError("WEBP chunk extends beyond the container")
        chunks.append((fourcc, data[data_start:data_end]))
        offset = padded_end
    if offset != container_end:
        raise MalformedImageError(
            "WEBP container has dangling bytes after the last chunk"
        )
    return chunks


def _webp_dimensions(data: bytes) -> Tuple[int, int]:
    chunks = _webp_chunks(data)
    if not chunks:
        raise MalformedImageError("WEBP has no chunks")
    fourcc, chunk = chunks[0]
    if fourcc == b"VP8X":
        if len(chunk) < 10:
            raise MalformedImageError("VP8X chunk is too short for dimensions")
        width = 1 + int.from_bytes(chunk[4:7], "little")
        height = 1 + int.from_bytes(chunk[7:10], "little")
        if width <= 0 or height <= 0:
            raise MalformedImageError("WEBP has a zero dimension")
        return width, height
    if fourcc == b"VP8L":
        if len(chunk) < 5:
            raise MalformedImageError("VP8L chunk is too short")
        if chunk[0] != 0x2F:
            raise MalformedImageError("VP8L has an invalid signature byte")
        b0 = chunk[1]
        b1 = chunk[2]
        b2 = chunk[3]
        b3 = chunk[4]
        width = (b0 | ((b1 & 0x3F) << 8)) + 1
        height = (((b1 >> 6) | (b2 << 2) | ((b3 & 0x0F) << 10))) + 1
        return width, height
    if fourcc == b"VP8 ":
        if len(chunk) < 10:
            raise MalformedImageError("VP8 chunk is too short")
        if chunk[3:6] != b"\x9d\x01\x2a":
            raise MalformedImageError("VP8 has an invalid start code")
        width = chunk[6] | ((chunk[7] & 0x3F) << 8)
        height = chunk[8] | ((chunk[9] & 0x3F) << 8)
        if width == 0 or height == 0:
            raise MalformedImageError("WEBP has a zero dimension")
        return width, height
    raise MalformedImageError("WEBP first chunk is not VP8/VP8L/VP8X")


def _webp_is_animated(data: bytes) -> bool:
    """Detect animated WEBP via ANIM/ANMF chunks AND the VP8X animation flag."""
    for fourcc, chunk in _webp_chunks(data):
        if fourcc in (b"ANIM", b"ANMF"):
            return True
        if fourcc == b"VP8X" and len(chunk) >= 4:
            flags = int.from_bytes(chunk[0:4], "little")
            if flags & 0x02:  # animation feature flag
                return True
    return False


def parse_image_dimensions(data: bytes, fmt: str) -> Tuple[int, int]:
    """Deterministically parse (width, height) from a supported image header."""
    if fmt == FORMAT_PNG:
        return _png_dimensions(data)
    if fmt == FORMAT_JPEG:
        return _jpeg_dimensions(data)
    if fmt == FORMAT_WEBP:
        return _webp_dimensions(data)
    raise UnsupportedFormatError(f"unsupported image format {fmt!r}")


def is_animated(data: bytes, fmt: str) -> bool:
    """Return True when the image is animated / multi-frame (fail-closed)."""
    if fmt == FORMAT_PNG:
        return _png_is_animated(data)
    if fmt == FORMAT_WEBP:
        return _webp_is_animated(data)
    return False  # baseline/progressive JPEG carries no animation in V1


def validate_image_bytes(data: bytes, fmt: str) -> Tuple[int, int]:
    """Validate already-sniffed bytes against the ratified limits (fail closed).

    Order: non-empty -> byte-size -> structure/animation -> deterministic
    dimensions -> raster-dimension limit. Returns (width, height). Raises a
    named ``CharacterMediaValidationError`` subclass on the first violation.
    """
    if len(data) == 0:
        raise SourceValidationError("image bytes are empty")
    if len(data) > MAX_ASSET_BYTES:
        raise OversizedAssetError(
            f"asset exceeds {MAX_ASSET_BYTES} bytes ({len(data)})"
        )
    if is_animated(data, fmt):
        raise AnimatedImageError("animated / multi-frame images are not supported")
    width, height = parse_image_dimensions(data, fmt)
    if width <= 0 or height <= 0:
        raise MalformedImageError(
            f"invalid raster dimensions ({width} x {height})"
        )
    if width > MAX_RASTER_DIMENSION or height > MAX_RASTER_DIMENSION:
        raise OversizedDimensionError(
            f"raster dimension exceeds {MAX_RASTER_DIMENSION} "
            f"({width} x {height})"
        )
    return width, height


def inspect_image(data: bytes) -> ValidatedImage:
    """Authoritatively validate actual image bytes and return their facts.

    Sniffs the format from magic bytes, then runs the full deterministic
    validation (byte-size, static-image, structural dimensions, raster limit).
    The returned ``ValidatedImage`` is the single source of truth for the
    actual format/MIME/length/dimensions/hash -- never the filename extension
    or revision-declared metadata.
    """
    fmt = sniff_image_format(data)
    if fmt is None:
        raise UnsupportedFormatError("unsupported or unrecognized image format")
    width, height = validate_image_bytes(data, fmt)
    return ValidatedImage(
        format=fmt,
        mime_type=format_mime_type(fmt),
        byte_length=len(data),
        width=width,
        height=height,
        sha256=compute_sha256(data),
    )

