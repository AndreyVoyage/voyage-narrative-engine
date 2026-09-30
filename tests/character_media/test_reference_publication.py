#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VCP-gated publication tests for the Character Reference Library slice."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests._vcp_dependency_gate import require_pinned_vcp

require_pinned_vcp()  # hard VCP dependency gate

from services.character_authoring import (  # noqa: E402
    ApprovalEvidence,
    CharacterAuthoringStore,
    LifecycleState,
)
from services.character_media import (  # noqa: E402
    CharacterMediaStore,
    MediaPublishability,
)
from services.character_publication.vcp_domains import (  # noqa: E402
    AuthoringVcpVisualMappingError,
)
from services.character_publication.vcp_release import (  # noqa: E402
    compile_authoring_release,
)
from voyage_character_platform.package_v1 import (  # noqa: E402
    materialize_package_v1,
    verify_package_v1,
)
from voyage_character_platform.vchar import (  # noqa: E402
    extract_vchar_v1,
    write_vchar_v1,
)

from tests.character_media._images import jpeg, png, webp_vp8l  # noqa: E402

DECIDED_AT = "2026-01-01T00:00:00Z"
DECIDED_BY = "test-owner"

ROLES = ("face", "body", "expression", "identity", "motion")
ROLE_TOKENS = {
    "face": "FACE",
    "body": "BODY",
    "expression": "EXPRESSION",
    "identity": "IDENTITY",
    "motion": "MOTION",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _semantic(visual_identity: dict) -> dict:
    return {
        "identity": {"display_name": "Synth"},
        "biography": "synthetic",
        "psychology": {
            "personality": [],
            "behavioral_traits": [],
            "emotional_tendencies": [],
            "goals_motivations": [],
        },
        "speech": {"speech_style": "plain", "register": None},
        "character_relations": {
            "relational_tendencies": [],
            "attachment_traits": [],
        },
        "appearance": {"descriptors": ["plain"]},
        "boundaries": {"principles": []},
        "visual_identity": visual_identity,
    }


@pytest.fixture
def lab(tmp_path: Path):
    authoring = CharacterAuthoringStore(tmp_path / "authoring")
    media = CharacterMediaStore(tmp_path / "character_media")
    authoring.create_character("synth")
    authoring.create_version("synth", "v1", version_label="V1")
    return authoring, media, tmp_path


def _persist(authoring: CharacterAuthoringStore, revision_id: str, semantic: dict):
    record = authoring.persist_revision(
        "synth", "v1", revision_id, semantic, lifecycle_state=LifecycleState.DRAFT
    )
    authoring.persist_approval_evidence(
        ApprovalEvidence(
            character_id="synth",
            version_id="v1",
            revision_id=revision_id,
            snapshot_hash=record.snapshot_hash,
            decided_by=DECIDED_BY,
            decided_at=DECIDED_AT,
        )
    )
    return record


def _compile(authoring: CharacterAuthoringStore, revision_id: str):
    record = authoring.load_revision("synth", "v1", revision_id)
    return compile_authoring_release(
        authoring,
        character_id="synth",
        version_id="v1",
        revision_id=revision_id,
        snapshot_hash=record.snapshot_hash,
        release_id=f"rel-{revision_id}",
        display_name="Synth",
    )


def _write(tmp: Path, name: str, data: bytes) -> Path:
    path = tmp / name
    path.write_bytes(data)
    return path


def _visual_identity(portrait: dict | None = None, references: list | None = None) -> dict:
    vi: dict = {"references": [] if references is None else references}
    if portrait is not None:
        vi["primary_portrait"] = portrait
    return vi


def _asset_refs(compilation):
    vi = next(d for d in compilation.domains if d.domain_id == "visual_identity")
    return vi.structured["assetRefs"]


# -- A/B/C/D/E: each role imports, binds, publishes ------------------------


@pytest.mark.parametrize("role", ROLES)
def test_each_reference_role_publishes(lab, role) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, f"{role}.png", image), "synth")
    binding = record.reference_binding(role, MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))

    compilation = _compile(authoring, "r1")
    refs = _asset_refs(compilation)
    assert len(refs) == 1
    assert refs[0]["semanticRole"] == ROLE_TOKENS[role]
    assert refs[0]["assetId"] == f"{role}:{record.asset_sha256}"
    expected_path = f"assets/references/{record.asset_sha256}.png"
    assert refs[0]["relativePath"] == expected_path
    assert compilation.files[expected_path].content == image


# -- F: multiple references in one revision --------------------------------


def test_multiple_references_in_one_revision(lab) -> None:
    authoring, media, tmp = lab
    refs = []
    sizes = {"face": (5, 5), "body": (5, 6), "expression": (6, 5)}
    for role in ("face", "body", "expression"):
        w, h = sizes[role]
        image = png(w, h)
        record = media.import_portrait(_write(tmp, f"{role}.png", image), "synth")
        refs.append(record.reference_binding(role, MediaPublishability.PUBLISHABLE).to_dict())
    _persist(authoring, "r1", _semantic(_visual_identity(references=refs)))

    compilation = _compile(authoring, "r1")
    asset_refs = _asset_refs(compilation)
    assert {r["semanticRole"] for r in asset_refs} == {"FACE", "BODY", "EXPRESSION"}
    reference_files = [p for p in compilation.files if p.startswith("assets/references/")]
    assert len(reference_files) == 3


# -- G: same SHA, FACE + IDENTITY -> one physical managed file -------------


def test_same_sha_two_roles_one_physical_file(lab) -> None:
    authoring, media, tmp = lab
    image = png(6, 6)
    record = media.import_portrait(_write(tmp, "shared.png", image), "synth")
    face = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    identity = record.reference_binding("identity", MediaPublishability.PUBLISHABLE)
    _persist(
        authoring,
        "r1",
        _semantic(_visual_identity(references=[face.to_dict(), identity.to_dict()])),
    )

    files = list((media.root / "synth").glob("*.png"))
    assert len(files) == 1

    compilation = _compile(authoring, "r1")
    asset_refs = _asset_refs(compilation)
    assert len(asset_refs) == 2
    assert {r["semanticRole"] for r in asset_refs} == {"FACE", "IDENTITY"}
    reference_paths = [
        r["relativePath"]
        for r in asset_refs
        if r["relativePath"].startswith("assets/references/")
    ]
    assert len(set(reference_paths)) == 1


# -- H: Primary Portrait SHA reused as FACE -> one physical file -----------


def test_portrait_sha_reused_as_reference(lab) -> None:
    authoring, media, tmp = lab
    image = png(7, 7)
    record = media.import_portrait(_write(tmp, "portrait.png", image), "synth")
    portrait = record.binding(MediaPublishability.PUBLISHABLE)
    face = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    _persist(
        authoring,
        "r1",
        _semantic(_visual_identity(portrait=portrait.to_dict(), references=[face.to_dict()])),
    )

    compilation = _compile(authoring, "r1")
    asset_refs = _asset_refs(compilation)
    assert {r["semanticRole"] for r in asset_refs} == {"PRIMARY_PORTRAIT", "FACE"}

    portrait_path = f"assets/portrait/{record.asset_sha256}.png"
    assert all(
        r["relativePath"] == portrait_path
        for r in asset_refs
        if r["semanticRole"] == "FACE"
    )
    assert portrait_path in compilation.files
    assert not any(p.startswith("assets/references/") for p in compilation.files)


# -- I: new revision adds reference without mutating prior -----------------


def test_new_revision_adds_reference_without_mutating_prior(lab) -> None:
    authoring, media, tmp = lab
    rec_a = media.import_portrait(_write(tmp, "a.png", png(4, 4)), "synth")
    rec_b = media.import_portrait(_write(tmp, "b.png", png(5, 5)), "synth")
    rec_c = media.import_portrait(_write(tmp, "c.png", png(6, 6)), "synth")

    face = rec_a.reference_binding("face", MediaPublishability.PUBLISHABLE)
    body = rec_b.reference_binding("body", MediaPublishability.PUBLISHABLE)
    expression = rec_c.reference_binding("expression", MediaPublishability.PUBLISHABLE)

    r1 = _persist(
        authoring,
        "r1",
        _semantic(_visual_identity(references=[face.to_dict(), body.to_dict()])),
    )
    r1_snapshot = r1.snapshot_hash
    _persist(
        authoring,
        "r2",
        _semantic(
            _visual_identity(
                references=[face.to_dict(), body.to_dict(), expression.to_dict()]
            )
        ),
    )

    r1_loaded = authoring.load_revision("synth", "v1", "r1")
    assert r1_loaded.snapshot_hash == r1_snapshot
    assert r1_loaded.semantic.to_dict()["visual_identity"]["references"] == [
        face.to_dict(),
        body.to_dict(),
    ]
    assert (
        r1_loaded.semantic.to_dict()["visual_identity"]["references"][0]["asset_sha256"]
        == rec_a.asset_sha256
    )


# -- J/K: publishability filtering ----------------------------------------


def test_authoring_only_reference_excluded(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "ao.png", image), "synth")
    binding = record.reference_binding("face", MediaPublishability.AUTHORING_ONLY)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))

    compilation = _compile(authoring, "r1")
    assert _asset_refs(compilation) == []
    assert not any(p.startswith("assets/references/") for p in compilation.files)


def test_publishable_reference_included(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "pub.png", image), "synth")
    binding = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))

    compilation = _compile(authoring, "r1")
    assert len(_asset_refs(compilation)) == 1


# -- L/Y: unknown role / legacy path reference fail closed -----------------


def test_unknown_role_rejected_at_publication(lab) -> None:
    authoring, _media, _tmp = lab
    _persist(
        authoring,
        "r1",
        _semantic(
            _visual_identity(
                references=[
                    {
                        "role": "pose",
                        "asset_sha256": "a" * 64,
                        "format": "PNG",
                        "mime_type": "image/png",
                        "byte_length": 10,
                        "publishability": "PUBLISHABLE",
                    }
                ]
            )
        ),
    )
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_legacy_path_reference_does_not_silently_publish(lab) -> None:
    authoring, _media, _tmp = lab
    _persist(
        authoring,
        "r1",
        _semantic(
            _visual_identity(references=[{"key": "legacy", "path": "characters/x/face.png"}])
        ),
    )
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


# -- O/P/Q: missing / tampered / mismatched reference ----------------------


def test_missing_managed_reference_fails_publication(lab) -> None:
    authoring, _media, _tmp = lab
    image = png(4, 4)
    _persist(
        authoring,
        "r1",
        _semantic(
            _visual_identity(
                references=[
                    {
                        "role": "face",
                        "asset_sha256": sha(image),
                        "format": "PNG",
                        "mime_type": "image/png",
                        "byte_length": len(image),
                        "publishability": "PUBLISHABLE",
                    }
                ]
            )
        ),
    )
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_tampered_managed_reference_fails_publication(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "t.png", image), "synth")
    path = media.managed_path("synth", record.asset_sha256, "PNG")
    path.write_bytes(path.read_bytes() + b"\x00")
    binding = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_format_mime_mismatch_fails_publication(lab) -> None:
    authoring, _media, _tmp = lab
    image = jpeg(4, 4)
    _persist(
        authoring,
        "r1",
        _semantic(
            _visual_identity(
                references=[
                    {
                        "role": "face",
                        "asset_sha256": sha(image),
                        "format": "PNG",  # wrong: actual bytes are JPEG
                        "mime_type": "image/png",
                        "byte_length": len(image),
                        "publishability": "PUBLISHABLE",
                    }
                ]
            )
        ),
    )
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


# -- R/S/T: exact assetRefs / role-qualified ids / dedup -------------------


def test_multiple_asset_refs_exact(lab) -> None:
    authoring, media, tmp = lab
    image = png(8, 8)
    record = media.import_portrait(_write(tmp, "exact.png", image), "synth")
    binding = record.reference_binding("identity", MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))

    compilation = _compile(authoring, "r1")
    ref = _asset_refs(compilation)[0]
    assert ref["assetId"] == f"identity:{record.asset_sha256}"
    assert ref["relativePath"] == f"assets/references/{record.asset_sha256}.png"
    assert ref["sha256"] == record.asset_sha256
    assert ref["byteLength"] == record.byte_length
    assert ref["mediaType"] == "image/png"
    assert ref["semanticRole"] == "IDENTITY"


def test_role_qualified_asset_ids_unique(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "u.png", image), "synth")
    face = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    identity = record.reference_binding("identity", MediaPublishability.PUBLISHABLE)
    _persist(
        authoring,
        "r1",
        _semantic(_visual_identity(references=[face.to_dict(), identity.to_dict()])),
    )
    compilation = _compile(authoring, "r1")
    asset_ids = [r["assetId"] for r in _asset_refs(compilation)]
    assert asset_ids == [f"face:{record.asset_sha256}", f"identity:{record.asset_sha256}"]
    assert len(set(asset_ids)) == 2


def test_multi_role_physical_package_not_duplicated(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "m.png", image), "synth")
    face = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    identity = record.reference_binding("identity", MediaPublishability.PUBLISHABLE)
    _persist(
        authoring,
        "r1",
        _semantic(_visual_identity(references=[face.to_dict(), identity.to_dict()])),
    )
    compilation = _compile(authoring, "r1")
    ref_paths = [p for p in compilation.files if p.startswith("assets/references/")]
    assert len(ref_paths) == 1


# -- U: packageHash changes when published reference set changes -----------


def test_package_hash_changes_when_reference_set_changes(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "h.png", image), "synth")
    binding = record.reference_binding("face", MediaPublishability.PUBLISHABLE)

    _persist(authoring, "r1", _semantic(_visual_identity(references=[])))
    _persist(
        authoring,
        "r2",
        _semantic(_visual_identity(references=[binding.to_dict()])),
    )

    c1 = _compile(authoring, "r1")
    c2 = _compile(authoring, "r2")
    m1 = materialize_package_v1(tmp / "pkg1", files=dict(c1.files))
    m2 = materialize_package_v1(tmp / "pkg2", files=dict(c2.files))
    assert m1.package_hash != m2.package_hash


# -- V: clean extract returns exact reference bytes ------------------------


def test_clean_extract_returns_exact_reference_bytes(lab) -> None:
    authoring, media, tmp = lab
    image = png(6, 5)
    record = media.import_portrait(_write(tmp, "v.png", image), "synth")
    binding = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))

    compilation = _compile(authoring, "r1")
    package_root = tmp / "pkg"
    materialize_package_v1(package_root, files=dict(compilation.files))
    verify_package_v1(package_root)
    vchar = tmp / "out.vchar"
    write_vchar_v1(package_root, vchar)
    roundtrip = extract_vchar_v1(vchar, tmp / "rt")

    refs = [
        p
        for p in roundtrip.root.rglob("*")
        if p.is_file()
        and p.relative_to(roundtrip.root).as_posix().startswith("assets/references/")
    ]
    assert len(refs) == 1
    assert refs[0].read_bytes() == image
    assert sha(refs[0].read_bytes()) == record.asset_sha256


# -- W/X: portrait-only and media-free still valid -------------------------


def test_portrait_only_package_still_valid(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "w.png", image), "synth")
    portrait = record.binding(MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(portrait=portrait.to_dict())))
    compilation = _compile(authoring, "r1")
    materialize_package_v1(tmp / "pkg", files=dict(compilation.files))
    verify_package_v1(tmp / "pkg")


def test_media_free_package_still_valid(lab) -> None:
    authoring, _media, tmp = lab
    _persist(authoring, "r1", _semantic(_visual_identity()))
    compilation = _compile(authoring, "r1")
    materialize_package_v1(tmp / "pkg", files=dict(compilation.files))
    verify_package_v1(tmp / "pkg")


# -- Z: PNG/JPEG/static WEBP reuse existing validator ----------------------


@pytest.mark.parametrize(
    "builder,name,mime",
    [
        (png, "z.png", "image/png"),
        (jpeg, "z.jpg", "image/jpeg"),
        (webp_vp8l, "z.webp", "image/webp"),
    ],
)
def test_supported_formats_reuse_validator(lab, builder, name, mime) -> None:
    authoring, media, tmp = lab
    image = builder(4, 4)
    record = media.import_portrait(_write(tmp, name, image), "synth")
    binding = record.reference_binding("face", MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(_visual_identity(references=[binding.to_dict()])))
    compilation = _compile(authoring, "r1")
    ref = _asset_refs(compilation)[0]
    assert ref["mediaType"] == mime
    assert compilation.files[ref["relativePath"]].content == image
