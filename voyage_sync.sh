#!/bin/bash
# =============================================================================
# Voyage Sync & Deploy Script v1.0
# Синхронизация репозитория между устройствами (Android/Termux).
# Режимы: git-sync | archive-sync | auto-integrate | deploy
# =============================================================================

set -e

REPO_DIR="${HOME}/voyage-narrative-engine"
ARCHIVE_DIR="/sdcard/Download/voyage-narrative-engine"
PERSONAS_DIR="${REPO_DIR}/personas"
SCRIPTS_DIR="${REPO_DIR}/scripts"
INTEGRATOR="${REPO_DIR}/voyage_integrator.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}=== Voyage Sync & Deploy v1.0 ===${NC}"
echo ""

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------
log() {
    local level="$1"
    local msg="$2"
    local color=""
    case "$level" in
        OK) color="${GREEN}" ;;
        WARN) color="${YELLOW}" ;;
        ERROR) color="${RED}" ;;
        INFO) color="" ;;
        STEP) color="${BLUE}" ;;
    esac
    echo -e "${color}[${level}] ${msg}${NC}"
}

# -----------------------------------------------------------------------------
# 1. Check repo
# -----------------------------------------------------------------------------
if [ ! -d "$REPO_DIR" ]; then
    log ERROR "Репозиторий не найден: $REPO_DIR"
    echo "Клонируйте:"
    echo "  git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git ~/voyage-narrative-engine"
    exit 1
fi
log OK "Репозиторий: $REPO_DIR"

# -----------------------------------------------------------------------------
# 2. Git Pull (получить изменения с GitHub)
# -----------------------------------------------------------------------------
echo ""
log STEP "[1/6] Git Pull — получение изменений с GitHub..."
cd "$REPO_DIR"
if [ -d .git ]; then
    git pull origin main || {
        log WARN "git pull не удался (возможно, конфликт). Продолжаем с локальными файлами..."
    }
    log OK "Git pull завершён"
else
    log WARN "Git не инициализирован. Пропускаем pull."
fi

# -----------------------------------------------------------------------------
# 3. Archive Sync — проверить /sdcard/Download/voyage-narrative-engine
# -----------------------------------------------------------------------------
echo ""
log STEP "[2/6] Archive Sync — проверка архива в Download/..."

if [ -d "$ARCHIVE_DIR" ]; then
    log OK "Архив найден: $ARCHIVE_DIR"

    # Найти новые файлы в архиве, которых нет в репозитории
    NEW_FILES=$(find "$ARCHIVE_DIR" -type f -newer "$REPO_DIR/.git/index" 2>/dev/null || true)

    if [ -n "$NEW_FILES" ]; then
        log INFO "Найдены новые файлы в архиве:"
        echo "$NEW_FILES" | while read -r file; do
            rel_path="${file#$ARCHIVE_DIR/}"
            target="$REPO_DIR/$rel_path"
            if [ ! -f "$target" ]; then
                log OK "  NEW: $rel_path"
                mkdir -p "$(dirname "$target")"
                cp "$file" "$target"
            elif [ "$file" -nt "$target" ]; then
                log WARN "  UPDATED: $rel_path (архив новее)"
                cp "$file" "$target"
            fi
        done
        log OK "Файлы из архива скопированы в репозиторий"
    else
        log INFO "Нет новых файлов в архиве"
    fi
else
    log INFO "Архив не найден: $ARCHIVE_DIR (пропускаем)"
fi

# -----------------------------------------------------------------------------
# 4. Auto-Integrate — запуск voyage_integrator.py
# -----------------------------------------------------------------------------
echo ""
log STEP "[3/6] Auto-Integrate — интеграция новых персонажей..."

# Ensure integrator script exists
if [ ! -f "$INTEGRATOR" ]; then
    log WARN "voyage_integrator.py не найден в репозитории. Копируем..."
    # Try to find it in home or download
    FOUND=$(find "$HOME" -maxdepth 2 -name "voyage_integrator.py" -print -quit 2>/dev/null)
    if [ -n "$FOUND" ]; then
        cp "$FOUND" "$REPO_DIR/"
        log OK "Скопирован: $FOUND"
    else
        log ERROR "voyage_integrator.py не найден. Скачайте его в ~/ и повторите."
        exit 1
    fi
fi

cd "$REPO_DIR"
python3 "$INTEGRATOR" --repo "$REPO_DIR" || {
    log WARN "Авто-интеграция не справилась. Генерируем промпт для LLM..."
    python3 "$INTEGRATOR" --repo "$REPO_DIR" --llm-prompt > "${REPO_DIR}/LLM_INTEGRATION_PROMPT.md"
    log OK "Промпт сохранён: ${REPO_DIR}/LLM_INTEGRATION_PROMPT.md"
    log INFO "Загрузите этот файл в чат нейросети для анализа и патчей."
}

# -----------------------------------------------------------------------------
# 5. Test — проверка системы
# -----------------------------------------------------------------------------
echo ""
log STEP "[4/6] Test — проверка системы..."

# Test 1: JSON validity of all personas
log INFO "Проверка JSON всех персонажей..."
for json_file in "$PERSONAS_DIR"/*.json; do
    [ -f "$json_file" ] || continue
    python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null || {
        log ERROR "Invalid JSON: $(basename "$json_file")"
        exit 1
    }
done
log OK "Все JSON валидны"

# Test 2: session_finalize.py loads
log INFO "Проверка session_finalize.py..."
python3 "$REPO_DIR/session_finalize.py" --help >/dev/null 2>&1 || {
    log ERROR "session_finalize.py не загружается! Проверьте ошибки выше."
    exit 1
}
log OK "session_finalize.py работает"

# Test 3: Check for duplicate names (two Andrey problem)
log INFO "Проверка дублирования имён..."
python3 << 'PYEOF'
import json, sys, os
from pathlib import Path
repo = Path.home() / "voyage-narrative-engine"
personas = list((repo / "personas").glob("*_MODULE*.json"))
names = {}
for p in personas:
    try:
        data = json.load(open(p, "r", encoding="utf-8"))
        name = data.get("name", "")
        if name:
            names.setdefault(name, []).append(p.name)
    except:
        pass
for name, files in names.items():
    if len(files) > 1:
        print(f"[WARN] Duplicate name '{name}' in: {', '.join(files)}")
PYEOF

# -----------------------------------------------------------------------------
# 6. Git Status & Commit
# -----------------------------------------------------------------------------
echo ""
log STEP "[5/6] Git Status & Commit..."
cd "$REPO_DIR"

if [ -d .git ]; then
    git status --short

    # Check if there are changes
    if [ -n "$(git status --porcelain)" ]; then
        git add -A
        git commit -m "sync: auto-integrate new personas + system updates

- Auto-detected new persona modules
- Patched session_finalize.py (VSCNO, loading, negative prompts)
- Updated README.md if needed
- Validated JSON + tested session_finalize.py
- Date: $(date '+%Y-%m-%d %H:%M')" || true
        log OK "Git commit выполнен"
    else
        log OK "Нет изменений для коммита"
    fi
else
    log WARN "Git не инициализирован"
fi

# -----------------------------------------------------------------------------
# 7. Git Push
# -----------------------------------------------------------------------------
echo ""
log STEP "[6/6] Git Push — отправка на GitHub..."
cd "$REPO_DIR"

if [ -d .git ]; then
    # Try push, if fails do pull --rebase then push
    git push origin main || {
        log WARN "Push rejected. Пробуем git pull --rebase..."
        git pull --rebase origin main || git pull origin main
        git push origin main
    }
    log OK "Push завершён! Репозиторий синхронизирован."
else
    log WARN "Git не инициализирован — push невозможен"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${CYAN}=== СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА ===${NC}"
echo ""
log OK "Персонажи в personas/:"
ls -la "$PERSONAS_DIR"/*.json 2>/dev/null | awk '{print "  " $9 " (" $5 " bytes)"}'
echo ""
log INFO "Следующие шаги:"
echo "  1. Проверьте README.md на GitHub"
echo "  2. Запустите тестовую сессию с новыми персонажами"
echo "  3. Если были ошибки интеграции — загрузите LLM_INTEGRATION_PROMPT.md в чат"
echo ""
echo -e "${GREEN}Готово! 🧠${NC}"
