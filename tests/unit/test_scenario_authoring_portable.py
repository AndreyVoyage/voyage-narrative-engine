#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SE-1.4 Scenario Authoring portable .vscenario tests (T01-T23 + vertical proof)."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.scenario_authoring import (  # noqa: E402
    SCENARIO_AUTHORING_SCHEMA_VERSION,
    CHARACTER_PROVENANCE_MANUAL,
    CONTENT_KIND_CHOICE,
    CONTENT_KIND_MEDIA,
    CONTENT_KIND_TEXT,
    PACKAGE_FORMAT_VERSION,
    AuthoredChoice,
    Card,
    CardConnection,
    CharacterReference,
    ChoiceOption,
    ContentItem,
    DisplayPortion,
    MediaReference,
    PortableProjectError,
    PortableProjectExportError,
    PortableProjectImportError,
    PortableProjectValidationError,
    Project,
    ProjectStore,
    Slide,
    SpeakerOverride,
    Utterance,
    export_project,
    import_project,
    validate_package,
)

_SCHEMA = SCENARIO_AUTHORING_SCHEMA_VERSION

_MEDIA_FILES = {
    "media/bg_a.png": b"\x89PNG\r\n\x1a\nbackground-a-bytes",
    "media/portrait_kira.png": b"\x89PNG\r\n\x1a\nportrait-kira-bytes",
    "media/fg_b.png": b"\x89PNG\r\n\x1a\nforeground-b-bytes",
}


def _media_project() -> Project:
    text = "Hello there, Kira."
    utt = Utterance(
        utterance_id="utt_hello",
        text=text,
        speaker_ids=("kira",),
        portions=(
            DisplayPortion(
                portion_id="por_1",
                start_offset=0,
                end_offset=5,
                overrides=(
                    SpeakerOverride(
                        character_id="kira",
                        portrait=MediaReference(relative_path="media/portrait_kira.png"),
                        emotion="neutral",
                    ),
                ),
            ),
            DisplayPortion(portion_id="por_2", start_offset=5, end_offset=len(text)),
        ),
    )
    slide_a = Slide(
        slide_id="slide_a1",
        background=MediaReference(relative_path="media/bg_a.png"),
        content_items=(ContentItem(item_id="item_hello", kind=CONTENT_KIND_TEXT, utterance=utt),),
    )

    choice = AuthoredChoice(
        choice_id="ch_branch",
        prompt="Go on?",
        options=(ChoiceOption(option_id="opt_yes", label="Yes"),),
    )
    slide_b1 = Slide(
        slide_id="slide_b1",
        content_items=(ContentItem(item_id="item_choice", kind=CONTENT_KIND_CHOICE, choice=choice),),
    )
    slide_b2 = Slide(
        slide_id="slide_b2",
        content_items=(
            ContentItem(item_id="item_media", kind=CONTENT_KIND_MEDIA, media=MediaReference(relative_path="media/fg_b.png")),
            ContentItem(item_id="item_media_asset", kind=CONTENT_KIND_MEDIA, media=MediaReference(asset_id="asset_fg_external")),
        ),
    )

    card_a = Card(
        card_id="card_a",
        slides=(slide_a,),
        connections=(CardConnection(connection_id="conn_ab", target_card_id="card_b", label="Next"),),
    )
    card_b = Card(card_id="card_b", slides=(slide_b1, slide_b2))

    return Project(
        schema_version=_SCHEMA,
        project_id="proj_alpha",
        cards=(card_a, card_b),
        start_card_id="card_a",
        characters=(CharacterReference(character_id="kira", provenance=CHARACTER_PROVENANCE_MANUAL, name="Kira"),),
    )


def _write_media_files(root: Path) -> None:
    for rel, data in _MEDIA_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def _export(tmp_path: Path, dest_name: str = "proj.vscenario"):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    pkg = tmp_path / dest_name
    export_project(src, pkg)
    return src, pkg, project


def _rewrite_package(pkg: Path, mutate):
    with zipfile.ZipFile(pkg, "r") as zf:
        items = [(i.filename, zf.read(i.filename)) for i in zf.infolist()]
    items = mutate(items)
    with zipfile.ZipFile(pkg, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items:
            zf.writestr(name, data)


def _mutate_manifest(pkg: Path, fn):
    def mutate(items):
        out = []
        for name, data in items:
            if name == "manifest.json":
                manifest = json.loads(data.decode("utf-8"))
                fn(manifest)
                data = json.dumps(manifest, sort_keys=True).encode("utf-8")
            out.append((name, data))
        return out

    _rewrite_package(pkg, mutate)


def test_t01_export_valid_project(tmp_path):
    _, pkg, _ = _export(tmp_path)
    assert pkg.is_file()


def test_t02_validate_exported_package(tmp_path):
    _, pkg, _ = _export(tmp_path)
    summary = validate_package(pkg)
    assert summary.project_id == "proj_alpha"
    assert summary.entry_count == 6  # project.json + 2 cards + 3 media


def test_t03_import_into_fresh_destination(tmp_path):
    _, pkg, _ = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    assert imported.project_id == "proj_alpha"


def test_t04_round_trip_to_dict_exact(tmp_path):
    _, pkg, original = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    assert imported.to_dict() == original.to_dict()


def test_t05_cards_and_slides_preserved(tmp_path):
    _, pkg, _ = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    assert imported.card_ids() == ("card_a", "card_b")
    assert imported.card_by_id("card_b").slide_ids() == ("slide_b1", "slide_b2")


def test_t06_complete_utterance_text_preserved(tmp_path):
    _, pkg, _ = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    utt = imported.card_by_id("card_a").slides[0].content_items[0].utterance
    assert utt.text == "Hello there, Kira."


def test_t07_display_portions_and_overrides_preserved(tmp_path):
    _, pkg, _ = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    utt = imported.card_by_id("card_a").slides[0].content_items[0].utterance
    assert [(p.portion_id, p.start_offset, p.end_offset) for p in utt.portions] == [
        ("por_1", 0, 5),
        ("por_2", 5, len("Hello there, Kira.")),
    ]
    assert utt.portions[0].overrides[0].portrait == MediaReference(relative_path="media/portrait_kira.png")
    assert utt.portions[0].overrides[0].emotion == "neutral"


def test_t08_connections_and_start_card_preserved(tmp_path):
    _, pkg, _ = _export(tmp_path)
    imported = import_project(pkg, tmp_path / "dest")
    assert imported.start_card_id == "card_a"
    assert [(c.connection_id, c.target_card_id, c.label) for c in imported.card_by_id("card_a").connections] == [
        ("conn_ab", "card_b", "Next")
    ]


def test_t09_media_bytes_survive_transfer(tmp_path):
    src, pkg, _ = _export(tmp_path)
    dest = tmp_path / "dest"
    import_project(pkg, dest)
    for rel, data in _MEDIA_FILES.items():
        assert (dest / rel).read_bytes() == data
        assert (dest / rel).read_bytes() == (src / rel).read_bytes()


def test_t10_missing_required_media_rejects_export(tmp_path):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    (src / "media" / "fg_b.png").unlink()
    with pytest.raises(PortableProjectExportError):
        export_project(src, tmp_path / "proj.vscenario")


def test_t11_tampered_member_rejects_import(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _rewrite_package(
        pkg,
        lambda items: [(n, b"TAMPERED" if n == "cards/card_a.json" else d) for n, d in items],
    )
    with pytest.raises(PortableProjectError):
        import_project(pkg, tmp_path / "dest")


def test_t12_missing_manifest_member_rejects_import(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _rewrite_package(pkg, lambda items: [(n, d) for n, d in items if n != "cards/card_b.json"])
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")


def test_t13_duplicate_archive_member_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    card_a = None
    with zipfile.ZipFile(pkg, "r") as zf:
        card_a = zf.read("cards/card_a.json")
    _rewrite_package(pkg, lambda items: items + [("cards/card_a.json", card_a)])
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")


def test_t14_traversal_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _rewrite_package(pkg, lambda items: items + [("../evil.txt", b"x")])
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")


def test_t15_windows_absolute_and_drive_paths_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    for bad in ("C:/evil.txt", "/evil.txt", "\\\\server\\evil.txt"):
        _rewrite_package(pkg, lambda items, b=bad: items + [(b, b"x")])
        with pytest.raises(PortableProjectValidationError):
            import_project(pkg, tmp_path / "dest")


def test_t16_symlink_escape_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    # Rebuild the package so a declared media member is a symlink entry.
    with zipfile.ZipFile(pkg, "r") as zf:
        items = [(i.filename, zf.read(i.filename)) for i in zf.infolist()]
    with zipfile.ZipFile(pkg, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in items:
            if name == "media/media/bg_a.png":
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o120000 | 0o777) << 16
                zf.writestr(info, b"target")
            else:
                zf.writestr(name, data)
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")


def test_t17_unsupported_manifest_version_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _mutate_manifest(pkg, lambda m: m.update({"format_version": PACKAGE_FORMAT_VERSION + 1}))
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")


def test_t18_oversized_or_excessive_archive_rejected(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _mutate_manifest(pkg, lambda m: m["entries"][0].update({"size": 64 * 1024 * 1024 + 1}))
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg, tmp_path / "dest")

    _, pkg2, _ = _export(tmp_path, dest_name="proj2.vscenario")
    _mutate_manifest(
        pkg2,
        lambda m: m.update(
            {"entries": [{"path": f"media/x{i}.bin", "size": 1, "sha256": "0" * 64} for i in range(2000)]}
        ),
    )
    with pytest.raises(PortableProjectValidationError):
        import_project(pkg2, tmp_path / "dest2")


def test_t19_existing_destination_remains_untouched(tmp_path):
    _, pkg, _ = _export(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "existing.txt").write_text("keep me", encoding="utf-8")
    with pytest.raises(PortableProjectImportError):
        import_project(pkg, dest)
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "keep me"
    assert sorted(p.name for p in dest.iterdir()) == ["existing.txt"]


def test_t20_failed_import_leaves_no_partial(tmp_path):
    _, pkg, _ = _export(tmp_path)
    _rewrite_package(
        pkg,
        lambda items: [(n, b"TAMPERED" if n == "cards/card_a.json" else d) for n, d in items],
    )
    dest = tmp_path / "dest"
    with pytest.raises(PortableProjectError):
        import_project(pkg, dest)
    assert not dest.exists()


def test_t21_failed_export_preserves_source(tmp_path):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    index_before = (src / "project.json").read_bytes()
    card_before = (src / "cards" / "card_a.json").read_bytes()
    (src / "media" / "fg_b.png").unlink()
    with pytest.raises(PortableProjectExportError):
        export_project(src, tmp_path / "proj.vscenario")
    assert (src / "project.json").read_bytes() == index_before
    assert (src / "cards" / "card_a.json").read_bytes() == card_before


def test_t22_imported_project_reopens_via_projectstore(tmp_path):
    _, pkg, _ = _export(tmp_path)
    dest = tmp_path / "dest"
    imported = import_project(pkg, dest)
    reopened = ProjectStore(dest).load()
    assert reopened.to_dict() == imported.to_dict()
    assert reopened == imported


def test_t23_deterministic_manifest_and_inventory(tmp_path):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    r1 = export_project(src, tmp_path / "a.vscenario")
    r2 = export_project(src, tmp_path / "b.vscenario")
    assert r1.manifest == r2.manifest
    assert r1.project_hash == r2.project_hash
    assert r1.entry_count == r2.entry_count
    assert r1.media_count == r2.media_count


def test_vertical_portability_proof(tmp_path):
    original = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(original)
    _write_media_files(src)

    pkg = tmp_path / "proof.vscenario"
    export_project(src, pkg)
    validate_package(pkg)

    dest = tmp_path / "dest"
    imported = import_project(pkg, dest)

    assert imported.to_dict() == original.to_dict()
    assert imported == original
    for rel, data in _MEDIA_FILES.items():
        assert (dest / rel).read_bytes() == data

    # asset_id reference preserved (external registry reference, not a local file)
    media_item = imported.card_by_id("card_b").slides[1].content_items[1]
    assert media_item.kind == CONTENT_KIND_MEDIA
    assert media_item.media == MediaReference(asset_id="asset_fg_external")

    reopened = ProjectStore(dest).load()
    assert reopened.to_dict() == original.to_dict()


def test_t24_export_rejects_existing_unrelated_destination(tmp_path):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    dest = tmp_path / "proj.vscenario"
    sentinel = b"UNRELATED-USER-FILE-SENTINEL"
    dest.write_bytes(sentinel)
    with pytest.raises(PortableProjectExportError):
        export_project(src, dest)
    assert dest.read_bytes() == sentinel


def test_t25_export_overwrite_true_replaces_destination(tmp_path):
    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    dest = tmp_path / "proj.vscenario"
    dest.write_bytes(b"STALE-OLD-PACKAGE")
    export_project(src, dest, overwrite=True)
    assert dest.is_file()
    summary = validate_package(dest)
    assert summary.project_id == "proj_alpha"
    assert dest.read_bytes() != b"STALE-OLD-PACKAGE"


def test_t26_export_no_clobber_when_destination_appears_during_publish(tmp_path, monkeypatch):
    import services.scenario_authoring.portable as portable_mod

    project = _media_project()
    src = tmp_path / "src"
    ProjectStore(src).save(project)
    _write_media_files(src)
    dest = tmp_path / "proj.vscenario"
    sentinel = b"RACE-SENTINEL"

    real_validate = portable_mod.validate_package

    def racy_validate(package_path):
        # Simulate a destination appearing after the archive is built and
        # validated, but before publication. The no-clobber publish must still
        # refuse to overwrite it (no check-then-replace race).
        dest.write_bytes(sentinel)
        return real_validate(package_path)

    monkeypatch.setattr(portable_mod, "validate_package", racy_validate)
    with pytest.raises(PortableProjectExportError):
        export_project(src, dest)
    assert dest.read_bytes() == sentinel
