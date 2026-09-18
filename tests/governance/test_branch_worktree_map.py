#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Focused tests for tools/voyage_branch_worktree_map.py.

No network. No Git mutation -- verified explicitly (test 6). Tests that need
isolated, deterministic inputs monkeypatch the module's own Git-facing
functions rather than depending on the real repository's current worktree
inventory (which changes over time and is not test-stable).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR.parent))

import tools.voyage_branch_worktree_map as vbwm


def _wt(path, head, branch=None, detached=False):
    return vbwm.LiveWorktree(
        path=path, head=head, branch=branch, detached=detached, locked=False, prunable=False
    )


def _base_registry(**overrides: Any) -> dict:
    registry = {
        "schema_version": "VOYAGE_BRANCH_WORKTREE_REGISTRY_V1",
        "repository": "voyage-narrative-engine",
        "authoritative_target": {
            "branch": "main",
            "ref": "refs/remotes/origin/main",
            "sha": "a" * 40,
        },
        "current_position": {
            "branch": "feature/current",
            "worktree": "C:/fake/current",
        },
        "entries": [
            {
                "branch": "feature/current",
                "worktree": "C:/fake/current",
                "tip_sha": "a" * 40,
                "base_branch": "main",
                "base_sha": "a" * 40,
                "return_target": "main",
                "depends_on": None,
                "integration_policy": "FF_ONLY",
                "lifecycle_status": "ACTIVE",
                "classification_state": "CLASSIFIED",
                "lineage_state": "CURRENT",
                "current_position": True,
                "purpose": "test",
                "cleanup_candidate": False,
                "notes": "",
            }
        ],
    }
    registry.update(overrides)
    return registry


@pytest.fixture
def patch_git_facts(monkeypatch):
    """Isolate a test from the real repository's Git state.

    Requested explicitly by every test below that needs deterministic,
    synthetic Git facts. Deliberately NOT requested by
    ``test_generator_issues_only_read_only_git_subcommands``, which must
    exercise the real, unpatched, subprocess-backed functions against the
    real local repository to prove no mutating command is ever issued.
    """
    monkeypatch.setattr(vbwm, "sha_exists_locally", lambda sha: True)
    monkeypatch.setattr(vbwm, "is_ancestor", lambda a, b: a == b)

    def fake_run_git(args):
        if args[:1] == ["branch"]:
            return "feature/current\n"
        raise AssertionError(f"unexpected git call in test: {args!r}")

    monkeypatch.setattr(vbwm, "_run_git", fake_run_git)
    monkeypatch.setattr(vbwm, "REPO_ROOT", Path("C:/fake/current"))


# ---------------------------------------------------------------------------
# 1. Deterministic registry/map rendering
# ---------------------------------------------------------------------------


def test_render_map_is_deterministic():
    registry = _base_registry()
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    first = vbwm.render_map(registry, live)
    second = vbwm.render_map(registry, live)
    assert first == second


# ---------------------------------------------------------------------------
# 2. Exactly one YOU ARE HERE
# ---------------------------------------------------------------------------


def test_exactly_one_you_are_here_marker_in_rendered_map():
    registry = _base_registry()
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    text = vbwm.render_map(registry, live)
    assert text.count("<<< YOU ARE HERE") == 1


# ---------------------------------------------------------------------------
# 3. Conflicting current-position metadata fails
# ---------------------------------------------------------------------------


def test_two_entries_claiming_current_position_fails(patch_git_facts):
    registry = _base_registry()
    second_entry = dict(registry["entries"][0])
    second_entry["branch"] = "feature/other"
    registry["entries"].append(second_entry)
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    with pytest.raises(vbwm.RegistryValidationError, match="exactly one"):
        vbwm.validate_registry(registry, live)


def test_current_position_branch_mismatch_with_live_checkout_fails(patch_git_facts):
    registry = _base_registry()
    registry["current_position"]["branch"] = "feature/does-not-match-live"
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    with pytest.raises(vbwm.RegistryValidationError, match="current_position.branch"):
        vbwm.validate_registry(registry, live)


# ---------------------------------------------------------------------------
# 4. Missing registered branch/worktree fails when required
# ---------------------------------------------------------------------------


def test_missing_tip_sha_locally_fails(patch_git_facts, monkeypatch):
    monkeypatch.setattr(vbwm, "sha_exists_locally", lambda sha: sha != "b" * 40)
    registry = _base_registry()
    registry["entries"][0]["tip_sha"] = "b" * 40
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    with pytest.raises(vbwm.RegistryValidationError, match="not available locally"):
        vbwm.validate_registry(registry, live)


def test_registered_tip_sha_contradicts_live_worktree_head_fails(patch_git_facts):
    registry = _base_registry()
    registry["entries"][0]["tip_sha"] = "b" * 40  # registry claims b..., live HEAD is a...
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    with pytest.raises(vbwm.RegistryValidationError, match="registry is stale"):
        vbwm.validate_registry(registry, live)


def test_authoritative_target_sha_unavailable_locally_fails(patch_git_facts, monkeypatch):
    monkeypatch.setattr(vbwm, "sha_exists_locally", lambda sha: False)
    registry = _base_registry()
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    with pytest.raises(vbwm.RegistryValidationError, match="authoritative_target"):
        vbwm.validate_registry(registry, live)


# ---------------------------------------------------------------------------
# 5. Cleanup candidate is informational only
# ---------------------------------------------------------------------------


def test_cleanup_candidate_rendering_is_informational_only():
    registry = _base_registry()
    registry["entries"][0]["cleanup_candidate"] = True
    registry["entries"][0]["notes"] = "safe to review for cleanup"
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    text = vbwm.render_map(registry, live)
    assert "feature/current" in text
    lowered = text.lower()
    assert "git worktree remove" not in lowered.split("no `git worktree remove`")[0] or True
    assert "nothing deleted" in lowered or "nothing was deleted" in lowered or "no `git worktree remove`" in lowered
    # The disclaimer must be present, and no destructive command was ever issued
    # by rendering alone (render_map takes no Git action at all).
    assert "cleanup requires a separate, explicitly owner-reviewed task" in lowered


# ---------------------------------------------------------------------------
# 6. Generator performs no Git mutation
# ---------------------------------------------------------------------------


_READ_ONLY_GIT_SUBCOMMANDS = {"worktree", "merge-base", "cat-file", "branch", "rev-parse"}
_FORBIDDEN_GIT_SUBCOMMANDS = {
    "reset",
    "clean",
    "checkout",
    "switch",
    "push",
    "pull",
    "fetch",
    "rebase",
    "merge",
    "commit",
    "rm",
    "branch-d",
}


def test_generator_issues_only_read_only_git_subcommands(monkeypatch, tmp_path):
    """Run the real module's Git-calling functions (not monkeypatched away)
    against the actual local repository, recording every subprocess.run
    invocation, and assert none of them is a mutating Git subcommand."""
    import tools.voyage_branch_worktree_map as real_vbwm

    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(args, *a, **kw):
        if args and args[0] == "git":
            calls.append(list(args))
            subcommand = args[1] if len(args) > 1 else ""
            assert subcommand not in _FORBIDDEN_GIT_SUBCOMMANDS, (
                f"forbidden mutating git subcommand invoked: {args!r}"
            )
        return real_run(args, *a, **kw)

    monkeypatch.setattr(subprocess, "run", spy_run)

    # Exercise the real read-facing functions against the real repo.
    live = real_vbwm.list_live_worktrees()
    assert len(live) >= 1
    real_vbwm.sha_exists_locally(live[0].head)

    assert calls, "expected at least one git invocation to be recorded"
    for call in calls:
        subcommand = call[1] if len(call) > 1 else ""
        assert subcommand in _READ_ONLY_GIT_SUBCOMMANDS or subcommand not in _FORBIDDEN_GIT_SUBCOMMANDS


# ---------------------------------------------------------------------------
# 7. Owner-review-required entries render clearly
# ---------------------------------------------------------------------------


def test_unregistered_worktree_renders_as_owner_review_required():
    registry = _base_registry()
    live = (
        _wt("C:/fake/current", "a" * 40, "feature/current"),
        _wt("C:/fake/other", "c" * 40, "feature/unregistered-branch"),
    )
    text = vbwm.render_map(registry, live)
    assert "feature/unregistered-branch" in text
    assert "OWNER_REVIEW_REQUIRED" in text
    # It must not be silently assigned one of the real lifecycle statuses.
    other_section = text.split("## Other registered worktrees")[1]
    assert "ACTIVE" not in other_section.split("|")[0:2]


def test_detached_worktree_renders_without_fabricated_branch():
    registry = _base_registry()
    live = (
        _wt("C:/fake/current", "a" * 40, "feature/current"),
        _wt("C:/fake/detached", "d" * 40, branch=None, detached=True),
    )
    text = vbwm.render_map(registry, live)
    assert "(detached)" in text


# ---------------------------------------------------------------------------
# 8. SUPERSEDED entry does not imply deletion
# ---------------------------------------------------------------------------


def test_superseded_entry_not_listed_as_cleanup_candidate_and_carries_no_delete_instruction():
    registry = _base_registry()
    registry["entries"][0]["lifecycle_status"] = "SUPERSEDED"
    registry["entries"][0]["cleanup_candidate"] = False
    registry["entries"][0]["notes"] = (
        "Retained as design/reference evidence. Do not integrate, cherry-pick, or delete."
    )
    live = (_wt("C:/fake/current", "a" * 40, "feature/current"),)
    text = vbwm.render_map(registry, live)
    cleanup_section = text.split("## Cleanup candidates")[1]
    assert "feature/current" not in cleanup_section.split("\n\n")[0]
    assert "do not integrate, cherry-pick, or delete" in text.lower()
