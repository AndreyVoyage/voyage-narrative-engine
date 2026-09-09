#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REFERENCE SELECTION + VISUAL CONTEXT + VISUAL PROMPT V1  (Slice B).

Offline. No provider, no network, no credentials, no real image generation, no
real Companion data root, and -- the hard rule -- NO Character Canon anywhere in
the visual chain. Every fixture snapshot is hand-built on a temp dir; the chain
runs purely from ``<snapshot_dir>/`` and ``CharacterLocalSnapshot.references``.

Covers:
  *  1-8   VisualContext bounds / request kinds / determinism
  *  9-21  deterministic local reference selection + fail-closed bundle build
  * 22-25  physical identity block rendering
  * 26-35  VisualPromptPackage assembly (fixed section order, binding, hashes)
  * 36-39  boundary rules (no-Canon, no leaked paths/bytes, constants)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import pytest

from services.character_companion.character_import.hashing import compute_sha256
from services.character_companion.character_import.local_snapshot import (
    CharacterLocalSnapshot,
    PortraitRef,
    SnapshotReference,
    SnapshotStore,
)
from services.character_companion.visual import (
    MAX_AUTO_REFS,
    MIN_AUTO_REFS,
    REQUEST_KIND_CONTEXT,
    REQUEST_KIND_CUSTOM,
    ReferenceBundleError,
    ReferenceSelectionError,
    VisualContextError,
    VisualPromptError,
    build_reference_bundle,
    build_visual_context,
    build_visual_prompt,
    render_physical_block,
    select_reference_asset_ids,
    validate_reference_bundle_integrity,
)
from services.character_companion.visual.context import MAX_DESCRIPTION_CHARS


# ============================================================ fixtures
def _png(pad: int = 48) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * pad


def _jpeg(pad: int = 48) -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * pad


def _webp(pad: int = 32) -> bytes:
    return b"RIFF" + b"\x2c\x00\x00\x00" + b"WEBP" + b"\x00" * pad


_EXT_TO_FILE_TYPE = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP"}


@dataclass
class RefSpec:
    asset_id: str
    roles: Tuple[str, ...]
    data: bytes
    ext: str = "png"
    semantic_key: Optional[str] = None


_FULL_PHYSICAL = {
    "role": "female",
    "height_cm": 170,
    "height_is_approx": False,
    "height_direction": "tall and slender",
    "weight_kg": 58,
    "weight_direction": "lean",
    "body_direction": "athletic, narrow shoulders",
    "face_direction": "oval face, high cheekbones",
    "hair_direction": "long dark hair",
    "style_direction_raw": "SECRET STYLE NOTE do-not-leak",
    "confirmed_traits": ["green eyes", "faint freckles"],
    "safety_rules": ["SECRET SAFETY RULE do-not-leak"],
    "source_preset_sha256": "0" * 64,
}


def make_snapshot(
    tmp_path: Path,
    refs: Sequence[RefSpec],
    *,
    character_id: str = "kira",
    version: str = "v1",
    physical: Optional[dict] = None,
    portrait_id: Optional[str] = None,
    data_root: Optional[Path] = None,
) -> Tuple[CharacterLocalSnapshot, Path]:
    data_root = data_root or (tmp_path / "companion-data")
    sdir = SnapshotStore(data_root).version_dir(character_id, version)
    (sdir / "references").mkdir(parents=True, exist_ok=True)

    snap_refs = []
    for spec in refs:
        rel = f"references/{spec.asset_id}.{spec.ext}"
        (sdir / rel).write_bytes(spec.data)
        snap_refs.append(
            SnapshotReference(
                asset_id=spec.asset_id,
                roles=spec.roles,
                relative_path=rel,
                sha256=compute_sha256(spec.data),
                file_type=_EXT_TO_FILE_TYPE[spec.ext],
                byte_length=len(spec.data),
                source_semantic_key=spec.semantic_key,
            )
        )

    portrait = None
    if portrait_id is not None:
        p = next(r for r in snap_refs if r.asset_id == portrait_id)
        portrait = PortraitRef(p.asset_id, p.relative_path, p.sha256)

    snap = CharacterLocalSnapshot(
        schema_version="companion_character_snapshot/0.1",
        character_id=character_id,
        snapshot_version=version,
        source_canon={
            "sourceKind": "canon",
            "sourceRef": "AI_CHARACTERS/KIRA",
            "contentHash": "a" * 64,
            "status": "APPROVED_AS_CANON",
            "sourceCharacterId": character_id.upper(),
        },
        source_preset_sha256="0" * 64,
        imported_at="2026-01-01T00:00:00Z",
        references=tuple(snap_refs),
        physical=physical if physical is not None else dict(_FULL_PHYSICAL),
        portrait=portrait,
    )
    return snap, sdir


def _kira_like(tmp_path: Path) -> Tuple[CharacterLocalSnapshot, Path]:
    """Mirrors the real KIRA v1 import: face+portrait, two body views, one expression."""
    return make_snapshot(
        tmp_path,
        [
            RefSpec("primary_face_reference", ("portrait", "face"), _png(10), "png",
                    "primary_face_reference"),
            RefSpec("body_canon_a", ("body",), _jpeg(20), "jpg", "body_canon_a"),
            RefSpec("body_canon_b", ("body",), _jpeg(30), "jpg", "body_canon_b"),
            RefSpec("expression_canon", ("expression",), _webp(16), "webp", "expression_canon"),
        ],
        portrait_id="primary_face_reference",
    )


# ==================================================== 1-8  VISUAL CONTEXT
def test_01_custom_requires_explicit_description(tmp_path):
    snap, _ = _kira_like(tmp_path)
    with pytest.raises(VisualContextError):
        build_visual_context(snapshot=snap, request_kind=REQUEST_KIND_CUSTOM)


def test_02_custom_drops_recent_messages(tmp_path):
    snap, _ = _kira_like(tmp_path)
    ctx = build_visual_context(
        snapshot=snap,
        request_kind=REQUEST_KIND_CUSTOM,
        explicit_description="Kira standing by a window in the evening",
        recent_messages=[{"role": "user", "text": "ignored"}],
    )
    assert ctx.recent_messages == ()
    assert ctx.request_kind == REQUEST_KIND_CUSTOM
    assert ctx.character_id == "kira" and ctx.character_snapshot_version == "v1"


def test_03_context_requires_scene_or_messages_or_description(tmp_path):
    snap, _ = _kira_like(tmp_path)
    with pytest.raises(VisualContextError):
        build_visual_context(snapshot=snap, request_kind=REQUEST_KIND_CONTEXT)


def test_04_recent_messages_clamped_to_last_eight(tmp_path):
    snap, _ = _kira_like(tmp_path)
    msgs = [{"role": "user" if i % 2 == 0 else "character", "text": f"m{i}"} for i in range(20)]
    ctx = build_visual_context(
        snapshot=snap, request_kind=REQUEST_KIND_CONTEXT, recent_messages=msgs
    )
    assert len(ctx.recent_messages) == 8
    assert [m.text for m in ctx.recent_messages] == [f"m{i}" for i in range(12, 20)]


def test_05_context_filters_non_dialogue_roles_and_blank_text(tmp_path):
    snap, _ = _kira_like(tmp_path)
    ctx = build_visual_context(
        snapshot=snap,
        request_kind=REQUEST_KIND_CONTEXT,
        recent_messages=[
            {"role": "system", "text": "sys"},
            {"role": "user", "text": "   "},
            {"role": "user", "text": "keep me"},
            {"role": "tool", "text": "call"},
            {"role": "character", "text": "and me"},
        ],
    )
    assert [(m.role, m.text) for m in ctx.recent_messages] == [
        ("user", "keep me"),
        ("character", "and me"),
    ]


def test_06_description_over_cap_rejected(tmp_path):
    snap, _ = _kira_like(tmp_path)
    with pytest.raises(VisualContextError):
        build_visual_context(
            snapshot=snap,
            request_kind=REQUEST_KIND_CUSTOM,
            explicit_description="x" * (MAX_DESCRIPTION_CHARS + 1),
        )


def test_07_visual_context_hash_is_deterministic(tmp_path):
    snap, _ = _kira_like(tmp_path)
    kw = dict(
        snapshot=snap,
        request_kind=REQUEST_KIND_CONTEXT,
        scene={"place": "kitchen", "time": "evening", "mood": "calm"},
        recent_messages=[{"role": "user", "text": "hi"}],
    )
    a = build_visual_context(**kw)
    b = build_visual_context(**kw)
    assert a.content_hash == b.content_hash == a.compute_hash()
    assert len(a.content_hash) == 64


def test_08_unknown_request_kind_rejected(tmp_path):
    snap, _ = _kira_like(tmp_path)
    with pytest.raises(VisualContextError):
        build_visual_context(snapshot=snap, request_kind="cinematic")


# ============================================ 9-21  REFERENCE SELECTION + BUNDLE
def test_09_auto_selection_priority_ladder(tmp_path):
    snap, _ = _kira_like(tmp_path)
    ids = select_reference_asset_ids(snap)
    assert ids == (
        "primary_face_reference",
        "body_canon_a",
        "body_canon_b",
        "expression_canon",
    )


def test_10_auto_selection_caps_at_four(tmp_path):
    snap, _ = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), _png(1)),
            RefSpec("b1", ("body",), _png(2)),
            RefSpec("b2", ("body",), _png(3)),
            RefSpec("b3", ("body",), _png(4)),
            RefSpec("b4", ("body",), _png(5)),
            RefSpec("expr", ("expression",), _png(6)),
        ],
    )
    ids = select_reference_asset_ids(snap)
    assert ids == ("face", "b1", "b2", "b3")
    assert len(ids) == MAX_AUTO_REFS


def test_11_portrait_sorts_ahead_of_plain_face(tmp_path):
    snap, _ = make_snapshot(
        tmp_path,
        [
            RefSpec("z_face_only", ("face",), _png(1)),
            RefSpec("a_portrait", ("portrait", "face"), _png(2)),
            RefSpec("body", ("body",), _png(3)),
        ],
    )
    assert select_reference_asset_ids(snap)[0] == "a_portrait"


def test_12_motion_used_as_last_support(tmp_path):
    snap, _ = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), _png(1)),
            RefSpec("mo", ("motion",), _png(2)),
        ],
    )
    assert select_reference_asset_ids(snap) == ("face", "mo")


def test_13_no_face_pool_is_fail_closed(tmp_path):
    snap, _ = make_snapshot(
        tmp_path,
        [RefSpec("b1", ("body",), _png(1)), RefSpec("b2", ("body",), _png(2))],
    )
    with pytest.raises(ReferenceSelectionError):
        select_reference_asset_ids(snap)


def test_14_sha_duplicate_reference_is_dropped(tmp_path):
    shared = _png(7)
    snap, _ = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), shared),
            RefSpec("body_dup", ("body",), shared),
            RefSpec("body_real", ("body",), _png(8)),
        ],
    )
    assert select_reference_asset_ids(snap) == ("face", "body_real")


def test_15_fewer_than_min_refs_is_fail_closed(tmp_path):
    snap, _ = make_snapshot(tmp_path, [RefSpec("face", ("portrait", "face"), _png(1))])
    with pytest.raises(ReferenceSelectionError):
        select_reference_asset_ids(snap)
    assert MIN_AUTO_REFS == 2


def test_16_explicit_asset_ids_preserve_order_and_dedupe(tmp_path):
    snap, _ = _kira_like(tmp_path)
    ids = select_reference_asset_ids(
        snap,
        explicit_asset_ids=["expression_canon", "primary_face_reference", "expression_canon"],
    )
    assert ids == ("expression_canon", "primary_face_reference")


def test_17_explicit_unknown_asset_id_rejected(tmp_path):
    snap, _ = _kira_like(tmp_path)
    with pytest.raises(ReferenceSelectionError):
        select_reference_asset_ids(snap, explicit_asset_ids=["nope"])


def test_18_build_bundle_happy_path_validates(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    assert [e.asset_id for e in bundle.references] == [
        "primary_face_reference",
        "body_canon_a",
        "body_canon_b",
        "expression_canon",
    ]
    assert bundle.character_id == "kira" and bundle.character_snapshot_version == "v1"
    assert bundle.content_hash == bundle.compute_hash()
    assert {e.content_type for e in bundle.references} == {
        "image/png",
        "image/jpeg",
        "image/webp",
    }
    for e in bundle.references:
        assert e.payload and len(e.payload) == e.byte_length
    validate_reference_bundle_integrity(bundle)


def test_19_bundle_fails_closed_on_byte_tamper(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    (sdir / "references" / "body_canon_a.jpg").write_bytes(_jpeg(999))
    with pytest.raises(ReferenceBundleError):
        build_reference_bundle(snapshot=snap, snapshot_dir=sdir)


def test_20_bundle_fails_closed_on_missing_file_and_format_mismatch(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    (sdir / "references" / "expression_canon.webp").unlink()
    with pytest.raises(ReferenceBundleError):
        build_reference_bundle(snapshot=snap, snapshot_dir=sdir)

    snap2, sdir2 = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), _png(3)),
            RefSpec("body", ("body",), _png(4)),
        ],
        data_root=tmp_path / "d2",
    )
    # declared PNG (fileType) on disk, but bytes are JPEG -> magic-byte mismatch.
    # keep byte_length + sha256 consistent with the new bytes so the format
    # check is the gate that trips (png(4) and jpeg(8) are both 12 bytes).
    tampered = _jpeg(8)
    assert len(tampered) == snap2.references[1].byte_length
    (sdir2 / "references" / "body.png").write_bytes(tampered)
    object.__setattr__(snap2.references[1], "sha256", compute_sha256(tampered))
    with pytest.raises(ReferenceBundleError):
        build_reference_bundle(snapshot=snap2, snapshot_dir=sdir2)


def test_21_bundle_integrity_check_detects_payload_drift(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    object.__setattr__(bundle.references[0], "payload", b"\x89PNG\r\n\x1a\n" + b"\xff" * 4)
    with pytest.raises(ReferenceBundleError):
        validate_reference_bundle_integrity(bundle)


# ==================================================== 22-25  PHYSICAL BLOCK
def test_22_physical_block_renders_known_facts(tmp_path):
    block = render_physical_block(_FULL_PHYSICAL, "Kira")
    assert block.startswith("CHARACTER PHYSICAL IDENTITY")
    assert "Kira:" in block
    assert "adult woman" in block
    assert "170 cm" in block
    assert "58 kg" in block
    assert "athletic, narrow shoulders" in block
    assert "face: oval face, high cheekbones" in block
    assert "hair: long dark hair" in block
    assert "confirmed traits: green eyes, faint freckles" in block


def test_23_physical_block_never_leaks_style_or_safety(tmp_path):
    block = render_physical_block(_FULL_PHYSICAL, "Kira")
    assert "SECRET STYLE NOTE" not in block
    assert "SECRET SAFETY RULE" not in block
    assert "style_direction" not in block
    assert "safety" not in block.lower()
    assert "0" * 64 not in block


def test_24_physical_block_tolerates_missing_weight_and_approx_height(tmp_path):
    prof = {
        "role": "male",
        "height_cm": 181,
        "height_is_approx": True,
        "body_direction": "broad",
    }
    block = render_physical_block(prof, "M")
    assert "approximately 181 cm" in block
    assert "kg" not in block
    assert "adult man" in block


def test_25_empty_physical_profile_renders_empty(tmp_path):
    assert render_physical_block({}, "X") == ""
    assert render_physical_block(None, "X") == ""  # type: ignore[arg-type]


# ==================================================== 26-35  VISUAL PROMPT
def _custom_ctx(snap):
    return build_visual_context(
        snapshot=snap,
        request_kind=REQUEST_KIND_CUSTOM,
        explicit_description="Kira standing by a window in the evening",
    )


def _context_ctx(snap):
    return build_visual_context(
        snapshot=snap,
        request_kind=REQUEST_KIND_CONTEXT,
        scene={"place": "small kitchen", "time": "late evening", "mood": "quiet"},
        recent_messages=[
            {"role": "user", "text": "тяжёлый день"},
            {"role": "character", "text": "я рядом"},
        ],
    )


_SECTIONS = (
    "[REQUEST]",
    "[SCENE]",
    "[RECENT CONTEXT]",
    "[CHARACTER IDENTITY]",
    "[REFERENCE GUIDANCE]",
)


def test_26_prompt_has_all_sections_in_fixed_order(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    pkg = build_visual_prompt(
        visual_context=_context_ctx(snap),
        reference_bundle=build_reference_bundle(snapshot=snap, snapshot_dir=sdir),
        physical=snap.physical,
        alias="Kira",
    )
    positions = [pkg.prompt_text.index(h) for h in _SECTIONS]
    assert positions == sorted(positions)
    assert all(h in pkg.prompt_text for h in _SECTIONS)


def test_27_custom_prompt_carries_description_and_empty_recent(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    pkg = build_visual_prompt(
        visual_context=_custom_ctx(snap),
        reference_bundle=build_reference_bundle(snapshot=snap, snapshot_dir=sdir),
        physical=snap.physical,
    )
    body = pkg.prompt_text
    assert "Kira standing by a window in the evening" in body
    recent = body.split("[RECENT CONTEXT]", 1)[1].split("[CHARACTER IDENTITY]", 1)[0]
    assert "(none)" in recent
    assert pkg.request_kind == REQUEST_KIND_CUSTOM


def test_28_context_prompt_carries_scene_and_messages(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    pkg = build_visual_prompt(
        visual_context=_context_ctx(snap),
        reference_bundle=build_reference_bundle(snapshot=snap, snapshot_dir=sdir),
        physical=snap.physical,
        alias="Kira",
    )
    body = pkg.prompt_text
    assert "place: small kitchen" in body
    assert "user: тяжёлый день" in body
    assert "character: я рядом" in body


def test_29_prompt_is_deterministic(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    ctx = _context_ctx(snap)
    a = build_visual_prompt(visual_context=ctx, reference_bundle=bundle, physical=snap.physical)
    b = build_visual_prompt(visual_context=ctx, reference_bundle=bundle, physical=snap.physical)
    assert a.prompt_text == b.prompt_text
    assert a.content_hash == b.content_hash == a.compute_hash()
    assert len(a.content_hash) == 64


def test_30_prompt_binds_context_and_bundle_hashes(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    ctx = _custom_ctx(snap)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    pkg = build_visual_prompt(visual_context=ctx, reference_bundle=bundle, physical=snap.physical)
    assert pkg.visual_context_hash == ctx.content_hash
    assert pkg.reference_bundle_hash == bundle.content_hash
    assert pkg.character_id == "kira" and pkg.character_snapshot_version == "v1"


def test_31_prompt_rejects_character_id_mismatch(tmp_path):
    snap_a, sdir_a = _kira_like(tmp_path)
    snap_b, sdir_b = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), _png(1)),
            RefSpec("body", ("body",), _png(2)),
        ],
        character_id="mara",
        data_root=tmp_path / "mara-data",
    )
    ctx = _custom_ctx(snap_a)
    other_bundle = build_reference_bundle(snapshot=snap_b, snapshot_dir=sdir_b)
    with pytest.raises(VisualPromptError):
        build_visual_prompt(visual_context=ctx, reference_bundle=other_bundle, physical={})


def test_32_prompt_rejects_snapshot_version_mismatch(tmp_path):
    snap_v1, sdir_v1 = _kira_like(tmp_path)
    snap_v2, sdir_v2 = make_snapshot(
        tmp_path,
        [
            RefSpec("face", ("portrait", "face"), _png(1)),
            RefSpec("body", ("body",), _png(2)),
        ],
        version="v2",
    )
    ctx = _custom_ctx(snap_v1)
    bundle_v2 = build_reference_bundle(snapshot=snap_v2, snapshot_dir=sdir_v2)
    with pytest.raises(VisualPromptError):
        build_visual_prompt(visual_context=ctx, reference_bundle=bundle_v2, physical={})


def test_33_prompt_reference_guidance_names_ids_and_roles_only(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    pkg = build_visual_prompt(visual_context=_custom_ctx(snap), reference_bundle=bundle, physical={})
    guidance = pkg.prompt_text.split("[REFERENCE GUIDANCE]", 1)[1]
    assert "primary_face_reference [roles: portrait, face]" in guidance
    assert "references/" not in pkg.prompt_text
    assert ".png" not in pkg.prompt_text and ".jpg" not in pkg.prompt_text
    assert str(sdir) not in pkg.prompt_text
    assert "\\x89PNG" not in pkg.prompt_text and "PNG\r\n" not in pkg.prompt_text


def test_34_prompt_works_without_physical(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    pkg = build_visual_prompt(visual_context=_custom_ctx(snap), reference_bundle=bundle)
    ci = pkg.prompt_text.split("[CHARACTER IDENTITY]", 1)[1].split("[REFERENCE GUIDANCE]", 1)[0]
    assert "character: kira (snapshot v1)" in ci
    assert "CHARACTER PHYSICAL IDENTITY" not in ci


def test_35_prompt_rejects_empty_reference_bundle(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    empty = build_reference_bundle(
        snapshot=snap, snapshot_dir=sdir, explicit_asset_ids=["primary_face_reference"]
    )
    object.__setattr__(empty, "references", ())
    with pytest.raises(VisualPromptError):
        build_visual_prompt(visual_context=_custom_ctx(snap), reference_bundle=empty, physical={})


# ==================================================== 36-39  BOUNDARY
def test_36_full_chain_runs_with_no_canon_root(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    ctx = build_visual_context(
        snapshot=snap,
        request_kind=REQUEST_KIND_CONTEXT,
        scene={"place": "window", "time": "evening"},
        recent_messages=[{"role": "user", "text": "посиди со мной"}],
    )
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    pkg = build_visual_prompt(visual_context=ctx, reference_bundle=bundle, physical=snap.physical)
    validate_reference_bundle_integrity(bundle)
    assert pkg.content_hash and pkg.prompt_text
    # nothing in the fixture tree resembles a Character Canon layout
    assert not list(tmp_path.rglob("AI_CHARACTERS"))
    assert not list(tmp_path.rglob("*_REFERENCE_PRESETS.json"))


def test_37_selection_errors_carry_no_absolute_paths(tmp_path):
    snap, sdir = make_snapshot(
        tmp_path, [RefSpec("b", ("body",), _png(1)), RefSpec("b2", ("body",), _png(2))]
    )
    try:
        select_reference_asset_ids(snap)
    except ReferenceSelectionError as exc:
        assert str(tmp_path) not in str(exc)
        assert "references/" not in str(exc)
    else:  # pragma: no cover
        pytest.fail("expected ReferenceSelectionError")


def test_38_bundle_entries_keep_bytes_but_prompt_does_not(tmp_path):
    snap, sdir = _kira_like(tmp_path)
    bundle = build_reference_bundle(snapshot=snap, snapshot_dir=sdir)
    assert all(isinstance(e.payload, bytes) and e.payload for e in bundle.references)
    pkg = build_visual_prompt(visual_context=_custom_ctx(snap), reference_bundle=bundle, physical={})
    for e in bundle.references:
        assert e.sha256 not in pkg.prompt_text
        assert e.relative_path not in pkg.prompt_text


def test_39_selection_bounds_match_published_constants(tmp_path):
    assert (MIN_AUTO_REFS, MAX_AUTO_REFS) == (2, 4)
    snap, _ = _kira_like(tmp_path)
    assert MIN_AUTO_REFS <= len(select_reference_asset_ids(snap)) <= MAX_AUTO_REFS
