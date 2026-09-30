#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic, deterministic test images (stdlib-only, no decode, no network).

The builders produce real PNG/JPEG/WEBP headers with known dimensions. No
Pillow is used; the Character Media validators only parse headers, so these
images are sufficient to prove format acceptance, dimension limits, and
animation rejection.
"""

from __future__ import annotations

import struct
import zlib


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return (
        struct.pack(">I", len(payload))
        + body
        + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    )


def png(width: int, height: int, *, animated: bool = False) -> bytes:
    """Build a minimal RGBA PNG with the given dimensions (optionally APNG)."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunks = [_png_chunk(b"IHDR", ihdr)]
    if animated:
        # An acTL chunk anywhere in the chunk stream marks an APNG.
        chunks.append(_png_chunk(b"acTL", struct.pack(">II", 1, 0)))
    raw = b"".join(b"\x00" + b"\x00\x00\x00\xff" * width for _ in range(height))
    chunks.append(_png_chunk(b"IDAT", zlib.compress(raw)))
    chunks.append(_png_chunk(b"IEND", b""))
    return signature + b"".join(chunks)


def _jpeg_segment(marker: int, payload: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload


def jpeg(width: int, height: int) -> bytes:
    """Build a minimal baseline JPEG header carrying width/height in a SOF0."""
    out = bytearray()
    out += b"\xff\xd8"  # SOI
    out += _jpeg_segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    sof0 = (
        b"\x08"  # precision
        + struct.pack(">HH", height, width)  # height, width
        + b"\x03"  # 3 components
        + b"\x01\x11\x00"
        + b"\x02\x11\x00"
        + b"\x03\x11\x00"
    )
    out += _jpeg_segment(0xC0, sof0)
    out += b"\xff\xd9"  # EOI
    return bytes(out)


def _webp_riff(fourcc: bytes, payload: bytes, extra=None) -> bytes:
    def chunk(cc: bytes, data: bytes) -> bytes:
        return cc + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) % 2 else b"")

    body = chunk(fourcc, payload)
    for cc, data in (extra or []):
        body += chunk(cc, data)
    # RIFF size field = everything after the 8-byte RIFF header ("WEBP" + body).
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def webp_vp8l(width: int, height: int) -> bytes:
    """Build a minimal static lossless WEBP (VP8L) with known dimensions."""
    w = width - 1
    h = height - 1
    b0 = w & 0xFF
    b1 = ((w >> 8) & 0x3F) | ((h & 0x03) << 6)
    b2 = (h >> 2) & 0xFF
    b3 = (h >> 10) & 0x0F
    return _webp_riff(b"VP8L", b"\x2f" + bytes([b0, b1, b2, b3]))


def webp_animated(width: int, height: int) -> bytes:
    """Build a minimal animated WEBP (VP8X with animation + an ANIM chunk)."""
    flags = 0x02  # animation flag
    vp8x = struct.pack("<I", flags) + (width - 1).to_bytes(3, "little") + (
        height - 1
    ).to_bytes(3, "little")
    anim = b"\x00\x00\x00\x00" + struct.pack("<H", 0)  # bg color + loop count
    return _webp_riff(b"VP8X", vp8x, extra=[(b"ANIM", anim)])


def gif() -> bytes:
    """Build a GIF header (rejected by the V1 allowlist)."""
    return b"GIF89a" + b"\x00" * 64


# --- negative / malformed fixtures -------------------------------------------


def png_truncated_ihdr() -> bytes:
    """A 24-byte PNG with a signature + IHDR header but a truncated payload."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_header = struct.pack(">I", 13) + b"IHDR"
    return signature + ihdr_header + b"\x00" * 8


def png_chunk_beyond_buffer() -> bytes:
    """A PNG with a valid IHDR then a chunk declaring bytes beyond the buffer."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0))
    bogus = struct.pack(">I", 1_000_000) + b"IDAT"
    return signature + ihdr + bogus


def jpeg_sof_len_2() -> bytes:
    """A JPEG whose SOF0 declares a segment length of exactly 2."""
    return b"\xff\xd8" + _jpeg_segment(0xC0, b"") + b"\xff\xd9"


def jpeg_truncated_segment() -> bytes:
    """A JPEG whose segment length exceeds the available bytes."""
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 1000) + b"\x00\x00"


def webp_vp8x_anim_flag_only(width: int, height: int) -> bytes:
    """A VP8X whose animation flag is set, with NO ANIM/ANMF chunks."""
    flags = 0x02  # animation feature flag
    vp8x = (
        struct.pack("<I", flags)
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    return _webp_riff(b"VP8X", vp8x)


def webp_vp8x_zero_size() -> bytes:
    """A VP8X with a declared chunk size of 0 (dimensions cannot be read)."""
    return _webp_riff(b"VP8X", b"")


def webp_chunk_beyond_container() -> bytes:
    """A WEBP whose first chunk declares bytes beyond the RIFF container."""
    header = b"RIFF" + struct.pack("<I", 12) + b"WEBP"  # container_end = 20
    return header + b"VP8X" + struct.pack("<I", 1_000_000)


def webp_riff_size_beyond() -> bytes:
    """A WEBP whose RIFF size field exceeds the available bytes."""
    return b"RIFF" + struct.pack("<I", 1000) + b"WEBP" + b"\x00" * 8


def png_iend_nonzero_length() -> bytes:
    """A PNG whose IEND declares a non-zero payload (invalid)."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0))
    raw = b"\x00" + b"\x00\x00\x00\xff" * 4
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend = _png_chunk(b"IEND", b"\x00\x00\x00\x00")  # declared length 4
    return signature + ihdr + idat + iend


def png_iend_truncated_crc() -> bytes:
    """A PNG whose IEND has a header but no CRC bytes."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0))
    raw = b"\x00" + b"\x00\x00\x00\xff" * 4
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend_header = struct.pack(">I", 0) + b"IEND"  # length=0 + type, no CRC
    return signature + ihdr + idat + iend_header


def png_iend_length_beyond() -> bytes:
    """A PNG whose IEND declares bytes beyond the available buffer."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0))
    raw = b"\x00" + b"\x00\x00\x00\xff" * 4
    idat = _png_chunk(b"IDAT", zlib.compress(raw))
    iend_header = struct.pack(">I", 1000) + b"IEND"  # declares 1000, no data
    return signature + ihdr + idat + iend_header


def webp_dangling_byte() -> bytes:
    """A valid VP8L chunk plus one dangling byte inside the declared container."""
    vp8l_payload = b"\x2f" + bytes([3, 0xC0, 0, 0])  # 4x4 lossless
    vp8l_chunk = (
        b"VP8L" + struct.pack("<I", len(vp8l_payload)) + vp8l_payload + b"\x00"
    )
    body = vp8l_chunk + b"\x00"  # 1 dangling byte
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body


def webp_incomplete_chunk_header() -> bytes:
    """A valid chunk plus a 4-byte partial chunk header (FOURCC only)."""
    vp8l_payload = b"\x2f" + bytes([3, 0xC0, 0, 0])
    vp8l_chunk = (
        b"VP8L" + struct.pack("<I", len(vp8l_payload)) + vp8l_payload + b"\x00"
    )
    body = vp8l_chunk + b"ANIM"  # 4-byte partial header
    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WEBP" + body
