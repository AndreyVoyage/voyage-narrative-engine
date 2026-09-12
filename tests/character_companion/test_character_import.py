#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHARACTER LOCAL SNAPSHOT + CONTROLLED CANON IMPORT V1.

Offline. Temp fixtures only -- no real Character Canon, no real Companion data
root, no provider, no network, no credentials. Proves the Companion-owned
versioned local visual snapshot layer and the controlled, read-only,
production-gated Canon import (vendored/adapted from the VNE repo per
docs/character_companion/VISUAL_PIPELINE_VENDOR_PROVENANCE_V1.md).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from services.character_companion.character_import import (
    IMPORTED,
    NO_OP_UNCHANGED,
    UPDATED_NEW_VERSION,
    AmbiguousCharacterError,
    AssetIdCollisionError,
    CanonFormatError,
    CanonStatusUnknownError,
    CharacterImportService,
    CharacterLocalSnapshot,
    FormatMismatchError,
    ProductionNotAllowedError,
    ReferencePathSafetyError,
    ReferenceValidationError,
    SnapshotNotFoundError,
    SnapshotOperationError,
    SnapshotStore,
    SnapshotValidationError,
    import_reference,
)
from services.character_companion.character_import.canon_reader import read_standing_identity
from services.character_companion.character_import.hashing import compute_sha256
from services.character_companion.character_import.local_snapshot import (
    SnapshotReference,
    StandingIdentity,
    StandingIdentityCategory,
    StandingIdentitySource,
)
from services.character_companion.character_import.reference_manifest import REFERENCES_DIR

CHAR = "KIRA_TEST"


# ------------------------------------------------------------- fixtures
def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 48


def _jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 48


def _webp() -> bytes:
    return b"RIFF" + b"\x2c\x00\x00\x00" + b"WEBP" + b"\x00" * 32


_DEFAULT_IDENTITY = {
    "role": "female",
    "height_cm": 170,
    "height_direction": "tall and slender",
    "weight_direction": "lean",
    "body_direction": "athletic build",
    "face_direction": "oval face",
    "hair_direction": "long dark hair",
    "style_direction": "casual modern",
}


def make_canon(
    tmp_path: Path,
    *,
    character_id: str = CHAR,
    declared_character: str | None = None,
    status: str = "APPROVED_AS_CANON",
    active_canon: dict | None = None,
    identity: dict | None = None,
    write_files: bool = True,
    file_bytes: dict | None = None,
    dirname: str = "canon",
    standing_identity: dict | None = None,
) -> Path:
    canon_root = tmp_path / dirname
    gen_rel = f"AI_CHARACTERS/{character_id}/07_generated"
    if active_canon is None:
        active_canon = {
            "primary_face_reference": f"{gen_rel}/face.png",
            "body_canon_a": f"{gen_rel}/body.jpg",
            "expression_canon": f"{gen_rel}/expr.webp",
        }
    if file_bytes is None:
        file_bytes = {"face.png": _png(), "body.jpg": _jpeg(), "expr.webp": _webp()}

    preset = {
        "character": declared_character if declared_character is not None else character_id,
        "status": status,
        "active_canon": active_canon,
        "scene_presets": {"bar": {"reference_images": [f"{gen_rel}/scene1.png"]}},
        "identity_summary": identity if identity is not None else dict(_DEFAULT_IDENTITY),
        "identity_confirmed_traits": ["green eyes", "faint freckles"],
        "safety_rules": ["adults only; no minors"],
    }
    if standing_identity is not None:
        preset["standing_identity"] = standing_identity
    notes_dir = canon_root / "AI_CHARACTERS" / character_id / "10_notes"
    notes_dir.mkdir(parents=True)
    (notes_dir / f"{character_id}_REFERENCE_PRESETS.json").write_text(
        json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if write_files:
        gen_dir = canon_root / "AI_CHARACTERS" / character_id / "07_generated"
        gen_dir.mkdir(parents=True, exist_ok=True)
        for name, data in file_bytes.items():
            (gen_dir / name).write_bytes(data)
        (gen_dir / "scene1.png").write_bytes(_png())
    return canon_root


def _service(tmp_path) -> CharacterImportService:
    return CharacterImportService(tmp_path / "companion-data")


def _canon_listing(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


# ================================================================ CANON
def test_01_known_production_status_accepted(tmp_path):
    res = _service(tmp_path).import_character(make_canon(tmp_path), CHAR, "add")
    assert res.status == IMPORTED and res.snapshot_version == "v1"


def test_02_non_production_status_rejected(tmp_path):
    with pytest.raises(ProductionNotAllowedError):
        _service(tmp_path).import_character(
            make_canon(tmp_path, status="APPROVED_AS_LOCAL"), CHAR, "add"
        )


def test_03_legacy_bare_approved_rejected_for_production(tmp_path):
    with pytest.raises(ProductionNotAllowedError):
        _service(tmp_path).import_character(
            make_canon(tmp_path, status="APPROVED"), CHAR, "add"
        )


def test_04_unknown_status_rejected(tmp_path):
    with pytest.raises(CanonStatusUnknownError):
        _service(tmp_path).import_character(
            make_canon(tmp_path, status="WOBBLE_STATE"), CHAR, "add"
        )


def test_05_character_id_mismatch_rejected(tmp_path):
    with pytest.raises(AmbiguousCharacterError):
        _service(tmp_path).import_character(
            make_canon(tmp_path, declared_character="SOMEONE_ELSE"), CHAR, "add"
        )


def test_06_unsafe_source_relative_path_rejected(tmp_path):
    canon = make_canon(
        tmp_path,
        active_canon={"primary_face_reference": "../../../etc/passwd.png"},
        file_bytes={},
    )
    with pytest.raises(ReferencePathSafetyError):
        _service(tmp_path).import_character(canon, CHAR, "add")


def test_07_canon_never_written(tmp_path):
    canon = make_canon(tmp_path)
    before = _canon_listing(canon)
    before_hash = {p: p.read_bytes() for p in canon.rglob("*") if p.is_file()}
    _service(tmp_path).import_character(canon, CHAR, "add")
    assert _canon_listing(canon) == before
    assert {p: p.read_bytes() for p in canon.rglob("*") if p.is_file()} == before_hash


# ================================================== REFERENCE IMPORT
@pytest.mark.parametrize("name,data,ftype", [
    ("face.png", _png(), "PNG"), ("body.jpg", _jpeg(), "JPEG"), ("expr.webp", _webp(), "WEBP"),
])
def test_08_09_10_formats_accepted_by_bytes(tmp_path, name, data, ftype):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    src = tmp_path / name
    src.write_bytes(data)
    out = import_reference(
        src, snapshot_dir=snap, asset_id=f"a_{ftype.lower()}", character_id="kira",
        manifest_path=snap / "references.manifest.json",
    )
    assert out.status == "IMPORTED" and out.record.file_type == ftype
    assert (snap / out.relative_path).read_bytes() == data


def test_11_extension_signature_mismatch_rejected(tmp_path):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    src = tmp_path / "actually_jpeg.png"
    src.write_bytes(_jpeg())
    with pytest.raises(FormatMismatchError):
        import_reference(src, snapshot_dir=snap, asset_id="x", character_id="kira",
                         manifest_path=snap / "references.manifest.json")


def test_12_13_source_copied_not_moved_and_sha_matches(tmp_path):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    src = tmp_path / "face.png"
    src.write_bytes(_png())
    from services.character_companion.character_import.hashing import compute_sha256
    src_sha = compute_sha256(src.read_bytes())
    out = import_reference(src, snapshot_dir=snap, asset_id="face", character_id="kira",
                           manifest_path=snap / "references.manifest.json")
    assert src.exists()                                   # never moved
    dest = snap / out.relative_path
    assert compute_sha256(dest.read_bytes()) == src_sha == out.sha256


def test_14_manifest_hash_matches_bytes(tmp_path):
    res = _service(tmp_path).import_character(make_canon(tmp_path), CHAR, "add")
    snap = _service(tmp_path).load_snapshot(CHAR, "v1")
    from services.character_companion.character_import.hashing import compute_sha256
    vdir = (tmp_path / "companion-data" / "characters" / CHAR / "snapshots" / "v1")
    for ref in snap.references:
        assert compute_sha256((vdir / ref.relative_path).read_bytes()) == ref.sha256
    assert res.snapshot_hash == snap.compute_hash()


def test_15_path_traversal_asset_id_rejected(tmp_path):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    src = tmp_path / "face.png"
    src.write_bytes(_png())
    with pytest.raises(ReferenceValidationError):
        import_reference(src, snapshot_dir=snap, asset_id="../evil", character_id="kira",
                         manifest_path=snap / "references.manifest.json")


def test_16_asset_id_collision_rejected(tmp_path):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    man = snap / "references.manifest.json"
    a = tmp_path / "a.png"; a.write_bytes(_png())
    b = tmp_path / "b.png"; b.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x11" * 60)
    import_reference(a, snapshot_dir=snap, asset_id="dup", character_id="kira", manifest_path=man)
    with pytest.raises(AssetIdCollisionError):
        import_reference(b, snapshot_dir=snap, asset_id="dup", character_id="kira", manifest_path=man)


def test_17_duplicate_bytes_behaviour_deterministic(tmp_path):
    snap = tmp_path / "snap"
    (snap / REFERENCES_DIR).mkdir(parents=True)
    man = snap / "references.manifest.json"
    a = tmp_path / "a.png"; a.write_bytes(_png())
    import_reference(a, snapshot_dir=snap, asset_id="same", character_id="kira", manifest_path=man)
    same_id = import_reference(a, snapshot_dir=snap, asset_id="same", character_id="kira", manifest_path=man)
    diff_id = import_reference(a, snapshot_dir=snap, asset_id="other", character_id="kira", manifest_path=man)
    assert same_id.status == "NO_OP_EXISTING_ASSET" and same_id.copied is False
    assert diff_id.status == "NO_OP_DUPLICATE" and diff_id.copied is False


# ========================================================== SNAPSHOT
def test_18_19_first_add_creates_and_activates_v1(tmp_path):
    svc = _service(tmp_path)
    res = svc.import_character(make_canon(tmp_path), CHAR, "add")
    assert res.status == IMPORTED and res.snapshot_version == "v1"
    assert res.active_version == "v1" and svc.active_version(CHAR) == "v1"
    assert svc.list_snapshot_versions(CHAR) == ("v1",)


def test_20_unchanged_update_is_noop(tmp_path):
    svc = _service(tmp_path)
    canon = make_canon(tmp_path)
    svc.import_character(canon, CHAR, "add")
    res = svc.import_character(canon, CHAR, "update")
    assert res.status == NO_OP_UNCHANGED
    assert svc.list_snapshot_versions(CHAR) == ("v1",)
    assert svc.active_version(CHAR) == "v1"


def test_21_22_23_changed_update_creates_v2_without_activating(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path, dirname="c1"), CHAR, "add")
    changed_identity = dict(_DEFAULT_IDENTITY, height_cm=172, hair_direction="short dark hair")
    res = svc.import_character(
        make_canon(tmp_path, dirname="c2", identity=changed_identity), CHAR, "update"
    )
    assert res.status == UPDATED_NEW_VERSION and res.snapshot_version == "v2"
    assert svc.active_version(CHAR) == "v1"               # NOT auto-activated
    assert svc.list_snapshot_versions(CHAR) == ("v1", "v2")
    assert svc.load_snapshot(CHAR, "v1").physical["height_cm"] == 170  # v1 intact


def test_24_explicit_activation_switches_active(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path, dirname="c1"), CHAR, "add")
    svc.import_character(
        make_canon(tmp_path, dirname="c2", identity=dict(_DEFAULT_IDENTITY, height_cm=180)),
        CHAR, "update",
    )
    assert svc.activate_snapshot(CHAR, "v2") == "v2"
    assert svc.active_version(CHAR) == "v2"
    assert svc.load_active_snapshot(CHAR).physical["height_cm"] == 180
    with pytest.raises(SnapshotOperationError):
        svc.activate_snapshot(CHAR, "v9")                 # missing version


def test_25_invalid_active_pointer_rejected(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path), CHAR, "add")
    active_file = tmp_path / "companion-data" / "characters" / CHAR / "snapshots" / "ACTIVE"
    active_file.write_text("v999\n", encoding="utf-8")
    with pytest.raises(SnapshotValidationError):
        svc.load_active_snapshot(CHAR)
    active_file.write_text("garbage", encoding="utf-8")
    with pytest.raises(SnapshotValidationError):
        svc.active_version(CHAR)


def test_26_27_load_verifies_hashes_and_corrupt_asset_fails_closed(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path), CHAR, "add")
    svc.load_active_snapshot(CHAR)                        # clean load OK
    vdir = tmp_path / "companion-data" / "characters" / CHAR / "snapshots" / "v1"
    ref_file = next((vdir / "references").iterdir())
    ref_file.write_bytes(ref_file.read_bytes() + b"tampered")
    with pytest.raises(SnapshotValidationError):
        svc.load_active_snapshot(CHAR)


def test_28_portrait_binds_to_valid_reference(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path), CHAR, "add")
    snap = svc.load_active_snapshot(CHAR)
    assert snap.portrait is not None
    ids = {r.asset_id: r for r in snap.references}
    assert snap.portrait.asset_id in ids
    assert "portrait" in ids[snap.portrait.asset_id].roles
    assert ids[snap.portrait.asset_id].sha256 == snap.portrait.sha256


def test_29_snapshot_survives_reopen(tmp_path):
    _service(tmp_path).import_character(make_canon(tmp_path), CHAR, "add")
    fresh = CharacterImportService(tmp_path / "companion-data")
    snap = fresh.load_active_snapshot(CHAR)
    assert snap.character_id == CHAR and snap.snapshot_version == "v1"
    assert len(snap.references) == 3


def test_30_no_live_canon_after_import(tmp_path):
    """HARD GATE: after import the snapshot is fully usable with Canon gone."""
    svc = _service(tmp_path)
    canon = make_canon(tmp_path)
    svc.import_character(canon, CHAR, "add")

    shutil.rmtree(canon)                                  # source Canon vanishes
    assert not canon.exists()

    snap = svc.load_active_snapshot(CHAR)                 # loads + fully validates
    vdir = tmp_path / "companion-data" / "characters" / CHAR / "snapshots" / "v1"
    from services.character_companion.character_import.hashing import compute_sha256
    for ref in snap.references:
        payload = (vdir / ref.relative_path).read_bytes()
        assert compute_sha256(payload) == ref.sha256 and len(payload) == ref.byte_length
    assert snap.physical["height_cm"] == 170
    assert snap.physical["confirmed_traits"] == ["green eyes", "faint freckles"]
    assert snap.source_canon["status"] == "APPROVED_AS_CANON"
    # no absolute source path leaked into the runtime manifest
    blob = json.dumps(snap.to_dict())
    assert str(tmp_path) not in blob and "\\\\" not in blob


# ======================================================== BOUNDARIES
def test_31_32_33_34_only_the_data_root_is_written(tmp_path):
    canon = make_canon(tmp_path)
    (tmp_path / "elsewhere").mkdir()
    before_elsewhere = _canon_listing(tmp_path / "elsewhere")
    before_canon = {p: p.read_bytes() for p in canon.rglob("*") if p.is_file()}

    _service(tmp_path).import_character(canon, CHAR, "add")

    assert {p: p.read_bytes() for p in canon.rglob("*") if p.is_file()} == before_canon
    assert _canon_listing(tmp_path / "elsewhere") == before_elsewhere
    # everything the import wrote is under the companion data root
    written = _canon_listing(tmp_path / "companion-data")
    assert written and all(w.startswith("characters") for w in written)

    # the import package pulls in no provider / image-job / runtime / core code
    import services.character_companion.character_import.service as svc_mod
    src = Path(svc_mod.__file__).read_text(encoding="utf-8")
    for banned in ("image_provider", "cloud_provider", "credentials", "image_jobs",
                   "character_runtime", "character_core", "socket", "urllib", "requests"):
        assert banned not in src


def test_35_staging_residue_removed_on_failure(tmp_path):
    """A reference whose bytes are missing aborts the import; no half version,
    no staging dir, old state untouched."""
    svc = _service(tmp_path)
    canon = make_canon(tmp_path, file_bytes={"face.png": _png(), "body.jpg": _jpeg()})
    # expr.webp path is declared in active_canon but the file was not written
    with pytest.raises(Exception):
        svc.import_character(canon, CHAR, "add")
    snaps = tmp_path / "companion-data" / "characters" / CHAR / "snapshots"
    assert svc.list_snapshot_versions(CHAR) == ()
    assert svc.active_version(CHAR) is None
    assert not snaps.exists() or not any(p.name.startswith(".staging-") for p in snaps.iterdir())


def test_36_add_when_active_exists_rejected(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path, dirname="c1"), CHAR, "add")
    with pytest.raises(SnapshotOperationError):
        svc.import_character(make_canon(tmp_path, dirname="c2"), CHAR, "add")
    with pytest.raises(SnapshotOperationError):
        CharacterImportService(tmp_path / "other-data").import_character(
            make_canon(tmp_path, dirname="c3"), CHAR, "update"
        )
    with pytest.raises(SnapshotNotFoundError):
        svc.load_active_snapshot("no_such_character")


# ============================================ CATALOG (minimum prep)
def test_37_catalog_surfaces_visual_snapshot_version_additively(tmp_path):
    from tests.character_companion.conftest import ACCEPTED_ROOT
    from services.character_companion.catalog import build_default_catalog

    data_root = tmp_path / "companion-data"
    cat0 = build_default_catalog(ACCEPTED_ROOT, data_root=data_root)
    kira0 = cat0.get("kira")
    assert kira0 is not None and kira0.available is True          # KIRA unchanged
    assert kira0.visual_snapshot_version is None                  # nothing imported

    # import a snapshot for "kira" and rebuild
    _service_kira = CharacterImportService(data_root)
    _service_kira.import_character(
        make_canon(tmp_path, character_id="kira", dirname="kira_canon"), "kira", "add"
    )
    cat1 = build_default_catalog(ACCEPTED_ROOT, data_root=data_root)
    kira1 = cat1.get("kira")
    assert kira1.available is True and kira1.visual_snapshot_version == "v1"
    # accepted-package identity is untouched by the visual import
    assert kira1.package_id == kira0.package_id and kira1.source_hash == kira0.source_hash


# ============================ CANON→COMPANION CHARACTER-ID MAPPING V1
def test_38_canon_to_companion_id_mapping_kira_shape(tmp_path):
    """Real KIRA shape: Canon id 'KIRA', Companion id 'kira'."""
    svc = _service(tmp_path)
    canon = make_canon(tmp_path, character_id="KIRA", dirname="kira_canon")
    res = svc.import_character(canon, "kira", "add", source_character_id="KIRA")

    assert res.status == IMPORTED and res.snapshot_version == "v1"
    assert res.character_id == "kira" and res.active_version == "v1"

    chars_dir = tmp_path / "companion-data" / "characters"
    entries = sorted(p.name for p in chars_dir.iterdir())
    assert entries == ["kira"]                            # NO characters/KIRA dir
    vdir = chars_dir / "kira" / "snapshots" / "v1"
    assert (vdir / "manifest.json").is_file()
    assert (vdir / "references.manifest.json").is_file()
    assert (chars_dir / "kira" / "snapshots" / "ACTIVE").read_text().strip() == "v1"

    # loaders / catalog are Companion-ID based ('kira')
    snap = svc.load_snapshot("kira", "v1")
    assert svc.load_active_snapshot("kira").snapshot_hash == snap.snapshot_hash
    assert svc.active_version("kira") == "v1"

    # persisted Companion identity is lowercase everywhere
    assert snap.character_id == "kira"
    manifest = json.loads((vdir / "manifest.json").read_text())
    assert manifest["characterId"] == "kira"
    for r in json.loads((vdir / "references.manifest.json").read_text())["references"]:
        assert r["character_id"] == "kira"               # local ownership crossed the boundary
    assert all(sr.roles or True for sr in snap.references)

    # exact Canon source identity is preserved as provenance only
    assert snap.source_canon["sourceCharacterId"] == "KIRA"
    assert snap.source_canon["sourceRef"] == (
        "AI_CHARACTERS/KIRA/10_notes/KIRA_REFERENCE_PRESETS.json"
    )
    assert snap.source_canon["status"] == "APPROVED_AS_CANON"
    # no absolute Canon path anywhere in the runtime manifest
    assert str(tmp_path) not in json.dumps(manifest)


def test_39_omitted_mapping_against_uppercase_canon_stays_strict(tmp_path):
    """No hidden case conversion: omitting source_character_id keeps the exact
    Canon identity check, so 'kira' vs a Canon that declares 'KIRA' fails."""
    svc = _service(tmp_path)
    canon = make_canon(tmp_path, character_id="KIRA", dirname="kira_canon")
    with pytest.raises(AmbiguousCharacterError):
        svc.import_character(canon, "kira", "add")        # source_character_id defaults to "kira"
    assert svc.list_snapshot_versions("kira") == () and svc.active_version("kira") is None


def test_40_mismatched_source_character_id_fails_closed(tmp_path):
    svc = _service(tmp_path)
    canon = make_canon(tmp_path, character_id="KIRA", declared_character="SOMEONE_ELSE",
                       dirname="kira_canon")
    with pytest.raises(AmbiguousCharacterError):
        svc.import_character(canon, "kira", "add", source_character_id="KIRA")
    assert svc.active_version("kira") is None


def test_41_same_id_default_backward_compatible(tmp_path):
    """Generic caller: omitting source_character_id == source_character_id == character_id."""
    svc = _service(tmp_path)
    res = svc.import_character(make_canon(tmp_path, character_id="TESTCHAR"), "TESTCHAR", "add")
    assert res.status == IMPORTED
    snap = svc.load_active_snapshot("TESTCHAR")
    assert snap.character_id == "TESTCHAR"
    assert snap.source_canon["sourceCharacterId"] == "TESTCHAR"


def test_42_mapping_update_flow(tmp_path):
    svc = _service(tmp_path)
    svc.import_character(make_canon(tmp_path, character_id="KIRA", dirname="c1"), "kira", "add",
                        source_character_id="KIRA")
    noop = svc.import_character(make_canon(tmp_path, character_id="KIRA", dirname="c2"), "kira",
                               "update", source_character_id="KIRA")
    assert noop.status == NO_OP_UNCHANGED and svc.list_snapshot_versions("kira") == ("v1",)

    changed = make_canon(
        tmp_path, character_id="KIRA", dirname="c3",
        identity=dict(_DEFAULT_IDENTITY, height_cm=181, hair_direction="short"),
    )
    upd = svc.import_character(changed, "kira", "update", source_character_id="KIRA")
    assert upd.status == UPDATED_NEW_VERSION and upd.snapshot_version == "v2"
    assert svc.active_version("kira") == "v1"             # UPDATE never auto-activates
    assert svc.list_snapshot_versions("kira") == ("v1", "v2")
    assert svc.load_snapshot("kira", "v2").source_canon["sourceCharacterId"] == "KIRA"


# ============================ V1F STANDING IDENTITY CANON BRIDGE ============
# Character-generic, whole-file standing-identity source_refs: Canon reader
# (A), legacy local-snapshot compatibility (B), and new-snapshot round-trip /
# hashing (C). No filename guessing, no hard-coded character name, ever.
STANDING_CHAR = "STANDING_TEST"
PRESERVATION_TEXT = "preserve same face, same eyes, same hair.\n"
PRESERVATION_TEXT_2 = "preserve the same warm smile.\n"
NEGATIVE_TEXT = "avoid distorted anatomy, avoid extra limbs.\n"


def _standing_section(preservation_refs, negative_refs=None) -> dict:
    out = {"preservation_rules": {"source_refs": list(preservation_refs)}}
    if negative_refs is not None:
        out["negative_constraints"] = {"source_refs": list(negative_refs)}
    return out


def _write_text_source(canon_root: Path, rel_path: str, text: str) -> None:
    full = canon_root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text, encoding="utf-8", newline="\n")


def _load_preset(canon_root: Path, character_id: str) -> dict:
    return json.loads(
        (canon_root / "AI_CHARACTERS" / character_id / "10_notes"
         / f"{character_id}_REFERENCE_PRESETS.json").read_text(encoding="utf-8")
    )


def _standing_canon(tmp_path, *, dirname: str, multi: bool = False, negative: bool = True) -> Path:
    rel1 = f"AI_CHARACTERS/{STANDING_CHAR}/06_prompts/PRESERVATION_1.txt"
    rel_neg = f"AI_CHARACTERS/{STANDING_CHAR}/06_prompts/NEGATIVE.txt"
    preservation_refs = [rel1]
    files = {rel1: PRESERVATION_TEXT}
    if multi:
        rel2 = f"AI_CHARACTERS/{STANDING_CHAR}/06_prompts/PRESERVATION_2.txt"
        preservation_refs.append(rel2)
        files[rel2] = PRESERVATION_TEXT_2
    negative_refs = None
    if negative:
        negative_refs = [rel_neg]
        files[rel_neg] = NEGATIVE_TEXT
    canon_root = make_canon(
        tmp_path, character_id=STANDING_CHAR, dirname=dirname,
        standing_identity=_standing_section(preservation_refs, negative_refs),
    )
    for rel, text in files.items():
        _write_text_source(canon_root, rel, text)
    return canon_root


# ---------------------------------------------------------------- A. CANON READER
def test_43_standing_identity_source_refs_resolve(tmp_path):
    canon_root = _standing_canon(tmp_path, dirname="standing_ok")
    standing = read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))
    assert isinstance(standing, StandingIdentity)
    assert standing.preservation_rules.sources[0].text == PRESERVATION_TEXT
    assert standing.negative_constraints.sources[0].text == NEGATIVE_TEXT
    assert standing.preservation_rules.sources[0].text_sha256 == compute_sha256(
        PRESERVATION_TEXT.encode("utf-8")
    )


def test_44_multiple_source_refs_preserve_order(tmp_path):
    canon_root = _standing_canon(tmp_path, dirname="standing_multi", multi=True)
    standing = read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))
    texts = [s.text for s in standing.preservation_rules.sources]
    assert texts == [PRESERVATION_TEXT, PRESERVATION_TEXT_2]


def test_45_absolute_source_ref_rejected(tmp_path):
    canon_root = make_canon(
        tmp_path, character_id=STANDING_CHAR, dirname="standing_abs",
        standing_identity=_standing_section(["/etc/passwd"]),
    )
    with pytest.raises(ReferencePathSafetyError):
        read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))


def test_46_dotdot_source_ref_rejected(tmp_path):
    canon_root = make_canon(
        tmp_path, character_id=STANDING_CHAR, dirname="standing_dotdot",
        standing_identity=_standing_section(["../outside.txt"]),
    )
    with pytest.raises(ReferencePathSafetyError):
        read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))


def test_47_drive_qualified_source_ref_rejected(tmp_path):
    """A distinct escape vector from a relative '..': a Windows drive-qualified
    path, rejected by the same path-safety guard the reader reuses unmodified
    from the existing active_canon reference check."""
    canon_root = make_canon(
        tmp_path, character_id=STANDING_CHAR, dirname="standing_drive",
        standing_identity=_standing_section(["C:/Windows/System32/config.txt"]),
    )
    with pytest.raises(ReferencePathSafetyError):
        read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))


def test_48_missing_source_file_fails_closed(tmp_path):
    canon_root = make_canon(
        tmp_path, character_id=STANDING_CHAR, dirname="standing_missing",
        standing_identity=_standing_section(
            [f"AI_CHARACTERS/{STANDING_CHAR}/06_prompts/DOES_NOT_EXIST.txt"]
        ),
    )
    with pytest.raises(CanonFormatError):
        read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR))


def test_49_no_standing_identity_key_never_invents_one(tmp_path):
    """No filename guessing: a plausibly-named file sitting on disk at a
    conventional path is NOT auto-discovered when the preset omits
    standing_identity entirely."""
    canon_root = make_canon(tmp_path, character_id=STANDING_CHAR, dirname="standing_absent")
    _write_text_source(
        canon_root, f"AI_CHARACTERS/{STANDING_CHAR}/06_prompts/{STANDING_CHAR}_BASE_PROMPT.txt",
        "preserve nothing -- must not be auto-discovered\n",
    )
    assert read_standing_identity(canon_root, _load_preset(canon_root, STANDING_CHAR)) is None


# ---------------------------------------------------------- B/C. LOCAL SNAPSHOT
def _write_local_snapshot(
    data_root: Path, character_id: str, version: str, *, standing_identity=None,
) -> CharacterLocalSnapshot:
    store = SnapshotStore(data_root)
    vdir = store.version_dir(character_id, version)
    (vdir / "references").mkdir(parents=True, exist_ok=True)
    data = _png()
    (vdir / "references" / "face.png").write_bytes(data)
    ref = SnapshotReference(
        asset_id="face", roles=("face",), relative_path="references/face.png",
        sha256=compute_sha256(data), file_type="PNG", byte_length=len(data),
    )
    snap = CharacterLocalSnapshot(
        schema_version="companion_character_local_snapshot/0.1",
        character_id=character_id,
        snapshot_version=version,
        source_canon={
            "sourceKind": "canon", "sourceRef": "x", "contentHash": "a" * 64,
            "status": "APPROVED_AS_CANON",
        },
        source_preset_sha256="0" * 64,
        imported_at="2026-01-01T00:00:00Z",
        references=(ref,),
        physical={},
        standing_identity=standing_identity,
    )
    snap = dataclasses.replace(snap, snapshot_hash=snap.compute_hash())
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "manifest.json").write_text(
        json.dumps(snap.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return snap


def test_50_legacy_snapshot_without_standing_identity_round_trips(tmp_path):
    data_root = tmp_path / "companion-data"
    snap = _write_local_snapshot(data_root, "legacy_char", "v1", standing_identity=None)
    loaded = SnapshotStore(data_root).load_snapshot("legacy_char", "v1")
    assert loaded.standing_identity is None
    assert loaded.snapshot_hash == snap.snapshot_hash
    manifest = json.loads(
        (SnapshotStore(data_root).version_dir("legacy_char", "v1") / "manifest.json")
        .read_text(encoding="utf-8")
    )
    assert "standingIdentity" not in manifest    # never fabricated


def test_51_legacy_semantic_payload_omits_standing_identity_key(tmp_path):
    data_root = tmp_path / "companion-data"
    snap = _write_local_snapshot(data_root, "legacy_char2", "v1", standing_identity=None)
    assert "standingIdentity" not in snap.semantic_payload()


def test_52_new_snapshot_standing_sources_round_trip(tmp_path):
    standing = StandingIdentity(
        preservation_rules=StandingIdentityCategory(sources=(
            StandingIdentitySource(
                "AI_CHARACTERS/X/06_prompts/P.txt", PRESERVATION_TEXT,
                compute_sha256(PRESERVATION_TEXT.encode("utf-8")),
            ),
        )),
        negative_constraints=StandingIdentityCategory(sources=(
            StandingIdentitySource(
                "AI_CHARACTERS/X/06_prompts/N.txt", NEGATIVE_TEXT,
                compute_sha256(NEGATIVE_TEXT.encode("utf-8")),
            ),
        )),
    )
    data_root = tmp_path / "companion-data"
    _write_local_snapshot(data_root, "new_char", "v1", standing_identity=standing)
    loaded = SnapshotStore(data_root).load_snapshot("new_char", "v1")
    pr = loaded.standing_identity.preservation_rules.sources[0]
    nc = loaded.standing_identity.negative_constraints.sources[0]
    assert pr.source_ref == "AI_CHARACTERS/X/06_prompts/P.txt"
    assert pr.text == PRESERVATION_TEXT
    assert pr.text_sha256 == compute_sha256(PRESERVATION_TEXT.encode("utf-8"))
    assert nc.text == NEGATIVE_TEXT


def test_53_standing_material_changes_snapshot_hash(tmp_path):
    data_root = tmp_path / "companion-data"
    without = _write_local_snapshot(data_root, "hashcmp1", "v1", standing_identity=None)
    standing = StandingIdentity(preservation_rules=StandingIdentityCategory(sources=(
        StandingIdentitySource("ref.txt", PRESERVATION_TEXT,
                               compute_sha256(PRESERVATION_TEXT.encode("utf-8"))),
    )))
    with_standing = _write_local_snapshot(data_root, "hashcmp2", "v1", standing_identity=standing)
    assert without.snapshot_hash != with_standing.snapshot_hash


def test_54_tampered_standing_text_hash_pair_fails_closed_on_load(tmp_path):
    standing = StandingIdentity(preservation_rules=StandingIdentityCategory(sources=(
        StandingIdentitySource("ref.txt", PRESERVATION_TEXT,
                               compute_sha256(PRESERVATION_TEXT.encode("utf-8"))),
    )))
    data_root = tmp_path / "companion-data"
    _write_local_snapshot(data_root, "tampered", "v1", standing_identity=standing)
    manifest_path = SnapshotStore(data_root).version_dir("tampered", "v1") / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Change the text but keep the now-stale textSha256, then recompute the
    # OUTER snapshotHash so only the inner standing-identity text/hash pair is
    # inconsistent -- isolating the V1F-specific integrity check from the
    # pre-existing whole-manifest hash check.
    manifest["standingIdentity"]["preservationRules"]["sources"][0]["text"] = "tampered text\n"
    recomputed = CharacterLocalSnapshot.from_dict(manifest)
    manifest["snapshotHash"] = recomputed.compute_hash()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with pytest.raises(SnapshotValidationError, match="standing identity text/hash mismatch"):
        SnapshotStore(data_root).load_snapshot("tampered", "v1")
