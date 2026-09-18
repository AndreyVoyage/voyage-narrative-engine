#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voyage Branch/Worktree Map generator (VOYAGE_BRANCH_WORKTREE_REGISTRY_V1).

Regenerates ``governance/BRANCH_WORKTREE_MAP.md`` deterministically from:

  A. live Git/worktree facts (``git worktree list --porcelain``,
     ``git merge-base --is-ancestor``) -- queried fresh every run, never
     cached or hand-typed;
  B. governance metadata in ``governance/BRANCH_WORKTREE_REGISTRY.json``
     (base target, return target, lifecycle status, purpose, ...) -- facts
     Git cannot infer.

This tool is READ-ONLY with respect to Git: it never creates, deletes,
renames, resets, or checks out any branch/worktree/ref, and never mutates
the registry JSON. Its only filesystem write is the generated map file.

It fails closed (raises, writes nothing) when the registry's claims
materially conflict with observed Git facts -- see ``validate_registry``.

Standard library only. No network, no external dependencies.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO_ROOT / "governance" / "BRANCH_WORKTREE_REGISTRY.json"
MAP_PATH = REPO_ROOT / "governance" / "BRANCH_WORKTREE_MAP.md"

_ALLOWED_LIFECYCLE = {
    "ACTIVE",
    "READY_TO_REVIEW",
    "READY_TO_INTEGRATE",
    "INTEGRATED",
    "SUPERSEDED",
    "ABANDONED",
}
_ALLOWED_LINEAGE = {"CURRENT", "STALE", "DIVERGED", "INTEGRATED"}


class RegistryValidationError(RuntimeError):
    """The registry's claims conflict with observed Git facts, or the
    registry/live-Git state is otherwise internally inconsistent."""


@dataclass(frozen=True)
class LiveWorktree:
    path: str
    head: str
    branch: Optional[str]  # None when detached
    detached: bool
    locked: bool
    prunable: bool


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RegistryValidationError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout


def list_live_worktrees() -> tuple[LiveWorktree, ...]:
    """Parse ``git worktree list --porcelain`` into structured records."""
    raw = _run_git(["worktree", "list", "--porcelain"])
    worktrees: list[LiveWorktree] = []
    path: Optional[str] = None
    head: Optional[str] = None
    branch: Optional[str] = None
    detached = False
    locked = False
    prunable = False

    def _flush() -> None:
        nonlocal path, head, branch, detached, locked, prunable
        if path is not None:
            worktrees.append(
                LiveWorktree(
                    path=path,
                    head=head or "",
                    branch=branch,
                    detached=detached,
                    locked=locked,
                    prunable=prunable,
                )
            )
        path = None
        head = None
        branch = None
        detached = False
        locked = False
        prunable = False

    for line in raw.splitlines():
        if line.startswith("worktree "):
            _flush()
            path = line[len("worktree ") :].strip()
        elif line.startswith("HEAD "):
            head = line[len("HEAD ") :].strip()
        elif line.startswith("branch "):
            ref = line[len("branch ") :].strip()
            branch = ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
        elif line.strip() == "detached":
            detached = True
        elif line.startswith("locked"):
            locked = True
        elif line.startswith("prunable"):
            prunable = True
    _flush()
    return tuple(worktrees)


def is_ancestor(candidate_sha: str, target_sha: str) -> bool:
    """True iff ``candidate_sha`` is an ancestor of (or equal to) ``target_sha``."""
    if candidate_sha == target_sha:
        return True
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate_sha, target_sha],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def sha_exists_locally(sha: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        raise RegistryValidationError(f"registry not found: {REGISTRY_PATH}")
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def compute_lineage_state(tip_sha: str, authoritative_sha: str) -> str:
    """Pure topology classification -- never an architectural claim on its own.

    INTEGRATED: tip is the authoritative target or an ancestor of it.
    CURRENT:    the authoritative target is an ancestor of tip (tip is ahead,
                same line, base still matches).
    (Anything else is reported by the caller as a bare topology fact, not
    mapped to STALE/DIVERGED, unless registry metadata supplies the
    architectural evidence -- see render_map.)
    """
    if is_ancestor(tip_sha, authoritative_sha):
        return "INTEGRATED"
    if is_ancestor(authoritative_sha, tip_sha):
        return "CURRENT"
    return "TOPOLOGY_UNCLASSIFIED"


def validate_registry(
    registry: dict[str, Any], live_worktrees: tuple[LiveWorktree, ...]
) -> None:
    if registry.get("schema_version") != "VOYAGE_BRANCH_WORKTREE_REGISTRY_V1":
        raise RegistryValidationError("unexpected or missing schema_version")

    authoritative = registry.get("authoritative_target") or {}
    authoritative_sha = authoritative.get("sha")
    if not authoritative_sha or not sha_exists_locally(authoritative_sha):
        raise RegistryValidationError(
            f"authoritative_target.sha is missing or unavailable locally: {authoritative_sha!r}"
        )

    entries = registry.get("entries") or []

    current_position_entries = [e for e in entries if e.get("current_position") is True]
    if len(current_position_entries) != 1:
        raise RegistryValidationError(
            "exactly one registry entry must have current_position=true; "
            f"found {len(current_position_entries)}"
        )

    declared_position = registry.get("current_position") or {}
    live_branch = _run_git(["branch", "--show-current"]).strip()
    live_path = str(REPO_ROOT).replace("\\", "/")
    if declared_position.get("branch") != live_branch:
        raise RegistryValidationError(
            "registry current_position.branch does not match the live checked-out "
            f"branch: registry={declared_position.get('branch')!r} live={live_branch!r}"
        )
    declared_path = str(declared_position.get("worktree", "")).replace("\\", "/")
    if declared_path.rstrip("/") != live_path.rstrip("/"):
        raise RegistryValidationError(
            "registry current_position.worktree does not match the live cwd: "
            f"registry={declared_path!r} live={live_path!r}"
        )
    if current_position_entries[0].get("branch") != live_branch:
        raise RegistryValidationError(
            "the entry marked current_position=true does not match the live "
            f"checked-out branch: entry={current_position_entries[0].get('branch')!r} "
            f"live={live_branch!r}"
        )

    live_by_branch = {w.branch: w for w in live_worktrees if w.branch is not None}

    for entry in entries:
        branch = entry.get("branch")
        if not branch:
            raise RegistryValidationError(f"registry entry missing 'branch': {entry!r}")
        lifecycle = entry.get("lifecycle_status")
        if lifecycle is not None and lifecycle not in _ALLOWED_LIFECYCLE:
            raise RegistryValidationError(
                f"entry {branch!r} has an unsupported lifecycle_status: {lifecycle!r}"
            )
        lineage = entry.get("lineage_state")
        if lineage is not None and lineage not in _ALLOWED_LINEAGE:
            raise RegistryValidationError(
                f"entry {branch!r} has an unsupported lineage_state: {lineage!r}"
            )
        tip_sha = entry.get("tip_sha")
        if tip_sha and not sha_exists_locally(tip_sha):
            raise RegistryValidationError(
                f"entry {branch!r} declares tip_sha {tip_sha!r} which is not "
                "available locally"
            )
        live_wt = live_by_branch.get(branch)
        if live_wt is not None and tip_sha and live_wt.head != tip_sha:
            raise RegistryValidationError(
                f"entry {branch!r} declares tip_sha {tip_sha!r} but the live "
                f"checked-out worktree for that branch has HEAD {live_wt.head!r} "
                "-- registry is stale relative to the live worktree"
            )


def _short(sha: str) -> str:
    return sha[:8] if sha else sha


def render_map(
    registry: dict[str, Any], live_worktrees: tuple[LiveWorktree, ...]
) -> str:
    authoritative = registry["authoritative_target"]
    authoritative_sha = authoritative["sha"]
    entries = registry.get("entries", [])
    known_branches = {e["branch"] for e in entries}

    lines: list[str] = []
    lines.append("# NARRATIVE / VNE Development Topology")
    lines.append("")
    lines.append(
        "GENERATED FROM: live Git/worktree facts "
        "(`git worktree list --porcelain`, `git merge-base --is-ancestor`) "
        "+ `governance/BRANCH_WORKTREE_REGISTRY.json` metadata."
    )
    lines.append("")
    lines.append(
        "This file is NOT an independent source of truth. Regenerate with "
        "`py tools/voyage_branch_worktree_map.py` after any registry change; "
        "do not hand-edit."
    )
    lines.append("")
    lines.append(f"Authoritative `{authoritative['branch']}` @ `{authoritative_sha}`")
    lines.append(f"(ref: `{authoritative['ref']}`)")
    if authoritative.get("note"):
        lines.append("")
        lines.append(f"> {authoritative['note']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Known / governed branches")
    lines.append("")

    for entry in entries:
        marker = " <<< YOU ARE HERE" if entry.get("current_position") else ""
        lines.append(f"### `{entry['branch']}`{marker}")
        lines.append("")
        lines.append(f"- worktree: `{entry.get('worktree') or '(none -- no worktree currently checked out)'}`")
        lines.append(f"- tip: `{_short(entry.get('tip_sha') or '')}` (`{entry.get('tip_sha')}`)")
        lines.append(f"- base: `{entry.get('base_branch')}` @ `{_short(entry.get('base_sha') or '') or 'n/a'}`")
        lines.append(f"- return target: `{entry.get('return_target')}`")
        lines.append(f"- depends on: `{entry.get('depends_on')}`")
        lines.append(f"- integration policy: `{entry.get('integration_policy')}`")
        lines.append(f"- lifecycle: **{entry.get('lifecycle_status')}**")
        lines.append(f"- lineage: **{entry.get('lineage_state')}**")
        lines.append(f"- cleanup candidate: **{entry.get('cleanup_candidate')}**")
        if entry.get("purpose"):
            lines.append(f"- purpose: {entry['purpose']}")
        if entry.get("notes"):
            lines.append(f"- notes: {entry['notes']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Other registered worktrees (owner review required)")
    lines.append("")
    lines.append(
        "The branches above are the only ones with recorded governance "
        "metadata (base/return target, lifecycle, purpose). Every other "
        "currently registered worktree is listed below with Git-derived "
        "facts only -- `lifecycle_status: null`, "
        "`classification_state: OWNER_REVIEW_REQUIRED` for all of them. "
        "`lineage` here is a bare topology fact (is the branch tip an "
        "ancestor of, or ahead of, the authoritative target?), not an "
        "architectural judgement -- per policy, topology distance alone "
        "must never be read as an architectural-divergence verdict."
    )
    lines.append("")
    lines.append("| worktree | branch | tip | lineage (topology only) |")
    lines.append("|---|---|---|---|")

    other = [w for w in live_worktrees if w.branch not in known_branches]
    other_sorted = sorted(other, key=lambda w: (w.branch or "~detached", w.path))
    integrated_count = 0
    unclassified_count = 0
    detached_count = 0
    for w in other_sorted:
        if w.detached:
            detached_count += 1
            lines.append(f"| `{w.path}` | *(detached)* | `{_short(w.head)}` | n/a (detached) |")
            continue
        lineage = compute_lineage_state(w.head, authoritative_sha)
        if lineage == "INTEGRATED":
            integrated_count += 1
        else:
            unclassified_count += 1
        lines.append(f"| `{w.path}` | `{w.branch}` | `{_short(w.head)}` | {lineage} |")

    lines.append("")
    lines.append(
        f"Total other worktrees: {len(other_sorted)} "
        f"({integrated_count} INTEGRATED, {unclassified_count} TOPOLOGY_UNCLASSIFIED, "
        f"{detached_count} detached). All require owner review before any "
        "lifecycle/cleanup classification is assigned."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Cleanup candidates (identification only -- nothing deleted)")
    lines.append("")
    cleanup_entries = [e for e in entries if e.get("cleanup_candidate")]
    if not cleanup_entries:
        lines.append("None among the known/governed branches.")
    else:
        for entry in cleanup_entries:
            lines.append(
                f"- `{entry['branch']}` (worktree: `{entry.get('worktree') or 'none'}`) "
                f"-- lifecycle {entry.get('lifecycle_status')}. "
                f"{entry.get('notes', '')}"
            )
    lines.append("")
    lines.append(
        "No `git worktree remove`, `git worktree prune`, `git branch -d/-D`, "
        "`git reset`, or `git clean` was performed by this tool or the task "
        "that generated this map. Cleanup requires a separate, explicitly "
        "owner-reviewed task."
    )
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    registry = load_registry()
    live_worktrees = list_live_worktrees()
    validate_registry(registry, live_worktrees)
    text = render_map(registry, live_worktrees)
    MAP_PATH.write_bytes(text.encode("utf-8"))
    print(f"wrote {MAP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
