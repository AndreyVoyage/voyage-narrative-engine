#!/bin/bash
# =============================================================================
# Voyage Local Scanner v1.2
# Исправление: ((var++)) → var=$((var + 1)) (set -e баг)
# =============================================================================

set -e

REPO_DIR="${HOME}/voyage-narrative-engine"
PERSONAS_DIR="${REPO_DIR}/personas"
DOWNLOAD_DIR="/sdcard/Download"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${CYAN}=== Voyage Local Scanner v1.2 ===${NC}"
echo ""

# 1. Находим папку с именем репозитория в Download/
ARCHIVE_DIR=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type d -iname "voyage-narrative-engine*" | head -n1)

if [ -z "$ARCHIVE_DIR" ]; then
    echo -e "${RED}[ERROR] Папка 'voyage-narrative-engine*' не найдена в $DOWNLOAD_DIR${NC}"
    echo ""
    echo -e "${YELLOW}Возможные причины:${NC}"
    echo "  1. ZIP репозитория ещё не распакован"
    echo "  2. Папка названа по-другому"
    echo ""
    echo -e "${YELLOW}Решение:${NC}"
    echo "  Распакуйте ZIP в $DOWNLOAD_DIR/"
    echo "  Или укажите путь вручную:"
    echo "    ARCHIVE_DIR=/sdcard/Download/МОЯ_ПАПКА ~/voyage_scan.sh"
    exit 1
fi

echo -e "${GREEN}[OK] Найдена папка: $ARCHIVE_DIR${NC}"

# 2. Рекурсивно сканируем ВСЕ подпапки внутри
COPIED=0
UPDATED=0

echo ""
echo -e "${YELLOW}[SCAN] Рекурсивный поиск *_MODULE*.json...${NC}"

while IFS= read -r -d '' file; do
    filename=$(basename "$file")

    # Пропускаем служебные файлы
    [[ "$filename" =~ ^[0-9]+_INDEX\.json$ ]] && continue
    [[ "$filename" =~ ^[0-9]+\.json$ ]] && continue
    [[ "$filename" =~ ^08_INDEX\.json$ ]] && continue

    target="$PERSONAS_DIR/$filename"
    rel_path="${file#$ARCHIVE_DIR/}"

    if [ ! -f "$target" ]; then
        # Файл НОВЫЙ
        echo -e "  ${GREEN}[NEW] $filename${NC}"
        echo -e "      ${BLUE}→${NC} ${rel_path}"
        cp "$file" "$target"
        COPIED=$((COPIED + 1))
    elif [ "$file" -nt "$target" ]; then
        # Файл ОБНОВЛЁН (новее по дате)
        echo -e "  ${YELLOW}[UPD] $filename (новее)${NC}"
        echo -e "      ${BLUE}→${NC} ${rel_path}"
        cp "$target" "${target}.bak.$(date +%s)"
        cp "$file" "$target"
        UPDATED=$((UPDATED + 1))
    fi
done < <(find "$ARCHIVE_DIR" -type f -iname "*_MODULE*.json" -print0 2>/dev/null)

# 3. Итог сканирования
echo ""
if [ $COPIED -eq 0 ] && [ $UPDATED -eq 0 ]; then
    echo -e "${GREEN}Новых/обновлённых модулей не найдено.${NC}"
    echo -e "${YELLOW}Все файлы в $ARCHIVE_DIR уже синхронизированы с репозиторием.${NC}"
    echo ""
    echo -e "${CYAN}=== Запуск voyage_sync.sh (для git push) ===${NC}"
    cd "$REPO_DIR"
    ./scripts/termux/voyage_sync.sh
    exit 0
fi

echo -e "${GREEN}=== Результат сканирования ===${NC}"
echo -e "  Новых файлов:  ${GREEN}$COPIED${NC}"
echo -e "  Обновлённых:   ${YELLOW}$UPDATED${NC}"
echo ""

# 4. Проверка JSON
echo -e "${YELLOW}[CHECK] Проверка JSON всех модулей...${NC}"
for json_file in "$PERSONAS_DIR"/*_MODULE*.json; do
    [ -f "$json_file" ] || continue
    python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null || {
        echo -e "${RED}[ERROR] Invalid JSON: $(basename "$json_file")${NC}"
        exit 1
    }
done
echo -e "${GREEN}[OK] Все JSON валидны${NC}"

# 5. Запуск интеграции и синхронизации
echo ""
echo -e "${CYAN}[SYNC] Запуск voyage_sync.sh (интеграция + git push)...${NC}"
echo ""
cd "$REPO_DIR"
./scripts/termux/voyage_sync.sh
