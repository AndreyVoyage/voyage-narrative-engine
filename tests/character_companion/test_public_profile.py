#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHARACTER PUBLIC PROFILE V1 -- backend.

Offline. Temp data roots only. Proves the editable public presentation layer:
model validation, short/long distinction, ordered sections + media, image/video
types, unsafe-ref rejection, no runtime/CRP leakage, the card summary, the
detail seam, deterministic fallback, a persisted override, and that editing a
public profile never touches accepted / runtime / snapshot / memory data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.character_companion import CompanionService
from services.character_companion.public_profile import (
    CharacterPublicProfile,
    CharacterPublicProfileStore,
    ProfileMedia,
    ProfileSection,
    PROFILE_SCHEMA_VERSION,
    PublicProfileError,
    default_profile,
    is_safe_media_ref,
)
from services.character_companion.transport import CompanionTransport

from tests.character_companion.conftest import ACCEPTED_ROOT, FAKE_PROVIDER_INFO, make_fake_factory


def _service(tmp_path, *, data_root=None) -> CompanionService:
    return CompanionService(
        acceptance_root=ACCEPTED_ROOT,
        data_root=data_root or (tmp_path / "companion-data"),
        provider_factory=make_fake_factory(),
        provider_info=FAKE_PROVIDER_INFO,
    )


def _full_profile(character_id="kira") -> CharacterPublicProfile:
    return CharacterPublicProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        character_id=character_id,
        display_name="Кира",
        short_description="Короткая строка для карточки.",
        long_description="Первый абзац.\n\nВторой абзац подробностей.",
        sections=(
            ProfileSection("about", "О персонаже", "Тело раздела «О персонаже»."),
            ProfileSection("style", "Стиль общения", "Тело раздела «Стиль»."),
        ),
        media=(
            ProfileMedia("m_img", "image", "characters/kira/KIRA_release_portrait_v1_APPROVED.png",
                         title="Портрет"),
            ProfileMedia("m_vid", "video", "characters/kira/intro.webm",
                         thumbnail_ref="characters/kira/intro_poster.png", title="Знакомство"),
        ),
        primary_media_id="m_img",
        is_fallback=False,
    )


# ------------------------------------------------------- 1. model validates
def test_01_full_profile_validates_and_round_trips():
    p = _full_profile()
    p.validate()
    again = CharacterPublicProfile.from_dict(json.loads(json.dumps(p.to_dict())), is_fallback=False)
    assert again.to_dict() == p.to_dict()
    assert again.schema_version == PROFILE_SCHEMA_VERSION


# --------------------------------------- 2. short vs long are distinct fields
def test_02_short_and_long_description_are_distinct():
    p = _full_profile()
    assert p.short_description != p.long_description
    assert "\n" not in p.short_description
    assert "\n\n" in p.long_description
    # short is never derived from long
    p2 = CharacterPublicProfile(
        schema_version=PROFILE_SCHEMA_VERSION, character_id="kira", display_name="Кира",
        short_description="", long_description="Длинный текст без короткого.",
    )
    p2.validate()
    assert p2.short_description == ""


def test_02b_multiline_or_overlong_short_description_rejected():
    with pytest.raises(PublicProfileError):
        CharacterPublicProfile(
            schema_version=PROFILE_SCHEMA_VERSION, character_id="kira", display_name="Кира",
            short_description="строка один\nстрока два",
        ).validate()
    with pytest.raises(PublicProfileError):
        CharacterPublicProfile(
            schema_version=PROFILE_SCHEMA_VERSION, character_id="kira", display_name="Кира",
            short_description="x" * 500,
        ).validate()


# ------------------------------------------------- 3. ordered sections preserved
def test_03_section_order_is_preserved_through_serialization():
    p = _full_profile()
    order = [s.section_id for s in p.sections]
    round_trip = CharacterPublicProfile.from_dict(p.to_dict())
    assert [s.section_id for s in round_trip.sections] == order == ["about", "style"]


# --------------------------------------------------- 4. ordered media preserved
def test_04_media_order_is_preserved_through_serialization():
    p = _full_profile()
    round_trip = CharacterPublicProfile.from_dict(p.to_dict())
    assert [m.media_id for m in round_trip.media] == ["m_img", "m_vid"]


# ------------------------------------------- 5. image + video media accepted
def test_05_image_and_video_media_types_accepted():
    p = _full_profile()
    p.validate()
    assert {m.media_type for m in p.media} == {"image", "video"}
    with pytest.raises(PublicProfileError):
        ProfileMedia("m_x", "audio", "characters/kira/x.mp3").validate()


# ------------------------------------------------- 6. unsafe media refs rejected
@pytest.mark.parametrize("bad", [
    r"C:\Users\andrc\AppData\Local\KiraCompanion\data\images\x.png",
    "/etc/passwd",
    "file:///C:/secret.png",
    "https://evil.example/x.png",
    "../../secret/x.png",
    "characters/../../../x.png",
    "data:image/png;base64,AAAA",
    "images\\..\\x.png",
    "",
    "random/relative/x.png",
])
def test_06_unsafe_media_ref_rejected(bad):
    assert is_safe_media_ref(bad) is False
    with pytest.raises(PublicProfileError):
        ProfileMedia("m_bad", "image", bad).validate()


def test_06b_safe_media_refs_accepted():
    for good in ("characters/kira/portrait.png", "images/img-abc123.png",
                 "characters/kira/clips/intro.webm"):
        assert is_safe_media_ref(good) is True


# ------------------------- 7. no Runtime / Memory / CRP leakage in the contract
def test_07_profile_contract_has_no_internal_fields():
    p = _full_profile()
    blob = json.dumps(p.to_dict(), ensure_ascii=False).lower()
    for banned in ("claim", "evidence", "reconstruction", "system_prompt", "systemprompt",
                   "package_hash", "packagehash", "snapshot_hash", "snapshothash",
                   "psychology", "relationship", "memory", "credential", "provider",
                   "r1", "r8", "coefficient", "appdata", "c:\\"):
        assert banned not in blob, f"public profile leaked {banned!r}"


# ----------------------------------- 8. character-list card carries short copy
def test_08_character_list_card_summary_is_lightweight(tmp_path):
    t = CompanionTransport(_service(tmp_path))
    cards = t.list_characters()["characters"]
    kira = next(c for c in cards if c["characterId"] == "kira")
    assert "shortDescription" in kira and isinstance(kira["shortDescription"], str)
    assert kira["hasDetailedProfile"] is False           # nothing persisted yet
    assert kira["profileIsFallback"] is True
    # the lightweight card never ships the long copy / sections / media
    assert "longDescription" not in kira and "sections" not in kira and "media" not in kira
    # the PROFILE-derived fields carry no internal state (pre-existing
    # packageId / sourceHash are outside this slice)
    profile_blob = json.dumps({
        "shortDescription": kira["shortDescription"],
        "hasDetailedProfile": kira["hasDetailedProfile"],
        "profileIsFallback": kira["profileIsFallback"],
    }).lower()
    for banned in ("claim", "psychology", "credential", "memory", "hash", "prompt"):
        assert banned not in profile_blob


# --------------------------- 9. full profile obtained through the service seam
def test_09_full_profile_via_service_and_transport(tmp_path):
    svc = _service(tmp_path)
    dom = svc.get_public_profile("kira")
    assert isinstance(dom, CharacterPublicProfile) and dom.character_id == "kira"

    t = CompanionTransport(svc)
    js = t.get_character_profile("kira")
    assert js["characterId"] == "kira" and js["schemaVersion"] == PROFILE_SCHEMA_VERSION
    assert set(js) >= {"shortDescription", "longDescription", "sections", "media",
                       "primaryMediaId", "isFallback"}
    with pytest.raises(Exception):
        t.get_character_profile("nobody")


# ---------------------------------- 10. missing profile -> deterministic fallback
def test_10_missing_persisted_profile_has_deterministic_fallback(tmp_path):
    svc = _service(tmp_path)
    a = svc.get_public_profile("kira")
    b = svc.get_public_profile("kira")
    assert a.to_dict() == b.to_dict()
    assert a.is_fallback is True
    assert a.long_description == "" and a.sections == () and a.media == ()
    assert a.short_description  # a restrained line, not empty for KIRA
    assert default_profile("kira", display_name="Кира").to_dict() == a.to_dict()


# ------------------------- 11. persisted override replaces the fallback cleanly
def test_11_persisted_profile_overrides_fallback(tmp_path):
    data_root = tmp_path / "companion-data"
    svc = _service(tmp_path, data_root=data_root)
    assert svc.get_public_profile("kira").is_fallback is True

    saved = svc.save_public_profile(_full_profile("kira"))
    assert saved.is_fallback is False
    assert (data_root / "character_profiles" / "kira.json").is_file()

    reloaded = _service(tmp_path, data_root=data_root).get_public_profile("kira")
    assert reloaded.is_fallback is False
    assert reloaded.short_description == "Короткая строка для карточки."
    assert [s.section_id for s in reloaded.sections] == ["about", "style"]
    assert reloaded.has_detailed_profile is True

    t = CompanionTransport(_service(tmp_path, data_root=data_root))
    card = next(c for c in t.list_characters()["characters"] if c["characterId"] == "kira")
    assert card["hasDetailedProfile"] is True and card["profileIsFallback"] is False


def test_11b_malformed_persisted_profile_fails_closed_to_fallback(tmp_path):
    data_root = tmp_path / "companion-data"
    store = CharacterPublicProfileStore(data_root)
    (data_root / "character_profiles").mkdir(parents=True)
    (data_root / "character_profiles" / "kira.json").write_text("{ not json", encoding="utf-8")
    got = store.load("kira", display_name="Кира")
    assert got.is_fallback is True and got.character_id == "kira"


def test_11c_hidden_sections_and_media_not_transported(tmp_path):
    data_root = tmp_path / "companion-data"
    svc = _service(tmp_path, data_root=data_root)
    p = _full_profile("kira")
    p = CharacterPublicProfile(
        **{**p.__dict__,
           "sections": (p.sections[0], ProfileSection("hidden", "Скрытый", "тело", visible=False)),
           "media": (p.media[0], ProfileMedia("m_hidden", "image", "characters/kira/h.png", visible=False))}
    )
    svc.save_public_profile(p)
    js = CompanionTransport(_service(tmp_path, data_root=data_root)).get_character_profile("kira")
    assert [s["sectionId"] for s in js["sections"]] == ["about"]
    assert [m["mediaId"] for m in js["media"]] == ["m_img"]


# ---------- 12. public-profile edits never touch accepted / runtime / snapshot / memory
def test_12_saving_profile_does_not_mutate_accepted_or_runtime_or_snapshot(tmp_path):
    data_root = tmp_path / "companion-data"
    svc = _service(tmp_path, data_root=data_root)

    # a full conversation turn first, so runtime memory + session files exist
    session = svc.create_session("kira")
    svc.send_message(session.session_id, "Привет, Кира.")

    def _tree(root: Path) -> dict:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()
        }

    accepted_before = _tree(ACCEPTED_ROOT)
    char_tree_before = _tree(data_root / "characters")          # memory + state
    sessions_before = (data_root / "companion_sessions.json").read_bytes()

    svc.save_public_profile(_full_profile("kira"))
    svc.get_public_profile("kira")

    assert _tree(ACCEPTED_ROOT) == accepted_before
    assert _tree(data_root / "characters") == char_tree_before
    assert (data_root / "companion_sessions.json").read_bytes() == sessions_before
    # the only new artefact is the profile file, in its own directory
    assert (data_root / "character_profiles" / "kira.json").is_file()
    # conversation + catalog are unaffected
    assert len(svc.get_messages(session.session_id)) == 2
    assert [c.character_id for c in svc.list_characters()] == ["kira"]
