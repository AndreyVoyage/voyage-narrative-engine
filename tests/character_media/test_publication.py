#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VCP-gated publication tests for the managed Primary Portrait slice."""

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
    PortraitBinding,
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
from voyage_character_platform.vchar import extract_vchar_v1, write_vchar_v1  # noqa: E402

from tests.character_media._images import jpeg, png  # noqa: E402

DECIDED_AT = "2026-01-01T00:00:00Z"
DECIDED_BY = "test-owner"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _semantic(binding: PortraitBinding | None = None) -> dict:
    visual_identity: dict = {"references": []}
    if binding is not None:
        visual_identity["primary_portrait"] = binding.to_dict()
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



def test_publishable_portrait_included_and_roundtrip(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    source = tmp / "portrait.png"
    source.write_bytes(image)
    record = media.import_portrait(source, "synth")
    binding = record.binding(MediaPublishability.PUBLISHABLE)

    _persist(authoring, "r1", _semantic(binding))
    compilation = _compile(authoring, "r1")

    package_root = tmp / "pkg"
    materialize_package_v1(package_root, files=dict(compilation.files))
    verified = verify_package_v1(package_root)

    vchar = tmp / "out.vchar"
    write_vchar_v1(package_root, vchar)
    roundtrip = extract_vchar_v1(vchar, tmp / "rt")

    portrait_files = [
        p
        for p in roundtrip.root.rglob("*")
        if p.is_file()
        and p.relative_to(roundtrip.root).as_posix().startswith("assets/portrait/")
    ]
    assert len(portrait_files) == 1
    assert portrait_files[0].read_bytes() == image
    assert sha(portrait_files[0].read_bytes()) == record.asset_sha256
    assert verified.package_hash == roundtrip.package_hash


def test_authoring_only_portrait_excluded(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    source = tmp / "portrait.png"
    source.write_bytes(image)
    record = media.import_portrait(source, "synth")
    binding = record.binding(MediaPublishability.AUTHORING_ONLY)

    _persist(authoring, "r1", _semantic(binding))
    compilation = _compile(authoring, "r1")

    assert "assets/portrait" not in " ".join(compilation.files)
    vi = next(d for d in compilation.domains if d.domain_id == "visual_identity")
    assert vi.structured.get("assetRefs") == []


def test_package_hash_changes_when_portrait_changes(lab) -> None:
    authoring, media, tmp = lab
    image_a = png(4, 4)
    image_b = png(5, 3)
    rec_a = media.import_portrait(_write(tmp, "a.png", image_a), "synth")
    rec_b = media.import_portrait(_write(tmp, "b.png", image_b), "synth")
    assert rec_a.asset_sha256 != rec_b.asset_sha256

    _persist(authoring, "r1", _semantic(rec_a.binding(MediaPublishability.PUBLISHABLE)))
    _persist(authoring, "r2", _semantic(rec_b.binding(MediaPublishability.PUBLISHABLE)))

    comp_a = _compile(authoring, "r1")
    comp_b = _compile(authoring, "r2")

    pkg_a = tmp / "pkg_a"
    pkg_b = tmp / "pkg_b"
    materialize_package_v1(pkg_a, files=dict(comp_a.files))
    materialize_package_v1(pkg_b, files=dict(comp_b.files))
    hash_a = verify_package_v1(pkg_a).package_hash
    hash_b = verify_package_v1(pkg_b).package_hash
    assert hash_a != hash_b


def test_media_free_package_still_verifies(lab) -> None:
    authoring, media, tmp = lab
    _persist(authoring, "r1", _semantic(None))
    compilation = _compile(authoring, "r1")

    assert "assets" not in " ".join(compilation.files)
    package_root = tmp / "pkg"
    materialize_package_v1(package_root, files=dict(compilation.files))
    verify_package_v1(package_root)


def test_publication_format_mismatch_fails_closed(lab) -> None:
    authoring, media, tmp = lab
    image = jpeg(4, 4)
    record = media.import_portrait(_write(tmp, "p.jpg", image), "synth")
    # Manually place the JPEG bytes at the path a PNG binding would resolve,
    # then bind format=PNG. The actual bytes are JPEG -> publication must fail.
    media._publish_bytes_no_clobber(
        media.managed_path("synth", record.asset_sha256, "PNG"),
        image,
        record.asset_sha256,
    )
    binding = PortraitBinding(
        asset_sha256=record.asset_sha256,
        format="PNG",
        mime_type="image/png",
        byte_length=record.byte_length,
        publishability=MediaPublishability.PUBLISHABLE,
    )
    _persist(authoring, "r1", _semantic(binding))
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_publication_mime_mismatch_fails_closed(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)  # actual PNG bytes
    asset_sha256 = sha(image)
    # Place PNG bytes at the .jpg path, then bind format=JPEG + image/jpeg.
    # The binding is internally consistent, but the actual bytes are PNG, so
    # re-sniffing detects the MIME/format mismatch and publication fails.
    media._publish_bytes_no_clobber(
        media.managed_path("synth", asset_sha256, "JPEG"), image, asset_sha256
    )
    binding = PortraitBinding(
        asset_sha256=asset_sha256,
        format="JPEG",
        mime_type="image/jpeg",
        byte_length=len(image),
        publishability=MediaPublishability.PUBLISHABLE,
    )
    _persist(authoring, "r1", _semantic(binding))
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_publication_missing_asset_fails(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    asset_sha256 = sha(image)
    binding = PortraitBinding(
        asset_sha256=asset_sha256,
        format="PNG",
        mime_type="image/png",
        byte_length=len(image),
        publishability=MediaPublishability.PUBLISHABLE,
    )
    _persist(authoring, "r1", _semantic(binding))
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_publication_tampered_asset_fails(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "p.png", image), "synth")
    path = media.managed_path("synth", record.asset_sha256, "PNG")
    path.write_bytes(path.read_bytes() + b"\x00")  # tamper
    binding = record.binding(MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(binding))
    with pytest.raises(AuthoringVcpVisualMappingError):
        _compile(authoring, "r1")


def test_asset_ref_matches_actual_bytes(lab) -> None:
    authoring, media, tmp = lab
    image = png(4, 4)
    record = media.import_portrait(_write(tmp, "p.png", image), "synth")
    binding = record.binding(MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(binding))
    compilation = _compile(authoring, "r1")

    vi = next(d for d in compilation.domains if d.domain_id == "visual_identity")
    refs = vi.structured["assetRefs"]
    assert len(refs) == 1
    ref = refs[0]
    relative_path = f"assets/portrait/{record.asset_sha256}.png"
    assert ref["assetId"] == record.asset_sha256
    assert ref["relativePath"] == relative_path
    assert ref["sha256"] == record.asset_sha256
    assert ref["byteLength"] == record.byte_length
    assert ref["mediaType"] == "image/png"
    assert ref["semanticRole"] == "PRIMARY_PORTRAIT"
    # The RAW package file must match the actual bytes.
    assert compilation.files[relative_path].content == image
    assert compilation.files[relative_path].semantic_role == "PRIMARY_PORTRAIT"


def test_portability_e2e_source_deleted_before_publication(lab) -> None:
    authoring, media, tmp = lab
    image = png(6, 5)
    source = tmp / "source.png"
    source.write_bytes(image)
    record = media.import_portrait(source, "synth")
    binding = record.binding(MediaPublishability.PUBLISHABLE)
    _persist(authoring, "r1", _semantic(binding))

    source.unlink()  # original source deleted BEFORE publication

    compilation = _compile(authoring, "r1")
    package_root = tmp / "pkg"
    materialize_package_v1(package_root, files=dict(compilation.files))
    verify_package_v1(package_root)
    vchar = tmp / "out.vchar"
    write_vchar_v1(package_root, vchar)
    roundtrip = extract_vchar_v1(vchar, tmp / "rt")

    portraits = [
        p
        for p in roundtrip.root.rglob("*")
        if p.is_file()
        and p.relative_to(roundtrip.root).as_posix().startswith("assets/portrait/")
    ]
    assert len(portraits) == 1
    assert portraits[0].read_bytes() == image
    assert sha(portraits[0].read_bytes()) == record.asset_sha256

