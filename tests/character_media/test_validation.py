#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic image-validation tests for the Character Media slice."""

from __future__ import annotations

import pytest

from services.character_media import (
    AnimatedImageError,
    MAX_ASSET_BYTES,
    MAX_RASTER_DIMENSION,
    MalformedImageError,
    OversizedAssetError,
    OversizedDimensionError,
    FORMAT_JPEG,
    FORMAT_PNG,
    FORMAT_WEBP,
    inspect_image,
    parse_image_dimensions,
    sniff_image_format,
    validate_image_bytes,
)
from tests.character_media._images import (
    gif,
    jpeg,
    jpeg_sof_len_2,
    jpeg_truncated_segment,
    png,
    png_chunk_beyond_buffer,
    png_iend_length_beyond,
    png_iend_nonzero_length,
    png_iend_truncated_crc,
    png_truncated_ihdr,
    webp_animated,
    webp_chunk_beyond_container,
    webp_dangling_byte,
    webp_incomplete_chunk_header,
    webp_riff_size_beyond,
    webp_vp8l,
    webp_vp8x_anim_flag_only,
    webp_vp8x_zero_size,
)


def test_sniff_png() -> None:
    assert sniff_image_format(png(4, 4)) == FORMAT_PNG


def test_sniff_jpeg() -> None:
    assert sniff_image_format(jpeg(4, 4)) == FORMAT_JPEG


def test_sniff_static_webp() -> None:
    assert sniff_image_format(webp_vp8l(4, 4)) == FORMAT_WEBP


def test_sniff_gif_is_none() -> None:
    assert sniff_image_format(gif()) is None


def test_png_dimensions() -> None:
    assert parse_image_dimensions(png(11, 7), FORMAT_PNG) == (11, 7)


def test_jpeg_dimensions() -> None:
    assert parse_image_dimensions(jpeg(11, 7), FORMAT_JPEG) == (11, 7)


def test_webp_dimensions() -> None:
    assert parse_image_dimensions(webp_vp8l(11, 7), FORMAT_WEBP) == (11, 7)


def test_png_static_accepted() -> None:
    validate_image_bytes(png(4, 4), FORMAT_PNG)


def test_jpeg_static_accepted() -> None:
    validate_image_bytes(jpeg(4, 4), FORMAT_JPEG)


def test_static_webp_accepted() -> None:
    validate_image_bytes(webp_vp8l(4, 4), FORMAT_WEBP)


def test_apng_rejected() -> None:
    with pytest.raises(AnimatedImageError):
        validate_image_bytes(png(4, 4, animated=True), FORMAT_PNG)


def test_animated_webp_rejected() -> None:
    with pytest.raises(AnimatedImageError):
        validate_image_bytes(webp_animated(4, 4), FORMAT_WEBP)


def test_oversized_dimension_rejected() -> None:
    with pytest.raises(OversizedDimensionError):
        validate_image_bytes(
            png(MAX_RASTER_DIMENSION + 1, 4), FORMAT_PNG
        )


def test_dimension_at_limit_accepted() -> None:
    validate_image_bytes(png(MAX_RASTER_DIMENSION, 2), FORMAT_PNG)


def test_oversized_asset_rejected() -> None:
    with pytest.raises(OversizedAssetError):
        validate_image_bytes(bytes(MAX_ASSET_BYTES + 1), FORMAT_PNG)


# -- negative / malformed container fixtures (fail closed) --------------------


def test_truncated_png_ihdr_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(png_truncated_ihdr())


def test_png_chunk_beyond_buffer_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(png_chunk_beyond_buffer())


def test_jpeg_sof_length_2_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(jpeg_sof_len_2())


def test_jpeg_truncated_segment_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(jpeg_truncated_segment())


def test_webp_vp8x_animation_flag_only_rejected() -> None:
    with pytest.raises(AnimatedImageError):
        inspect_image(webp_vp8x_anim_flag_only(4, 4))


def test_webp_vp8x_zero_size_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(webp_vp8x_zero_size())


def test_webp_chunk_beyond_container_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(webp_chunk_beyond_container())


def test_webp_riff_size_beyond_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(webp_riff_size_beyond())


# -- authoritative inspect_image facts -----------------------------------------


def test_inspect_image_returns_facts() -> None:
    data = png(11, 7)
    info = inspect_image(data)
    assert info.format == FORMAT_PNG
    assert info.mime_type == "image/png"
    assert info.byte_length == len(data)
    assert info.width == 11
    assert info.height == 7
    import hashlib

    assert info.sha256 == hashlib.sha256(data).hexdigest()


# -- PNG IEND bounds -----------------------------------------------------------


def test_valid_png_iend_passes() -> None:
    inspect_image(png(4, 4))


def test_png_iend_length_beyond_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(png_iend_length_beyond())


def test_png_iend_truncated_crc_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(png_iend_truncated_crc())


def test_png_iend_nonzero_length_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(png_iend_nonzero_length())


# -- WEBP exact exhaustion -----------------------------------------------------


def test_webp_exact_exhaustion_passes() -> None:
    inspect_image(webp_vp8l(4, 4))


def test_webp_odd_padded_chunk_passes() -> None:
    # webp_vp8l has a 5-byte payload (odd) with a single pad byte.
    inspect_image(webp_vp8l(5, 5))


def test_webp_dangling_byte_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(webp_dangling_byte())


def test_webp_incomplete_chunk_header_rejected() -> None:
    with pytest.raises(MalformedImageError):
        inspect_image(webp_incomplete_chunk_header())
