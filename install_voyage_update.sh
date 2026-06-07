#!/bin/bash
# Voyage Narrative Engine v2.0 — Installer for Termux
# Usage: bash install_voyage_update.sh [path_to_repo]
# Default path: ~/voyage-narrative-engine

set -e

REPO_PATH="${1:-$HOME/voyage-narrative-engine}"
ARCHIVE_DIR="$(dirname "$0")"

echo "========================================"
echo " Voyage Narrative Engine v2.0 Installer"
echo "========================================"
echo "Target repo: $REPO_PATH"
echo ""

# Check if repo exists
if [ ! -d "$REPO_PATH" ]; then
    echo "[INFO] Repository not found. Creating..."
    mkdir -p "$REPO_PATH"
    cd "$REPO_PATH"
    git init 2>/dev/null || true
else
    echo "[INFO] Repository found. Backing up legacy files..."
    cd "$REPO_PATH"

    # Backup legacy files if they exist
    mkdir -p legacy/v1.0 2>/dev/null || true

    for file in core/VOYAGE_NARRATIVE_CORE.md personas/KIRA_MODULE.json personas/SERGEY_MODULE.json state/STATE_TEMPLATE.json scenarios/SCENARIO_MATRIX.json governance/AUTONOMY_GOVERNOR.md visual/QWEN_ADAPTER.md memory/MEMORY_PROTOCOL.md; do
        if [ -f "$file" ]; then
            cp "$file" "legacy/v1.0/$(basename "$file")" 2>/dev/null || true
            echo "  [BACKUP] $file → legacy/v1.0/"
        fi
    done
fi

# Create directory structure
echo ""
echo "[STEP 1] Creating directory structure..."
mkdir -p core personas state scenarios governance visual memory legacy/v1.0

# Copy new files
echo ""
echo "[STEP 2] Installing v2.0 files..."

cp "$ARCHIVE_DIR/README.md" "$REPO_PATH/README.md" 2>/dev/null || echo "  [SKIP] README.md not in archive"
cp "$ARCHIVE_DIR/core/VOYAGE_NARRATIVE_CORE_v2.md" "$REPO_PATH/core/" 2>/dev/null || echo "  [SKIP] CORE_v2 not in archive"
cp "$ARCHIVE_DIR/personas/KIRA_MODULE_v12.json" "$REPO_PATH/personas/" 2>/dev/null || echo "  [SKIP] KIRA_MODULE_v12 not in archive"
cp "$ARCHIVE_DIR/personas/SERGEY_MODULE_v3.json" "$REPO_PATH/personas/" 2>/dev/null || echo "  [SKIP] SERGEY_MODULE_v3 not in archive"
cp "$ARCHIVE_DIR/state/STATE_TEMPLATE_v2.json" "$REPO_PATH/state/" 2>/dev/null || echo "  [SKIP] STATE_TEMPLATE_v2 not in archive"
cp "$ARCHIVE_DIR/scenarios/SCENARIO_SHY_BLOOM.json" "$REPO_PATH/scenarios/" 2>/dev/null || echo "  [SKIP] SCENARIO_SHY_BLOOM not in archive"
cp "$ARCHIVE_DIR/governance/AUTONOMY_GOVERNOR_v2.md" "$REPO_PATH/governance/" 2>/dev/null || echo "  [SKIP] GOVERNOR_v2 not in archive"
cp "$ARCHIVE_DIR/visual/QWEN_ADAPTER_v2.md" "$REPO_PATH/visual/" 2>/dev/null || echo "  [SKIP] QWEN_ADAPTER_v2 not in archive"
cp "$ARCHIVE_DIR/memory/MEMORY_PROTOCOL_v2.md" "$REPO_PATH/memory/" 2>/dev/null || echo "  [SKIP] MEMORY_PROTOCOL_v2 not in archive"

# Create PROMPT builder script
echo ""
echo "[STEP 3] Creating helper scripts..."

cat > "$REPO_PATH/build_prompt.sh" << 'EOF'
#!/bin/bash
# Build PROMPT.txt for LLM session
# Usage: bash build_prompt.sh [mode] [scenario_id]
# mode: default | shy_to_bitch
# scenario_id: optional, e.g. SC_001-A

REPO_DIR="$(dirname "$0")"
MODE="${1:-shy_to_bitch}"
SCENARIO_ID="${2:-}"
OUTPUT="$REPO_DIR/PROMPT.txt"

echo "Building PROMPT.txt for mode: $MODE"

# Core
cat "$REPO_DIR/core/VOYAGE_NARRATIVE_CORE_v2.md" > "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== PERSONA: KIRA ===" >> "$OUTPUT"
cat "$REPO_DIR/personas/KIRA_MODULE_v12.json" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== PERSONA: SERGEY ===" >> "$OUTPUT"
cat "$REPO_DIR/personas/SERGEY_MODULE_v3.json" >> "$OUTPUT"
echo "" >> "$OUTPUT"
echo "=== STATE ===" >> "$OUTPUT"
cat "$REPO_DIR/state/STATE_TEMPLATE_v2.json" >> "$OUTPUT"

# Scenario if specified
if [ -n "$SCENARIO_ID" ]; then
    echo "" >> "$OUTPUT"
    echo "=== SCENARIO: $SCENARIO_ID ===" >> "$OUTPUT"
    # Extract scenario from SCENARIO_SHY_BLOOM.json (requires python or jq)
    if command -v python3 &> /dev/null; then
        python3 -c "
import json, sys
with open('$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json') as f:
    data = json.load(f)
    for sc in data.get('library_index', []):
        if sc.get('id') == '$SCENARIO_ID':
            print(json.dumps(sc, ensure_ascii=False, indent=2))
            sys.exit(0)
    print('Scenario not found')
" >> "$OUTPUT"
    else
        echo "[WARNING] python3 not found. Cannot extract specific scenario. Full scenario file included." >> "$OUTPUT"
        cat "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json" >> "$OUTPUT"
    fi
else
    echo "" >> "$OUTPUT"
    echo "=== SCENARIOS ===" >> "$OUTPUT"
    cat "$REPO_DIR/scenarios/SCENARIO_SHY_BLOOM.json" >> "$OUTPUT"
fi

echo ""
echo "=== INSTRUCTIONS ===" >> "$OUTPUT"
echo "Запускаем Voyage Engine v2.0." >> "$OUTPUT"
echo "Режим: kira_persona_mode = '$MODE'" >> "$OUTPUT"
echo "Сергей: sergey_role = 'catalyst'" >> "$OUTPUT"
echo "Текущий STATE: Кира У1-А, Сергей С1, локация gym." >> "$OUTPUT"
if [ -n "$SCENARIO_ID" ]; then
    echo "Начни сцену $SCENARIO_ID." >> "$OUTPUT"
else
    echo "Начни сцену SC_000." >> "$OUTPUT"
fi

echo ""
echo "PROMPT.txt built successfully: $OUTPUT"
echo "Size: $(wc -c < $OUTPUT) bytes"
EOF

chmod +x "$REPO_PATH/build_prompt.sh"

# Create state updater script
cat > "$REPO_PATH/update_state.sh" << 'EOF'
#!/bin/bash
# Update STATE from LLM response
# Usage: bash update_state.sh [state_file] [new_level] [new_sublevel] [flags...]

STATE_FILE="${1:-$HOME/voyage-narrative-engine/state/STATE_TEMPLATE_v2.json}"
NEW_LEVEL="$2"
NEW_SUBLEVEL="$3"
shift 3
NEW_FLAGS="$@"

if [ ! -f "$STATE_FILE" ]; then
    echo "[ERROR] State file not found: $STATE_FILE"
    exit 1
fi

if [ -z "$NEW_LEVEL" ] || [ -z "$NEW_SUBLEVEL" ]; then
    echo "Usage: bash update_state.sh [state_file] [U1-U7] [A|B] [flag1 flag2 ...]"
    exit 1
fi

# Update using python3 if available
if command -v python3 &> /dev/null; then
    python3 -c "
import json, sys, datetime
with open('$STATE_FILE', 'r') as f:
    state = json.load(f)

state['timestamp'] = datetime.datetime.now().isoformat() + 'Z'
state['characters']['kira']['level'] = '$NEW_LEVEL'
state['characters']['kira']['sublevel'] = '$NEW_SUBLEVEL'
state['characters']['kira']['full_level'] = '$NEW_LEVEL-$NEW_SUBLEVEL'

for flag in '$NEW_FLAGS'.split():
    if flag:
        state['flags'][flag] = True

with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f'[OK] State updated: {NEW_LEVEL}-{NEW_SUBLEVEL}')
print(f'[OK] Flags set: {NEW_FLAGS}')
"
else
    echo "[ERROR] python3 required for state updates"
    exit 1
fi
EOF

chmod +x "$REPO_PATH/update_state.sh"

# Create git commit helper
cat > "$REPO_PATH/git_commit.sh" << 'EOF'
#!/bin/bash
# Git commit helper for Voyage sessions
# Usage: bash git_commit.sh [message]

REPO_DIR="$(dirname "$0")"
cd "$REPO_DIR"

MSG="${1:-Session update $(date +%Y-%m-%d_%H:%M)}"

git add -A 2>/dev/null || true
git commit -m "$MSG" 2>/dev/null || echo "[INFO] Nothing to commit or git not initialized"

echo "[OK] Committed: $MSG"
EOF

chmod +x "$REPO_PATH/git_commit.sh"

# Create quick start guide
cat > "$REPO_PATH/QUICKSTART.md" << 'EOF'
# Быстрый старт Voyage Engine v2.0

## 1. Сборка PROMPT.txt

```bash
cd ~/voyage-narrative-engine
bash build_prompt.sh shy_to_bitch SC_000
```

Режимы:
- `default` — классическая Кира (стальная бабочка)
- `shy_to_bitch` — невинность → стерва (новый v2.0)

## 2. Загрузка в Kimi

1. Откройте Kimi (kimi.moonshot.cn)
2. Загрузите файл `PROMPT.txt`
3. Напишите: `Запускаем Voyage Engine v2.0`

## 3. Управление внутри сессии

| Команда | Эффект |
|---|---|
| `У1-А` … `У7-Б` | Переключить подуровень |
| `ТГ1` … `ТГ3` | Переключить грань |
| `АД [код]` | Активировать алгоритм |
| `М [параметры]` | Сгенерировать сценарий |
| `В` | Сгенерировать Qwen-промпт |
| `Г [0-4]` | Установить Autonomy Governor |
| `СТОП` | Emergency exit → У7-А |
| `режим default` | Переключить в legacy |
| `режим shy_to_bitch` | Переключить в совращение |
| `Сергей catalyst` | Роль Сергея: зеркало |
| `Сергей ally` | Роль Сергея: союзник |
| `Сергей rival` | Роль Сергея: соперник |

## 4. Обновление STATE после сессии

```bash
bash update_state.sh state/STATE_TEMPLATE_v2.json U2 B kira_first_blush kira_asked_why_you_look
```

## 5. Git commit

```bash
bash git_commit.sh "Session 2026-06-07: U2-B reached, SC_001-B completed"
```

## 6. Генерация картинок (Qwen Studio)

1. В конце каждого ответа Kimi генерирует `[AUTO_VISUAL]` блок.
2. Скопируйте Qwen-промпт (строка после `Qwen:`).
3. Вставьте в Qwen Studio (qwen.ai/studio).
4. Настройте: CFG из блока, Steps из блока, Seed = 54321 (для Киры) или 67890 (для Сергея).

## 7. Структура репозитория

```
voyage-narrative-engine/
├── README.md
├── QUICKSTART.md          ← вы здесь
├── build_prompt.sh        ← сборщик PROMPT.txt
├── update_state.sh        ← обновление STATE
├── git_commit.sh          ← git commit
├── PROMPT.txt             ← собранный промпт для Kimi
├── core/
│   └── VOYAGE_NARRATIVE_CORE_v2.md
├── personas/
│   ├── KIRA_MODULE_v12.json
│   └── SERGEY_MODULE_v3.json
├── state/
│   └── STATE_TEMPLATE_v2.json
├── scenarios/
│   └── SCENARIO_SHY_BLOOM.json
├── governance/
│   └── AUTONOMY_GOVERNOR_v2.md
├── visual/
│   └── QWEN_ADAPTER_v2.md
├── memory/
│   └── MEMORY_PROTOCOL_v2.md
└── legacy/v1.0/           ← старые файлы (backup)
```

## 8. Режимы Киры

### `default` (Стальная бабочка)
- У1: Стойкость → У7: Aftercare
- Классическая дуга спринтерши
- Используйте: `bash build_prompt.sh default`

### `shy_to_bitch` (Невинность → Стерва)
- У1-А: Невинность → У7-Б: Интеграция
- 14 подуровней (A/Б)
- Сергей — катализатор (зеркало)
- Используйте: `bash build_prompt.sh shy_to_bitch`

## 9. Треугольник отношений (Модель C)

- **Кира ↔ Я:** якорь, спасатель. Он ведёт её через невинность.
- **Сергей ↔ Я:** союзник по совращению. Уступает, если «я» сказал «стоп».
- **Кира ↔ Сергей:** зеркало. Он видит её микродвижения и отражает их.

## 10. Поддержка

- GitHub: https://github.com/AndreyVoyage/voyage-narrative-engine
- Issues: создавайте для багов и предложений
- Форки: приветствуются

---

> **Примечание:** Это prompt-native framework. Вся логика выполняется LLM на основе загруженного контекста. Для автоматизации парсинга STATE требуется runtime-скрипт (в разработке).
EOF

# Git commit (if git available)
if command -v git &> /dev/null && [ -d "$REPO_PATH/.git" ]; then
    cd "$REPO_PATH"
    git add -A 2>/dev/null || true
    git commit -m "Voyage Engine v2.0 installed: shy_to_bitch mode, sublevels A/B, catalyst Sergey" 2>/dev/null || echo "[INFO] Git commit skipped"
fi

echo ""
echo "========================================"
echo " Installation Complete!"
echo "========================================"
echo ""
echo "Files installed:"
ls -lh "$REPO_PATH/core/"*.md 2>/dev/null || true
ls -lh "$REPO_PATH/personas/"*.json 2>/dev/null || true
ls -lh "$REPO_PATH/state/"*.json 2>/dev/null || true
ls -lh "$REPO_PATH/scenarios/"*.json 2>/dev/null || true
ls -lh "$REPO_PATH/governance/"*.md 2>/dev/null || true
ls -lh "$REPO_PATH/visual/"*.md 2>/dev/null || true
ls -lh "$REPO_PATH/memory/"*.md 2>/dev/null || true
echo ""
echo "Helper scripts:"
ls -lh "$REPO_PATH/build_prompt.sh" 2>/dev/null || true
ls -lh "$REPO_PATH/update_state.sh" 2>/dev/null || true
ls -lh "$REPO_PATH/git_commit.sh" 2>/dev/null || true
echo ""
echo "Next steps:"
echo "  1. cd $REPO_PATH"
echo "  2. bash build_prompt.sh shy_to_bitch SC_000"
echo "  3. Upload PROMPT.txt to Kimi"
echo "  4. Start: 'Запускаем Voyage Engine v2.0'"
echo ""
echo "Read QUICKSTART.md for detailed instructions."
echo "========================================"
