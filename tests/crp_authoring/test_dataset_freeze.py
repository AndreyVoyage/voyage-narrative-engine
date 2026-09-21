#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRP MVP Slice 10 -- Kira dataset freeze tests (offline, synthetic fixtures).

No provider, no network, no Kira substantive content copy. Verifies the A/B/C
partition isolation, deterministic hashes, A_AUTHORING containment, knowledge
policy, and the A-only projection surface.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from services.crp_authoring import (
    CrpValidationError,
    SourceType,
    build_a_snapshot,
    canonical_json_sha256,
    load_a_projection,
    load_manifest,
    validate_freeze_knowledge_policy,
    verify_manifest,
)
from services.crp_authoring.dataset_freeze import (
    _safe_resolve,
    canonical_text_bytes,
    verify_canonical_text_bytes,
)

FIXTURE_ROOT = Path("tests/fixtures/crp_authoring/kira_dataset_freeze/v1")
MANIFEST_REL = "KIRA_DATASET_FREEZE.manifest.json"
NORMALIZED_REL = "A_AUTHORING/OWNER_AUTHORED_KIRA.normalized.json"


def _manifest():
    return load_manifest(FIXTURE_ROOT, MANIFEST_REL)


def _projection():
    return load_a_projection(FIXTURE_ROOT, MANIFEST_REL)


def _tmp_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "freeze"
    shutil.copytree(FIXTURE_ROOT, dst)
    return dst


# ---------------------------------------------------------------------------
# Structural / integrity
# ---------------------------------------------------------------------------

class TestManifestIntegrity:
    def test_t1_manifest_loads_and_is_frozen(self):
        m = _manifest()
        assert m["status"] == "OWNER_RATIFIED_FROZEN"
        assert m["subject_id"] == "kira"

    def test_manifest_fields_conform(self):
        m = _manifest()
        assert m["schema_version"] == "1"
        assert m["freeze_id"] == "kira-dataset-freeze-v1"
        assert m["freeze_version"] == "1"
        assert m["status"] == "OWNER_RATIFIED_FROZEN"

    def test_artifact_size_field_is_size_bytes_and_legacy_size_rejected(self, tmp_path):
        m = _manifest()
        for art in m["artifacts"]:
            assert "size_bytes" in art
            assert "size" not in art
        # A manifest using the legacy "size" key must fail closed.
        dst = _tmp_copy(tmp_path)
        m2 = load_manifest(dst, MANIFEST_REL)
        for art in m2["artifacts"]:
            art["size"] = art.pop("size_bytes")
        (dst / MANIFEST_REL).write_text(json.dumps(m2, ensure_ascii=False, indent=2), encoding="utf-8")
        with pytest.raises(CrpValidationError):
            verify_manifest(dst, MANIFEST_REL)

    def test_t2_all_non_root_artifacts_verify(self):
        verify_manifest(FIXTURE_ROOT, MANIFEST_REL)  # raises on any mismatch

    def test_t3_root_sha256_verifies(self):
        verify_manifest(FIXTURE_ROOT, MANIFEST_REL)

    def test_t4_a_snapshot_hash_verifies(self):
        proj = _projection()
        assert proj.evidence_snapshot_id.startswith("sha256:")

    def test_t22_malformed_or_unknown_partition_fails_closed(self, tmp_path):
        dst = _tmp_copy(tmp_path)
        m = load_manifest(dst, MANIFEST_REL)
        # Introduce an unknown partition into an artifact entry.
        m["artifacts"][0]["partition"] = "X"
        (dst / MANIFEST_REL).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        with pytest.raises(CrpValidationError):
            verify_manifest(dst, MANIFEST_REL)


# ---------------------------------------------------------------------------
# A-only projection isolation
# ---------------------------------------------------------------------------

class TestAOnlyProjection:
    def test_t5_projection_contains_only_kira_a_ids(self):
        proj = _projection()
        assert proj.evidence
        assert all(ev.source_id.startswith("kira-a-") for ev in proj.evidence)

    def test_t6_projection_includes_substantive_payload(self):
        proj = _projection()
        # At least one payload carries substantive owner facts.
        assert any(len(p["facts"]) > 0 for p in proj.payloads.values())
        assert any("Kira is 26" in f for p in proj.payloads.values() for f in p["facts"])

    def test_t7_no_b_content_enters_projection(self):
        proj = _projection()
        for p in proj.payloads.values():
            for fact in p["facts"]:
                assert "client" not in fact.lower() or "Kira is already practicing psychology" not in fact
        # Specifically: no B scenario text is present.
        joined = " ".join(f for p in proj.payloads.values() for f in p["facts"])
        assert "hyper-controls her adult daughter" not in joined

    def test_t8_no_c_content_enters_projection(self):
        proj = _projection()
        joined = " ".join(f for p in proj.payloads.values() for f in p["facts"])
        assert "git_blob_sha1" not in joined
        assert "benchmark_only" not in joined

    def test_t9_root_manifest_data_does_not_enter_projection(self):
        proj = _projection()
        joined = " ".join(f for p in proj.payloads.values() for f in p["facts"])
        assert "manifest_id" not in joined
        assert "root_sha256" not in joined

    def test_t10_b_never_deserializes_as_source_evidence(self):
        proj = _projection()
        # All materialized evidence is A-only with OWNER_DIRECT source type.
        assert all(ev.source_type is SourceType.OWNER_DIRECT for ev in proj.evidence)
        assert all(ev.provenance == "KIRA_OWNER_INTERVIEW_2026-08-22" for ev in proj.evidence)

    def test_t11_c_never_deserializes_as_source_evidence(self):
        m = _manifest()
        c_paths = [a["path"] for a in m["artifacts"] if a["partition"] == "C"]
        # C artifacts are not under A_AUTHORING.
        assert all(not p.startswith("A_AUTHORING/") for p in c_paths)


class TestPolicyAndHashes:
    def test_t23_missing_forbidden_pattern_fails(self):
        m = dict(_manifest())
        m["knowledge_policy"]["forbidden_refs"] = []
        with pytest.raises(CrpValidationError):
            validate_freeze_knowledge_policy(m)

    def test_t24_nonempty_allowed_kb_refs_fails(self):
        m = dict(_manifest())
        m["knowledge_policy"]["allowed_kb_refs"] = ["legacy/x"]
        with pytest.raises(CrpValidationError):
            validate_freeze_knowledge_policy(m)

    def test_t27_all_a_evidence_share_snapshot_id(self):
        proj = _projection()
        ids = {ev.evidence_snapshot_id for ev in proj.evidence}
        assert ids == {proj.evidence_snapshot_id}

    def test_t28_all_a_content_hashes_verify(self):
        # Recompute each record's content hash against the normalized payload
        # facts and confirm it matches the materialized SourceEvidence.
        normalized = json.loads((FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8"))
        proj = _projection()
        by_ref = {ev.content_ref: ev for ev in proj.evidence}
        for section in normalized["sections"]:
            ref = f"{NORMALIZED_REL}#{section['section_id']}"
            assert by_ref[ref].content_hash == canonical_json_sha256(section["facts"])

    def test_t29_deterministic_regeneration(self):
        _, records1, snapshot1, a1 = build_a_snapshot(FIXTURE_ROOT, NORMALIZED_REL)
        _, records2, snapshot2, a2 = build_a_snapshot(FIXTURE_ROOT, NORMALIZED_REL)
        assert a1 == a2
        assert records1 == records2
        assert snapshot1 == snapshot2

    def test_t12_source_ids_unique_in_materialized_projection(self):
        # The freeze must never emit duplicate source ids (closed-set invariant).
        proj = _projection()
        ids = [ev.source_id for ev in proj.evidence]
        assert len(ids) == len(set(ids))

    def test_t18_symlink_handled_safely(self, tmp_path):
        from services.crp_authoring.dataset_freeze import _reject_symlink
        # A regular file never trips the symlink guard (no false positive).
        regular = tmp_path / "regular.txt"
        regular.write_text("x", encoding="utf-8")
        _reject_symlink(regular)  # must not raise

        # On platforms that expose symlinks, a symlink must be rejected; where
        # symlink creation is unsupported it is treated as safely-unsupported
        # (the containment/existence checks remain authoritative).
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(regular)
            with pytest.raises(CrpValidationError):
                _reject_symlink(link)
        except (OSError, NotImplementedError):
            # Symlink creation unsupported on this filesystem; the guard already
            # returned safely for regular files, satisfying the contract.
            pass


class TestSnapshotMismatchAndContainment:
    def test_t13_snapshot_mismatch_fails_closed(self, tmp_path):
        dst = _tmp_copy(tmp_path)
        m = load_manifest(dst, MANIFEST_REL)
        m["integrity"]["a_snapshot_sha256"] = "0" * 64
        # Recompute root self-hash so only the snapshot hash is wrong.
        from services.crp_authoring.dataset_freeze import canonical_json_sha256
        logical = dict(m)
        logical_integrity = dict(m["integrity"])
        logical_integrity.pop("root_sha256", None)
        logical["integrity"] = logical_integrity
        m["integrity"]["root_sha256"] = canonical_json_sha256(logical)
        (dst / MANIFEST_REL).write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        with pytest.raises(CrpValidationError):
            load_a_projection(dst, MANIFEST_REL)

    def test_t14_content_ref_outside_a_fails_closed(self):
        with pytest.raises(CrpValidationError):
            build_a_snapshot(FIXTURE_ROOT, "B_HIDDEN_EVALUATION/SCENARIOS.json")

    def test_t15_parent_traversal_fails_closed(self):
        with pytest.raises(CrpValidationError):
            _safe_resolve(FIXTURE_ROOT, "../etc/passwd")

    def test_t16_absolute_path_fails_closed(self):
        with pytest.raises(CrpValidationError):
            _safe_resolve(FIXTURE_ROOT, "/etc/passwd")

    def test_t17_separator_tricks_fail_closed(self):
        with pytest.raises(CrpValidationError):
            _safe_resolve(FIXTURE_ROOT, "..\\..\\outside")
        with pytest.raises(CrpValidationError):
            _safe_resolve(FIXTURE_ROOT, "A_AUTHORING/..\\..\\outside")


class TestIntegrityMutation:
    def test_t19_modified_a_artifact_fails_integrity(self, tmp_path):
        dst = _tmp_copy(tmp_path)
        target = dst / "A_AUTHORING/OWNER_AUTHORED_KIRA.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n# tampered", encoding="utf-8")
        with pytest.raises(CrpValidationError):
            verify_manifest(dst, MANIFEST_REL)

    def test_t20_modified_b_artifact_fails_integrity(self, tmp_path):
        dst = _tmp_copy(tmp_path)
        target = dst / "B_HIDDEN_EVALUATION/SCENARIOS.json"
        target.write_text(target.read_text(encoding="utf-8") + "\n{}", encoding="utf-8")
        with pytest.raises(CrpValidationError):
            verify_manifest(dst, MANIFEST_REL)

    def test_t21_modified_c_metadata_artifact_fails_integrity(self, tmp_path):
        dst = _tmp_copy(tmp_path)
        target = dst / "C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json"
        target.write_text(target.read_text(encoding="utf-8") + "\n// tampered", encoding="utf-8")
        with pytest.raises(CrpValidationError):
            verify_manifest(dst, MANIFEST_REL)


class TestAContentConformance:
    """Slice 10 correction: owner-confirmed A content restored + parity."""

    def _md(self) -> str:
        return (FIXTURE_ROOT / "A_AUTHORING/OWNER_AUTHORED_KIRA.md").read_text(encoding="utf-8")

    def _norm(self):
        return json.loads((FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8"))

    def _facts(self) -> str:
        norm = self._norm()
        return " ".join(f for s in norm["sections"] for f in s["facts"])

    def test_past_controlling_partner_present(self):
        md = self._md()
        facts = self._facts()
        assert "controlling partner" in md
        assert "controlling partner" in facts
        assert "behavior, social circle" in md or "social circle" in md
        assert "could not continue living under that level" in md

    def test_early_modesty_present(self):
        md = self._md()
        facts = self._facts()
        assert "modest and shy" in md
        assert "modest and shy" in facts
        assert "gradual" in md
        assert "gradually" in facts

    def test_social_circle_present(self):
        md = self._md()
        facts = self._facts()
        assert "acquaintances" in md
        assert "acquaintances" in facts
        assert "social circle" in md

    def test_relationship_saving_rollback_present(self):
        facts = self._facts()
        assert "Relationship-saving rollback is distinct from self-initiated rehabilitation" in facts
        assert "willingness to reduce some freedoms" in facts

    def test_sport_nostalgia_control_conflict_present(self):
        facts = self._facts()
        assert "sport can temporarily outweigh her usual resistance to external control" in facts

    def test_leadership_hyper_control_distinction_present(self):
        facts = self._facts()
        assert "distinguish demanding leadership from suppression" in facts

    def test_markdown_normalized_section_parity(self):
        md = self._md()
        norm = self._norm()
        # Markdown headings are the uppercase rendering of the normalized title
        # (compared case-insensitively, since some MD headings keep mixed case for
        # the parenthetical qualifier).
        for s in norm["sections"]:
            heading = s["title"].upper()
            assert f"## {heading}\n".lower() in md.lower(), \
                f"section title {s['title']!r} missing in markdown"

    def test_no_normalized_only_owner_facts(self):
        # The normalized file must not contain semantic sections absent from
        # Markdown; verified by matching section count parity.
        md = self._md()
        norm = self._norm()
        assert len(norm["sections"]) == md.count("\n## ")

    def test_confidentiality_general_not_marina_only(self):
        facts = self._facts()
        assert "A personally entrusted confidential secret from someone close is a strong boundary" in facts
        # The general principle comes first; Marina is framed as an example.
        assert "Marina's secret is one example" in facts

    def test_attractiveness_insight_developmental_qualifier(self):
        facts = self._facts()
        assert "gradually comes to understand" in facts
        assert "not a timeless static trait" in facts

    def test_guilt_shame_anger_explicit(self):
        facts = self._facts()
        assert "Guilt, shame, and anger at herself" in facts

    def test_parties_demonstrative_development(self):
        md = self._md()
        facts = self._facts()
        assert "may not understand the appeal of parties" in facts
        assert "development possibility" in facts
        assert "not an unconditional starting trait" in facts

    def test_psychology_daily_life(self):
        facts = self._facts()
        assert "inseparable from her personality and profession" in facts
        assert "not make her immune to emotion" in facts

    def test_playful_competition_and_gossip(self):
        facts = self._facts()
        assert "who is faster / who is higher" in facts
        assert "friendly gossip with close girlfriends" in facts


class TestBScenarioRestoration:
    """Slice 10 correction: hidden-B scenarios preserve full conditions."""

    def _scenarios(self):
        data = json.loads((FIXTURE_ROOT / "B_HIDDEN_EVALUATION/SCENARIOS.json").read_text(encoding="utf-8"))
        return {r["id"]: r for r in data["records"]}

    def test_b2_coach_helped_kira_condition(self):
        s = self._scenarios()["kira-b-002"]
        assert "did help Kira herself achieve serious sporting results" in s["scenario"]
        assert "not that a strict coach is simply bad" in s["scenario"]

    def test_b3_bias_vs_knowing_andrey_conflict(self):
        s = self._scenarios()["kira-b-003"]
        assert "confirmation of her own jealousy or bias" in s["scenario"]
        assert "she genuinely feels that something is wrong" in s["scenario"]

    def test_b6_three_part_question(self):
        s = self._scenarios()["kira-b-006"]
        assert "what does she say to the client" in s["question"].lower()
        assert "how does she react later" in s["question"].lower()

    def test_b8_andrey_husband_separate_home_context(self):
        s = self._scenarios()["kira-b-008"]
        assert "Andrey is Kira's husband" in s["scenario"]
        assert "lives separately from her mother with Andrey" in s["scenario"]

    def test_no_hidden_answer_leakage_into_a(self):
        md = (FIXTURE_ROOT / "A_AUTHORING/OWNER_AUTHORED_KIRA.md").read_text(encoding="utf-8")
        norm = (FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8")
        for sentinel in ("I cooked dinner for you", "We are not for everyone", "I will handle it"):
            assert sentinel not in md
            assert sentinel not in norm
        # B answer sentinel for b-008 must also be absent.
        assert "partly a piece of you" not in md
        assert "partly a piece of you" not in norm


class TestB36FinalCorridors:
    """Slice 10 final correction: owner-ratified B3/B6 reference corridors."""

    def _answers(self):
        data = json.loads((FIXTURE_ROOT / "B_HIDDEN_EVALUATION/OWNER_REFERENCE_ANSWERS.json").read_text(encoding="utf-8"))
        return {r["id"]: r["answer"] for r in data["records"]}

    def test_b3_holds_both_possibilities(self):
        a = self._answers()["kira-b-003"]
        assert "jealousy may distort her perception" in a
        assert "genuinely sees/feels that something is wrong" in a

    def test_b3_care_before_confrontation(self):
        a = self._answers()["kira-b-003"]
        assert "creates care and closeness" in a
        assert "calmly asks what happened" in a
        assert "does NOT begin with accusation or interrogation" in a

    def test_b3_no_suspicion_as_proof(self):
        a = self._answers()["kira-b-003"]
        assert "does NOT declare her suspicion to be established fact" in a
        assert "MUST NOT: immediately accuse Andrey of cheating" in a

    def test_b6_covers_three_phases_and_reflected_stance(self):
        a = self._answers()["kira-b-006"]
        assert "mild professional sting" in a
        assert "remains professional and calm" in a
        assert "another specialist may fit the client better" in a
        assert "We are not for everyone, and everyone is not for us." in a

    def test_b6_no_humiliation_or_resentment(self):
        a = self._answers()["kira-b-006"]
        assert "MUST NOT: treat successful transfer as personal humiliation" in a
        assert "resent the client for improving elsewhere" in a
        assert "conclude she must adapt herself to everyone" in a

    def test_b3_b6_absent_from_a(self):
        md = (FIXTURE_ROOT / "A_AUTHORING/OWNER_AUTHORED_KIRA.md").read_text(encoding="utf-8")
        norm = (FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8")
        for sentinel in ("MUST NOT: immediately accuse", "We are not for everyone, and everyone is not for us."):
            assert sentinel not in md
            assert sentinel not in norm

    def test_final_a_snapshot_valid(self):
        m = _manifest()
        assert m["integrity"]["a_snapshot_sha256"] == (
            "88f9c822a9d56f7154472c0192511fdc6402c1379a4cc040df287a99f81d5386"
        )

    def test_evidence_snapshot_id_full_and_exact(self):
        m = _manifest()
        evid = m["a_snapshot"]["evidence_snapshot_id"]
        assert evid == "sha256:88f9c822a9d56f7154472c0192511fdc6402c1379a4cc040df287a99f81d5386"
        assert len(evid.split("sha256:")[1]) == 64


class TestFrozenStatus:
    """Slice 10 final promotion: lifecycle status markers synchronized."""

    def test_manifest_status_frozen(self):
        assert _manifest()["status"] == "OWNER_RATIFIED_FROZEN"

    def test_markdown_status_marker_agrees(self):
        md = (FIXTURE_ROOT / "A_AUTHORING/OWNER_AUTHORED_KIRA.md").read_text(encoding="utf-8")
        assert "STATUS: OWNER_RATIFIED_FROZEN" in md

    def test_normalized_status_marker_agrees(self):
        norm = json.loads((FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8"))
        assert norm.get("status") == "OWNER_RATIFIED_FROZEN"

    def test_status_markers_no_draft_remnant(self):
        md = (FIXTURE_ROOT / "A_AUTHORING/OWNER_AUTHORED_KIRA.md").read_text(encoding="utf-8")
        norm = (FIXTURE_ROOT / NORMALIZED_REL).read_text(encoding="utf-8")
        assert "DRAFT" not in md
        assert "DRAFT" not in norm


class TestByteCanonicalization:
    """Slice 10 byte-contract correction regression tests."""

    TEXT_ARTIFACTS = [
        "A_AUTHORING/OWNER_AUTHORED_KIRA.md",
        "A_AUTHORING/OWNER_AUTHORED_KIRA.normalized.json",
        "A_AUTHORING/SOURCE_EVIDENCE_SNAPSHOT.json",
        "B_HIDDEN_EVALUATION/SCENARIOS.json",
        "B_HIDDEN_EVALUATION/OWNER_REFERENCE_ANSWERS.json",
        "C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json",
        "KIRA_DATASET_FREEZE.manifest.json",
    ]

    def _bytes(self, rel):
        return (FIXTURE_ROOT / rel).read_bytes()

    def test_byte_01_no_bom(self):
        for rel in self.TEXT_ARTIFACTS:
            assert not self._bytes(rel).startswith(b"\xef\xbb\xbf"), rel

    def test_byte_02_no_cr(self):
        for rel in self.TEXT_ARTIFACTS:
            assert b"\r" not in self._bytes(rel), rel

    def test_byte_03_exactly_one_final_lf(self):
        for rel in self.TEXT_ARTIFACTS:
            b = self._bytes(rel)
            assert b.endswith(b"\n") and not b.endswith(b"\n\n"), rel

    def test_byte_04_crlf_mutation_fails_closed(self):
        data = self._bytes("A_AUTHORING/OWNER_AUTHORED_KIRA.md")
        mut = data.replace(b"\n", b"\r\n")
        with pytest.raises(CrpValidationError):
            verify_canonical_text_bytes(mut)

    def test_byte_05_lone_cr_mutation_fails_closed(self):
        data = self._bytes("A_AUTHORING/OWNER_AUTHORED_KIRA.md")
        mut = data.replace(b"\n", b"\r")
        with pytest.raises(CrpValidationError):
            verify_canonical_text_bytes(mut)

    def test_byte_06_missing_final_newline_fails_closed(self):
        data = self._bytes("A_AUTHORING/OWNER_AUTHORED_KIRA.md")
        mut = data.rstrip(b"\n")
        with pytest.raises(CrpValidationError):
            verify_canonical_text_bytes(mut)

    def test_byte_07_extra_final_newline_fails_closed(self):
        data = self._bytes("A_AUTHORING/OWNER_AUTHORED_KIRA.md")
        mut = data + b"\n"
        with pytest.raises(CrpValidationError):
            verify_canonical_text_bytes(mut)

    def test_byte_08_bom_mutation_fails_closed(self):
        data = self._bytes("A_AUTHORING/OWNER_AUTHORED_KIRA.md")
        mut = b"\xef\xbb\xbf" + data
        with pytest.raises(CrpValidationError):
            verify_canonical_text_bytes(mut)

    def test_byte_09_canonicalization_preserves_json_values(self):
        for rel in ("B_HIDDEN_EVALUATION/SCENARIOS.json", "A_AUTHORING/OWNER_AUTHORED_KIRA.normalized.json"):
            raw = self._bytes(rel)
            canonical = canonical_text_bytes(raw)
            assert json.loads(raw.decode("utf-8")) == json.loads(canonical.decode("utf-8"))

    def test_byte_10_canonicalization_preserves_md_line_content(self):
        md = "A_AUTHORING/OWNER_AUTHORED_KIRA.md"
        raw = self._bytes(md)
        canonical = canonical_text_bytes(raw)
        # Line content preserved after EOL normalization (already canonical).
        assert raw.decode("utf-8").split("\n") == canonical.decode("utf-8").split("\n")

    def test_byte_11_b3_semantic_unchanged(self):
        scenarios = json.loads((FIXTURE_ROOT / "B_HIDDEN_EVALUATION/SCENARIOS.json").read_text(encoding="utf-8"))
        b3 = [r for r in scenarios["records"] if r["id"] == "kira-b-003"][0]
        assert "another woman is possible" in b3["scenario"]

    def test_byte_12_b6_semantic_unchanged(self):
        scenarios = json.loads((FIXTURE_ROOT / "B_HIDDEN_EVALUATION/SCENARIOS.json").read_text(encoding="utf-8"))
        b6 = [r for r in scenarios["records"] if r["id"] == "kira-b-006"][0]
        assert "improved with another psychologist" in b6["scenario"]

    def test_byte_13_anti_leakage_still_passes(self):
        TestBScenarioRestoration().test_no_hidden_answer_leakage_into_a()

    def test_byte_14_manifest_hashes_match_canonical_bytes(self):
        m = _manifest()
        by_path = {a["path"]: a for a in m["artifacts"]}
        for rel in self.TEXT_ARTIFACTS:
            if rel == "KIRA_DATASET_FREEZE.manifest.json":
                continue
            raw = self._bytes(rel)
            import hashlib
            assert hashlib.sha256(raw).hexdigest() == by_path[rel]["sha256"]
            assert len(raw) == by_path[rel]["size_bytes"]

    def test_byte_15_root_sha256_validates(self):
        verify_manifest(FIXTURE_ROOT, MANIFEST_REL)

    def test_byte_16_a_snapshot_validates(self):
        assert _projection().evidence_snapshot_id.startswith("sha256:")


class TestLegacyBoundary:
    def test_t25_b_like_evidence_id_unknown(self):
        proj = _projection()
        ids = {ev.source_id for ev in proj.evidence}
        # kira-b-* ids cannot appear as A source ids.
        assert not any(i.startswith("kira-b-") for i in ids)

    def test_t26_legacy_c_like_evidence_id_unknown(self):
        proj = _projection()
        ids = {ev.source_id for ev in proj.evidence}
        # No evidence references legacy personas/kira paths.
        assert all(not ev.content_ref.startswith("personas/") for ev in proj.evidence)

    def test_t30_no_substantive_legacy_content_in_c_fixture(self):
        c = json.loads((FIXTURE_ROOT / "C_LEGACY_BENCHMARK/LEGACY_REFERENCES.json").read_text(encoding="utf-8"))
        text = json.dumps(c, ensure_ascii=False)
        # C carries only metadata fields; no free-form legacy prose.
        assert "claim" not in c
        assert "psychology" not in text.lower()