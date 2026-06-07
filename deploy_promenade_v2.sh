#!/bin/bash
# =============================================================================
# Voyage Promenade v2.0 — Termux Deploy & Extract Script
# Автор: Voyage Narrative Engine
# Дата: 2026-06-07
# Описание: git pull → найти архив → распаковать → распределить → STATE → промпт
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

REPO_DIR="${HOME}/voyage-narrative-engine"
ARCHIVE_NAME="voyage_promenade_v2.zip"
ARCHIVE_PATH="${REPO_DIR}/${ARCHIVE_NAME}"
TMP_DIR="/tmp/voyage_promenade_extract"
PROMPT_FILE="${REPO_DIR}/full_prompt_promenade.txt"
GUIDE_FILE="${REPO_DIR}/QUICKSTART_PROMENADE.txt"

print_header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  VOYAGE PROMENADE v2.0 — Deploy & Extract Script             ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() { echo -e "${BLUE}[${1}/8]${NC} ${2}"; }
print_ok()   { echo -e "${GREEN}✓${NC} ${1}"; }
print_warn() { echo -e "${YELLOW}⚠${NC} ${1}"; }
print_error(){ echo -e "${RED}✗${NC} ${1}"; }

# =============================================================================
# Шаг 1: Проверка окружения
# =============================================================================
print_header
print_step "1" "Проверка окружения..."

if ! command -v git &> /dev/null; then
    print_error "git не установлен. Установи: pkg install git"
    exit 1
fi

if ! command -v unzip &> /dev/null; then
    print_warn "unzip не установлен. Устанавливаю..."
    pkg install unzip -y
fi

if [ ! -d "${REPO_DIR}" ]; then
    print_error "Репозиторий не найден в ${REPO_DIR}"
    echo "Сначала клонируй: git clone https://github.com/AndreyVoyage/voyage-narrative-engine.git"
    exit 1
fi

print_ok "Окружение готово"

# =============================================================================
# Шаг 2: Git Pull
# =============================================================================
print_step "2" "Git pull origin main..."
cd "${REPO_DIR}"

if ! git pull origin main; then
    print_warn "Git pull не удался. Пробуем git stash..."
    git stash
    if ! git pull origin main; then
        print_error "Не удалось выполнить git pull. Проверь вручную."
        exit 1
    fi
    print_warn "Локальные изменения сохранены в stash"
fi
print_ok "Репозиторий обновлён"

# =============================================================================
# Шаг 3: Поиск и распаковка архива
# =============================================================================
print_step "3" "Поиск архива Promenade v2..."

ARCHIVE_FOUND=0
if [ -f "${ARCHIVE_PATH}" ]; then
    print_ok "Архив найден: ${ARCHIVE_NAME}"
    ARCHIVE_FOUND=1
else
    # Ищем любой zip с "promenade" в имени
    FOUND_ZIP=$(find "${REPO_DIR}" -maxdepth 1 -name "*promenade*.zip" -print -quit)
    if [ -n "${FOUND_ZIP}" ]; then
        ARCHIVE_PATH="${FOUND_ZIP}"
        ARCHIVE_NAME=$(basename "${FOUND_ZIP}")
        print_ok "Архив найден: ${ARCHIVE_NAME}"
        ARCHIVE_FOUND=1
    fi
fi

if [ $ARCHIVE_FOUND -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Распаковка архива...${NC}"
    rm -rf "${TMP_DIR}"
    mkdir -p "${TMP_DIR}"
    unzip -o "${ARCHIVE_PATH}" -d "${TMP_DIR}"
    print_ok "Архив распакован в ${TMP_DIR}"

    # Определяем корень распакованных файлов
    EXTRACTED_ROOT="${TMP_DIR}"
    if [ -d "${TMP_DIR}/voyage_promenade_v2" ]; then
        EXTRACTED_ROOT="${TMP_DIR}/voyage_promenade_v2"
    fi

    # Копируем файлы в репозиторий
    echo ""
    echo -e "${YELLOW}Копирование файлов в репозиторий...${NC}"

    if [ -f "${EXTRACTED_ROOT}/scenarios/SCENARIO_PROMENADE_v2.md" ]; then
        cp "${EXTRACTED_ROOT}/scenarios/SCENARIO_PROMENADE_v2.md" "${REPO_DIR}/scenarios/"
        print_ok "→ scenarios/SCENARIO_PROMENADE_v2.md"
    fi

    if [ -f "${EXTRACTED_ROOT}/personas/FEMALE_USER_MODULE.json" ]; then
        cp "${EXTRACTED_ROOT}/personas/FEMALE_USER_MODULE.json" "${REPO_DIR}/personas/"
        print_ok "→ personas/FEMALE_USER_MODULE.json"
    fi

    if [ -f "${EXTRACTED_ROOT}/state/STATE_TEMPLATE_PROMENADE.json" ]; then
        cp "${EXTRACTED_ROOT}/state/STATE_TEMPLATE_PROMENADE.json" "${REPO_DIR}/state/"
        print_ok "→ state/STATE_TEMPLATE_PROMENADE.json"
    fi

    if [ -f "${EXTRACTED_ROOT}/docs/INTERACTION_GUIDE.md" ]; then
        cp "${EXTRACTED_ROOT}/docs/INTERACTION_GUIDE.md" "${REPO_DIR}/docs/"
        print_ok "→ docs/INTERACTION_GUIDE.md"
    fi

    if [ -f "${EXTRACTED_ROOT}/docs/README_PROMENADE.md" ]; then
        cp "${EXTRACTED_ROOT}/docs/README_PROMENADE.md" "${REPO_DIR}/docs/"
        print_ok "→ docs/README_PROMENADE.md"
    fi

    # Удаляем архив из репозитория (чтобы не мешал git)
    rm -f "${ARCHIVE_PATH}"
    print_ok "Архив удалён из репозитория (файлы уже распакованы)"

    # Git commit распакованных файлов
    git add scenarios/SCENARIO_PROMENADE_v2.md personas/FEMALE_USER_MODULE.json state/STATE_TEMPLATE_PROMENADE.json docs/INTERACTION_GUIDE.md docs/README_PROMENADE.md 2>/dev/null || true
    git commit -m "feat: extract and deploy promenade v2 files" 2>/dev/null || print_warn "Git commit пропущен (возможно, нет изменений)"

else
    print_warn "Архив не найден. Проверяю, может файлы уже на месте..."
fi

# =============================================================================
# Шаг 4: Проверка файлов после распаковки
# =============================================================================
print_step "4" "Проверка файлов Promenade v2..."

REQUIRED_FILES=(
    "scenarios/SCENARIO_PROMENADE_v2.md"
    "personas/FEMALE_USER_MODULE.json"
    "state/STATE_TEMPLATE_PROMENADE.json"
    "docs/INTERACTION_GUIDE.md"
)

MISSING=0
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "${REPO_DIR}/${file}" ]; then
        print_error "Отсутствует: ${file}"
        MISSING=1
    else
        print_ok "OK: ${file}"
    fi
done

if [ $MISSING -eq 1 ]; then
    print_error "Критические файлы отсутствуют. Сценарий не может продолжить."
    echo ""
    echo "Возможные причины:"
    echo "  1. Архив не был загружен в репозиторий"
    echo "  2. Архив повреждён или не содержит нужных файлов"
    echo "  3. Файлы в архиве имеют другие имена"
    echo ""
    echo "Решение: загрузи архив voyage_promenade_v2.zip в корень репозитория через GitHub Web"
    exit 1
fi

# =============================================================================
# Шаг 5: Проверка базовых модулей
# =============================================================================
print_step "5" "Проверка базовых модулей..."

BASE_FILES=(
    "core/VOYAGE_NARRATIVE_CORE_v2.md"
    "personas/SERGEY_MODULE_v3.json"
    "personas/MAXIM_MODULE_v1.json"
    "governance/AUTONOMY_GOVERNOR_v2.md"
)

for file in "${BASE_FILES[@]}"; do
    if [ ! -f "${REPO_DIR}/${file}" ]; then
        print_warn "Базовый файл отсутствует: ${file}"
    else
        print_ok "Базовый OK: ${file}"
    fi
done

# =============================================================================
# Шаг 6: Запрос имени героини и обновление STATE
# =============================================================================
print_step "6" "Настройка героини..."

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  КАК ТЕБЯ ЗОВУТ?                                            ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Это имя будет использоваться в повествовании и диалогах."
echo "Не обязательно настоящее — любое, под которым ты хочешь быть."
echo ""

read -p "Введи имя [Анна]: " HEROINE_NAME
HEROINE_NAME=${HEROINE_NAME:-"Анна"}

echo ""
print_ok "Имя героини: ${HEROINE_NAME}"

STATE_FILE="${REPO_DIR}/state/STATE_TEMPLATE_PROMENADE.json"
if [ -f "${STATE_FILE}" ]; then
    cp "${STATE_FILE}" "${REPO_DIR}/state/STATE_ACTIVE.json"
    sed -i "s/{{HEROINE_NAME}}/${HEROINE_NAME}/g" "${REPO_DIR}/state/STATE_ACTIVE.json"
    sed -i 's/"heroine_name_set": false/"heroine_name_set": true/g' "${REPO_DIR}/state/STATE_ACTIVE.json"
    sed -i "s/\"heroine_name_value\": \"\"/\"heroine_name_value\": \"${HEROINE_NAME}\"/g" "${REPO_DIR}/state/STATE_ACTIVE.json"
    print_ok "STATE_ACTIVE.json создан с именем ${HEROINE_NAME}"
else
    print_warn "STATE_TEMPLATE не найден. Создаём базовый STATE..."
    cat > "${REPO_DIR}/state/STATE_ACTIVE.json" << EOF
{
  "session_id": "SN_PROMENADE_001",
  "scenario": "SCENARIO_PROMENADE_v2",
  "timestamp": "$(date -Iseconds)",
  "heroine_name": "${HEROINE_NAME}",
  "characters": {
    "heroine": { "vl": 0, "st": 0, "nzh": 0, "og": 0, "location": "promenade_sunset" },
    "maksim": { "level": "MX2", "location": "promenade_bench" },
    "sergey": { "level": "S2", "location": "promenade_bench" }
  },
  "flags": { "promenade_met": false, "menu_choice_shown": false },
  "governance": { "autonomy_level": 2, "safety_override": false }
}
EOF
    print_ok "Базовый STATE создан"
fi

# =============================================================================
# Шаг 7: Сборка единого промпта
# =============================================================================
print_step "7" "Сборка единого промпта..."

echo ""
echo -e "${YELLOW}Собираем full_prompt_promenade.txt...${NC}"
echo ""

> "${PROMPT_FILE}"

# 1. CORE
if [ -f "${REPO_DIR}/core/VOYAGE_NARRATIVE_CORE_v2.md" ]; then
    echo "[1/5] CORE..."
    cat "${REPO_DIR}/core/VOYAGE_NARRATIVE_CORE_v2.md" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "CORE"
fi

# 2. Персонажи
if [ -f "${REPO_DIR}/personas/SERGEY_MODULE_v3.json" ]; then
    echo "[2/5] Сергей..."
    echo "[PERSONA: SERGEY]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/personas/SERGEY_MODULE_v3.json" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "Сергей"
fi

if [ -f "${REPO_DIR}/personas/MAXIM_MODULE_v1.json" ]; then
    echo "[3/5] Максим..."
    echo "[PERSONA: MAXIM]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/personas/MAXIM_MODULE_v1.json" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "Максим"
fi

if [ -f "${REPO_DIR}/personas/FEMALE_USER_MODULE.json" ]; then
    echo "[4/5] Героиня..."
    echo "[PERSONA: HEROINE]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/personas/FEMALE_USER_MODULE.json" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "Героиня"
fi

# 3. Сценарий
if [ -f "${REPO_DIR}/scenarios/SCENARIO_PROMENADE_v2.md" ]; then
    echo "[5/5] Сценарий..."
    echo "[SCENARIO: PROMENADE v2]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/scenarios/SCENARIO_PROMENADE_v2.md" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "Сценарий"
fi

# 4. STATE
if [ -f "${REPO_DIR}/state/STATE_ACTIVE.json" ]; then
    echo "[STATE]..."
    echo "[STATE: ACTIVE]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/state/STATE_ACTIVE.json" >> "${PROMPT_FILE}"
    echo -e "\n\n---\n\n" >> "${PROMPT_FILE}"
    print_ok "STATE"
fi

# 5. Governance
if [ -f "${REPO_DIR}/governance/AUTONOMY_GOVERNOR_v2.md" ]; then
    echo "[GOVERNANCE]..."
    echo "[GOVERNANCE]" >> "${PROMPT_FILE}"
    cat "${REPO_DIR}/governance/AUTONOMY_GOVERNOR_v2.md" >> "${PROMPT_FILE}"
    print_ok "Governance"
fi

# Подстановка имени
sed -i "s/{{HEROINE_NAME}}/${HEROINE_NAME}/g" "${PROMPT_FILE}"

SIZE=$(wc -c < "${PROMPT_FILE}")
LINES=$(wc -l < "${PROMPT_FILE}")
print_ok "Промпт собран: ${SIZE} байт, ${LINES} строк"

# =============================================================================
# Шаг 8: Гайд запуска
# =============================================================================
print_step "8" "Создание гайда..."

cat > "${GUIDE_FILE}" << GUIDE
╔══════════════════════════════════════════════════════════════════╗
║     VOYAGE PROMENADE v2.0 — ГАЙД ПО ЗАПУСКУ                      ║
╚══════════════════════════════════════════════════════════════════╝

📁 Готовые файлы:
   • ${PROMPT_FILE}  — единый промпт (вставь в чат-бот)
   • ${REPO_DIR}/state/STATE_ACTIVE.json  — состояние сессии
   • ${REPO_DIR}/docs/INTERACTION_GUIDE.md  — полный гайд команд

🚀 БЫСТРЫЙ СТАРТ:

1. Открой файл промпта:
   cat ${PROMPT_FILE}

2. Скопируй ВСЁ содержимое (долгое нажатие → "Копировать")

3. Вставь в чат-бот (Kimi / DeepSeek / Qwen):
   - Kimi: вставь в первое сообщение
   - DeepSeek: вставь в первое сообщение
   - Qwen: вставь в системный промпт или первое сообщение

4. Напиши: Начни  (или Старт)

5. Система начнёт сценарий с именем: ${HEROINE_NAME}

🔥 КОМАНДЫ УПРАВЛЕНИЯ (пиши в чате):

   ВСНО-МЕТРИКИ:
   • ВЛ0–ВЛ4  — влюблённость (0=индифферентность, 4=привязанность)
   • СТ0–СТ4  — страсть (0=холод, 4=пожар)
   • НЖ0–НЖ4  — нежность (0=осторожность, 4=слияние)
   • ОГ0–ОГ4  — контраст мужчин (0=пепел, 4=вспышка)
   Пример: "ВЛ3 СТ2 НЖ1 ОГ4"

   POV (точка зрения):
   • "От лица девушки" / "POV героини"
   • "От лица Максима" / "POV Максима"
   • "От лица Сергея" / "POV Сергея"
   • "Три POV" — все вместе

   СЦЕНАРИИ (меню свиданий):
   • "Ресторан" / "крыша" — ресторан на крыше
   • "Траттория" / "пицца" — итальянская траттория
   • "Темнота" / "Dining in the Dark" — ужин в темноте
   • "Фуд-корт" / "шаверма" — уличная еда
   • "Готовка" / "кухня" — готовим вместе
   • "Кино" / "фильм" — кинотеатр/квартира
   • "И то, и другое" — полный вечер

   АВТОНОМИЯ:
   • Г0 — строго реактивный (только отвечает)
   • Г1 — мягкий (продолжает сцену)
   • Г2 — средний (переключает POV)
   • Г3 — высокий (proactive, мужчины пишут первыми)
   • Г4 — максимальный (полная автономия)

   БЕЗОПАСНОСТЬ:
   • СТОП / ХВАТИТ / КРАСНАЯ КАРТОЧКА — мгновенный aftercare

   ВИЗУАЛ:
   • "Картинка" / "Визуал" / "Qwen" — добавит [AUTO_VISUAL] блок

   ПАМЯТЬ:
   • "Запомни" — фиксация факта
   • "Как меня зовут?" — напомнит имя
   • "Состояние" / "State" — покажет текущий STATE

⚠️ ВАЖНО:
   • Safety Check автоматически перед переходом на СТ4
   • Имя можно сменить только через перезапуск (Сброс)
   • Визуал работает если есть visual/QWEN_ADAPTER_v2.md

📞 ПРОБЛЕМЫ?
   Если промпт слишком большой — разбей на 2 части:
   Часть 1: CORE + Персонажи
   Часть 2: Сценарий + STATE + Governance

   Или используй API с system prompt.

═══════════════════════════════════════════════════════════════════
   Имя героини: ${HEROINE_NAME}
   Удачного вечера у набережной! 🌆
═══════════════════════════════════════════════════════════════════
GUIDE

print_ok "Гайд создан: ${GUIDE_FILE}"

# =============================================================================
# Финал
# =============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО                         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Имя героини:${NC}  ${HEROINE_NAME}"
echo -e "${CYAN}Промпт:${NC}       ${PROMPT_FILE}"
echo -e "${CYAN}Гайд:${NC}         ${GUIDE_FILE}"
echo -e "${CYAN}STATE:${NC}        ${REPO_DIR}/state/STATE_ACTIVE.json"
echo ""
echo -e "${YELLOW}СЛЕДУЮЩИЕ ШАГИ:${NC}"
echo "  1. cat ${PROMPT_FILE}"
echo "  2. Скопируй всё содержимое (долгое нажатие → Копировать)"
echo "  3. Вставь в чат-бот (Kimi / DeepSeek / Qwen)"
echo "  4. Напиши: Начни"
echo ""
echo -e "${YELLOW}Или прочитай гайд:${NC} cat ${GUIDE_FILE}"
echo ""
