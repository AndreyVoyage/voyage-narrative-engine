#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidated Memory v1 -- selective, verbatim-first, human-approved.

One Memory architecture: the raw runtime **Event Log** (``memory.py``) stays
append-only and authoritative as history. This module adds two more
append-only persistence structures *in the SAME per-workspace database file*
(``runtime_memory.sqlite3``) -- it never opens a new DB and never touches the
Runtime State DB:

    runtime_events                  (existing -- unchanged)
    memory_promotion_candidates     (new -- an operator picked this event)
    memory_promotion_decisions      (new -- append-only APPROVE / REJECT ledger)
    consolidated_memory_records     (new -- approved durable records)
    consolidated_memory_relations   (new -- operator-declared SUPERSEDES / CONFLICTS_WITH)

Flow (V1):

    runtime event  ->  eligibility validation  ->  MemoryPromotionCandidate
        ->  explicit operator APPROVE / REJECT
        ->  (on APPROVE) one verbatim-first ConsolidatedMemoryRecord

Hard V1 limits, matching the owner decisions:

- NO LLM summarization -- one approved source event -> one verbatim record
  (``basis_event_ids`` holds exactly ONE id). No multi-event merge.
- NO automatic selection -- the operator selects the source event; this layer
  only *validates* it. No salience scanning.
- NO automatic forgetting / decay / TTL.
- NO embeddings / vector / graph retrieval -- exact normalized dedupe only.
- NO autonomous promotion -- approval is always explicit.
- Epistemic honesty: a record promoted from a ``USER_STATED`` event is a
  ``USER_REPORT`` ("the user stated this"), never a ``WORLD_FACT``. A
  ``CHARACTER_UTTERANCE`` can NEVER be promoted.
- This module never alters RELATIONSHIP / PSYCHOLOGY / FACT Runtime State, the
  Accepted Package, or dimension semantics.

Every table is append-only. "Supersede" is expressed by an operator-declared
relation row, not by editing or deleting the superseded record; active-ness is
*derived* at read time.

Standard library only. No provider, no network. Writes only under the
caller-supplied ``root``.
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

# ---- V1 vocabularies (plain strings -- adding a value never migrates schema) --

MEMORY_KIND_EPISODIC = "EPISODIC"
MEMORY_KIND_SEMANTIC = "SEMANTIC"
#: The only two memory kinds in V1. Relationship / emotional / self-narrative
#: kinds are explicitly deferred (may become future values if evidence
#: justifies them) -- this slice does not build those engines.
MEMORY_KINDS: Tuple[str, ...] = (MEMORY_KIND_EPISODIC, MEMORY_KIND_SEMANTIC)

#: Epistemic kind of a record. V1 only ever promotes user reports.
#: ``USER_REPORT`` == "the user reported/stated this", NOT "verified world
#: truth". ``WORLD_FACT`` is deliberately NOT a value here.
EPISTEMIC_USER_REPORT = "USER_REPORT"
EPISTEMIC_KINDS: Tuple[str, ...] = (EPISTEMIC_USER_REPORT,)

DECISION_APPROVE = "APPROVE"
DECISION_REJECT = "REJECT"
DECISIONS: Tuple[str, ...] = (DECISION_APPROVE, DECISION_REJECT)

RELATION_SUPERSEDES = "SUPERSEDES"
RELATION_CONFLICTS_WITH = "CONFLICTS_WITH"
RELATION_KINDS: Tuple[str, ...] = (RELATION_SUPERSEDES, RELATION_CONFLICTS_WITH)

RECORD_STATUS_ACTIVE = "ACTIVE"
RECORD_STATUS_SUPERSEDED = "SUPERSEDED"

#: Provenance strings shared with ``services.character_lab.provenance`` (kept
#: as local literals so this runtime module never imports Character Lab).
PROVENANCE_USER_STATED = "USER_STATED"
PROVENANCE_CHARACTER_UTTERANCE = "CHARACTER_UTTERANCE"

#: Runtime event types accepted as a promotion source. A character message is
#: never a source (see the CHARACTER_UTTERANCE safety rule).
ELIGIBLE_SOURCE_EVENT_TYPES: Tuple[str, ...] = ("USER_MESSAGE",)

_DB_FILENAME = "runtime_memory.sqlite3"

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS memory_promotion_candidates (
        candidate_id   TEXT PRIMARY KEY,
        subject_id     TEXT NOT NULL,
        source_event_id TEXT NOT NULL,
        memory_kind    TEXT NOT NULL,
        epistemic_kind TEXT NOT NULL,
        provenance     TEXT NOT NULL,
        meaning        TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        seq            INTEGER
    );
    CREATE TABLE IF NOT EXISTS memory_promotion_decisions (
        decision_id    TEXT PRIMARY KEY,
        candidate_id   TEXT NOT NULL,
        decision       TEXT NOT NULL,
        decided_by     TEXT,
        record_id      TEXT,
        note           TEXT,
        created_at     TEXT NOT NULL,
        seq            INTEGER
    );
    CREATE TABLE IF NOT EXISTS consolidated_memory_records (
        record_id        TEXT PRIMARY KEY,
        subject_id       TEXT NOT NULL,
        source_event_id  TEXT NOT NULL,
        memory_kind      TEXT NOT NULL,
        epistemic_kind   TEXT NOT NULL,
        provenance       TEXT NOT NULL,
        meaning          TEXT NOT NULL,
        normalized_meaning TEXT NOT NULL,
        status_at_creation TEXT NOT NULL,
        holder_id        TEXT,
        candidate_id     TEXT NOT NULL,
        decision_id      TEXT NOT NULL,
        approved_by      TEXT,
        created_at       TEXT NOT NULL,
        seq              INTEGER
    );
    CREATE TABLE IF NOT EXISTS consolidated_memory_relations (
        relation_id    TEXT PRIMARY KEY,
        subject_id     TEXT NOT NULL,
        kind           TEXT NOT NULL,
        from_record_id TEXT NOT NULL,
        to_record_id   TEXT NOT NULL,
        declared_by    TEXT,
        created_at     TEXT NOT NULL,
        seq            INTEGER
    );
    """
)


class ConsolidatedMemoryError(RuntimeError):
    """Fail-closed error for the Consolidated Memory layer."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_meaning(text: str) -> str:
    """Minimal deterministic normalization for exact dedupe: collapse
    whitespace and case-fold. No stemming, no semantic analysis."""
    return " ".join((text or "").split()).casefold()


# --------------------------------------------------------------------------
# Domain records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryPromotionCandidate:
    candidate_id: str
    subject_id: str
    source_event_id: str
    memory_kind: str
    epistemic_kind: str
    provenance: str
    meaning: str
    created_at: str
    seq: Optional[int] = None

    @property
    def basis_event_ids(self) -> Tuple[str, ...]:
        return (self.source_event_id,)


@dataclass(frozen=True)
class MemoryPromotionDecision:
    decision_id: str
    candidate_id: str
    decision: str
    decided_by: Optional[str]
    record_id: Optional[str]
    note: Optional[str]
    created_at: str
    seq: Optional[int] = None


@dataclass(frozen=True)
class ConsolidatedMemoryRecord:
    record_id: str
    subject_id: str
    source_event_id: str
    memory_kind: str
    epistemic_kind: str
    provenance: str
    meaning: str
    normalized_meaning: str
    candidate_id: str
    decision_id: str
    approved_by: Optional[str]
    created_at: str
    #: DERIVED at read time from relations, never stored mutable.
    status: str = RECORD_STATUS_ACTIVE
    holder_id: Optional[str] = None
    seq: Optional[int] = None
    #: When ``status == SUPERSEDED``, the record that superseded it.
    superseded_by_record_id: Optional[str] = None

    @property
    def basis_event_ids(self) -> Tuple[str, ...]:
        return (self.source_event_id,)


@dataclass(frozen=True)
class MemoryRelation:
    relation_id: str
    subject_id: str
    kind: str
    from_record_id: str
    to_record_id: str
    declared_by: Optional[str]
    created_at: str
    seq: Optional[int] = None


# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------


class ConsolidatedMemoryBackend:
    """Append-only Consolidated Memory store, sharing the per-workspace
    ``runtime_memory.sqlite3`` file with :class:`RuntimeMemoryBackend`."""

    def __init__(self, root: Path, subject_id: str) -> None:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ConsolidatedMemoryError("subject_id must be a non-empty string")
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self._subject_id = subject_id
        self._db_path = root / _DB_FILENAME
        self._conn = sqlite3.connect(str(self._db_path))
        try:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.close()
            raise ConsolidatedMemoryError(
                f"failed to initialise consolidated memory: {exc}"
            ) from exc

    @property
    def subject_id(self) -> str:
        return self._subject_id

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    # -- internal --------------------------------------------------------
    def _require_open(self) -> None:
        if self._conn is None:
            raise ConsolidatedMemoryError("consolidated memory backend is closed")

    def _insert_with_seq(self, table: str, columns: Sequence[str], values: Sequence, key_col: str) -> int:
        placeholders = ", ".join("?" for _ in columns)
        cur = self._conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values),
        )
        key_val = values[list(columns).index(key_col)]
        self._conn.execute(
            f"UPDATE {table} SET seq = ? WHERE {key_col} = ?",
            (cur.lastrowid, key_val),
        )
        self._conn.commit()
        return cur.lastrowid

    # -- relations (shared by decide(... relations=...) and declare_relation) --
    def _record_exists(self, subject_id: str, record_id: str) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM consolidated_memory_records WHERE record_id = ? "
                "AND subject_id = ? LIMIT 1",
                (record_id, subject_id),
            ).fetchone()
            is not None
        )

    def _relation_row_exists(
        self, subject_id: str, kind: str, from_record_id: str, to_record_id: str
    ) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM consolidated_memory_relations WHERE subject_id = ? "
                "AND kind = ? AND from_record_id = ? AND to_record_id = ? LIMIT 1",
                (subject_id, kind, from_record_id, to_record_id),
            ).fetchone()
            is not None
        )

    def _append_relation(
        self,
        *,
        subject_id: str,
        kind: str,
        from_record_id: str,
        to_record_id: str,
        declared_by: Optional[str],
    ) -> MemoryRelation:
        """Append ONE relation row (no UPDATE, no DELETE, no mirror row).

        The single insertion point used by both the approval-time
        ``decide(..., relations=[...])`` path and the standalone
        :meth:`declare_relation`, so the two share exactly one row format,
        one id scheme (``memrel-…``) and one seq mechanism.
        """
        relation_id = f"memrel-{uuid.uuid4().hex}"
        created_at = _now_iso()
        cols = ("relation_id", "subject_id", "kind", "from_record_id",
                "to_record_id", "declared_by", "created_at")
        vals = (relation_id, subject_id, kind, from_record_id, to_record_id,
                declared_by, created_at)
        seq = self._insert_with_seq("consolidated_memory_relations", cols, vals, "relation_id")
        return MemoryRelation(
            relation_id=relation_id, subject_id=subject_id, kind=kind,
            from_record_id=from_record_id, to_record_id=to_record_id,
            declared_by=declared_by, created_at=created_at, seq=seq,
        )

    # -- eligibility + candidate --------------------------------------------
    def propose(
        self,
        *,
        memory_backend,
        source_event_id: str,
        memory_kind: str = MEMORY_KIND_SEMANTIC,
        subject_id: Optional[str] = None,
    ) -> MemoryPromotionCandidate:
        """Validate an operator-selected source event and create a PENDING
        candidate. Does NOT create consolidated memory.

        Fail-closed :class:`ConsolidatedMemoryError` when the event is missing,
        is not a ``USER_MESSAGE`` / ``USER_STATED`` event (e.g. a
        ``CHARACTER_UTTERANCE``), has empty content, or belongs to a different
        subject/workspace than this backend.
        """
        self._require_open()
        subject_id = subject_id or self._subject_id
        if subject_id != self._subject_id:
            raise ConsolidatedMemoryError(
                f"subject {subject_id!r} != backend subject {self._subject_id!r}"
            )
        if memory_kind not in MEMORY_KINDS:
            raise ConsolidatedMemoryError(
                f"memory_kind must be one of {MEMORY_KINDS}, got {memory_kind!r}"
            )
        if not isinstance(source_event_id, str) or not source_event_id.strip():
            raise ConsolidatedMemoryError("source_event_id must be a non-empty string")

        events = memory_backend.load_events_causal(subject_id)
        event = next((e for e in events if e.event_id == source_event_id), None)
        if event is None:
            raise ConsolidatedMemoryError(
                f"source event {source_event_id!r} not found in this workspace memory"
            )
        if event.subject_id != self._subject_id:
            raise ConsolidatedMemoryError(
                "source event belongs to a different subject/workspace"
            )
        if event.event_type not in ELIGIBLE_SOURCE_EVENT_TYPES:
            raise ConsolidatedMemoryError(
                f"ineligible: event_type {event.event_type!r} is not a promotable "
                f"user event (allowed: {ELIGIBLE_SOURCE_EVENT_TYPES}); a character "
                "utterance can never become consolidated memory"
            )
        if event.provenance != PROVENANCE_USER_STATED:
            raise ConsolidatedMemoryError(
                f"ineligible: provenance {event.provenance!r} is not "
                f"{PROVENANCE_USER_STATED!r}; only explicitly user-stated events "
                "are promotable in V1"
            )
        if not str(event.meaning).strip():
            raise ConsolidatedMemoryError("ineligible: source event has empty content")

        candidate_id = f"memcand-{uuid.uuid4().hex}"
        created_at = _now_iso()
        cols = ("candidate_id", "subject_id", "source_event_id", "memory_kind",
                "epistemic_kind", "provenance", "meaning", "created_at")
        vals = (candidate_id, self._subject_id, source_event_id, memory_kind,
                EPISTEMIC_USER_REPORT, event.provenance, event.meaning, created_at)
        seq = self._insert_with_seq("memory_promotion_candidates", cols, vals, "candidate_id")
        return MemoryPromotionCandidate(
            candidate_id=candidate_id, subject_id=self._subject_id,
            source_event_id=source_event_id, memory_kind=memory_kind,
            epistemic_kind=EPISTEMIC_USER_REPORT, provenance=event.provenance,
            meaning=event.meaning, created_at=created_at, seq=seq,
        )

    # -- decision -----------------------------------------------------------
    def decide(
        self,
        *,
        candidate_id: str,
        decision: str,
        decided_by: Optional[str] = None,
        note: Optional[str] = None,
        relations: Iterable[Tuple[str, str]] = (),
    ) -> MemoryPromotionDecision:
        """Record an explicit operator APPROVE / REJECT (append-only).

        ``relations`` (only on APPROVE) is a list of operator-declared
        ``(kind, target_record_id)`` pairs, ``kind`` in
        :data:`RELATION_KINDS`. On APPROVE a single verbatim
        :class:`ConsolidatedMemoryRecord` is created (exact-duplicate blocked);
        on REJECT nothing is created.
        """
        self._require_open()
        if decision not in DECISIONS:
            raise ConsolidatedMemoryError(f"decision must be one of {DECISIONS}")
        row = self._conn.execute(
            "SELECT subject_id, source_event_id, memory_kind, epistemic_kind, "
            "provenance, meaning FROM memory_promotion_candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise ConsolidatedMemoryError(f"unknown candidate {candidate_id!r}")
        already = self._conn.execute(
            "SELECT 1 FROM memory_promotion_decisions WHERE candidate_id = ? LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if already is not None:
            raise ConsolidatedMemoryError(
                f"candidate {candidate_id!r} was already decided (decisions are final)"
            )

        rel_list = list(relations or ())
        if rel_list and decision != DECISION_APPROVE:
            raise ConsolidatedMemoryError("relations are only valid on APPROVE")

        c_subject, c_src, c_kind, c_epi, c_prov, c_meaning = row
        decision_id = f"memdec-{uuid.uuid4().hex}"
        created_at = _now_iso()
        record_id: Optional[str] = None

        if decision == DECISION_APPROVE:
            normalized = normalize_meaning(c_meaning)
            for existing in self.load_active_records(c_subject):
                if (
                    existing.normalized_meaning == normalized
                    and existing.epistemic_kind == c_epi
                ):
                    raise ConsolidatedMemoryError(
                        "duplicate: an active consolidated record with the same "
                        f"normalized meaning already exists (record_id="
                        f"{existing.record_id!r})"
                    )
            # validate relation targets up front (fail before any write)
            for kind, target in rel_list:
                if kind not in RELATION_KINDS:
                    raise ConsolidatedMemoryError(
                        f"relation kind must be one of {RELATION_KINDS}, got {kind!r}"
                    )
                tgt = self._conn.execute(
                    "SELECT 1 FROM consolidated_memory_records WHERE record_id = ? "
                    "AND subject_id = ?",
                    (target, c_subject),
                ).fetchone()
                if tgt is None:
                    raise ConsolidatedMemoryError(
                        f"relation target record {target!r} does not exist for this subject"
                    )

            record_id = f"memrec-{uuid.uuid4().hex}"
            rec_cols = ("record_id", "subject_id", "source_event_id", "memory_kind",
                        "epistemic_kind", "provenance", "meaning", "normalized_meaning",
                        "status_at_creation", "holder_id", "candidate_id", "decision_id",
                        "approved_by", "created_at")
            rec_vals = (record_id, c_subject, c_src, c_kind, c_epi, c_prov, c_meaning,
                        normalized, RECORD_STATUS_ACTIVE, None, candidate_id, decision_id,
                        decided_by, created_at)
            self._insert_with_seq("consolidated_memory_records", rec_cols, rec_vals, "record_id")

            for kind, target in rel_list:
                self._append_relation(
                    subject_id=c_subject, kind=kind,
                    from_record_id=record_id, to_record_id=target,
                    declared_by=decided_by,
                )

        dec_cols = ("decision_id", "candidate_id", "decision", "decided_by",
                    "record_id", "note", "created_at")
        dec_vals = (decision_id, candidate_id, decision, decided_by, record_id, note, created_at)
        seq = self._insert_with_seq("memory_promotion_decisions", dec_cols, dec_vals, "decision_id")

        return MemoryPromotionDecision(
            decision_id=decision_id, candidate_id=candidate_id, decision=decision,
            decided_by=decided_by, record_id=record_id, note=note,
            created_at=created_at, seq=seq,
        )

    # -- standalone relation ---------------------------------------------
    def declare_relation(
        self,
        *,
        from_record_id: str,
        to_record_id: str,
        kind: str,
        declared_by: Optional[str] = None,
    ) -> MemoryRelation:
        """Operator-declare a relation between TWO ALREADY-APPROVED records.

        Additive and append-only: inserts exactly one row into
        ``consolidated_memory_relations`` (no UPDATE, no DELETE, no record
        mutation, no schema change, no mirror row). Existing derived
        semantics are unchanged -- ``SUPERSEDES`` is directional
        (``from`` supersedes ``to``; ``to`` becomes derived ``SUPERSEDED``,
        ``from`` stays active unless separately superseded), ``CONFLICTS_WITH``
        leaves both records active with the conflict surfaced (unresolved,
        auditable) for both by :meth:`active_conflict_record_ids`.

        Fail-closed :class:`ConsolidatedMemoryError` for: an unknown relation
        kind; a self-relation; a missing ``from``/``to`` record; a record from
        a different workspace/subject (each per-workspace DB only contains its
        own subject's records, so a foreign id simply "does not exist" here);
        or an EXACT duplicate declaration (same ``from`` + ``to`` + ``kind``).
        """
        self._require_open()
        if kind not in RELATION_KINDS:
            raise ConsolidatedMemoryError(
                f"relation kind must be one of {RELATION_KINDS}, got {kind!r}"
            )
        for name, value in (("from_record_id", from_record_id), ("to_record_id", to_record_id)):
            if not isinstance(value, str) or not value.strip():
                raise ConsolidatedMemoryError(f"{name} must be a non-empty string")
        from_record_id = from_record_id.strip()
        to_record_id = to_record_id.strip()
        if from_record_id == to_record_id:
            raise ConsolidatedMemoryError("a record cannot relate to itself")
        if not self._record_exists(self._subject_id, from_record_id):
            raise ConsolidatedMemoryError(
                f"from_record {from_record_id!r} does not exist for this subject/workspace"
            )
        if not self._record_exists(self._subject_id, to_record_id):
            raise ConsolidatedMemoryError(
                f"to_record {to_record_id!r} does not exist for this subject/workspace"
            )
        if self._relation_row_exists(self._subject_id, kind, from_record_id, to_record_id):
            raise ConsolidatedMemoryError(
                f"duplicate relation: {kind} from {from_record_id!r} to "
                f"{to_record_id!r} already exists"
            )
        return self._append_relation(
            subject_id=self._subject_id, kind=kind,
            from_record_id=from_record_id, to_record_id=to_record_id,
            declared_by=declared_by,
        )

    # -- reads ------------------------------------------------------------
    def _all_relations(self, subject_id: str) -> Tuple[MemoryRelation, ...]:
        rows = self._conn.execute(
            "SELECT relation_id, subject_id, kind, from_record_id, to_record_id, "
            "declared_by, created_at, seq FROM consolidated_memory_relations "
            "WHERE subject_id = ? ORDER BY seq, rowid",
            (subject_id,),
        ).fetchall()
        return tuple(MemoryRelation(*r) for r in rows)

    def load_relations(self, subject_id: Optional[str] = None) -> Tuple[MemoryRelation, ...]:
        self._require_open()
        return self._all_relations(subject_id or self._subject_id)

    def _record_from_row(self, r, superseded_by) -> ConsolidatedMemoryRecord:
        status = RECORD_STATUS_SUPERSEDED if superseded_by else RECORD_STATUS_ACTIVE
        return ConsolidatedMemoryRecord(
            record_id=r[0], subject_id=r[1], source_event_id=r[2], memory_kind=r[3],
            epistemic_kind=r[4], provenance=r[5], meaning=r[6], normalized_meaning=r[7],
            holder_id=r[8], candidate_id=r[9], decision_id=r[10], approved_by=r[11],
            created_at=r[12], seq=r[13], status=status, superseded_by_record_id=superseded_by,
        )

    def _load_records(self, subject_id: str) -> Tuple[ConsolidatedMemoryRecord, ...]:
        rows = self._conn.execute(
            "SELECT record_id, subject_id, source_event_id, memory_kind, epistemic_kind, "
            "provenance, meaning, normalized_meaning, holder_id, candidate_id, decision_id, "
            "approved_by, created_at, seq FROM consolidated_memory_records "
            "WHERE subject_id = ? ORDER BY seq, rowid",
            (subject_id,),
        ).fetchall()
        superseded_by = {
            rel.to_record_id: rel.from_record_id
            for rel in self._all_relations(subject_id)
            if rel.kind == RELATION_SUPERSEDES
        }
        return tuple(self._record_from_row(r, superseded_by.get(r[0])) for r in rows)

    def load_all_records(self, subject_id: Optional[str] = None) -> Tuple[ConsolidatedMemoryRecord, ...]:
        """Every approved record ever created (active + superseded), seq order."""
        self._require_open()
        return self._load_records(subject_id or self._subject_id)

    def load_active_records(self, subject_id: Optional[str] = None) -> Tuple[ConsolidatedMemoryRecord, ...]:
        """Approved records that have NOT been superseded, in seq order.

        Superseded records are never deleted -- they are simply derived out of
        this view by the presence of a ``SUPERSEDES`` relation pointing at them.
        """
        self._require_open()
        return tuple(
            r for r in self._load_records(subject_id or self._subject_id)
            if r.status == RECORD_STATUS_ACTIVE
        )

    def active_conflict_record_ids(self, subject_id: Optional[str] = None) -> frozenset:
        """Record ids that are in an unresolved CONFLICTS_WITH relation where
        BOTH endpoints are currently active. Retrieval uses this to expose the
        conflict without inventing a resolution."""
        self._require_open()
        subject_id = subject_id or self._subject_id
        active = {r.record_id for r in self.load_active_records(subject_id)}
        out = set()
        for rel in self._all_relations(subject_id):
            if rel.kind != RELATION_CONFLICTS_WITH:
                continue
            if rel.from_record_id in active and rel.to_record_id in active:
                out.add(rel.from_record_id)
                out.add(rel.to_record_id)
        return frozenset(out)

    def load_candidates(self, subject_id: Optional[str] = None) -> Tuple[MemoryPromotionCandidate, ...]:
        self._require_open()
        rows = self._conn.execute(
            "SELECT candidate_id, subject_id, source_event_id, memory_kind, epistemic_kind, "
            "provenance, meaning, created_at, seq FROM memory_promotion_candidates "
            "WHERE subject_id = ? ORDER BY seq, rowid",
            (subject_id or self._subject_id,),
        ).fetchall()
        return tuple(MemoryPromotionCandidate(*r) for r in rows)

    def load_decisions(self, candidate_id: Optional[str] = None) -> Tuple[MemoryPromotionDecision, ...]:
        self._require_open()
        if candidate_id is not None:
            rows = self._conn.execute(
                "SELECT decision_id, candidate_id, decision, decided_by, record_id, note, "
                "created_at, seq FROM memory_promotion_decisions WHERE candidate_id = ? "
                "ORDER BY seq, rowid",
                (candidate_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT decision_id, candidate_id, decision, decided_by, record_id, note, "
                "created_at, seq FROM memory_promotion_decisions ORDER BY seq, rowid"
            ).fetchall()
        return tuple(MemoryPromotionDecision(*r) for r in rows)
