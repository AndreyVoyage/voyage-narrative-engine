#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HistoryQueryService -- read-only literal/token search over saved aside
history (N7 Persona Data Gateway, P1a-S1 partial runtime).

Per N7_P1A_CONTRACT_CORRECTION_READONLY_PREFLIGHT_2026-07-17.md Phase 6,
this is a thin wrapper over ``tools.aside_memory_store.load_memory`` (the
same read function used by ``state_snapshot_service.py``). It never
imports or calls ``append_session``/``reset_memory``, never performs
semantic/embedding search, never calls an LLM, and never touches the
network.

Searchable text sources, both already past-only filtered and size-capped
by ``load_memory`` itself:

* ``summary`` -- one merged string built by
  ``tools.aside_memory_store._summary_from_sessions`` as a sequence of
  lines shaped ``"[<progress_index> <scene_id>/<beat_id>] <text>"``. This
  is the only source that carries genuine per-session attribution
  (scene_id/beat_id/progress_index), so summary lines are parsed and
  matched first, in their original (chronological, past-only) order.
* ``recent`` -- the flat, already-truncated transcript
  (``role``/``content`` pairs) with no per-message session boundary in the
  public return shape. Matches here are reported with ``session_id=None``
  and unknown scene/beat attribution -- this is an intentional, documented
  limitation of the underlying read API, not a bug.

Matches from both sources are deduplicated by insertion order, deterministic
(summary-derived matches first, then transcript matches, both in original
order), and truncated at the caller-supplied positive ``limit``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tools.aside_memory_store import load_memory

from .errors import HistoryNotFoundError, HistoryRecordError
from .models import HistoryRecord, HistorySearchResult

LoadMemoryFn = Callable[..., Dict[str, Any]]

_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)
_SUMMARY_LINE_RE = re.compile(
    r"^\[(?P<progress>-?\d+)\s+(?P<scene>[^/\]]+)/(?P<beat>[^\]]+)\]\s*(?P<text>.*)$"
)
_SNIPPET_LIMIT = 400


def _normalize_tokens(text: str) -> set:
    return {tok for tok in _TOKEN_SPLIT_RE.split(text.lower()) if tok}


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


class HistoryQueryService:
    """Thin, read-only query layer over saved aside/session history.

    ``load_memory_fn`` is injectable for testability; it defaults to the
    real ``tools.aside_memory_store.load_memory``.
    """

    def __init__(
        self,
        root: Path,
        slot: str,
        *,
        load_memory_fn: LoadMemoryFn = load_memory,
    ) -> None:
        self._root = root
        self._slot = slot
        self._load_memory_fn = load_memory_fn

    def search_history(
        self,
        character_id: str,
        query: str,
        limit: int,
        progress: int,
    ) -> HistorySearchResult:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be an explicit positive integer")
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        raw = self._load_memory_fn(
            root=self._root,
            slot=self._slot,
            character=character_id,
            progress=progress,
        )
        if not isinstance(raw, dict):
            raise HistoryRecordError("malformed memory payload: not a JSON object")

        sessions_meta = raw.get("sessions_meta")
        recent = raw.get("recent")
        summary = raw.get("summary")

        if sessions_meta is None or recent is None or summary is None:
            raise HistoryRecordError(
                "malformed memory payload: missing summary/recent/sessions_meta"
            )
        if not isinstance(sessions_meta, list) or not isinstance(recent, list) or not isinstance(summary, str):
            raise HistoryRecordError(
                "malformed memory payload: summary/recent/sessions_meta have wrong types"
            )

        if not sessions_meta and not recent and not summary:
            raise HistoryNotFoundError(
                f"no saved aside history for character_id={character_id!r}"
            )

        session_lookup: Dict[tuple, Optional[str]] = {}
        for meta in sessions_meta:
            if not isinstance(meta, dict):
                raise HistoryRecordError("malformed session metadata record")
            scene_id = meta.get("scene_id")
            beat_id = meta.get("beat_id")
            progress_index = meta.get("progress_index")
            if (
                not isinstance(scene_id, str)
                or not isinstance(beat_id, str)
                or not isinstance(progress_index, int)
            ):
                raise HistoryRecordError("malformed session metadata fields")
            session_id = meta.get("session_id")
            if session_id is not None and not isinstance(session_id, str):
                raise HistoryRecordError("malformed session metadata session_id")
            session_lookup[(progress_index, scene_id, beat_id)] = session_id

        records: List[HistoryRecord] = []

        query_stripped = query.strip()
        query_tokens = _normalize_tokens(query) if query_stripped else set()

        if query_stripped:
            for line in summary.splitlines():
                match = _SUMMARY_LINE_RE.match(line)
                if not match:
                    continue
                text = match.group("text")
                match_type = self._classify_match(query, query_tokens, text)
                if match_type is None:
                    continue
                progress_index = int(match.group("progress"))
                scene_id = match.group("scene")
                beat_id = match.group("beat")
                session_id = session_lookup.get((progress_index, scene_id, beat_id))
                records.append(
                    HistoryRecord(
                        session_id=session_id,
                        scene_id=scene_id,
                        beat_id=beat_id,
                        progress_index=progress_index,
                        match_type=match_type,
                        snippet=_truncate(text, _SNIPPET_LIMIT),
                    )
                )
                if len(records) >= limit:
                    return HistorySearchResult(
                        character_id=character_id,
                        query=query,
                        limit=limit,
                        records=tuple(records),
                    )

            for entry in recent:
                if not isinstance(entry, dict):
                    raise HistoryRecordError("malformed transcript entry")
                content = entry.get("content")
                role = entry.get("role")
                if not isinstance(content, str) or not isinstance(role, str):
                    raise HistoryRecordError("malformed transcript entry fields")

                match_type = self._classify_match(query, query_tokens, content)
                if match_type is None:
                    continue
                records.append(
                    HistoryRecord(
                        session_id=None,
                        scene_id=None,
                        beat_id=None,
                        progress_index=None,
                        match_type=match_type,
                        snippet=_truncate(content, _SNIPPET_LIMIT),
                    )
                )
                if len(records) >= limit:
                    break

        return HistorySearchResult(
            character_id=character_id,
            query=query,
            limit=limit,
            records=tuple(records[:limit]),
        )

    @staticmethod
    def _classify_match(query: str, query_tokens: set, candidate: str) -> Optional[str]:
        if query and query.lower() in candidate.lower():
            return "literal"
        if query_tokens:
            candidate_tokens = _normalize_tokens(candidate)
            if query_tokens & candidate_tokens:
                return "token"
        return None
