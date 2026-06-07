#!/bin/bash
# Voyage Roles Update Script v1.0
# Исправлено: абсолютные пути, проверка существования, нет /tmp

set -e  # Остановить при любой ошибке

REPO_DIR="$HOME/voyage-narrative-engine"
TMP_DIR="$HOME/.voyage_tmp"
ARCHIVE_NAME="voyage_roles_update_2026-06-08.zip"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

error_exit() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

info() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

# 1. Проверка: мы в домашней папке или в репозитории?
info "Проверка окружения..."

if [ -d "$REPO_DIR" ]; then
    info "Репозиторий найден: $REPO_DIR"
else
    error_exit "Репозиторий не найден: $REPO_DIR\nСначала клонируйте: git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git"
fi

# 2. Проверка: архив рядом?
if [ -f "$HOME/$ARCHIVE_NAME" ]; then
    ARCHIVE_PATH="$HOME/$ARCHIVE_NAME"
    info "Архив найден в домашней папке: $ARCHIVE_PATH"
elif [ -f "$REPO_DIR/$ARCHIVE_NAME" ]; then
    ARCHIVE_PATH="$REPO_DIR/$ARCHIVE_NAME"
    info "Архив найден в репозитории: $ARCHIVE_PATH"
elif [ -f "./$ARCHIVE_NAME" ]; then
    ARCHIVE_PATH="$(pwd)/$ARCHIVE_NAME"
    info "Архив найден в текущей папке: $ARCHIVE_PATH"
else
    error_exit "Архив $ARCHIVE_NAME не найден!\nПоложите его в ~/ или в ~/voyage-narrative-engine/"
fi

# 3. Создаём временную папку в HOME (не в /tmp!)
mkdir -p "$TMP_DIR"
cd "$TMP_DIR"
info "Распаковка архива в $TMP_DIR..."
unzip -o "$ARCHIVE_PATH" || error_exit "Не удалось распаковать архив"

# 4. Проверяем структуру
if [ ! -d "$TMP_DIR/roles" ] || [ ! -d "$TMP_DIR/docs" ]; then
    error_exit "В архиве нет папок roles/ или docs/ — проверьте архив"
fi

# 5. Создаём нужные папки в репозитории (если ещё нет)
cd "$REPO_DIR"
info "Создание структуры папок..."
mkdir -p roles
mkdir -p docs
mkdir -p sessions/raw
mkdir -p sessions/state
mkdir -p sessions/memory
mkdir -p sessions/stories
mkdir -p sessions/visuals
mkdir -p scripts/termux

# 6. Копируем файлы с проверкой
info "Копирование файлов..."

for file in "$TMP_DIR"/roles/*.md; do
    if [ -f "$file" ]; then
        cp "$file" "$REPO_DIR/roles/"
        info "  → roles/$(basename $file)"
    fi
done

for file in "$TMP_DIR"/docs/*.md; do
    if [ -f "$file" ]; then
        cp "$file" "$REPO_DIR/docs/"
        info "  → docs/$(basename $file)"
    fi
done

# 7. Очистка временной папки
rm -rf "$TMP_DIR"
info "Временная папка очищена"

# 8. Git-фиксация
info "Git-операции..."
cd "$REPO_DIR"

git add roles/
git add docs/
git add sessions/

# Проверяем, есть ли что коммитить
if git diff --cached --quiet; then
    warn "Нет изменений для коммита (файлы уже были добавлены?)"
else
    git commit -m "roles: add State Manager, Narrative Editor v1.1, Visual Extractor\ndocs: add workflow analysis and session finalization guide\nsessions: create folder structure for raw/state/memory/stories/visuals"
    info "Коммит создан"
fi

info "Готово! Файлы в репозитории:"
ls -la "$REPO_DIR/roles/"
ls -la "$REPO_DIR/docs/"

echo ""
echo "=== Следующие шаги ==="
echo "1. Проверьте файлы: cd $REPO_DIR && ls roles/ docs/"
echo "2. Если нужно — запушьте: git push origin main"
echo "3. Создайте папки для персонажей: mkdir -p sessions/raw sessions/stories"
