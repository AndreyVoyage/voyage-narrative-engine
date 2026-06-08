#!/data/data/com.termux/files/usr/bin/bash
# Voyage Deploy — загрузка файлов/архивов в GitHub репозиторий
# Использование: ./voyage_deploy.sh <файл> [папка_в_репо]
# Автоопределение пути по имени файла если папка не указана
set -euo pipefail

REPO_URL="https://github.com/AndreyVoyage/voyage-narrative-engine.git"
REPO_DIR="${HOME}/voyage-narrative-engine"
DOWNLOAD="${HOME}/storage/downloads"
BACKUP="${REPO_DIR}/.backup"
REPORTS="${REPO_DIR}/.deploy_reports"
MAX_MB=100
MAX_BYTES=$((MAX_MB*1024*1024))

C0='\033[0m'; C1='\033[0;32m'; C2='\033[1;33m'; C3='\033[0;31m'
ok()  { echo -e "${C1}[OK]${C0} $1"; }
wrn() { echo -e "${C2}[WARN]${C0} $1"; }
err() { echo -e "${C3}[ERR]${C0} $1" >&2; }

# --- зависимости ---
for c in git unzip python3; do command -v "$c" >/dev/null || { err "Установите: pkg install $c"; exit 1; }; done
[ -d "$DOWNLOAD" ] || { err "Запустите termux-setup-storage"; exit 1; }

# --- репозиторий ---
[ -d "${REPO_DIR}/.git" ] || git clone "$REPO_URL" "$REPO_DIR"
cd "$REPO_DIR"
git pull origin "$(git branch --show-current 2>/dev/null || echo main)" --ff-only 2>/dev/null || wrn "git pull пропущён"

# --- auth ---
if ! git ls-remote --exit-code origin HEAD &>/dev/null; then
    echo -n "GitHub токен (repo права): "; read -s TOKEN; echo
    git config --global credential.helper "store --file=${HOME}/.git-credentials"
    sed -i "/AndreyVoyage/d" "${HOME}/.git-credentials" 2>/dev/null || true
    echo "https://AndreyVoyage:${TOKEN}@github.com" >> "${HOME}/.git-credentials"
    chmod 600 "${HOME}/.git-credentials"
    git ls-remote --exit-code origin HEAD || { err "Неверный токен"; exit 1; }
    ok "Токен сохранён"
fi

# --- источник ---
SRC="$1"
[ -f "$SRC" ] || { [ -f "${DOWNLOAD}/${SRC}" ] && SRC="${DOWNLOAD}/${SRC}"; }
[ -f "$SRC" ] || { err "Файл не найден: $1"; exit 1; }
FNAME=$(basename "$SRC")

# --- автоопределение пути ---
auto_path() {
    local n=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    case "$n" in
        *_module*.json) echo "personas/" ;;
        session_*.log|*.log) echo "sessions/raw/" ;;
        scenario_*.json) echo "scenarios/" ;;
        role_*.md) echo "roles/" ;;
        *.py) echo "scripts/python/" ;;
        *.sh) echo "scripts/termux/" ;;
        *.md) echo "docs/" ;;
        state_*.json) echo "state/" ;;
        *) echo "" ;;
    esac
}

TARGET="${2:-}"
[ -z "$TARGET" ] && TARGET=$(auto_path "$FNAME")
[ -n "$TARGET" ] && wrn "Автоопределение пути: ${TARGET}"
TARGET=$(echo "$TARGET" | sed 's:^/*::; s:/*$::')
[ "$TARGET" = "." ] && TARGET=""
TDIR="${REPO_DIR}${TARGET:+/${TARGET}}"
mkdir -p "$TDIR"

# --- размер ---
FSIZE=$(wc -c < "$SRC" | tr -d ' ')
[ "$FSIZE" -gt "$MAX_BYTES" ] && { err "Файл > ${MAX_MB}MB"; exit 1; }

# --- бэкап ---
backup() { [ -f "$1" ] && { mkdir -p "$BACKUP"; cp "$1" "${BACKUP}/$(basename "$1").$(date +%Y%m%d_%H%M%S).bak"; wrn "Бэкап: $(basename "$1")"; }; }

# --- обработка ---
ISZIP=0; DEST=""
if [[ "$FNAME" =~ \.(zip|ZIP)$ ]]; then
    ISZIP=1; TMP="${REPO_DIR}/.tmp$$"
    mkdir -p "$TMP"
    unzip -oq "$SRC" -d "$TMP"
    items=( "$TMP"/* )
    if [ ${#items[@]} -eq 1 ] && [ -d "${items[0]}" ]; then
        mv "${items[0]}"/* "$TDIR/" 2>/dev/null || true
        rmdir "${items[0]}" 2>/dev/null || true
    else
        mv "$TMP"/* "$TDIR/" 2>/dev/null || true
    fi
    rm -rf "$TMP"
    DEST="${TARGET:-корень} (распакован)"
else
    backup "${TDIR}/${FNAME}"
    cp "$SRC" "${TDIR}/${FNAME}"
    DEST="${TARGET:+${TARGET}/}${FNAME}"
fi

# --- валидация ---
VALERR=""
validate() {
    local f="$1" e=""
    case "$f" in
        *.json) python3 -c "import json; json.load(open('$f'))" 2>/dev/null || e="Невалидный JSON: $(basename "$f")" ;;
        *.py)   python3 -m py_compile "$f" 2>/dev/null || e="Ошибка Python: $(basename "$f")" ;;
    esac
    [ -n "$e" ] && { err "$e"; VALERR="${VALERR}${e}\n"; }
}
find "$TDIR" -maxdepth 1 -type f \( -name "*.json" -o -name "*.py" \) | while read -r f; do validate "$f"; done

# --- VSCNO check для persona ---
if [[ "$FNAME" =~ _MODULE.*\.json$ ]]; then
    VSCNO=$(python3 -c "
import json
d=json.load(open('${TDIR}/${FNAME}'))
v=d.get('vscno',{})
print(sum(v.get(k,0) for k in ['ВЛ','СТ','НЖ','ОГ']))
" 2>/dev/null || echo "0")
    [ "$VSCNO" != "0" ] && [ "$VSCNO" != "10" ] && { err "VSCNO сумма=${VSCNO} (должна быть 10)"; VALERR="${VALERR}VSCNO=${VSCNO}\n"; }
fi

# --- git ---
[ -n "$TARGET" ] && git add "$TARGET" || git add "$FNAME"
if git diff --cached --quiet; then
    wrn "Нет изменений (файл идентичен)"
else
    git commit -m "deploy: ${FNAME} → ${TARGET:-root}"
    git push origin HEAD || { err "Push не удался"; exit 1; }
    ok "Загружено на GitHub"
fi

# --- отчёт ---
HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "?")
REPORT="${REPORTS}/report_$(date +%Y%m%d_%H%M%S).md"
mkdir -p "$REPORTS"

cat > "$REPORT" << EOR
# Отчёт деплоя — $(date '+%Y-%m-%d %H:%M')

**Файл:** \`${FNAME}\`  
**Размер:** ${FSIZE} bytes  
**Размещение:** \`${DEST}\`  
**Коммит:** \`${HASH}\`  
**Ошибки:** ${VALERR:-"нет"}

## Действия
- Бэкап: \`${BACKUP}\`
- Отчёт: \`${REPORT}\`

## Для нейросети
> Деплой \`${FNAME}\` в \`${DEST}\`. ${VALERR:+"Обнаружены ошибки: ${VALERR}"}Коммит ${HASH}.
EOR

echo -e "\n${C1}=== ОТЧЁТ ===${C0}"
echo "Файл:    ${FNAME}"
echo "Куда:    ${DEST}"
echo "Коммит:  ${HASH}"
echo "Бэкапы:  ${BACKUP}"
echo "Отчёт:   ${REPORT}"
[ -n "$VALERR" ] && echo -e "${C3}Ошибки:${C0} ${VALERR}"
echo -e "${C1}===========${C0}"
echo "Скопируйте отчёт в чат нейросети."
