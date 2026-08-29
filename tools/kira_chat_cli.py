#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive terminal chat for Accepted KIRA (provider-injectable).

Run later with:  py tools/kira_chat_cli.py

The CLI loads the accepted character ONLY through the committed acceptance/runtime
gate, persists conversation turns as generic runtime events in a durable SQLite
memory database OUTSIDE the repository, and sends one provider completion per
user message (no retry, no fallback). Character behavior comes from the Accepted
KIRA package/runtime context, never from hard-coded personality prose.

Provider is injected (``Callable[[list], str]``); the real DeepSeek callable is
built lazily in ``main()`` only, so this module never performs a live call on
import and tests can inject a deterministic fake.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = Path(__file__).resolve().parent
for _p in (str(_REPO_ROOT), str(_TOOLS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.character_runtime import (  # noqa: E402
    AcceptedCharacter,
    CharacterRuntimeError,
    RuntimeSession,
    load_accepted_character,
    start_session,
)
from services.crp_authoring.auditor_checks import compute_package_hash  # noqa: E402
from services.crp_authoring.candidate_rehydration import (  # noqa: E402
    rehydrate_candidate_package,
)
from crp_provider_adapter import ProviderConfig, build_provider_callable  # noqa: E402
from crp_kira_r4_runner import (  # noqa: E402
    LIVE_BASE_URL,
    LIVE_CREDENTIAL_ENV,
    LIVE_MAX_TOKENS,
    LIVE_MODEL,
    LIVE_PROVIDER_ID,
    LIVE_TIMEOUT_S,
)

SUBJECT = "kira"
ACCEPTANCE_ROOT = _REPO_ROOT / "accepted"

# Stable user-data location (outside the repository) so memory survives restarts.
# Overridable via env for tests / alternate storage.
DEFAULT_MEMORY_ROOT = Path(
    os.environ.get("KIRA_RUNTIME_MEMORY_ROOT")
    or str(Path.home() / ".voyage-narrative-engine" / "kira_runtime")
)

DEFAULT_RUN015 = Path(
    os.environ.get("KIRA_RUN_015_STDOUT")
    or r"C:\DEV\Narrative\LOCAL_STORAGE\crp_r4_live_runs\RUN_015.stdout.json"
)

HELP_TEXT = (
    "/help   — показать доступные команды\n"
    "/new    — завершить текущую сессию и начать новую (память сохраняется)\n"
    "/memory — показать сохранённые воспоминания (без вызова модели)\n"
    "/exit   — закрыть сессию и выйти"
)


def build_run015_source_loader(run015_path: Path):
    """Return a source loader that rehydrates the accepted RUN_015 candidate."""

    def loader(subject_id: str):
        import json

        data = json.loads(Path(run015_path).read_text(encoding="utf-8"))
        package = rehydrate_candidate_package(data["candidate_package"])
        if package.subject_id != subject_id:
            raise CharacterRuntimeError(
                f"source subject {package.subject_id!r} != requested {subject_id!r}"
            )
        return package

    return loader


def build_deepseek_provider() -> Callable[[list], str]:
    """Build the committed DeepSeek provider callable (one-shot transport).

    No secret value is stored here; ``credential_env`` is a NAME only and the
    committed transport reads it once, at call time, fail-closed when absent.
    """
    config = ProviderConfig(
        provider_id=LIVE_PROVIDER_ID,
        model=LIVE_MODEL,
        base_url=LIVE_BASE_URL,
        credential_env=LIVE_CREDENTIAL_ENV,
        timeout_s=LIVE_TIMEOUT_S,
        max_tokens=LIVE_MAX_TOKENS,
        json_mode=False,
    )
    return build_provider_callable(config)

class KiraChatCLI:
    """Provider-injectable interactive chat core (no I/O side effects in tests)."""

    def __init__(
        self,
        *,
        acceptance_root: Path,
        source_loader: Callable[[str], object],
        memory_root: Path,
        provider: Callable[[list], str],
        subject_id: str = SUBJECT,
    ) -> None:
        self._acceptance_root = Path(acceptance_root)
        self._source_loader = source_loader
        self._memory_root = Path(memory_root)
        self._provider = provider
        self.subject_id = subject_id
        self._accepted: Optional[AcceptedCharacter] = None
        self._session: Optional[RuntimeSession] = None
        self._history: list = []
        self._should_exit = False
        self._package_hash_before: Optional[str] = None

    @property
    def accepted(self) -> Optional[AcceptedCharacter]:
        return self._accepted

    @property
    def session(self) -> Optional[RuntimeSession]:
        return self._session

    @property
    def should_exit(self) -> bool:
        return self._should_exit

    def start(self) -> None:
        """Load the accepted character through the gate and open a session."""
        self._accepted = load_accepted_character(
            self.subject_id,
            acceptance_root=self._acceptance_root,
            source_loader=self._source_loader,
        )
        self._package_hash_before = compute_package_hash(self._accepted.package)
        self._open_session()

    def _open_session(self) -> None:
        self._session = start_session(
            self.subject_id,
            acceptance_root=self._acceptance_root,
            source_loader=self._source_loader,
            memory_root=self._memory_root,
        )
        self._history = []

    def _build_system_prompt(self) -> str:
        ctx = self._session.build_runtime_context()
        prior = [
            e for e in ctx["runtime_memory"]
            if e["session_id"] != self._session.session_id
        ]
        mem_lines = "\n".join(
            f"- [{e['event_type']}] {e['meaning']}" for e in prior
        ) or "(нет сохранённых воспоминаний)"
        return (
            "Ты — Кира, персонаж. Отвечай от лица персонажа на русском языке.\n"
            f"Персонаж: subject_id={ctx['subject_id']}, "
            f"package_id={ctx['package_id']}, package_version={ctx['package_version']}, "
            f"status={ctx['package_status']}.\n"
            f"source_candidate_hash={ctx['source_candidate_hash']}.\n"
            "Память из предыдущих сессий:\n" + mem_lines + "\n"
            "Используй только известную тебе информацию о собеседнике."
        )

    def handle_user_message(self, text: str) -> str:
        """One user turn -> exactly one provider completion, then persist both turns."""
        text = text.strip()
        if not text:
            return ""
        self._history.append({"role": "user", "content": text})

        system = self._build_system_prompt()
        messages = [{"role": "system", "content": system}] + list(self._history)
        response = self._provider(messages)

        self._session.record_runtime_event(
            "USER_MESSAGE", text, event_id=f"turn-{uuid.uuid4().hex}-user"
        )
        self._session.record_runtime_event(
            "CHARACTER_MESSAGE", response, event_id=f"turn-{uuid.uuid4().hex}-char"
        )
        self._history.append({"role": "assistant", "content": response})
        return response

    def memory_view(self) -> str:
        """Read-only view of persisted runtime memories (no provider call)."""
        ctx = self._session.build_runtime_context()
        events = ctx["runtime_memory"]
        if not events:
            return "(нет сохранённых воспоминаний)"
        return "\n".join(
            f"[{e['event_type']}] {e['meaning']}  (session={e['session_id']})"
            for e in events
        )

    def handle_command(self, cmd: str) -> str:
        """Handle a slash command; unknown commands never call the provider."""
        cmd = cmd.strip()
        if cmd == "/help":
            return HELP_TEXT
        if cmd == "/new":
            self._session.close()
            self._open_session()
            return f"Новая сессия: {self._session.session_id}"
        if cmd == "/memory":
            return self.memory_view()
        if cmd == "/exit":
            self._should_exit = True
            return "Bye."
        return f"Неизвестная команда: {cmd}. Введите /help для списка команд."

    def close(self) -> None:
        """Close the current session/backend cleanly (idempotent)."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def run_repl(self, read_line: Callable[[str], str], write_line: Callable[[str], None]) -> None:
        """Drive the terminal loop with injected read/write functions."""
        self.start()
        write_line("KIRA CHAT")
        write_line(f"Session: {self._session.session_id}")
        while not self._should_exit:
            try:
                line = read_line("Ты > ")
            except (KeyboardInterrupt, EOFError):
                write_line("")
                break
            if line is None:
                break
            line = line.strip() if isinstance(line, str) else ""
            if not line:
                continue
            if line.startswith("/"):
                out = self.handle_command(line)
                if out:
                    write_line(out)
                if self._should_exit:
                    break
            else:
                try:
                    response = self.handle_user_message(line)
                    write_line(f"Кира > {response}")
                except Exception as exc:  # no retry; surface and continue
                    write_line(f"[ошибка] {exc}")
        self.close()

def main(argv=None) -> int:
    """Build the real provider/source loader and run the interactive loop.

    Provider construction and credential PRESENCE check happen here, lazily, so
    importing this module (or the offline tests) never touches the provider or a
    credential value.
    """
    run015 = Path(DEFAULT_RUN015)
    if not run015.exists():
        print(f"KIRA source artifact not found: {run015}", file=sys.stderr)
        return 1
    if LIVE_CREDENTIAL_ENV not in os.environ:
        print(
            f"Credential environment variable {LIVE_CREDENTIAL_ENV} is not set; "
            "set it before running a live chat.",
            file=sys.stderr,
        )
        return 1

    cli = KiraChatCLI(
        acceptance_root=ACCEPTANCE_ROOT,
        source_loader=build_run015_source_loader(run015),
        memory_root=DEFAULT_MEMORY_ROOT,
        provider=build_deepseek_provider(),
        subject_id=SUBJECT,
    )
    try:
        cli.run_repl(lambda prompt: input(prompt), print)
    except Exception as exc:
        print(f"KIRA CHAT error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
