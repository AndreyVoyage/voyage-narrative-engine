"""Canonical ASS storage: strict envelope, no-clobber publication, exact reload."""

import base64
import dataclasses
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from services.ass import (
    OrderedASSStore, OrderedASSStoreError, OrderedASSNotFoundError,
    OrderedASSConflictError, OrderedASSIntegrityError,
    build_ordered_ass, compute_content_hash, parse_ordered_ass, serialize_ordered_ass,
)
from services.scene_body import SceneBody
from tests.scene_draft.conftest import make_body


def make_ass(*, scene_id="SC_900", version=1, **metadata):
    body = SceneBody.from_dict(make_body(
        scene_id=scene_id, scene_title="Сцена — проверка",
        character_state_overrides={"KIRA": {"state": [1, True, None, "текст"]}},
        location_state_overrides=[{"predicate": "lights", "value": {"on": True}}],
    ))
    return build_ordered_ass(body, ass_id=metadata.pop("ass_id", "ass_sc900"),
                             version=version, source_ref="authoring/scenes/test.json",
                             source_hash="1" * 64, **metadata)


@pytest.fixture
def store(tmp_path):
    return OrderedASSStore(tmp_path / "ass")


def _path(store, ass):
    return store.path_for(scene_id=ass.scene_id, version=ass.version)


def _write_raw(store, raw, *, rehash=False):
    if rehash:
        # Semantic hash excludes these envelope fields, including content_hash.
        excluded = {"ass_id", "version", "provenance", "content_hash",
                    "supersedes", "created_at", "author"}
        raw["content_hash"] = compute_content_hash({k: v for k, v in raw.items() if k not in excluded})
    path = store.path_for(scene_id="SC_900", version=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(raw, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode())
    return path


def test_exact_complete_envelope_and_bytes(store):
    ass = make_ass(author="Автор", created_at="2026-09-10T00:00:00Z", supersedes="old_ass")
    expected = (json.dumps(ass.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
    saved = store.save(ass)
    loaded = store.load(scene_id=ass.scene_id, version=1,
                        expected_ass_id=ass.ass_id, expected_content_hash=ass.content_hash)
    assert saved.to_dict() == loaded.to_dict() == ass.to_dict()
    assert loaded is not ass
    assert _path(store, ass).read_bytes() == serialize_ordered_ass(ass) == expected
    assert b"\r" not in expected and expected.endswith(b"\n") and not expected.endswith(b"\n\n")
    assert "Автор".encode() in expected
    assert loaded.content_hash == compute_content_hash(loaded.semantic_payload())


@pytest.mark.parametrize("scene_id", ["../a\\b:C?", "Сцена/№1", "CON", "é", "e\u0301", "SC_900"])
def test_injective_safe_path(store, scene_id):
    ass = make_ass(scene_id=scene_id)
    token = base64.b32encode(scene_id.encode()).decode().lower().rstrip("=")
    path = _path(store, ass)
    assert path.relative_to(store._root).parts == ("scenes", token, "versions", "1.json")
    store.save(ass)
    assert store.load(scene_id=scene_id, version=1).scene_id == scene_id


def test_no_unicode_normalization(store):
    assert store.path_for(scene_id="é", version=1) != store.path_for(scene_id="e\u0301", version=1)


@pytest.mark.parametrize("version", [0, -1, True, "1", 1.0, None])
def test_bad_version(store, version):
    with pytest.raises(OrderedASSIntegrityError):
        store.load(scene_id="SC_900", version=version)


def test_explicit_root_and_missing_identity(store):
    with pytest.raises(OrderedASSStoreError):
        OrderedASSStore(Path("relative"))
    with pytest.raises(OrderedASSNotFoundError):
        store.load(scene_id="absent", version=1)


@pytest.mark.parametrize("data", [b"{", b"[]", b"null", b"\xff", b'{"x":1,"x":2}',
                                     b'{"x":NaN}', b'{"x":Infinity}'])
def test_malformed_json(data):
    with pytest.raises(OrderedASSIntegrityError):
        parse_ordered_ass(data)


@pytest.mark.parametrize("shape", ["legacy", "body", "version"])
def test_non_ordered_contracts_rejected(store, shape):
    raw = make_ass().to_dict()
    if shape == "legacy":
        raw["schema_version"] = "ass/0.1"
    elif shape == "body":
        raw = make_body()
    else:
        raw = {"scene_id": "SC_900", "version": 1, "lifecycle": "DRAFT", "body": make_body()}
    _write_raw(store, raw)
    with pytest.raises(OrderedASSIntegrityError):
        store.load(scene_id="SC_900", version=1)


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(extra="unsupported"),
    lambda r: r["provenance"].update(extra=True),
    lambda r: r["participants"][0].update(extra=True),
    lambda r: r["participants"][0].pop("present"),
    lambda r: r["participants"][0].update(present=1),
    lambda r: r["ordered_flow"][0].update(extra=True),
    lambda r: r["ordered_flow"][0].update(presentation="BAD"),
    lambda r: r["ordered_flow"][0].update(text=""),
    lambda r: r["ordered_flow"][0].pop("character_id"),
    lambda r: r["ordered_flow"][1]["options"][0].update(extra=True),
    lambda r: r["ordered_flow"][1]["options"][0]["target"].update(extra=True),
    lambda r: r["ordered_flow"][1]["options"][0]["target"].update(target_kind="BAD"),
    lambda r: r["ordered_flow"][1]["options"][0].update(target=None),
    lambda r: r["ordered_flow"][2].update(operation="BAD"),
    lambda r: r["ordered_flow"][2].update(operation="CLEAR"),
    lambda r: r["ordered_flow"][2].update(asset_id=None),
    lambda r: r["location_state_overrides"][0].update(extra=True),
    lambda r: r.update(character_state_overrides={"KIRA": []}),
    lambda r: r.update(author=42),
    lambda r: r.update(scene_title=None),
    lambda r: r.update(ordered_flow=[]),
])
def test_strict_structure_even_with_rehashed_content(store, mutate):
    raw = make_ass().to_dict()
    mutate(raw)
    _write_raw(store, raw, rehash=True)
    with pytest.raises(OrderedASSIntegrityError):
        store.load(scene_id="SC_900", version=1)


def test_corruption_independently_recomputed(store):
    raw = make_ass().to_dict()
    raw["ordered_flow"][0]["text"] = "Changed but old hash"
    _write_raw(store, raw)
    with pytest.raises(OrderedASSIntegrityError, match="hash mismatch"):
        store.load(scene_id="SC_900", version=1)


@pytest.mark.parametrize("field,value", [("scene_id", "other"), ("version", 2)])
def test_identity_in_file_must_match_locator(store, field, value):
    raw = make_ass().to_dict()
    raw[field] = value
    _write_raw(store, raw, rehash=True)
    with pytest.raises(OrderedASSIntegrityError, match="scene_id/version"):
        store.load(scene_id="SC_900", version=1)


@pytest.mark.parametrize("kwargs", [{"expected_ass_id": "wrong"}, {"expected_content_hash": "0" * 64}])
def test_expected_pin_mismatch(store, kwargs):
    store.save(make_ass())
    with pytest.raises(OrderedASSIntegrityError):
        store.load(scene_id="SC_900", version=1, **kwargs)


def test_identical_resave_is_noop(store, monkeypatch):
    ass = make_ass()
    store.save(ass)
    before = _path(store, ass).stat().st_mtime_ns
    monkeypatch.setattr("services.ass.store.os.link", lambda *a: pytest.fail("must not publish again"))
    assert store.save(ass).to_dict() == ass.to_dict()
    assert _path(store, ass).stat().st_mtime_ns == before


@pytest.mark.parametrize("change", [{"author": "different"}, {"created_at": "different"},
                                     {"supersedes": "other"}, {"ass_id": "different"}])
def test_full_envelope_conflict_with_same_semantic_hash(store, change):
    ass = make_ass()
    store.save(ass)
    other = dataclasses.replace(ass, **change)
    assert other.content_hash == ass.content_hash
    with pytest.raises(OrderedASSConflictError):
        store.save(other)
    assert _path(store, ass).read_bytes() == serialize_ordered_ass(ass)


def test_provenance_only_conflict_preserves_original(store):
    ass = make_ass()
    store.save(ass)
    other = dataclasses.replace(ass, provenance=dataclasses.replace(
        ass.provenance, source_ref="different/ref.json", source_hash="2" * 64))
    assert other.content_hash == ass.content_hash
    with pytest.raises(OrderedASSConflictError):
        store.save(other)
    assert store.load(scene_id=ass.scene_id, version=1).to_dict() == ass.to_dict()


@pytest.mark.parametrize("invalid", [None, {}, make_body()])
def test_save_rejects_non_ordered_objects(store, invalid):
    with pytest.raises(OrderedASSIntegrityError):
        store.save(invalid)
    assert not store._root.exists()


def test_save_rejects_bad_in_memory_hash(store):
    with pytest.raises(OrderedASSIntegrityError):
        store.save(dataclasses.replace(make_ass(), content_hash="0" * 64))
    assert not store._root.exists()


def test_all_entry_types_reload_without_normalization(store):
    body = make_body()
    body["entries"] += [
        {"entry_id": "speech", "kind": "TEXT", "presentation": "DIALOGUE",
         "text": "Привет", "character_id": "KIRA", "thought_visibility": None},
        {"entry_id": "thought", "kind": "TEXT", "presentation": "THOUGHT",
         "text": "Мысль", "character_id": "KIRA", "thought_visibility": "hidden"},
        {"entry_id": "clear", "kind": "VISUAL_CHANGE", "operation": "CLEAR",
         "asset_id": None, "transition": None},
    ]
    body["entries"][1]["options"][0]["target"] = {"target_kind": "ENTRY", "target_id": "speech"}
    ass = build_ordered_ass(SceneBody.from_dict(body), ass_id="ass_test", version=1,
                            source_ref="test.json", source_hash="3" * 64)
    store.save(ass)
    loaded = store.load(scene_id=ass.scene_id, version=1)
    assert loaded.to_dict() == ass.to_dict()
    assert tuple(type(e) for e in loaded.ordered_flow) == tuple(type(e) for e in ass.ordered_flow)


def test_atomic_publication_sees_complete_staged_bytes(store, monkeypatch):
    import services.ass.store as module
    original = module.os.link
    ass = make_ass()
    def publish(src, dst):
        assert Path(src).parent == dst.parent
        assert not dst.exists()
        assert Path(src).read_bytes() == serialize_ordered_ass(ass)
        original(src, dst)
        assert dst.read_bytes() == serialize_ordered_ass(ass)
    monkeypatch.setattr(module.os, "link", publish)
    store.save(ass)
    assert list(_path(store, ass).parent.glob("*.tmp")) == []


@pytest.mark.parametrize("stage", ["fsync", "link"])
def test_write_failure_no_final_file(store, monkeypatch, stage):
    def fail(*args):
        raise OSError("injected")
    monkeypatch.setattr("services.ass.store.os." + stage, fail)
    ass = make_ass()
    with pytest.raises(OrderedASSStoreError):
        store.save(ass)
    assert not _path(store, ass).exists()
    assert list(_path(store, ass).parent.glob("*.tmp")) == []


def test_staged_byte_corruption_is_not_published(store, monkeypatch):
    import services.ass.store as module
    original = module.os.fsync
    def corrupt(fd):
        original(fd)
        module.os.lseek(fd, 0, 0)
        module.os.write(fd, b"!")
    monkeypatch.setattr(module.os, "fsync", corrupt)
    ass = make_ass()
    with pytest.raises(OrderedASSIntegrityError, match="staged ASS bytes"):
        store.save(ass)
    assert not _path(store, ass).exists()
    assert list(_path(store, ass).parent.glob("*.tmp")) == []


def test_noncanonical_file_bytes_rejected_without_rewrite(store):
    ass = make_ass()
    store.save(ass)
    path = _path(store, ass)
    altered = path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(altered)
    with pytest.raises(OrderedASSIntegrityError, match="non-canonical"):
        store.load(scene_id=ass.scene_id, version=1)
    with pytest.raises(OrderedASSIntegrityError):
        store.save(ass)
    assert path.read_bytes() == altered


@pytest.mark.parametrize("identical", [True, False])
def test_concurrent_first_publication_cannot_clobber(store, monkeypatch, identical):
    import services.ass.store as module
    original = module.os.link
    barrier = Barrier(2)
    a = make_ass(author="one")
    b = a if identical else make_ass(author="two")
    def racing_publish(src, dst):
        barrier.wait(timeout=10)
        original(src, dst)
    monkeypatch.setattr(module.os, "link", racing_publish)
    def save(scene):
        try:
            return OrderedASSStore(store._root).save(scene)
        except OrderedASSConflictError as exc:
            return exc
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, (a, b)))
    conflicts = sum(isinstance(r, OrderedASSConflictError) for r in results)
    assert conflicts == (0 if identical else 1)
    winner = store.load(scene_id=a.scene_id, version=1)
    successes = [r for r in results if not isinstance(r, OrderedASSConflictError)]
    assert all(r.to_dict() == winner.to_dict() for r in successes)
    assert list(_path(store, a).parent.glob("*.tmp")) == []


def test_corrupt_existing_artifact_is_not_repaired(store):
    ass = make_ass()
    path = _write_raw(store, {"bad": True})
    before = path.read_bytes()
    with pytest.raises(OrderedASSIntegrityError):
        store.save(ass)
    assert path.read_bytes() == before


def test_retains_old_version_without_discovery(store, monkeypatch):
    a, b = make_ass(), make_ass(version=2)
    store.save(a)
    before = _path(store, a).read_bytes()
    monkeypatch.setattr(Path, "glob", lambda *a: pytest.fail("no scan"))
    monkeypatch.setattr(Path, "rglob", lambda *a: pytest.fail("no recursive scan"))
    monkeypatch.setattr(Path, "iterdir", lambda *a: pytest.fail("no enumeration"))
    store.save(b)
    assert store.load(scene_id=a.scene_id, version=1).to_dict() == a.to_dict()
    assert store.load(scene_id=b.scene_id, version=2).to_dict() == b.to_dict()
    assert _path(store, a).read_bytes() == before
