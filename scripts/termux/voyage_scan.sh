#!/bin/bash
# =============================================================================
# Voyage Local Scanner v2.0
# Сканирует ВСЕ папки (personas, scenarios, roles, docs...)
# =============================================================================

set -e

REPO_DIR="${HOME}/voyage-narrative-engine"
DOWNLOAD_DIR="/sdcard/Download"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}=== Voyage Local Scanner v2.0 ===${NC}"
echo ""

ARCHIVE_DIR=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type d -iname "voyage-narrative-engine*" | head -n1)

if [ -z "$ARCHIVE_DIR" ]; then
    echo -e "${RED}[ERROR] Папка 'voyage-narrative-engine*' не найдена в $DOWNLOAD_DIR${NC}"
    echo "Решение: распакуйте ZIP в $DOWNLOAD_DIR/"
    exit 1
fi

echo -e "${GREEN}[OK] Найдена папка: $ARCHIVE_DIR${NC}"

COPIED=0
UPDATED=0

echo ""
echo -e "${YELLOW}[SCAN] Рекурсивный поиск всех файлов...${NC}"

while IFS= read -r -d '' file; do
    filename=$(basename "$file")
    rel_path="${file#$ARCHIVE_DIR/}"
    target="$REPO_DIR/$rel_path"
    
    [[ "$rel_path" == .git* ]] && continue
    [[ "$rel_path" == __pycache__* ]] && continue
    [[ "$rel_path" == node_modules* ]] && continue
    [[ "$rel_path" == *.bak* ]] && continue
    [[ "$rel_path" == *.tmp ]] && continue
    [[ "$filename" =~ ^[0-9]+_INDEX\.json$ ]] && continue
    [[ "$filename" == "08_INDEX.json" ]] && continue
    [[ "$filename" == ".gitignore" ]] && continue
    
    [ -d "$file" ] && continue
    
    if [ ! -f "$target" ]; then
        echo -e "  ${GREEN}[NEW] $rel_path${NC}"
        mkdir -p "$(dirname "$target")"
        cp "$file" "$target"
        COPIED=$((COPIED + 1))
    elif [ "$file" -nt "$target" ]; then
        echo -e "  ${YELLOW}[UPD] $rel_path (новее)${NC}"
        mkdir -p "$(dirname "$target")"
        cp "$target" "${target}.bak.$(date +%s)" 2>/dev/null || true
        cp "$file" "$target"
        UPDATED=$((UPDATED + 1))
    fi
done < <(find "$ARCHIVE_DIR" -type f -print0 2>/dev/null)

echo ""
if [ $COPIED -eq 0 ] && [ $UPDATED -eq 0 ]; then
    echo -e "${GREEN}Новых/обновлённых файлов не найдено.${NC}"
    echo -e "${CYAN}=== Запуск voyage_sync.sh ===${NC}"
    cd "$REPO_DIR"
    ./scripts/termux/voyage_sync.sh
    exit 0
fi

echo -e "${GREEN}=== Результат ===${NC}"
echo -e "  Новых:  ${GREEN}$COPIED${NC}"
echo -e "  Обновлённых: ${YELLOW}$UPDATED${NC}"
echo ""

if [ -d "$REPO_DIR/personas" ]; then
    echo -e "${YELLOW}[CHECK] Проверка JSON...${NC}"
    for json_file in "$REPO_DIR/personas"/*_MODULE*.json; do
        [ -f "$json_file" ] || continue
        python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null || {
            echo -e "${RED}[ERROR] Invalid JSON: $(basename "$json_file")${NC}"
            exit 1
        }
    done
    echo -e "${GREEN}[OK] JSON валиден${NC}"
fi

echo ""
echo -e "${CYAN}[SYNC] Запуск voyage_sync.sh...${NC}"
cd "$REPO_DIR"
./scripts/termux/voyage_sync.sh
