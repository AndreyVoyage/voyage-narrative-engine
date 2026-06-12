#!/bin/bash
# =============================================================================
# Voyage Sync & Deploy v1.1
# Исправление: путь к voyage_integrator.py
# =============================================================================

set -e

REPO_DIR="${HOME}/voyage-narrative-engine"
PERSONAS_DIR="${REPO_DIR}/personas"
SESSION_FINALIZE="${REPO_DIR}/session_finalize.py"
INTEGRATOR="${REPO_DIR}/scripts/termux/voyage_integrator.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}=== Voyage Sync & Deploy v1.1 ===${NC}"
echo ""

# 1. Check repo
if [ ! -d "$REPO_DIR" ]; then
    echo -e "${RED}[ERROR] Репозиторий не найден: $REPO_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Репозиторий: $REPO_DIR${NC}"

# 2. Git Pull
echo ""
echo -e "${YELLOW}[STEP] [1/6] Git Pull...${NC}"
cd "$REPO_DIR"
if [ -d .git ]; then
    git pull origin main || true
    echo -e "${GREEN}[OK] Git pull завершён${NC}"
else
    echo -e "${YELLOW}[WARN] Git не инициализирован${NC}"
fi

# 3. Archive Sync
echo ""
echo -e "${YELLOW}[STEP] [2/6] Archive Sync...${NC}"
ARCHIVE_DIR=$(find /sdcard/Download -maxdepth 1 -type d -iname "voyage-narrative-engine*" | head -n1)
if [ -d "$ARCHIVE_DIR" ]; then
    echo -e "${GREEN}[OK] Архив найден: $ARCHIVE_DIR${NC}"
    # Find new files
    NEW_FILES=$(find "$ARCHIVE_DIR" -type f -newer "$REPO_DIR/.git/index" 2>/dev/null || true)
    if [ -n "$NEW_FILES" ]; then
        echo "$NEW_FILES" | while read -r file; do
            rel_path="${file#$ARCHIVE_DIR/}"
            target="$REPO_DIR/$rel_path"
            if [ ! -f "$target" ]; then
                echo -e "  ${GREEN}[NEW] $rel_path${NC}"
                mkdir -p "$(dirname "$target")"
                cp "$file" "$target"
            elif [ "$file" -nt "$target" ]; then
                echo -e "  ${YELLOW}[UPD] $rel_path${NC}"
                cp "$file" "$target"
            fi
        done
    fi
else
    echo -e "${INFO}[INFO] Архив не найден (пропускаем)${NC}"
fi

# 4. Auto-Integrate
echo ""
echo -e "${YELLOW}[STEP] [3/6] Auto-Integrate...${NC}"
if [ -f "$INTEGRATOR" ]; then
    python3 "$INTEGRATOR" --repo "$REPO_DIR" || {
        echo -e "${YELLOW}[WARN] Авто-интеграция не справилась${NC}"
    }
else
    echo -e "${YELLOW}[WARN] voyage_integrator.py не найден: $INTEGRATOR${NC}"
fi

# 5. Test
echo ""
echo -e "${YELLOW}[STEP] [4/6] Test...${NC}"
echo -e "${INFO}[INFO] Проверка JSON...${NC}"
for json_file in "$PERSONAS_DIR"/*_MODULE*.json; do
    [ -f "$json_file" ] || continue
    python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null || {
        echo -e "${RED}[ERROR] Invalid JSON: $(basename "$json_file")${NC}"
        exit 1
    }
done
echo -e "${GREEN}[OK] JSON валиден${NC}"

echo -e "${INFO}[INFO] Проверка session_finalize.py...${NC}"
python3 "$SESSION_FINALIZE" --help >/dev/null 2>&1 || {
    echo -e "${RED}[ERROR] session_finalize.py не загружается${NC}"
    exit 1
}
echo -e "${GREEN}[OK] session_finalize.py работает${NC}"

# 6. Git Commit
echo ""
echo -e "${YELLOW}[STEP] [5/6] Git Commit...${NC}"
cd "$REPO_DIR"
if [ -d .git ]; then
    git add -A
    git commit -m "sync: auto-update $(date '+%Y-%m-%d %H:%M')" || true
    echo -e "${GREEN}[OK] Git commit${NC}"
else
    echo -e "${YELLOW}[WARN] Git не инициализирован${NC}"
fi

# 7. Git Push
echo ""
echo -e "${YELLOW}[STEP] [6/6] Git Push...${NC}"
cd "$REPO_DIR"
if [ -d .git ]; then
    git push origin main || {
        git pull --rebase origin main
        git push origin main
    }
    echo -e "${GREEN}[OK] Push завершён!${NC}"
else
    echo -e "${YELLOW}[WARN] Git не инициализирован${NC}"
fi

echo ""
echo -e "${CYAN}=== СИНХРОНИЗАЦИЯ ЗАВЕРШЕНА ===${NC}"
echo ""
echo -e "${GREEN}Готово! 🧠${NC}"
