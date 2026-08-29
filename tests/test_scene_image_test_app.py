#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for the Scene Image Test App v0 runner.

Hermetic: no provider calls, no network, no real Reference Library imports and
no real Character Canon reads. Reference sources are tiny synthetic magic-byte
files; the real profile/fixture JSON are only loaded (never mutated).

    PROVIDER_CALLS = 0 (except the explicitly mocked generate tests)
    NETWORK = 0
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tools.scene_image_test_app as app  # noqa: E402
from tools.scene_image_test_app import (  # noqa: E402
    API_KEY_ENV_VAR,
    DEFAULT_MODEL,
    DEFAULT_QUALITY,
    DEFAULT_SIZE,
    LIVE_ENV_VAR,
    OUTPUT_ROOT,
    Profile,
    ProfileError,
    ReferenceConflictError,
    ReferenceShaMismatchError,
    apply_cast_override,
    format_preview,
    load_profile,
    orchestrate,
    prepare_references,
    run_generate,
    run_preview,
)
from services.reference_library import IMPORTED, import_reference, load_manifest  # noqa: E402

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"

PROFILE_ID = "SC_004_ANDREY_OLGA"

_REF_SPECS = [
    ("OLGA", "olga_face_primary_01", "primary_face_reference", "jpeg"),
    ("OLGA", "olga_face_canon_01", "face_reference", "png"),
    ("OLGA", "olga_body_01", "body_reference", "png"),
    ("OLGA", "olga_sports_01", "sports_reference", "png"),
    ("ANDREY_JUNIOR", "andrey_junior_face_01", "primary_face_reference", "png"),
    ("ANDREY_JUNIOR", "andrey_junior_face_support_01", "face_reference", "png"),
    ("ANDREY_JUNIOR", "andrey_junior_body_01", "body_reference", "png"),
    ("ANDREY_JUNIOR", "andrey_junior_gym_01", "sports_reference", "png"),
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture_dict() -> dict:
    return json.loads(
        (_REPO_ROOT / "tests/fixtures/scene_image_test_app/SC_004.v2.json").read_text(
            encoding="utf-8"
        )
    )


def _gym_dict() -> dict:
    return {
        "schema_version": "location/0.1",
        "location_id": "gym",
        "tier": "standard",
        "scale": ["medium"],
        "identity": ["gym", "stretching"],
        "palette": ["neutral"],
        "fixed_features": [{"feature_id": "mirrored_wall", "label": "mirrored wall"}],
    }


def _real_profile_dir() -> Path:
    return _REPO_ROOT / "authoring/scene_image_test_profiles"


def _payload_for(fmt: str, tag: str) -> bytes:
    return (_JPEG if fmt == "jpeg" else _PNG) + tag.encode("utf-8")


def _build_hermetic(tmp_path: Path) -> dict:
    """Build a fully isolated repo + synthetic profile for offline runs."""
    root = tmp_path / "repo"
    (root / "scenarios" / "locations").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "fixtures" / "scene_image_test_app").mkdir(
        parents=True, exist_ok=True
    )
    (root / "authoring" / "scene_image_test_profiles").mkdir(parents=True, exist_ok=True)
    src_dir = tmp_path / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)

    (root / "scenarios" / "locations" / "gym.json").write_text(
        json.dumps(_gym_dict()), encoding="utf-8"
    )
    shutil.copyfile(
        _REPO_ROOT / "tests/fixtures/scene_image_test_app/SC_004.v2.json",
        root / "tests/fixtures/scene_image_test_app/SC_004.v2.json",
    )

    refs: list[dict] = []
    for i, (cid, aid, role, fmt) in enumerate(_REF_SPECS):
        payload = _payload_for(fmt, f"{aid}#{i}")
        ext = "jpg" if fmt == "jpeg" else "png"
        src = src_dir / f"{aid}.{ext}"
        src.write_bytes(payload)
        refs.append(
            {
                "character_id": cid,
                "asset_id": aid,
                "source_path": str(src),
                "expected_sha256": _sha(payload),
                "role": role,
            }
        )

    profile = {
        "profile_id": PROFILE_ID,
        "scene_id": "SC_004",
        "branch_id": "1B",
        "location_id": "gym",
        "fixture_ref": "tests/fixtures/scene_image_test_app/SC_004.v2.json",
        "media_item_id": "andrey_olga_gym_sc004_b1_image_01",
        "cast_override": {"KIRA": "ANDREY_JUNIOR", "SERGEY": "OLGA"},
        "prompt_aliases": {"ANDREY_JUNIOR": "Andrey", "OLGA": "Olga"},
        "scene_intent": "Gym stretching on the red mat.",
        "visual_goal": "Two characters on the red mat, restrained early closeness.",
        "references": refs,
    }
    (root / "authoring" / "scene_image_test_profiles" / f"{PROFILE_ID}.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )

    manifest = root / "authoring" / "reference_library" / "REFERENCE_LIBRARY_MANIFEST.json"
    return {
        "root": root,
        "manifest": manifest,
        "src_dir": src_dir,
        "profile": profile,
        "refs": refs,
    }


# ---------------------------------------------------------------------------
# Profile loading + reference preparation (items 1-8)
# ---------------------------------------------------------------------------


def test_profile_loads():
    profile = load_profile(PROFILE_ID, _real_profile_dir())
    assert profile.profile_id == PROFILE_ID
    assert profile.scene_id == "SC_004"
    assert profile.branch_id == "1B"
    assert profile.location_id == "gym"
    assert profile.cast_override == {"KIRA": "ANDREY_JUNIOR", "SERGEY": "OLGA"}
    assert profile.prompt_aliases == {"ANDREY_JUNIOR": "Andrey", "OLGA": "Olga"}
    assert profile.characters_in_frame == ("ANDREY_JUNIOR", "OLGA")


def test_unknown_profile_fails():
    with pytest.raises(ProfileError):
        load_profile("DOES_NOT_EXIST", _real_profile_dir())


def test_expected_sha_mismatch_fails(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    refs = list(hermetic["profile"]["references"])
    refs[0] = {**refs[0], "expected_sha256": "0" * 64}
    profile = Profile({**hermetic["profile"], "references": refs})
    with pytest.raises(ReferenceShaMismatchError):
        prepare_references(
            profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
        )


def test_exact_eight_configured_refs():
    profile = load_profile(PROFILE_ID, _real_profile_dir())
    assert len(profile.references) == 8
    assert sum(1 for r in profile.references if r.character_id == "OLGA") == 4
    assert sum(1 for r in profile.references if r.character_id == "ANDREY_JUNIOR") == 4


def test_existing_matching_asset_reuse(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    profile = Profile(hermetic["profile"])
    _, imported, reused, _ = prepare_references(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    assert len(imported) == 8 and not reused
    _, imported2, reused2, _ = prepare_references(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    assert not imported2 and len(reused2) == 8


def test_missing_asset_uses_rl2_import(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    profile = Profile(hermetic["profile"])
    _, imported, _, _ = prepare_references(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    assert sorted(imported) == sorted(r["asset_id"] for r in hermetic["refs"])


def test_conflicting_asset_fails(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    root = hermetic["root"]
    manifest = hermetic["manifest"]

    aid = "olga_face_primary_01"
    import_reference(
        str(hermetic["src_dir"] / f"{aid}.jpg"),
        repo_root=root,
        manifest_path=manifest,
        asset_id=aid,
        character_id="OLGA",
    )

    refs = list(hermetic["profile"]["references"])
    payload = _payload_for("jpeg", "NEW")
    src = hermetic["src_dir"] / "olga_new.jpg"
    src.write_bytes(payload)
    refs[0] = {**refs[0], "source_path": str(src), "expected_sha256": _sha(payload)}
    profile = Profile({**hermetic["profile"], "references": refs})

    with pytest.raises(ReferenceConflictError):
        prepare_references(profile, repo_root=root, manifest_path=manifest)


def test_no_unconfigured_file_imported(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    profile = Profile(hermetic["profile"])
    prepare_references(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    records = load_manifest(hermetic["manifest"])
    assert len(records) == 8
    assert {r.asset_id for r in records} == {r["asset_id"] for r in hermetic["refs"]}


# ---------------------------------------------------------------------------
# Fixture / ASS / cast override (items 9-13)
# ---------------------------------------------------------------------------


def _import_real_fixture():
    from services.ass import import_scene

    source = _fixture_dict()
    overridden = apply_cast_override(source, {"KIRA": "ANDREY_JUNIOR", "SERGEY": "OLGA"})
    ass = import_scene(
        overridden,
        ass_id="sc_004_andrey_olga_ass_v1",
        version=1,
        location_id="gym",
        source_ref="tests/fixtures/scene_image_test_app/SC_004.v2.json",
        branch_id="1B",
    )
    return ass, overridden


def test_sc004_fixture_imports_via_ass():
    ass, _ = _import_real_fixture()
    assert ass.scene_id == "SC_004"


def test_branch_1b_resolves():
    ass, _ = _import_real_fixture()
    assert "1B-b1" in [b.beat_id for b in ass.ordered_beats]


def test_cast_override_kira_to_andrey_junior():
    ass, overridden = _import_real_fixture()
    ids = {p.character_id for p in ass.participants}
    assert "ANDREY_JUNIOR" in ids
    assert "KIRA" not in ids
    char_ids = {c["id"] for c in overridden["characters"]}
    assert "ANDREY_JUNIOR" in char_ids and "KIRA" not in char_ids


def test_cast_override_sergey_to_olga():
    ass, overridden = _import_real_fixture()
    ids = {p.character_id for p in ass.participants}
    assert "OLGA" in ids
    assert "SERGEY" not in ids
    char_ids = {c["id"] for c in overridden["characters"]}
    assert "OLGA" in char_ids and "SERGEY" not in char_ids


def test_fixture_source_not_mutated():
    source = _fixture_dict()
    before = json.dumps(source, sort_keys=True, ensure_ascii=False)
    result = apply_cast_override(source, {"KIRA": "ANDREY_JUNIOR", "SERGEY": "OLGA"})
    after = json.dumps(source, sort_keys=True, ensure_ascii=False)
    assert before == after
    assert result is not source
    assert result["characters"][0]["id"] == "ANDREY_JUNIOR"
    disk = (_REPO_ROOT / "tests/fixtures/scene_image_test_app/SC_004.v2.json").read_text(
        encoding="utf-8"
    )
    assert '"id": "KIRA"' in disk


# ---------------------------------------------------------------------------
# Bundle / alias / prompt gates (items 14-23)
# ---------------------------------------------------------------------------


@pytest.fixture
def result(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    profile = Profile(hermetic["profile"])
    return orchestrate(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )


def test_two_reference_character_groups(result):
    assert len(result.bundle.character_groups) == 2


def test_four_refs_for_andrey(result):
    by_id = {g.character_id: g for g in result.bundle.character_groups}
    assert len(by_id["ANDREY_JUNIOR"].references) == 4


def test_four_refs_for_olga(result):
    by_id = {g.character_id: g for g in result.bundle.character_groups}
    assert len(by_id["OLGA"].references) == 4


def test_alias_andrey_applied(result):
    by_id = {g.character_id: g for g in result.bundle.character_groups}
    assert by_id["ANDREY_JUNIOR"].prompt_alias == "Andrey"


def test_alias_olga_applied(result):
    by_id = {g.character_id: g for g in result.bundle.character_groups}
    assert by_id["OLGA"].prompt_alias == "Olga"


_INTERNAL_IDS = ("ANDREY_JUNIOR", "OLGA")
_YOUTH_FAMILY_TOKENS = ("junior", "son", "boy", "teen", "father-son", "father_son")


def _assert_no_forbidden_tokens(text: str) -> None:
    """Assert ``text`` exposes no configured internal id or youth/family token."""
    assert not app._has_forbidden_tokens(text, _INTERNAL_IDS)
    for cid in _INTERNAL_IDS:
        assert cid not in text
    lowered = text.lower()
    for token in _YOUTH_FAMILY_TOKENS:
        assert token not in lowered


def test_raw_andrey_junior_absent_from_reference_map(result):
    assert "Andrey" in result.reference_map
    assert "Olga" in result.reference_map
    # The aliased source label is the safe multipart filename, not the raw
    # asset basename (which would embed the internal id).
    assert "source=ref_000_Andrey.png" in result.reference_map
    assert "andrey_junior_face_01" not in result.reference_map
    _assert_no_forbidden_tokens(result.reference_map)


def test_raw_andrey_junior_absent_from_attachment_filenames(result):
    assert result.attachment_filenames[0] == "ref_000_Andrey.png"
    for name in result.attachment_filenames:
        _assert_no_forbidden_tokens(name)


def test_forbidden_tokens_absent_from_final_prompt(result):
    _assert_no_forbidden_tokens(result.final_prompt_text)
    assert "ANDREY_JUNIOR" not in result.final_prompt_text


def test_provider_exposure_verdict_is_no(result):
    assert result.provider_exposure is False
    assert result.gates["provider_exposure"] is True
    assert not app.has_provider_exposure(
        prompt_text=result.final_prompt_text,
        reference_map=result.reference_map,
        filenames=result.attachment_filenames,
        internal_ids=result.profile.characters_in_frame,
    )


def test_reference_bundle_validates(result):
    from services.character_visual_conditioning import validate_reference_bundle_integrity

    assert validate_reference_bundle_integrity(result.bundle) is None


def test_prompt_package_builds(result):
    assert len(result.prompt_package.prompt_items) == 1
    assert result.prompt_item.media_item_id == "andrey_olga_gym_sc004_b1_image_01"


# ---------------------------------------------------------------------------
# Preview / generate / deterministic (items 24-30)
# ---------------------------------------------------------------------------


def test_preview_returns_pass(tmp_path, capsys):
    hermetic = _build_hermetic(tmp_path)
    code = run_preview(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "DRY_RUN_RESULT=PASS" in out
    assert "READY_FOR_LIVE_GENERATION=YES" in out


def test_preview_performs_no_provider_call(tmp_path, monkeypatch):
    hermetic = _build_hermetic(tmp_path)

    def boom(*args, **kwargs):
        raise AssertionError("provider must not be called during --preview")

    monkeypatch.setattr(app, "generate_conditioned_image_from_bundle", boom)
    code = run_preview(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
    )
    assert code == 0


def test_generate_without_env_gate_refuses(tmp_path, monkeypatch):
    hermetic = _build_hermetic(tmp_path)
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    called = []

    def boom(*args, **kwargs):
        called.append(1)
        raise AssertionError("must not reach provider")

    monkeypatch.setattr(app, "generate_conditioned_image_from_bundle", boom)
    code = run_generate(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
    )
    assert code == 1
    assert not called


def test_generate_with_missing_api_key_refuses_before_provider(tmp_path, monkeypatch):
    hermetic = _build_hermetic(tmp_path)
    monkeypatch.setenv(LIVE_ENV_VAR, "1")
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    called = []

    def boom(*args, **kwargs):
        called.append(1)
        raise AssertionError("must not reach provider")

    monkeypatch.setattr(app, "generate_conditioned_image_from_bundle", boom)
    code = run_generate(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
    )
    assert code == 1
    assert not called


def test_output_path_is_outside_repo():
    out = (OUTPUT_ROOT / PROFILE_ID / app._output_filename(PROFILE_ID)).resolve()
    repo = _REPO_ROOT.resolve()
    assert str(repo) not in str(out)


def test_output_filename_derived_from_profile_id():
    assert (
        app._output_filename("SC_004_MARINA_MAKSIM")
        == "sc_004_marina_maksim_image_01.png"
    )
    assert (
        app._output_filename("SC_004_ANDREY_OLGA")
        == "sc_004_andrey_olga_image_01.png"
    )


def test_preview_uses_generic_exposure_label(tmp_path, capsys):
    hermetic = _build_hermetic(tmp_path)
    code = run_preview(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "PROVIDER_INTERNAL_ID_EXPOSURE=NO" in out
    assert "ANDREY_JUNIOR_PROVIDER_EXPOSURE" not in out


def test_no_retry_or_fallback_logic(tmp_path, monkeypatch):
    src = Path(app.__file__).read_text(encoding="utf-8")
    assert "retry" not in src.lower()
    assert "fallback" not in src.lower()

    hermetic = _build_hermetic(tmp_path)
    monkeypatch.setenv(LIVE_ENV_VAR, "1")
    monkeypatch.setenv(API_KEY_ENV_VAR, "test-key")
    calls = []

    def fake_provider(**kwargs):
        calls.append(kwargs)
        payload = b"\x89PNG\r\n\x1a\n" + b"X"
        return SimpleNamespace(
            payload=payload,
            payload_sha256=_sha(payload),
            content_type="image/png",
            model=kwargs["model"],
        )

    monkeypatch.setattr(app, "generate_conditioned_image_from_bundle", fake_provider)
    out_root = tmp_path / "out"
    code = run_generate(
        PROFILE_ID,
        repo_root=hermetic["root"],
        manifest_path=hermetic["manifest"],
        output_root=out_root,
    )
    assert code == 0
    assert len(calls) == 1
    # The generated image uses the derived profile filename, not a hardcoded one.
    assert (out_root / PROFILE_ID / "sc_004_andrey_olga_image_01.png").exists()


def test_deterministic_preview_for_same_inputs(tmp_path):
    hermetic = _build_hermetic(tmp_path)
    profile = Profile(hermetic["profile"])
    r1 = orchestrate(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    r2 = orchestrate(
        profile, repo_root=hermetic["root"], manifest_path=hermetic["manifest"]
    )
    assert r1.bundle.content_hash == r2.bundle.content_hash
    assert r1.final_prompt_hash == r2.final_prompt_hash
    p1 = format_preview(r1, model=DEFAULT_MODEL, size=DEFAULT_SIZE, quality=DEFAULT_QUALITY)
    p2 = format_preview(r2, model=DEFAULT_MODEL, size=DEFAULT_SIZE, quality=DEFAULT_QUALITY)
    assert p1 == p2
