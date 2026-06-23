#!/usr/bin/env python3
"""VNE Adapter — обёртка над Framework-voyage-mvp CLI.

Не импортирует voyage_framework напрямую, чтобы VNE оставался
спецификационным репозиторием без Python-зависимостей.

Использование:
    python tools/vne_adapter.py list
    python tools/vne_adapter.py task --track session_retrospector --task "Реализовать v0.1"
    python tools/vne_adapter.py run --role vne_canon_guard --task "Проверить канон"
    python tools/vne_adapter.py status
    python tools/vne_adapter.py tasks list
    python tools/vne_adapter.py sync
    python tools/vne_adapter.py gates --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _configure_console_encoding() -> None:
    """Переключить stdout/stderr на utf-8 для корректного вывода кириллицы.

    На Windows с консолью cp1252 вывод русского help argparse вызывает
    UnicodeEncodeError. reconfigure(encoding='utf-8', errors='replace')
    решает проблему безопасно.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_console_encoding()


# Путь к YAML-файлам проекта
VOYAGE_DIR = Path(".voyage")
PROJECT_YAML = VOYAGE_DIR / "project.yaml"
ROLES_YAML = VOYAGE_DIR / "roles.yaml"
TEMPLATES_DIR = VOYAGE_DIR / "task_templates"
# NOTE: .voyage/tasks.db is Framework runtime state, not VNE source.
# It is created by voyage CLI calls and must be gitignored.
TASKS_DIR = VOYAGE_DIR / "tasks"


# ---------------------------------------------------------------------------
# Framework environment helpers
# ---------------------------------------------------------------------------

def _get_framework_root() -> Path:
    """Найти корень Framework-voyage-mvp."""
    env_root = os.environ.get("VOYAGE_FRAMEWORK_ROOT")
    if env_root:
        return Path(env_root)
    return Path("C:/DEV/Framework/Framework-voyage-mvp")


def _get_python_exe() -> Path:
    """Найти Python из Framework venv."""
    root = _get_framework_root()
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        root / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    python = shutil.which("python") or shutil.which("python3")
    if python:
        return Path(python)
    print("❌ Python не найден. Установите Framework или укажите VOYAGE_FRAMEWORK_ROOT.")
    sys.exit(1)


def _find_voyage_exe() -> Path | None:
    """Найти исполняемый файл voyage, если он установлен."""
    root = _get_framework_root()
    for candidate in (
        root / ".venv" / "Scripts" / "voyage.exe",
        root / ".venv" / "bin" / "voyage",
    ):
        if candidate.exists():
            return candidate
    return None


def _get_voyage_env() -> dict[str, str]:
    """Подготовить окружение с PATH, включающим Framework venv."""
    env = os.environ.copy()
    root = _get_framework_root()
    venv_bins = [
        root / ".venv" / "Scripts",
        root / ".venv" / "bin",
        root / "venv" / "Scripts",
        root / "venv" / "bin",
    ]
    paths = [str(p) for p in venv_bins if p.exists()]
    current_path = env.get("PATH", "")
    if paths:
        env["PATH"] = os.pathsep.join(paths + [current_path])
    if "VOYAGE_FRAMEWORK_ROOT" not in env:
        env["VOYAGE_FRAMEWORK_ROOT"] = str(root)
    return env


def _get_gate_env() -> dict[str, str]:
    """Prepare gate subprocess env with UTF-8 Python output defaults."""
    env = _get_voyage_env()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def _run_command(
    args: list[str | Path],
    cwd: Path | None = None,
    shell: bool = False,
    echo: bool = True,
    env: dict[str, str] | None = None,
) -> int:
    """Запустить команду и вернуть exit code."""
    cmd = [str(a) for a in args]
    if echo:
        print(f"▶ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        check=False,
        cwd=str(cwd) if cwd else None,
        env=env if env is not None else _get_voyage_env(),
        shell=shell,
    )
    return result.returncode


def _voyage_command(args: list[str]) -> list[str]:
    """Собрать команду вызова voyage CLI."""
    voyage_exe = _find_voyage_exe()
    if voyage_exe is not None:
        return [str(voyage_exe), *args]
    return [str(_get_python_exe()), "-m", "voyage_framework.cli", *args]


def _invoke_voyage(args: list[str]) -> int:
    """Вызвать voyage CLI и вернуть exit code."""
    return _run_command(_voyage_command(args))


# ---------------------------------------------------------------------------
# YAML / project helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    """Прочитать YAML-файл, если pyyaml доступен. Иначе — fallback на JSON."""
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        print(f"❌ Ошибка: для {path.name} нужен pyyaml (pip install pyyaml)")
        sys.exit(1)


def _load_project(required: bool = True) -> dict[str, Any]:
    """Загрузить project.yaml."""
    if not PROJECT_YAML.exists():
        if required:
            print(f"❌ {PROJECT_YAML} не найден. Сначала запустите: voyage init")
            sys.exit(1)
        return {}
    return _load_yaml(PROJECT_YAML)


def _load_roles() -> dict[str, Any]:
    """Загрузить roles.yaml."""
    if not ROLES_YAML.exists():
        print(f"⚠️ {ROLES_YAML} не найден. Роли будут неизвестны.")
        return {}
    return _load_yaml(ROLES_YAML)


# ---------------------------------------------------------------------------
# VNE → Framework role/mode mapping
# ---------------------------------------------------------------------------

_VNE_ROLE_MAP: dict[str, str] = {
    "vne_canon_guard": "architect",
    "vne_retrospector_dev": "developer",
    "vne_renpy_adapter": "developer",
    "vne_qa": "qa",
    "vne_qa_guard": "qa",
    "vne_schema_engineer": "architect",
    "vne_narrative_editor": "developer",
}

_VNE_MODE_MAP: dict[str, str] = {
    "audit": "solution",
    "analysis": "discover",
    "review": "solution",
    "implementation": "implement",
    "implement": "implement",
    "plan": "plan",
    "design": "design",
    "discover": "discover",
    "solution": "solution",
}


def _map_role_to_framework(role: str) -> tuple[str, str | None]:
    """Преобразовать VNE-роль в Framework-роль.

    Returns:
        (framework_role, original_vne_role or None)
    """
    normalized = role.strip().lower()
    mapped = _VNE_ROLE_MAP.get(normalized)
    if mapped is not None and mapped != normalized:
        return mapped, role
    return role, None


def _map_mode_to_framework(mode: str) -> tuple[str, str | None]:
    """Преобразовать VNE-режим в Framework-режим.

    Returns:
        (framework_mode, original_vne_mode or None)
    """
    normalized = mode.strip().lower()
    mapped = _VNE_MODE_MAP.get(normalized)
    if mapped is not None and mapped != normalized:
        return mapped, mode
    return mode, None


def _escape_yaml_string(value: str) -> str:
    """Безопасное экранирование строки для ручной записи YAML."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _write_yaml_line(key: str, value: Any, indent: int = 0) -> str:
    """Записать одну пару key-value в YAML."""
    prefix = "  " * indent
    if value is None:
        return f"{prefix}{key}:"
    if isinstance(value, bool):
        return f"{prefix}{key}: {'true' if value else 'false'}"
    if isinstance(value, int):
        return f"{prefix}{key}: {value}"
    if isinstance(value, str):
        return f"{prefix}{key}: {_escape_yaml_string(value)}"
    if isinstance(value, list):
        if not value:
            return f"{prefix}{key}: []"
        lines = [f"{prefix}{key}:"]
        for item in value:
            lines.append(f"{prefix}  - {_escape_yaml_string(str(item))}")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return f"{prefix}{key}: {{}}"
        lines = [f"{prefix}{key}:"]
        for k, v in value.items():
            lines.append(_write_yaml_line(k, v, indent + 1))
        return "\n".join(lines)
    return f"{prefix}{key}: {_escape_yaml_string(str(value))}"


def _write_task_yaml(path: Path, data: dict[str, Any]) -> None:
    """Записать task.yaml вручную (standard library only)."""
    lines: list[str] = []
    order = [
        "id",
        "title",
        "description",
        "role",
        "mode",
        "priority",
        "status",
        "acceptance_criteria",
        "files",
        "tests",
        "metadata",
    ]
    written = set()
    for key in order:
        if key in data:
            lines.append(_write_yaml_line(key, data[key]))
            written.add(key)
    for key, value in data.items():
        if key not in written:
            lines.append(_write_yaml_line(key, value))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_task_id() -> str:
    """Сгенерировать уникальный task id вида VNE-001."""
    if not TASKS_DIR.exists():
        return "VNE-001"
    max_num = 0
    for child in TASKS_DIR.iterdir():
        if not child.is_dir():
            continue
        match = re.match(r"VNE-(\d{3})", child.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"VNE-{max_num + 1:03d}"


def _generate_task_yaml(
    role: str,
    mode: str,
    task_desc: str,
    track: str | None = None,
    phase: str | None = None,
) -> Path:
    """Сгенерировать task.yaml и вернуть путь к нему."""
    task_id = _generate_task_id()
    task_dir = TASKS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = task_dir / "task.yaml"

    if yaml_path.exists():
        print(f"⚠️  {yaml_path} уже существует. Пропуск генерации.")
        return yaml_path

    now = datetime.now(timezone.utc).isoformat()
    framework_role, vne_role = _map_role_to_framework(role)
    framework_mode, vne_mode = _map_mode_to_framework(mode)

    metadata: dict[str, Any] = {
        "track": track or "",
        "phase": phase or "",
        "created_at": now,
        "source": "vne_adapter",
        "framework_role": framework_role,
        "framework_mode": framework_mode,
    }
    if vne_role is not None:
        metadata["vne_role"] = vne_role
    if vne_mode is not None:
        metadata["vne_mode"] = vne_mode

    data: dict[str, Any] = {
        "id": task_id,
        "title": task_desc[:80],
        "description": task_desc,
        "role": framework_role,
        "mode": framework_mode,
        "priority": "medium",
        "status": "pending",
        "acceptance_criteria": [
            "Требования поняты",
            "Код реализован",
            "Проверки пройдены",
        ],
        "files": {
            "read": [],
            "modify": [],
        },
        "tests": [],
        "metadata": metadata,
    }
    _write_task_yaml(yaml_path, data)
    print(f"📝 Task YAML создан: {yaml_path}")
    return yaml_path


# ---------------------------------------------------------------------------
# Команды
# ---------------------------------------------------------------------------

def cmd_list(_args: argparse.Namespace) -> int:
    """Показать доступные tracks и task templates."""
    project = _load_project()
    roles = _load_roles()

    print("📋 Project:", project.get("project_id", "unknown"))
    print("   Type:", project.get("type", "unknown"))
    print()

    tracks = project.get("development_tracks", {})
    if tracks:
        print("🛤 Development Tracks:")
        for name, info in tracks.items():
            role = info.get("role", "unknown")
            desc = info.get("description", "")
            print(f"   {name:20} | role={role:25} | {desc}")
        print()

    if roles:
        print("👤 VNE Roles:")
        for name, info in roles.items():
            purpose = info.get("purpose", "")[:50]
            print(f"   {name:25} | {purpose}")
        print()

    if TEMPLATES_DIR.exists():
        templates = sorted(TEMPLATES_DIR.glob("TASK_*.md"))
        if templates:
            print("📄 Task Templates:")
            for t in templates:
                print(f"   {t.name}")
        else:
            print("⚠️  Нет task templates в .voyage/task_templates/")
    else:
        print("⚠️  Директория .voyage/task_templates/ не найдена")

    return 0


def cmd_task(args: argparse.Namespace) -> int:
    """Сгенерировать TASK.md через voyage task с VNE-контекстом."""
    project = _load_project()
    roles = _load_roles()
    track = args.track

    # Определить роль из track или аргументов
    role = args.role
    if not role and track:
        tracks = project.get("development_tracks", {})
        track_info = tracks.get(track, {})
        role = track_info.get("role")

    if not role:
        print("❌ Не указана роль. Используйте --role или --track с известным track.")
        return 1

    original_role = role
    framework_role, vne_role = _map_role_to_framework(original_role)
    if vne_role is not None:
        print(f"Role: {vne_role} → {framework_role}")

    original_mode = args.mode
    framework_mode, vne_mode = _map_mode_to_framework(original_mode)
    if vne_mode is not None:
        print(f"Mode: {vne_mode} → {framework_mode}")

    # Определить шаблон
    template_name = args.template
    if not template_name and track:
        mapping = {
            "session_retrospector": "TASK_SESSION_RETROSPECTOR_v0.1.md",
            "canon": "TASK_CANON_SYNC.md",
            "renpy_mvp": "TASK_RENPY_MVP.md",
        }
        template_name = mapping.get(track)

    if template_name:
        template_path = TEMPLATES_DIR / template_name
        if template_path.exists():
            print(f"📄 Task template: {template_path}")
            print("   Используйте его как reference при формировании задачи.")
            print()
        else:
            print(f"⚠️  Шаблон {template_name} не найден.")

    task_desc = args.task
    if not task_desc:
        print("❌ Не указано описание задачи (--task)")
        return 1

    # Генерация task.yaml по запросу
    if args.yaml:
        _generate_task_yaml(
            original_role,
            original_mode,
            task_desc,
            track=track,
            phase=args.phase,
        )

    voyage_args = [
        "task",
        framework_role,
        "--task",
        task_desc,
        "--project",
        project.get("project_id", "voyage-narrative-engine"),
    ]

    if args.phase:
        voyage_args.extend(["--phase", args.phase])

    print(f"🚀 Track: {track or 'N/A'} | Role: {framework_role}")
    print(f"   Task: {task_desc}")
    print()

    return _invoke_voyage(voyage_args)


def cmd_run(args: argparse.Namespace) -> int:
    """Запустить voyage run с VNE-контекстом."""
    project = _load_project()
    role = args.role

    if not role:
        print("❌ Не указана роль (--role)")
        return 1

    framework_role, vne_role = _map_role_to_framework(role)
    if vne_role is not None:
        print(f"Role: {vne_role} → {framework_role}")
    role = framework_role

    task_desc = args.task or "No task specified"
    plan = args.plan or ""

    voyage_args = [
        "run",
        role,
        "--task",
        task_desc,
        "--project",
        project.get("project_id", "voyage-narrative-engine"),
    ]

    if plan:
        voyage_args.extend(["--plan", plan])

    if args.backend:
        voyage_args.extend(["--backend", args.backend])

    print(f"🚀 Role: {role} | Task: {task_desc}")
    if plan:
        print(f"   Plan: {plan}")
    print()

    return _invoke_voyage(voyage_args)


def cmd_status(_args: argparse.Namespace) -> int:
    """Показать статус VNE проекта через voyage status."""
    project = _load_project()
    print(f"📊 Project: {project.get('project_id', 'unknown')}")
    print(f"   Type: {project.get('type', 'unknown')}")
    print()
    return _invoke_voyage(["status"])


def _default_scenario() -> str:
    """Выбрать сценарий для сборки prompt."""
    if (Path("scenarios") / "sportcomplex_triad" / "core" / "INDEX.json").exists():
        return "sportcomplex_triad"
    return "sauna_extended"


def _normalize_command_tokens(tokens: list[str]) -> list[str]:
    """Заменить маркеры python/voyage на реальные исполняемые файлы."""
    if not tokens:
        return tokens
    first = tokens[0].lower()
    rest = tokens[1:]
    if first in ("python", "python.exe", "python3", "py"):
        return [str(_get_python_exe()), *rest]
    if first in ("voyage", "voyage.exe"):
        return _voyage_command(rest)
    return tokens


def _fallback_gate_commands() -> list[tuple[str, list[str], str]]:
    """Команды quality gates по умолчанию, если project.yaml не задан."""
    scenario = _default_scenario()
    return [
        (
            "default",
            _normalize_command_tokens(["voyage", "tasks", "list"]),
            "fallback",
        ),
        (
            "default",
            _normalize_command_tokens(
                ["python", "-m", "json.tool", "schemas/persona_schema_v3_2_VOYAGE.json"]
            ),
            "fallback",
        ),
        (
            "default",
            _normalize_command_tokens(
                ["python", "scripts/python/build_prompt_modular.py", scenario, "standard", "AG3"]
            ),
            "fallback",
        ),
    ]


def _parse_quality_gates(raw: Any) -> dict[str, list[str]]:
    """Нормализовать quality_gates из project.yaml в dict[group] -> commands."""
    groups: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, (list, tuple)):
                groups[str(key)] = [str(item) for item in value]
            else:
                groups[str(key)] = [str(value)]
    elif isinstance(raw, list):
        groups["default"] = [str(item) for item in raw]
    return groups


def _collect_gate_commands(args: argparse.Namespace) -> list[tuple[str, list[str], str]]:
    """Собрать команды quality gates из project.yaml с учётом --gate."""
    project = _load_project(required=False)
    groups = _parse_quality_gates(project.get("quality_gates") if project else None)

    if not groups:
        commands = _fallback_gate_commands()
    else:
        commands: list[tuple[str, list[str], str]] = []
        for group, cmd_strs in groups.items():
            for cmd_str in cmd_strs:
                tokens = shlex.split(str(cmd_str))
                commands.append(
                    (group, _normalize_command_tokens(tokens), f"project.yaml:quality_gates.{group}")
                )

    if args.gate:
        filtered = [c for c in commands if c[0] == args.gate]
        if not filtered:
            available = sorted({c[0] for c in commands})
            print(
                f"❌ Gate group '{args.gate}' не найден. "
                f"Доступные: {', '.join(available) or 'none'}"
            )
            return []
        commands = filtered

    return commands


def cmd_gates(args: argparse.Namespace) -> int:
    """Запустить quality gates."""
    commands = _collect_gate_commands(args)
    if not commands:
        return 1

    if args.dry_run:
        print("🔍 Dry-run gates:")
        for group, cmd, source in commands:
            print(f"   [{source}] ({group}) $ {' '.join(str(c) for c in cmd)}")
        return 0

    for group, cmd, source in commands:
        print(f"   ▶ [{source}] ({group}) $ {' '.join(str(c) for c in cmd)}")
        result = _run_command(cmd, echo=False, env=_get_gate_env())
        if result != 0:
            print(f"   ❌ Gate failed: {' '.join(str(c) for c in cmd)}")
            return result
        print(f"   ✅ Gate passed: {' '.join(str(c) for c in cmd)}")
    print("✅ All gates passed")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    """Runtime управление задачами (v4.1)."""
    sub = args.tasks_command
    if not sub:
        print("❌ Не указана subcommand. Используйте: create, list, show, start, block, unblock, complete, fail, archive")
        return 1

    voyage_args = ["tasks", sub]

    if sub == "create":
        if not args.file:
            print("❌ Для 'tasks create' нужен --file <task.yaml>")
            return 1
        source_path = Path(args.file)
        try:
            data = _load_yaml(source_path)
        except Exception as exc:
            print(f"❌ Не удалось прочитать {source_path}: {exc}")
            return 1

        if not isinstance(data, dict):
            print(f"❌ {source_path} должен содержать YAML mapping верхнего уровня")
            return 1

        original_role = str(data.get("role", ""))
        original_mode = str(data.get("mode", "solution"))
        mapped_role, vne_role = _map_role_to_framework(original_role)
        mapped_mode, vne_mode = _map_mode_to_framework(original_mode)

        if vne_role is not None or vne_mode is not None:
            data["role"] = mapped_role
            data["mode"] = mapped_mode
            metadata = data.get("metadata")
            if metadata is None:
                metadata = {}
            elif not isinstance(metadata, dict):
                print(f"❌ metadata в {source_path} должен быть YAML mapping")
                return 1
            if vne_role is not None:
                metadata.setdefault("vne_role", vne_role)
            if vne_mode is not None:
                metadata.setdefault("vne_mode", vne_mode)
            metadata.setdefault("framework_role", mapped_role)
            metadata.setdefault("framework_mode", mapped_mode)
            data["metadata"] = metadata

            with tempfile.TemporaryDirectory(prefix="vne-framework-mapped-") as temp_dir:
                temp_path = Path(temp_dir) / source_path.name
                _write_task_yaml(temp_path, data)

                if vne_role is not None:
                    print(f"Role: {vne_role} → {mapped_role}")
                if vne_mode is not None:
                    print(f"Mode: {vne_mode} → {mapped_mode}")
                print(f"📝 Mapped task YAML: {temp_path}")
                voyage_args.extend(["--file", str(temp_path)])
                return _invoke_voyage(voyage_args)
        else:
            voyage_args.extend(["--file", args.file])
    elif sub == "list":
        if args.status:
            voyage_args.extend(["--status", args.status])
        if args.role:
            framework_role, vne_role = _map_role_to_framework(args.role)
            if vne_role is not None:
                print(f"Role filter: {vne_role} → {framework_role}")
            voyage_args.extend(["--role", framework_role])
        if args.limit:
            voyage_args.extend(["--limit", str(args.limit)])
    elif sub in ("show", "start", "unblock", "complete", "archive"):
        if not args.task_id:
            print(f"❌ Для 'tasks {sub}' нужен <id>")
            return 1
        voyage_args.append(args.task_id)
    elif sub in ("block", "fail"):
        if not args.task_id:
            print(f"❌ Для 'tasks {sub}' нужен <id>")
            return 1
        voyage_args.append(args.task_id)
        if args.reason:
            voyage_args.extend(["--reason", args.reason])

    return _invoke_voyage(voyage_args)


def cmd_sync(args: argparse.Namespace) -> int:
    """Context sync (v4.1)."""
    subcommand = args.subcommand or "build"
    return _invoke_voyage(["sync", subcommand])


def cmd_chronicler(args: argparse.Namespace) -> int:
    """Chronicler commands (v4.1)."""
    remainder = getattr(args, "remainder", [])
    return _invoke_voyage(["chronicler", *remainder])


def cmd_graph(args: argparse.Namespace) -> int:
    """LangGraph workflow commands (v4.1)."""
    remainder = getattr(args, "remainder", [])
    return _invoke_voyage(["graph", *remainder])


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Show improvement summary (v4.1)."""
    voyage_args = ["evaluate"]
    if args.dir:
        voyage_args.extend(["--dir", args.dir])
    if args.project:
        voyage_args.extend(["--project", args.project])
    return _invoke_voyage(voyage_args)


def cmd_docs(args: argparse.Namespace) -> int:
    """Documentation commands (v4.1)."""
    remainder = getattr(args, "remainder", [])
    return _invoke_voyage(["docs", *remainder])


def cmd_events(args: argparse.Namespace) -> int:
    """Show events (v4.1)."""
    voyage_args = ["events"]
    if args.limit:
        voyage_args.extend(["--limit", str(args.limit)])
    return _invoke_voyage(voyage_args)


def cmd_approve(_args: argparse.Namespace) -> int:
    """Show pending approvals (v4.1)."""
    return _invoke_voyage(["approve"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="vne_adapter",
        description="VNE Adapter — обёртка над Framework-voyage-mvp CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="Показать tracks, роли и templates")

    # task
    task_parser = subparsers.add_parser("task", help="Сгенерировать TASK.md через voyage")
    task_parser.add_argument("--track", help="Track разработки (canon, session_retrospector, renpy_mvp)")
    task_parser.add_argument("--role", help="Роль (vne_canon_guard, vne_retrospector_dev, ...)")
    task_parser.add_argument("--task", required=True, help="Описание задачи")
    task_parser.add_argument("--phase", help="Микро-фаза (SR1, C1, RN1)")
    task_parser.add_argument(
        "--mode",
        default="solution",
        help="Режим task.yaml (например, audit, analysis, solution)",
    )
    task_parser.add_argument("--template", help="Имя шаблона (TASK_SESSION_RETROSPECTOR_v0.1.md)")
    task_parser.add_argument("--yaml", action="store_true", help="Также сгенерировать task.yaml")

    # run
    run_parser = subparsers.add_parser("run", help="Запустить voyage run")
    run_parser.add_argument("--role", required=True, help="Роль")
    run_parser.add_argument("--task", default="", help="Описание задачи")
    run_parser.add_argument("--plan", default="", help="План (semicolon-separated)")
    run_parser.add_argument("--backend", default="subprocess", help="Sandbox backend")

    # status
    subparsers.add_parser("status", help="Статус проекта")

    # gates
    gates_parser = subparsers.add_parser("gates", help="Запустить quality gates")
    gates_parser.add_argument("--gate", help="Запустить только указанную группу gates (например, runtime, schema)")
    gates_parser.add_argument("--dry-run", action="store_true", help="Показать команды, не выполняя")

    # tasks
    tasks_parser = subparsers.add_parser("tasks", help="Task runtime management (v4.1)")
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_command")

    create_parser = tasks_sub.add_parser("create", help="Создать задачу из task.yaml")
    create_parser.add_argument("--file", required=True, help="Путь к task.yaml")

    list_parser = tasks_sub.add_parser("list", help="Список задач")
    list_parser.add_argument("--status", help="Фильтр по статусу")
    list_parser.add_argument("--role", help="Фильтр по роли")
    list_parser.add_argument("--limit", type=int, help="Лимит записей")

    show_parser = tasks_sub.add_parser("show", help="Показать задачу")
    show_parser.add_argument("task_id", help="ID задачи")

    start_parser = tasks_sub.add_parser("start", help="Начать задачу")
    start_parser.add_argument("task_id", help="ID задачи")

    block_parser = tasks_sub.add_parser("block", help="Заблокировать задачу")
    block_parser.add_argument("task_id", help="ID задачи")
    block_parser.add_argument("--reason", help="Причина блокировки")

    unblock_parser = tasks_sub.add_parser("unblock", help="Разблокировать задачу")
    unblock_parser.add_argument("task_id", help="ID задачи")

    complete_parser = tasks_sub.add_parser("complete", help="Завершить задачу")
    complete_parser.add_argument("task_id", help="ID задачи")

    fail_parser = tasks_sub.add_parser("fail", help="Провалить задачу")
    fail_parser.add_argument("task_id", help="ID задачи")
    fail_parser.add_argument("--reason", help="Причина")

    archive_parser = tasks_sub.add_parser("archive", help="Архивировать задачу")
    archive_parser.add_argument("task_id", help="ID задачи")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Context sync commands (v4.1)")
    sync_parser.add_argument(
        "subcommand",
        nargs="?",
        default="build",
        choices=["build", "check", "status"],
        help="Действие sync (default: build)",
    )

    # chronicler
    chronicler_parser = subparsers.add_parser("chronicler", help="Chronicler commands (v4.1)")
    chronicler_parser.add_argument(
        "remainder",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to 'voyage chronicler'",
    )

    # graph
    graph_parser = subparsers.add_parser("graph", help="LangGraph workflow commands (v4.1)")
    graph_parser.add_argument(
        "remainder",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to 'voyage graph'",
    )

    # evaluate
    evaluate_parser = subparsers.add_parser("evaluate", help="Show improvement summary (v4.1)")
    evaluate_parser.add_argument("--dir", help="Project directory")
    evaluate_parser.add_argument("--project", help="Project ID")

    # docs
    docs_parser = subparsers.add_parser("docs", help="Documentation commands (v4.1)")
    docs_parser.add_argument(
        "remainder",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to 'voyage docs'",
    )

    # events
    events_parser = subparsers.add_parser("events", help="Show events (v4.1)")
    events_parser.add_argument("--limit", type=int, help="Limit events")

    # approve
    subparsers.add_parser("approve", help="Show pending approvals (v4.1)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    commands: dict[str, Any] = {
        "list": cmd_list,
        "task": cmd_task,
        "run": cmd_run,
        "status": cmd_status,
        "gates": cmd_gates,
        "tasks": cmd_tasks,
        "sync": cmd_sync,
        "chronicler": cmd_chronicler,
        "graph": cmd_graph,
        "evaluate": cmd_evaluate,
        "docs": cmd_docs,
        "events": cmd_events,
        "approve": cmd_approve,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
