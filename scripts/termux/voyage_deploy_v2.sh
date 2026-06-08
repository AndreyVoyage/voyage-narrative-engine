#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPO="${REPO:-$HOME/voyage-narrative-engine}"
DOWNLOAD_BASE="${DOWNLOAD_BASE:-/sdcard/Download}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err()   { echo -e "${RED}[ERR]${NC} $*"; }

for cmd in git find cp mkdir; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        log_err "Команда '$cmd' не найдена. Установите: pkg install $cmd"
        exit 1
    fi
done

find_file() {
    local query="$1" found="" tmpfile=""
    found=$(find "$DOWNLOAD_BASE" -type f -iname "$query" -print -quit 2>/dev/null)
    if [ -n "$found" ] && [ -f "$found" ]; then echo "$found"; return 0; fi
    local base="${query%.*}" ext=""; [[ "$query" == *.* ]] && ext=".${query##*.}"
    local pattern="${base}*${ext}"; tmpfile=$(mktemp)
    if find "$DOWNLOAD_BASE" -type f -iname "$pattern" -printf '%T@ %p\n' 2>/dev/null > "$tmpfile" && [ -s "$tmpfile" ]; then
        found=$(sort -rn "$tmpfile" | head -1 | cut -d' ' -f2-)
    else
        find "$DOWNLOAD_BASE" -type f -iname "$pattern" -print0 2>/dev/null | while IFS= read -r -d '' f; do
            mtime=$(stat -c '%Y' "$f" 2>/dev/null || echo "0"); printf '%s\t%s\n' "$mtime" "$f"
        done | sort -rn | head -1 | cut -f2- > "$tmpfile"
        found=$(cat "$tmpfile")
    fi
    rm -f "$tmpfile"
    if [ -n "$found" ] && [ -f "$found" ]; then echo "$found"; return 0; fi
    tmpfile=$(mktemp)
    if find "$DOWNLOAD_BASE" -type f -iname "*${query}*" -printf '%T@ %p\n' 2>/dev/null > "$tmpfile" && [ -s "$tmpfile" ]; then
        found=$(sort -rn "$tmpfile" | head -1 | cut -d' ' -f2-)
    else
        find "$DOWNLOAD_BASE" -type f -iname "*${query}*" -print0 2>/dev/null | while IFS= read -r -d '' f; do
            mtime=$(stat -c '%Y' "$f" 2>/dev/null || echo "0"); printf '%s\t%s\n' "$mtime" "$f"
        done | sort -rn | head -1 | cut -f2- > "$tmpfile"
        found=$(cat "$tmpfile")
    fi
    rm -f "$tmpfile"
    if [ -n "$found" ] && [ -f "$found" ]; then echo "$found"; return 0; fi
    return 1
}

detect_folder() {
    case "$1" in
        *_MODULE*.json|*_module*.json)         echo "personas/" ;;
        session_*.log|*.log)                   echo "sessions/raw/" ;;
        scenario_*.json|SCENARIO_*.json)         echo "scenarios/" ;;
        role_*.md|ROLE_*.md|AGENT_*_PROMPT.md)  echo "roles/" ;;
        *.py)                                  echo "" ;;
        *.sh)                                  echo "scripts/termux/" ;;
        *.md)                                  echo "docs/" ;;
        state_*.json)                           echo "state/" ;;
        *.zip|*.tar.gz|*.tar)                   echo "" ;;
        *)                                      echo "" ;;
    esac
}

parse_arg() {
    local arg="$1" src="${arg%%:*}" dest="${arg#*:}"
    [ "$dest" = "$arg" ] && dest=""
    printf '%s\t%s' "$src" "$dest"
}

if [ $# -eq 0 ]; then
    cat << 'USAGE'
Использование: voyage_deploy_v2.sh <файл>[:<<цель>] ...
  файл — имя в /sdcard/Download/ (ищется рекурсивно, игнорирует индексы)
  цель — путь в репозитории (опционально, автоопределение по имени)
Примеры:
  $0 "session_finalize_v2.py:session_finalize.py"
  $0 "AGENT_PROMPT.md:roles/ROLE_X.md"
  $0 "KIRA_MODULE.json:personas/"
  $0 "update.zip"
USAGE
    exit 1
fi

cd "$REPO" || { log_err "Нет папки $REPO"; exit 1; }
DEPLOYED=0

for arg in "$@"; do
    IFS=$'\t' read -r src_name target <<< "$(parse_arg "$arg")"
    log_info "🔍 Обработка: $src_name"
    src_path=$(find_file "$src_name") || true
    if [ -z "$src_path" ] || [ ! -f "$src_path" ]; then
        log_err "Не найден: $src_name"
        log_info "Проверьте: find /sdcard/Download -iname '*${src_name%.*}*'"
        continue
    fi
    log_ok "Найден: $src_path"
    if [ -n "$target" ]; then
        if [[ "$target" == */ ]]; then target_folder="$target"; target_name="$src_name"
        elif [[ "$target" == */* ]]; then target_folder="$(dirname "$target")/"; target_name="$(basename "$target")"
        else target_folder=""; target_name="$target"; fi
    else target_folder=$(detect_folder "$src_name"); target_name="$src_name"; fi
    [ -n "$target_folder" ] && mkdir -p "$target_folder"
    target_full="${target_folder}${target_name}"
    if [ "$src_name" != "$target_name" ] && [ -f "$target_full" ]; then
        log_warn "Удаляю старый $target_full из git..."
        git rm "$target_full" 2>/dev/null || rm -f "$target_full"
    fi
    cp "$src_path" "$target_full"
    if [[ "$target_name" == *.sh ]] || [[ "$target_name" == *.py ]]; then chmod +x "$target_full" 2>/dev/null || true; fi
    log_ok "→ $target_full"
    git add "$target_full"
    DEPLOYED=$((DEPLOYED + 1))
done

if [ "$DEPLOYED" -eq 0 ]; then log_warn "Ничего не задеплоено."; exit 1; fi
log_info "📤 Git commit & push..."
git status --short
if git diff --cached --quiet; then log_warn "Нет изменений для коммита"
else git commit -m "feat: deploy $(date +%Y%m%d_%H%M%S) — ${DEPLOYED} file(s)"
    git push origin main
    log_ok "Готово! Загружено файлов: $DEPLOYED"
fi
